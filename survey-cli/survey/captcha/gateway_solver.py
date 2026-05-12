"""================================================================================
VERCEL AI GATEWAY SOLVER — Gemini 3.1 Flash + Claude Opus 4.7 Fallback
================================================================================

MODUL-KONZEPT (SR-138, 2026-05-12):
    Dieses Modul implementiert Schritt 3 der Captcha-Fallback-Chain.
    Nutzt Vercel AI Gateway für zero-config Zugriff auf:
    - Primary: google/gemini-3.1-flash-image-preview (schnell, native bounding-box)
    - Fallback: anthropic/claude-opus-4.7 (starkes vision-reasoning)

WARUM VERCEL AI GATEWAY?
    - Zero-config: Kein Provider-SDK nötig, nur AI_GATEWAY_API_KEY
    - Model-String Format: "provider/model-name" (z.B. "google/gemini-3.1-flash-image-preview")
    - Unified API: Gleiche Schnittstelle für alle Modelle
    - Kostenlos für v0-Projekte mit gesetztem API-Key

GRACEFUL DEGRADATION:
    - Wenn AI_GATEWAY_API_KEY nicht gesetzt → Chain überspringt diesen Schritt
    - Kein Crash, nur Warning im Log
    - Nächster Schritt (audio_solver) wird versucht

UNTERSTÜTZTE CAPTCHA-TYPEN:
    ✅ angular_drag_drop — Drag-Drop Puzzles
    ✅ visual_text — Text-Captchas
    ✅ geetest_v4 — Slider/Click Captchas
    ✅ hcaptcha, recaptcha — Image-Selection Captchas (nur visuell, kein Token)
    ✅ turnstile — Cloudflare Challenges

API (konform mit Solver-Interface aus captcha_router):
    solve(cdp, detection) -> CaptchaResult

VERCEL AI GATEWAY DOCS:
    https://vercel.com/docs/ai-gateway/capabilities
    Model strings: "google/gemini-3.1-flash-image-preview", "anthropic/claude-opus-4.7"

Module Status: NEW (SR-138, 2026-05-12)
================================================================================
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from dataclasses import dataclass, field
from typing import Any, Optional
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

logger = logging.getLogger("gateway_solver")

# ── CONFIG ─────────────────────────────────────────────────────────────────

GATEWAY_BASE_URL = "https://api.vercel.ai/v1"
GATEWAY_PRIMARY_MODEL = "google/gemini-3.1-flash-image-preview"
GATEWAY_FALLBACK_MODEL = "anthropic/claude-opus-4.7"
MAX_TOKENS = 512
TIMEOUT_S = 30
RETRIES = 2

# Alle Captcha-Typen die dieser Solver unterstützt
SUPPORTED_TYPES = frozenset(
    {
        "angular_drag_drop",
        "visual_text",
        "geetest_v4",
        "geetest_v3",
        "slider",
        "click_captcha",
        "hcaptcha",
        "recaptcha",
        "turnstile",
    }
)

# ── RESULT DATACLASS ───────────────────────────────────────────────────────


@dataclass
class CaptchaResult:
    """Ergebnis eines Captcha-Lösungsversuchs."""

    solved: bool
    captcha_type: str = ""
    token: str = ""
    elapsed_ms: float = 0.0
    reason: str = "ok"
    extra: dict[str, Any] = field(default_factory=dict)


# ── SCREENSHOT CAPTURE ─────────────────────────────────────────────────────


def _capture_screenshot_b64(cdp, frame_id: str = "") -> Optional[str]:
    """Capture Screenshot als Base64 PNG."""
    try:
        params = {"format": "png", "quality": 80}
        resp = cdp.call_result("Page.captureScreenshot", params)
        return resp.get("data")
    except Exception as e:
        logger.warning("Screenshot capture failed: %s", e)
        return None


# ── VISION PROMPT BUILDERS ─────────────────────────────────────────────────


def _build_unified_prompt(detection) -> str:
    """Unified prompt für alle Captcha-Typen mit Gemini/Claude.

    Diese Modelle sind intelligent genug für einen generischen Prompt,
    der alle Captcha-Varianten abdeckt.
    """
    ctype = detection.captcha_type
    dom_hint = detection.dom_hint or ""

    return f"""You are a CAPTCHA solving assistant. Analyze this image and solve the CAPTCHA.

