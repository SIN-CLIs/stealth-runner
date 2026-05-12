"""================================================================================
NIM SECONDARY SOLVER — Qwen2.5-VL-72B Vision Model als Fallback für Captchas
================================================================================

MODUL-KONZEPT (SR-138, 2026-05-12):
    Dieses Modul implementiert den zweiten Schritt der Captcha-Fallback-Chain.
    Wenn der primäre NIM-Solver (Nemotron-3-Nano-Omni) fehlschlägt, wird hier
    ein alternatives Vision-Modell auf NVIDIA NIM verwendet.

WARUM EIN ZWEITES NIM-MODELL?
    - Unterschiedliche Modelle haben unterschiedliche Stärken bei Captchas
    - Qwen2.5-VL-72B ist state-of-the-art für Vision-Grounding (2026)
    - Kostenlos auf NVIDIA NIM verfügbar
    - Reduziert modellspezifische Fehler durch Diversität

UNTERSTÜTZTE CAPTCHA-TYPEN:
    ✅ angular_drag_drop — PureSpectrum Drag-Drop Puzzles
    ✅ visual_text — Text-basierte Captchas mit Bild
    ✅ geetest_v4 — GeeTest Slider/Click-Captchas
    ❌ hcaptcha, recaptcha — benötigen Token-basierte Lösung (siehe audio_solver)

ARCHITEKTUR:
    1. Screenshot des Captcha-Bereichs via CDP
    2. Vision-Prompt an Qwen2.5-VL-72B für Koordinaten/Text-Extraktion
    3. Ausführung der erkannten Aktion (Klick, Drag, Text-Eingabe)

API (konform mit Solver-Interface aus captcha_router):
    solve(cdp, detection) -> CaptchaResult

NVIDIA NIM ENDPOINT:
    Model: nvidia/qwen2.5-vl-72b-instruct
    Docs: https://build.nvidia.com/qwen/qwen2_5-vl-72b-instruct

Module Status: NEW (SR-138, 2026-05-12)
================================================================================
"""

from __future__ import annotations

import base64
import json
import logging
import os
import re
import time
from dataclasses import dataclass
from typing import Any, Optional

from openai import OpenAI, APIConnectionError, APITimeoutError, RateLimitError

logger = logging.getLogger("nim_secondary_solver")

# ── CONFIG ─────────────────────────────────────────────────────────────────

NIM_SECONDARY_MODEL = "nvidia/qwen2.5-vl-72b-instruct"
NIM_BASE_URL = "https://integrate.api.nvidia.com/v1"
MAX_TOKENS = 512
TIMEOUT_S = 30
RETRIES = 2

# Captcha-Typen die dieser Solver unterstützt (Vision-basiert)
SUPPORTED_TYPES = frozenset({
    "angular_drag_drop",
    "visual_text",
    "geetest_v4",
    "geetest_v3",
    "slider",
    "click_captcha",
})

# ── RESULT DATACLASS ───────────────────────────────────────────────────────

@dataclass
class CaptchaResult:
    """Ergebnis eines Captcha-Lösungsversuchs."""
    solved: bool
    captcha_type: str = ""
    token: str = ""
    elapsed_ms: float = 0.0
    reason: str = "ok"
    extra: dict[str, Any] = None

    def __post_init__(self):
        if self.extra is None:
            self.extra = {}


# ── SCREENSHOT CAPTURE ─────────────────────────────────────────────────────

def _capture_screenshot_b64(cdp, frame_id: str = "") -> Optional[str]:
    """Capture full-page oder Frame-Screenshot als Base64 PNG.

    Args:
        cdp: CDPConnection instance
        frame_id: Optional Frame-ID für iframe-Captchas

    Returns:
        Base64-encoded PNG string oder None bei Fehler
    """
    try:
        params = {"format": "png", "quality": 80}
        resp = cdp.call_result("Page.captureScreenshot", params)
        return resp.get("data")
    except Exception as e:
        logger.warning("Screenshot capture failed: %s", e)
        return None


# ── VISION PROMPT BUILDERS ─────────────────────────────────────────────────

