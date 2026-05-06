"""Text/OCR captcha solver — captures the captcha image, sends to vision model,
types the recognized text, and submits.

Designed for the Legacy/Simple text captchas that present a distorted image
with characters to transcribe. Uses pluggable OCR backends — default is
Mistral Pixtral Large via the Stealth Suite AI Gateway.

See research/2026-05-05-vision-benchmarks.md: pixtral-large was the only
model that correctly transcribed "QXem34" from a captcha image.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any, Protocol

from stealth_captcha.cdp.client import CDPSession
from stealth_captcha.solver.base import BaseSolver, SolveOutcome, SolveResult
from stealth_captcha.telemetry import get_logger

log = get_logger(__name__)


class VisionOCRBackend(Protocol):
    """Protocol for OCR backends (e.g. Pixtral, Llama Vision, Tesseract)."""

    async def transcribe(self, image_png_base64: str) -> str:
        """Transcribe text from a PNG image (base64-encoded).

        Args:
            image_png_base64: Base64-encoded PNG image data.

        Returns:
            The recognized text, or empty string on failure.
        """
        ...


@dataclass(slots=True)
class TextCaptchaSolver(BaseSolver):
    """Solves text/OCR captchas by capturing the image and using a vision model.

    Usage:
        solver = TextCaptchaSolver(backend=pixtral_backend)
        result = await solver.solve(session)
    """

    backend: VisionOCRBackend
    image_selector: str = (
        "img.captcha-image, img.gc-text-captcha, "
        ".captcha-image img, [data-captcha='text'] img"
    )
    input_selector: str = (
        "input[name='captcha'], input.captcha-input, "
        "input[data-captcha='input']"
    )
    submit_selector: str = (
        "button[type='submit'], .captcha-submit, "
        "button[data-captcha='submit']"
    )

    async def solve(self, session: CDPSession) -> SolveResult:
        """Run the OCR pipeline: screenshot → transcribe → type → submit."""
        started = time.monotonic()
        await session.send("Page.enable")

        # 1. Locate the captcha image in the DOM
        rect = await self._get_image_rect(session)
        if not rect:
            return SolveResult(
                SolveOutcome.FAILURE,
                1,
                time.monotonic() - started,
                "captcha image not found in DOM",
            )

        # 2. Capture the image via Page.captureScreenshot with clip
        cap = await session.send(
            "Page.captureScreenshot",
            {
                "format": "png",
                "clip": {
                    "x": rect["x"],
                    "y": rect["y"],
                    "width": rect["width"],
                    "height": rect["height"],
                    "scale": 2.0,
                },
                "captureBeyondViewport": True,
                "fromSurface": True,
            },
        )
        b64 = cap["data"]

        # 3. OCR via vision model
        text = (await self.backend.transcribe(b64)).strip()
        log.info("ocr_result", text=text, length=len(text))

        if not text:
            return SolveResult(
                SolveOutcome.FAILURE,
                1,
                time.monotonic() - started,
                "OCR returned empty result",
            )

        # 4. Type the recognized text into the input field
        await session.send(
            "Runtime.evaluate",
            {
                "expression": self._fill_js(
                    self.input_selector,
                    self.submit_selector,
                    text,
                ),
                "returnByValue": True,
                "awaitPromise": False,
            },
        )

        return SolveResult(
            SolveOutcome.SUCCESS,
            1,
            time.monotonic() - started,
            text,
        )

    async def _get_image_rect(
        self,
        session: CDPSession,
    ) -> dict[str, float] | None:
        """Get the bounding rect of the captcha image element."""
        result = await session.send(
            "Runtime.evaluate",
            {
                "expression": (
                    f"(() => {{"
                    f"  const el = document.querySelector({json.dumps(self.image_selector)});"
                    f"  if (!el) return null;"
                    f"  const r = el.getBoundingClientRect();"
                    f"  return {{x: r.left, y: r.top, width: r.width, height: r.height}};"
                    f"}})()"
                ),
                "returnByValue": True,
                "awaitPromise": False,
            },
        )
        value: Any = result.get("result", {}).get("value")
        if isinstance(value, dict) and value.get("width", 0) > 0:
            return value
        return None

    @staticmethod
    def _fill_js(
        input_selector: str,
        submit_selector: str,
        text: str,
    ) -> str:
        """Generate JS to fill the captcha input and submit."""
        return (
            f"(() => {{"
            f"  const i = document.querySelector({json.dumps(input_selector)});"
            f"  if (!i) return false;"
            f"  i.focus();"
            f"  i.value = {json.dumps(text)};"
            f"  i.dispatchEvent(new Event('input', {{bubbles: true}}));"
            f"  i.dispatchEvent(new Event('change', {{bubbles: true}}));"
            f"  const s = document.querySelector({json.dumps(submit_selector)});"
            f"  if (s) s.click();"
            f"  return true;"
            f"}})()"
        )


# ── Reference Pixtral Large OCR backend ────────────────────────────────
@dataclass(slots=True)
class PixtralLargeOCR:
    """OCR via Pixtral Large through the AI Gateway.

    Set STEALTH_AI_GATEWAY_URL and STEALTH_AI_API_KEY env vars.
    Default gateway is the Stealth Suite AI Gateway.
    """

    gateway_url: str = "https://integrate.api.nvidia.com/v1/chat/completions"
    api_key: str | None = None

    async def transcribe(self, image_png_base64: str) -> str:
        import os

        import httpx

        key = self.api_key or os.environ.get("NVIDIA_API_KEY", "")
        if not key:
            log.warning("no_nvidia_api_key")
            return ""

        prompt = (
            "You are a captcha transcription tool. "
            "Read the characters in the image EXACTLY as they appear. "
            "Output ONLY the characters — no explanation, no quotes, no whitespace."
        )

        payload = {
            "model": "mistralai/pixtral-large",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{image_png_base64}"
                            },
                        },
                    ],
                }
            ],
            "temperature": 0.0,
            "max_tokens": 16,
        }

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {key}",
        }

        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                resp = await client.post(
                    self.gateway_url,
                    json=payload,
                    headers=headers,
                )
                resp.raise_for_status()
                data = resp.json()
        except Exception as e:
            log.warning("ocr_api_error", error=str(e))
            return ""

        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            return ""

        if isinstance(content, list):
            parts = [
                p.get("text", "") for p in content if isinstance(p, dict)
            ]
            content = "".join(parts)

        return str(content).strip()