CAPTCHA TYPE DETECTED: {ctype}
ADDITIONAL HINT: {dom_hint}

TASK: Based on the CAPTCHA type, provide the solution:

FOR DRAG-DROP PUZZLES:
- Find the element that needs to be dragged (often a number or shape)
- Find the drop zone
- Return source and target coordinates

FOR TEXT CAPTCHAS:
- Read the distorted text characters
- Return the exact text

FOR SLIDER PUZZLES:
- Find the gap/hole in the background image
- Calculate the distance to slide

FOR CLICK-BASED CAPTCHAS (select images):
- Identify which images match the instruction
- Return coordinates of each image to click

FOR CLOUDFLARE TURNSTILE / CHECKBOX:
- Find the checkbox or button to click
- Return its coordinates

OUTPUT FORMAT (JSON only, no markdown, no explanation):
{{
    "action_type": "drag" | "text" | "slide" | "click" | "checkbox",
    "solved": true,
    "data": {{
        // For drag: {{"source": {{"x": N, "y": N}}, "target": {{"x": N, "y": N}}}}
        // For text: {{"text": "ABCD"}}
        // For slide: {{"distance": N}}
        // For click: {{"clicks": [{{"x": N, "y": N}}]}}
        // For checkbox: {{"x": N, "y": N}}
    }}
}}

If you cannot solve it:
{{"solved": false, "reason": "description of why"}}"""


def _build_bounding_box_prompt(detection) -> str:
    """Spezial-Prompt für Gemini's native bounding-box Fähigkeit."""
    ctype = detection.captcha_type
    dom_hint = detection.dom_hint or ""

    return f"""Analyze this CAPTCHA image. Type: {ctype}. Hint: {dom_hint}

Your task is to identify interactive elements and their bounding boxes.

For DRAG puzzles: Find the draggable element and drop zone.
For SLIDER puzzles: Find the slider handle and the gap position.
For CLICK puzzles: Find all elements that should be clicked.

Return JSON with bounding boxes:
{{
    "elements": [
        {{"label": "draggable", "bbox": [x1, y1, x2, y2]}},
        {{"label": "dropzone", "bbox": [x1, y1, x2, y2]}}
    ],
    "action": "drag" | "click" | "slide",
    "solved": true
}}

If unsolvable: {{"solved": false, "reason": "why"}}"""


# ── GATEWAY CLIENT ─────────────────────────────────────────────────────────