def _build_drag_drop_prompt(detection) -> str:
    """Prompt für Angular CDK Drag-Drop Puzzles."""
    target = detection.dom_hint.replace("target=", "") if detection.dom_hint else "?"
    return f"""You are solving a drag-and-drop CAPTCHA puzzle.

TASK: Find the number "{target}" in the image and determine its drag coordinates.

The puzzle shows:
- Multiple draggable number images
- A drop zone where one number should be placed
- Instructions saying "Please drag the number {target}"

ANALYZE the image and provide:
1. The bounding box of the number {target} (source)
2. The bounding box of the drop zone (target)

OUTPUT FORMAT (JSON only, no markdown):
{{"source": {{"x": <center_x>, "y": <center_y>}}, "target": {{"x": <center_x>, "y": <center_y>}}, "found": true}}

If you cannot find the number, return:
{{"found": false, "reason": "number not visible"}}"""


def _build_visual_text_prompt(detection) -> str:
    """Prompt für Visual-Text Captchas."""
    return """You are solving a text-based image CAPTCHA.

TASK: Read the distorted text shown in the CAPTCHA image.

The image contains:
- Distorted, warped, or noisy text characters
- Usually 4-6 alphanumeric characters
- May have lines, dots, or color noise as obfuscation

ANALYZE the image and provide:
1. The exact characters you can read

OUTPUT FORMAT (JSON only, no markdown):
{"text": "<characters>", "confidence": <0.0-1.0>}

If unreadable, return:
{"text": "", "confidence": 0.0, "reason": "unreadable"}"""


def _build_slider_prompt() -> str:
    """Prompt für Slider-Captchas (GeeTest etc.)."""
    return """You are solving a slider CAPTCHA puzzle.

TASK: Find the puzzle piece and the gap where it should be placed.

The image shows:
- A background image with a missing puzzle piece (gap/hole)
- A separate puzzle piece that needs to slide into the gap

ANALYZE the image and provide:
1. The X-coordinate of the gap (target position)
2. The current X-coordinate of the slider piece
3. The distance to slide

OUTPUT FORMAT (JSON only, no markdown):
{"gap_x": <x_coordinate>, "slider_x": <start_x>, "distance": <pixels_to_slide>, "found": true}

If you cannot determine the gap position, return:
{"found": false, "reason": "gap not visible"}"""


def _build_click_captcha_prompt() -> str:
    """Prompt für Click-basierte Captchas."""
    return """You are solving a click-based CAPTCHA.

TASK: Identify which elements need to be clicked based on the instruction.

Common instructions:
- "Click on all traffic lights"
- "Select all images with crosswalks"
- "Click the objects in order: cat, dog, bird"

ANALYZE the image and provide:
1. List of coordinates to click
2. Order of clicks if specified

OUTPUT FORMAT (JSON only, no markdown):
{"clicks": [{"x": <x>, "y": <y>, "label": "<what>"}], "found": true}

If unclear what to click, return:
{"found": false, "reason": "instruction unclear"}"""


# ── NIM CLIENT ─────────────────────────────────────────────────────────────

class NimSecondarySolver:
    """NVIDIA NIM Qwen2.5-VL Solver für Vision-basierte Captchas.

    Nutzt das Qwen2.5-VL-72B Modell auf NVIDIA NIM für:
    - Koordinaten-Extraktion (Drag-Drop, Slider)
    - Text-Erkennung (Visual-Text Captchas)
    - Click-Target-Identifikation

    Circuit-Breaker und Retry-Pattern analog zu nim.py.
    """

    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv("NVIDIA_API_KEY")
        self.client = None
        if self.api_key:
            self.client = OpenAI(api_key=self.api_key, base_url=NIM_BASE_URL)
        self._available = self.client is not None
        self.consecutive_failures = 0

    @property
    def available(self) -> bool:
        return self._available and self.consecutive_failures < 3

    def _record_failure(self, reason: str):
        self.consecutive_failures += 1
        logger.warning("NimSecondary failure: %s (count: %d)", reason, self.consecutive_failures)
        if self.consecutive_failures >= 3:
            self._available = False

    def _record_success(self):
        self.consecutive_failures = 0
        self._available = True

    def _call_vision_api(self, prompt: str, image_b64: str) -> Optional[str]:
        """Call NIM Vision API with image + prompt.

        Args:
            prompt: Text prompt describing the task
            image_b64: Base64-encoded PNG image

        Returns:
            Raw model response text or None on failure
        """
        if not self.client:
            return None

        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{image_b64}"}
                    }
                ]
            }
        ]

        for attempt in range(1, RETRIES + 1):
            try:
                response = self.client.chat.completions.create(
                    model=NIM_SECONDARY_MODEL,
                    messages=messages,
                    max_tokens=MAX_TOKENS,
                    temperature=0.1,
                )
                self._record_success()
                return response.choices[0].message.content
            except (APIConnectionError, APITimeoutError) as e:
                self._record_failure(f"network: {e}")
                if attempt < RETRIES:
                    time.sleep(2 ** attempt)
            except RateLimitError as e:
                self._record_failure(f"rate_limit: {e}")
                if attempt < RETRIES:
                    time.sleep(5)
            except Exception as e:
                self._record_failure(f"unknown: {e}")
                break
        return None

    def _parse_json_response(self, raw: str) -> Optional[dict]:
        """Parse JSON from model response, handling markdown wrapping."""
        if not raw:
            return None
        raw = raw.strip()
        # Strip markdown code blocks
        if raw.startswith("```"):
            lines = raw.split("\n")
            lines = [l for l in lines if not l.strip().startswith("```")]
            raw = "\n".join(lines)
        # Try direct parse
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass
        # Try extracting JSON object
        match = re.search(r"\{[^{}]*\}", raw, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
        return None

    def solve(self, cdp, detection) -> CaptchaResult:
        """Hauptmethode: Löst Captcha via NIM Qwen2.5-VL Vision Model.

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

        # Check availability
        if not self.available:
            return CaptchaResult(
                solved=False,
                captcha_type=ctype,
                reason="nim_secondary_unavailable",
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

        # Build type-specific prompt
        if ctype == "angular_drag_drop":
            prompt = _build_drag_drop_prompt(detection)
        elif ctype == "visual_text":
            prompt = _build_visual_text_prompt(detection)
        elif ctype in ("geetest_v4", "geetest_v3", "slider"):
            prompt = _build_slider_prompt()
        elif ctype == "click_captcha":
            prompt = _build_click_captcha_prompt()
        else:
            prompt = _build_click_captcha_prompt()  # Generic fallback

        # Call Vision API
        raw_response = self._call_vision_api(prompt, screenshot)
        if not raw_response:
            return CaptchaResult(
                solved=False,
                captcha_type=ctype,
                reason="nim_api_failed",
                elapsed_ms=(time.time() - t0) * 1000,
            )

        # Parse response
        parsed = self._parse_json_response(raw_response)
        if not parsed:
            return CaptchaResult(
                solved=False,
                captcha_type=ctype,
                reason="parse_failed",
                elapsed_ms=(time.time() - t0) * 1000,
                extra={"raw": raw_response[:200]},
            )

        # Check if model found the target
        if not parsed.get("found", True):
            return CaptchaResult(
                solved=False,
                captcha_type=ctype,
                reason=parsed.get("reason", "not_found"),
                elapsed_ms=(time.time() - t0) * 1000,
            )

        # Execute action based on type
        try:
            if ctype == "angular_drag_drop":
                success = self._execute_drag_drop(cdp, parsed)
            elif ctype == "visual_text":
                success = self._execute_text_input(cdp, parsed)
            elif ctype in ("geetest_v4", "geetest_v3", "slider"):
                success = self._execute_slider(cdp, parsed)
            elif ctype == "click_captcha":
                success = self._execute_clicks(cdp, parsed)
            else:
                success = False
        except Exception as e:
            logger.error("Action execution failed: %s", e)
            success = False

        return CaptchaResult(
            solved=success,
            captcha_type=ctype,
            reason="ok" if success else "execution_failed",
            elapsed_ms=(time.time() - t0) * 1000,
            extra={"model": NIM_SECONDARY_MODEL, "response": parsed},
        )

    def _execute_drag_drop(self, cdp, parsed: dict) -> bool:
        """Execute drag-drop action based on parsed coordinates."""
        source = parsed.get("source", {})
        target = parsed.get("target", {})
        sx, sy = source.get("x"), source.get("y")
        tx, ty = target.get("x"), target.get("y")
        if None in (sx, sy, tx, ty):
            return False

        # Mouse down at source
        cdp.call_result("Input.dispatchMouseEvent", {
            "type": "mousePressed", "x": sx, "y": sy,
            "button": "left", "clickCount": 1
        })
        time.sleep(0.05)

        # Move in steps
        steps = 10
        for i in range(1, steps + 1):
            t = i / steps
            px = sx + (tx - sx) * t
            py = sy + (ty - sy) * t
            cdp.call_result("Input.dispatchMouseEvent", {
                "type": "mouseMoved", "x": px, "y": py, "button": "left"
            })
            time.sleep(0.03)

        # Mouse up at target
        cdp.call_result("Input.dispatchMouseEvent", {
            "type": "mouseReleased", "x": tx, "y": ty,
            "button": "left", "clickCount": 1
        })
        time.sleep(0.3)
        return True

    def _execute_text_input(self, cdp, parsed: dict) -> bool:
        """Execute text input for visual-text captcha."""
        text = parsed.get("text", "")
        if not text:
            return False

        # Find input field and type
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

    def _execute_slider(self, cdp, parsed: dict) -> bool:
        """Execute slider drag for GeeTest-style captchas."""
        distance = parsed.get("distance", 0)
        if not distance:
            return False

        # Find slider handle
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

        # Execute slide
        cdp.call_result("Input.dispatchMouseEvent", {
            "type": "mousePressed", "x": sx, "y": sy,
            "button": "left", "clickCount": 1
        })
        time.sleep(0.1)

        # Slide with acceleration curve
        steps = 15
        for i in range(1, steps + 1):
            t = i / steps
            # Ease-out curve
            ease = 1 - (1 - t) ** 3
            px = sx + (tx - sx) * ease
            cdp.call_result("Input.dispatchMouseEvent", {
                "type": "mouseMoved", "x": px, "y": sy, "button": "left"
            })
            time.sleep(0.02)

        cdp.call_result("Input.dispatchMouseEvent", {
            "type": "mouseReleased", "x": tx, "y": sy,
            "button": "left", "clickCount": 1
        })
        return True

    def _execute_clicks(self, cdp, parsed: dict) -> bool:
        """Execute click sequence for click-based captchas."""
        clicks = parsed.get("clicks", [])
        if not clicks:
            return False

        for click in clicks:
            x, y = click.get("x"), click.get("y")
            if x is None or y is None:
                continue
            cdp.call_result("Input.dispatchMouseEvent", {
                "type": "mousePressed", "x": x, "y": y,
                "button": "left", "clickCount": 1
            })
            time.sleep(0.05)
            cdp.call_result("Input.dispatchMouseEvent", {
                "type": "mouseReleased", "x": x, "y": y,
                "button": "left", "clickCount": 1
            })
            time.sleep(0.2)
        return True


# ── SINGLETON + PUBLIC API ─────────────────────────────────────────────────

_solver_instance: Optional[NimSecondarySolver] = None


def get_solver() -> NimSecondarySolver:
    """Singleton-Accessor für NimSecondarySolver."""
    global _solver_instance
    if _solver_instance is None:
        _solver_instance = NimSecondarySolver()
    return _solver_instance


def solve(cdp, detection) -> CaptchaResult:
    """Public API: Löst Captcha via NIM Qwen2.5-VL-72B.

    Konform mit Solver-Interface aus captcha_router:
        solve(cdp, detection) -> CaptchaResult

    Args:
        cdp: CDPConnection instance
        detection: CaptchaDetection mit captcha_type und dom_hint

    Returns:
        CaptchaResult mit solved, captcha_type, reason, elapsed_ms, extra
    """
    return get_solver().solve(cdp, detection)