class GatewaySolver:
    """Vercel AI Gateway Solver für Vision-basierte Captchas.

    Nutzt Vercel AI Gateway mit:
    - Primary: Gemini 3.1 Flash Image (schnell, native grounding)
    - Fallback: Claude Opus 4.7 (stärkeres reasoning)

    Graceful skip wenn AI_GATEWAY_API_KEY nicht gesetzt.
    """

    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv("AI_GATEWAY_API_KEY")
        self._available = bool(self.api_key)
        self.consecutive_failures = 0

        if not self._available:
            logger.warning(
                "AI_GATEWAY_API_KEY not set — GatewaySolver will be skipped in fallback chain"
            )

    @property
    def available(self) -> bool:
        """Check if solver is available (API key set + not circuit-broken)."""
        return self._available and self.consecutive_failures < 3

    def _record_failure(self, reason: str):
        self.consecutive_failures += 1
        logger.warning("Gateway failure: %s (count: %d)", reason, self.consecutive_failures)
        if self.consecutive_failures >= 3:
            logger.error("Gateway circuit breaker OPEN")

    def _record_success(self):
        if self.consecutive_failures > 0:
            logger.info("Gateway success: resetting failure count")
        self.consecutive_failures = 0

    def _call_gateway_api(self, model: str, prompt: str, image_b64: str) -> Optional[str]:
        """Call Vercel AI Gateway with vision request.

        Args:
            model: Model string (e.g. "google/gemini-3.1-flash-image-preview")
            prompt: Text prompt
            image_b64: Base64-encoded PNG image

        Returns:
            Raw model response text or None on failure
        """
        if not self.api_key:
            return None

        # Build request payload (OpenAI-compatible format)
        payload = {
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{image_b64}"},
                        },
                    ],
                }
            ],
            "max_tokens": MAX_TOKENS,
            "temperature": 0.1,
        }

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        for attempt in range(1, RETRIES + 1):
            try:
                req = Request(
                    f"{GATEWAY_BASE_URL}/chat/completions",
                    data=json.dumps(payload).encode("utf-8"),
                    headers=headers,
                    method="POST",
                )
                with urlopen(req, timeout=TIMEOUT_S) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                    self._record_success()
                    return content
            except HTTPError as e:
                self._record_failure(f"http_{e.code}: {e.reason}")
                if e.code == 429 and attempt < RETRIES:
                    time.sleep(5)
                    continue
                if e.code >= 500 and attempt < RETRIES:
                    time.sleep(2**attempt)
                    continue
            except URLError as e:
                self._record_failure(f"network: {e.reason}")
                if attempt < RETRIES:
                    time.sleep(2**attempt)
                    continue
            except Exception as e:
                self._record_failure(f"unknown: {e}")
                break
        return None

    def _parse_json_response(self, raw: str) -> Optional[dict]:
        """Parse JSON from model response."""
        if not raw:
            return None
        raw = raw.strip()
        # Strip markdown
        if raw.startswith("```"):
            lines = raw.split("\n")
            lines = [line for line in lines if not line.strip().startswith("```")]
            raw = "\n".join(lines)
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass
        # Extract JSON object
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
        return None

    def solve(self, cdp, detection) -> CaptchaResult:
        """Hauptmethode: Löst Captcha via Vercel AI Gateway.

        Versucht zuerst Gemini 3.1 Flash Image, dann Claude Opus 4.7.

        Args:
            cdp: CDPConnection instance
            detection: CaptchaDetection mit captcha_type und dom_hint

        Returns:
            CaptchaResult mit solved=True/False und Details
        """
        t0 = time.time()
        ctype = detection.captcha_type

        # Check support
        if ctype not in SUPPORTED_TYPES:
            return CaptchaResult(
                solved=False,
                captcha_type=ctype,
                reason="unsupported_type",
                elapsed_ms=(time.time() - t0) * 1000,
            )

        # Check availability (graceful skip if no API key)
        if not self.available:
            reason = "api_key_not_set" if not self.api_key else "circuit_breaker_open"
            return CaptchaResult(
                solved=False,
                captcha_type=ctype,
                reason=reason,
                elapsed_ms=(time.time() - t0) * 1000,
            )

        # Capture screenshot
        screenshot = _capture_screenshot_b64(cdp, detection.frame_id)
        if not screenshot:
            return CaptchaResult(
                solved=False,
                captcha_type=ctype,
                reason="screenshot_failed",
                elapsed_ms=(time.time() - t0) * 1000,
            )

        # Try Gemini first (fast, native bounding-box)
        logger.info("Trying %s for %s", GATEWAY_PRIMARY_MODEL, ctype)
        prompt = _build_bounding_box_prompt(detection)
        raw_response = self._call_gateway_api(GATEWAY_PRIMARY_MODEL, prompt, screenshot)

        parsed = self._parse_json_response(raw_response) if raw_response else None
        model_used = GATEWAY_PRIMARY_MODEL

        # If Gemini failed, try Claude
        if not parsed or not parsed.get("solved", False):
            logger.info("Gemini failed, trying %s", GATEWAY_FALLBACK_MODEL)
            prompt = _build_unified_prompt(detection)
            raw_response = self._call_gateway_api(GATEWAY_FALLBACK_MODEL, prompt, screenshot)
            parsed = self._parse_json_response(raw_response) if raw_response else None
            model_used = GATEWAY_FALLBACK_MODEL

        # Check if we got a valid response
        if not parsed:
            return CaptchaResult(
                solved=False,
                captcha_type=ctype,
                reason="both_models_failed",
                elapsed_ms=(time.time() - t0) * 1000,
            )

        if not parsed.get("solved", False):
            return CaptchaResult(
                solved=False,
                captcha_type=ctype,
                reason=parsed.get("reason", "model_returned_unsolved"),
                elapsed_ms=(time.time() - t0) * 1000,
                extra={"model": model_used},
            )

        # Execute action based on response
        try:
            success = self._execute_action(cdp, parsed)
        except Exception as e:
            logger.error("Action execution failed: %s", e)
            success = False

        return CaptchaResult(
            solved=success,
            captcha_type=ctype,
            reason="ok" if success else "execution_failed",
            elapsed_ms=(time.time() - t0) * 1000,
            extra={"model": model_used, "response": parsed},
        )

    def _execute_action(self, cdp, parsed: dict) -> bool:
        """Execute action based on parsed model response."""
        action_type = parsed.get("action_type") or parsed.get("action", "")
        data = parsed.get("data", parsed)

        if action_type == "drag":
            return self._execute_drag(cdp, data)
        elif action_type == "text":
            return self._execute_text(cdp, data)
        elif action_type == "slide":
            return self._execute_slide(cdp, data)
        elif action_type in ("click", "checkbox"):
            return self._execute_click(cdp, data)
        elif "elements" in parsed:
            # Bounding-box response from Gemini
            return self._execute_from_bboxes(cdp, parsed)
        else:
            logger.warning("Unknown action type: %s", action_type)
            return False

    def _execute_drag(self, cdp, data: dict) -> bool:
        """Execute drag action."""
        source = data.get("source", {})
        target = data.get("target", {})
        sx, sy = source.get("x"), source.get("y")
        tx, ty = target.get("x"), target.get("y")
        if None in (sx, sy, tx, ty):
            return False

        cdp.call_result(
            "Input.dispatchMouseEvent",
            {"type": "mousePressed", "x": sx, "y": sy, "button": "left", "clickCount": 1},
        )
        time.sleep(0.05)

        steps = 10
        for i in range(1, steps + 1):
            t = i / steps
            px = sx + (tx - sx) * t
            py = sy + (ty - sy) * t
            cdp.call_result(
                "Input.dispatchMouseEvent",
                {"type": "mouseMoved", "x": px, "y": py, "button": "left"},
            )
            time.sleep(0.03)

        cdp.call_result(
            "Input.dispatchMouseEvent",
            {"type": "mouseReleased", "x": tx, "y": ty, "button": "left", "clickCount": 1},
        )
        return True

    def _execute_text(self, cdp, data: dict) -> bool:
        """Execute text input."""
        text = data.get("text", "")
        if not text:
            return False

        js = (
            f"(function(){{"
            f"var inp=document.querySelector('input[type=text],input:not([type])');"
            f"if(!inp)return false;"
            f"inp.focus();"
            f"inp.value='{text}';"
            f"inp.dispatchEvent(new Event('input',{{bubbles:true}}));"
            f"return true;"
            f"}})()"
        )
        resp = cdp.call_result("Runtime.evaluate", {"expression": js})
        return resp.get("result", {}).get("value", False)

    def _execute_slide(self, cdp, data: dict) -> bool:
        """Execute slider action."""
        distance = data.get("distance", 0)
        if not distance:
            return False

        js = (
            "(function(){"
            "var s=document.querySelector('.geetest_slider_button,.slider-handle,[class*=slider]');"
            "if(!s)return null;"
            "var r=s.getBoundingClientRect();"
            "return {x:r.left+r.width/2,y:r.top+r.height/2};"
            "})()"
        )
        resp = cdp.call_result("Runtime.evaluate", {"expression": js})
        pos = resp.get("result", {}).get("value")
        if not pos:
            return False

        sx, sy = pos["x"], pos["y"]
        tx = sx + distance

        cdp.call_result(
            "Input.dispatchMouseEvent",
            {"type": "mousePressed", "x": sx, "y": sy, "button": "left", "clickCount": 1},
        )

        steps = 15
        for i in range(1, steps + 1):
            t = i / steps
            ease = 1 - (1 - t) ** 3
            px = sx + (tx - sx) * ease
            cdp.call_result(
                "Input.dispatchMouseEvent",
                {"type": "mouseMoved", "x": px, "y": sy, "button": "left"},
            )
            time.sleep(0.02)

        cdp.call_result(
            "Input.dispatchMouseEvent",
            {"type": "mouseReleased", "x": tx, "y": sy, "button": "left", "clickCount": 1},
        )
        return True

    def _execute_click(self, cdp, data: dict) -> bool:
        """Execute click(s)."""
        clicks = data.get("clicks", [])
        if not clicks:
            # Single click (checkbox)
            x, y = data.get("x"), data.get("y")
            if x is not None and y is not None:
                clicks = [{"x": x, "y": y}]

        if not clicks:
            return False

        for click in clicks:
            x, y = click.get("x"), click.get("y")
            if x is None or y is None:
                continue
            cdp.call_result(
                "Input.dispatchMouseEvent",
                {"type": "mousePressed", "x": x, "y": y, "button": "left", "clickCount": 1},
            )
            time.sleep(0.05)
            cdp.call_result(
                "Input.dispatchMouseEvent",
                {"type": "mouseReleased", "x": x, "y": y, "button": "left", "clickCount": 1},
            )
            time.sleep(0.2)
        return True

    def _execute_from_bboxes(self, cdp, parsed: dict) -> bool:
        """Execute action from Gemini's bounding-box response."""
        elements = parsed.get("elements", [])
        action = parsed.get("action", "click")

        if action == "drag" and len(elements) >= 2:
            source = next((e for e in elements if "drag" in e.get("label", "").lower()), None)
            target = next(
                (
                    e
                    for e in elements
                    if "drop" in e.get("label", "").lower() or "zone" in e.get("label", "").lower()
                ),
                None,
            )
            if source and target:
                sb = source["bbox"]
                tb = target["bbox"]
                return self._execute_drag(
                    cdp,
                    {
                        "source": {"x": (sb[0] + sb[2]) / 2, "y": (sb[1] + sb[3]) / 2},
                        "target": {"x": (tb[0] + tb[2]) / 2, "y": (tb[1] + tb[3]) / 2},
                    },
                )

        elif action == "click":
            clicks = []
            for elem in elements:
                bbox = elem.get("bbox", [])
                if len(bbox) == 4:
                    clicks.append(
                        {
                            "x": (bbox[0] + bbox[2]) / 2,
                            "y": (bbox[1] + bbox[3]) / 2,
                        }
                    )
            if clicks:
                return self._execute_click(cdp, {"clicks": clicks})

        return False


# ── SINGLETON + PUBLIC API ─────────────────────────────────────────────────

_solver_instance: Optional[GatewaySolver] = None


def get_solver() -> GatewaySolver:
    """Singleton-Accessor für GatewaySolver."""
    global _solver_instance
    if _solver_instance is None:
        _solver_instance = GatewaySolver()
    return _solver_instance


def solve(cdp, detection) -> CaptchaResult:
    """Public API: Löst Captcha via Vercel AI Gateway.

    Versucht zuerst google/gemini-3.1-flash-image-preview,
    dann anthropic/claude-opus-4.7 bei Fehler.

    Graceful skip wenn AI_GATEWAY_API_KEY nicht gesetzt.

    Args:
        cdp: CDPConnection instance
        detection: CaptchaDetection mit captcha_type und dom_hint

    Returns:
        CaptchaResult mit solved, captcha_type, reason, elapsed_ms, extra
    """
    return get_solver().solve(cdp, detection)
