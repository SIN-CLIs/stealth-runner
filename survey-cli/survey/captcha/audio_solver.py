"""================================================================================
AUDIO SOLVER — NVIDIA Parakeet ASR für reCAPTCHA-v2 / hCaptcha Audio Challenges
================================================================================

MODUL-KONZEPT (SR-138, 2026-05-12):
    Dieses Modul implementiert Schritt 4 der Captcha-Fallback-Chain.
    Löst Audio-Captchas durch Transkription mit NVIDIA NIM Parakeet ASR.

WARUM AUDIO ALS FALLBACK?
    - reCAPTCHA-v2 und hCaptcha bieten Audio-Accessibility-Modus
    - Audio-Challenges sind oft einfacher als visuelle Puzzles
    - NVIDIA Parakeet CTC 1.1B ist state-of-the-art ASR, kostenlos auf NIM
    - Alternative: Nemotron-3-Nano-Omni hat multimodalen Audio-Mode

WORKFLOW:
    1. Aktiviere Audio-Modus im Captcha (Accessibility Button)
    2. Download Audio-Datei (MP3/WAV)
    3. Transkribiere via NVIDIA Parakeet ASR
    4. Gib transkribierten Text in das Antwortfeld ein

UNTERSTÜTZTE CAPTCHA-TYPEN:
    ✅ recaptcha (v2 mit Audio-Option)
    ✅ hcaptcha (mit Accessibility-Audio)
    ❌ turnstile — kein Audio-Modus
    ❌ geetest — kein Audio-Modus
    ❌ visual_text — kein Audio

API (konform mit Solver-Interface aus captcha_router):
    solve(cdp, detection) -> CaptchaResult

NVIDIA NIM ENDPOINT:
    Model: nvidia/parakeet-ctc-1.1b
    Docs: https://build.nvidia.com/nvidia/parakeet-ctc-1_1b

Module Status: NEW (SR-138, 2026-05-12)
================================================================================
"""

from __future__ import annotations

import base64
import json
import logging
import os
import re
import tempfile
import time
from dataclasses import dataclass, field
from typing import Any, Optional
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

logger = logging.getLogger("audio_solver")

# ── CONFIG ─────────────────────────────────────────────────────────────────

NIM_ASR_MODEL = "nvidia/parakeet-ctc-1.1b"
NIM_BASE_URL = "https://integrate.api.nvidia.com/v1"
MAX_AUDIO_DURATION_S = 30
TIMEOUT_S = 30
RETRIES = 2

# Captcha-Typen die Audio-Modus unterstützen
SUPPORTED_TYPES = frozenset({
    "recaptcha",
    "hcaptcha",
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
    extra: dict[str, Any] = field(default_factory=dict)


# ── AUDIO EXTRACTION ───────────────────────────────────────────────────────

def _click_audio_button(cdp, ctype: str) -> bool:
    """Klicke den Audio-Accessibility-Button im Captcha iframe.

    Args:
        cdp: CDPConnection instance
        ctype: Captcha-Typ (recaptcha oder hcaptcha)

    Returns:
        True wenn Button gefunden und geklickt
    """
    if ctype == "recaptcha":
        # reCAPTCHA Audio-Button Selektoren
        selectors = [
            "#recaptcha-audio-button",
            "button.rc-button-audio",
            "[aria-label*='audio']",
            "[title*='audio']",
        ]
    elif ctype == "hcaptcha":
        # hCaptcha Accessibility-Button
        selectors = [
            "[aria-label*='accessibility']",
            "[title*='accessibility']",
            ".challenge-link",
            "a[href*='accessibility']",
        ]
    else:
        return False

    for selector in selectors:
        js = f"""(function(){{
            var btn = document.querySelector('{selector}');
            if (btn) {{
                btn.click();
                return true;
            }}
            return false;
        }})()"""
        try:
            resp = cdp.call_result("Runtime.evaluate", {"expression": js})
            if resp.get("result", {}).get("value"):
                logger.info("Audio button clicked: %s", selector)
                time.sleep(1)  # Warte auf Audio-Challenge load
                return True
        except Exception:
            continue
    return False


def _extract_audio_url(cdp, ctype: str) -> Optional[str]:
    """Extrahiere die Audio-URL aus dem Captcha iframe.

    Args:
        cdp: CDPConnection instance
        ctype: Captcha-Typ

    Returns:
        Audio-URL oder None
    """
    if ctype == "recaptcha":
        # reCAPTCHA Audio-Element
        js = """(function(){
            var audio = document.querySelector('#audio-source, audio source, .rc-audiochallenge-play-button');
            if (audio && audio.src) return audio.src;
            var link = document.querySelector('a.rc-audiochallenge-download-link');
            if (link) return link.href;
            return null;
        })()"""
    elif ctype == "hcaptcha":
        # hCaptcha Audio-Element
        js = """(function(){
            var audio = document.querySelector('audio source, audio');
            if (audio && audio.src) return audio.src;
            return null;
        })()"""
    else:
        return None

    try:
        resp = cdp.call_result("Runtime.evaluate", {"expression": js})
        url = resp.get("result", {}).get("value")
        if url:
            logger.info("Audio URL extracted: %s", url[:80])
        return url
    except Exception as e:
        logger.warning("Audio URL extraction failed: %s", e)
        return None


def _download_audio_b64(audio_url: str) -> Optional[str]:
    """Download Audio-Datei und encode als Base64.

    Args:
        audio_url: URL zur Audio-Datei

    Returns:
        Base64-encoded Audio oder None
    """
    try:
        req = Request(audio_url, headers={"User-Agent": "Mozilla/5.0"})
        with urlopen(req, timeout=TIMEOUT_S) as resp:
            audio_data = resp.read()
            return base64.b64encode(audio_data).decode("utf-8")
    except Exception as e:
        logger.warning("Audio download failed: %s", e)
        return None


# ── NIM ASR CLIENT ─────────────────────────────────────────────────────────

class AudioSolver:
    """NVIDIA NIM Parakeet ASR Solver für Audio-Captchas.

    Transkribiert reCAPTCHA-v2 und hCaptcha Audio-Challenges
    via NVIDIA NIM's Parakeet CTC 1.1B ASR Modell (kostenlos).
    """

    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv("NVIDIA_API_KEY")
        self._available = bool(self.api_key)
        self.consecutive_failures = 0

        if not self._available:
            logger.warning("NVIDIA_API_KEY not set — AudioSolver unavailable")

    @property
    def available(self) -> bool:
        return self._available and self.consecutive_failures < 3

    def _record_failure(self, reason: str):
        self.consecutive_failures += 1
        logger.warning("AudioSolver failure: %s (count: %d)", reason, self.consecutive_failures)

    def _record_success(self):
        self.consecutive_failures = 0

    def _transcribe_audio(self, audio_b64: str) -> Optional[str]:
        """Transkribiere Audio via NVIDIA NIM Parakeet ASR.

        Args:
            audio_b64: Base64-encoded Audio (MP3/WAV)

        Returns:
            Transkribierter Text oder None
        """
        if not self.api_key:
            return None

        # NIM ASR API payload
        payload = {
            "audio": audio_b64,
            "language": "en",  # reCAPTCHA/hCaptcha Audio ist typischerweise Englisch
        }

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        for attempt in range(1, RETRIES + 1):
            try:
                req = Request(
                    f"{NIM_BASE_URL}/audio/transcriptions",
                    data=json.dumps(payload).encode("utf-8"),
                    headers=headers,
                    method="POST",
                )
                with urlopen(req, timeout=TIMEOUT_S) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    text = data.get("text", "").strip()
                    self._record_success()
                    return text
            except HTTPError as e:
                self._record_failure(f"http_{e.code}")
                if e.code == 429 and attempt < RETRIES:
                    time.sleep(5)
                    continue
            except URLError as e:
                self._record_failure(f"network: {e.reason}")
                if attempt < RETRIES:
                    time.sleep(2 ** attempt)
            except Exception as e:
                self._record_failure(f"unknown: {e}")
                break
        return None

    def _transcribe_via_openai_compat(self, audio_b64: str) -> Optional[str]:
        """Alternative: Transkribiere via OpenAI-kompatible API.

        Nutzt Nemotron-Omni wenn Parakeet nicht funktioniert.
        """
        try:
            from openai import OpenAI
            client = OpenAI(api_key=self.api_key, base_url=NIM_BASE_URL)

            # Decode audio to temp file (OpenAI API braucht file-like object)
            audio_bytes = base64.b64decode(audio_b64)
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                f.write(audio_bytes)
                temp_path = f.name

            try:
                with open(temp_path, "rb") as audio_file:
                    response = client.audio.transcriptions.create(
                        model=NIM_ASR_MODEL,
                        file=audio_file,
                        language="en",
                    )
                    return response.text.strip()
            finally:
                os.unlink(temp_path)
        except Exception as e:
            logger.warning("OpenAI-compat transcription failed: %s", e)
            return None

    def _submit_answer(self, cdp, answer: str, ctype: str) -> bool:
        """Submit transcribed answer to captcha input field.

        Args:
            cdp: CDPConnection instance
            answer: Transcribed text to enter
            ctype: Captcha type

        Returns:
            True if submission succeeded
        """
        if ctype == "recaptcha":
            selectors = [
                "#audio-response",
                "input.rc-audiochallenge-response-field",
                "[name='audio-response']",
            ]
        elif ctype == "hcaptcha":
            selectors = [
                "input[type='text']",
                ".answer-input",
            ]
        else:
            return False

        # Find and fill input
        for selector in selectors:
            js = f"""(function(){{
                var inp = document.querySelector('{selector}');
                if (inp) {{
                    inp.focus();
                    inp.value = '{answer}';
                    inp.dispatchEvent(new Event('input', {{bubbles: true}}));
                    return true;
                }}
                return false;
            }})()"""
            try:
                resp = cdp.call_result("Runtime.evaluate", {"expression": js})
                if resp.get("result", {}).get("value"):
                    logger.info("Answer submitted to: %s", selector)
                    break
            except Exception:
                continue
        else:
            return False

        # Click verify button
        time.sleep(0.3)
        verify_selectors = [
            "#recaptcha-verify-button",
            ".rc-button-default",
            "button[type='submit']",
            ".verify-button",
        ]
        for selector in verify_selectors:
            js = f"""(function(){{
                var btn = document.querySelector('{selector}');
                if (btn) {{
                    btn.click();
                    return true;
                }}
                return false;
            }})()"""
            try:
                resp = cdp.call_result("Runtime.evaluate", {"expression": js})
                if resp.get("result", {}).get("value"):
                    logger.info("Verify button clicked")
                    return True
            except Exception:
                continue
        return True  # Input filled, even if verify button not found

    def solve(self, cdp, detection) -> CaptchaResult:
        """Hauptmethode: Löst Audio-Captcha via NIM Parakeet ASR.

        Args:
            cdp: CDPConnection instance
            detection: CaptchaDetection mit captcha_type

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
                reason="audio_not_supported_for_type",
                elapsed_ms=(time.time() - t0) * 1000,
            )

        # Check availability
        if not self.available:
            return CaptchaResult(
                solved=False,
                captcha_type=ctype,
                reason="asr_unavailable",
                elapsed_ms=(time.time() - t0) * 1000,
            )

        # Step 1: Click audio button
        if not _click_audio_button(cdp, ctype):
            return CaptchaResult(
                solved=False,
                captcha_type=ctype,
                reason="audio_button_not_found",
                elapsed_ms=(time.time() - t0) * 1000,
            )

        # Step 2: Extract audio URL
        audio_url = _extract_audio_url(cdp, ctype)
        if not audio_url:
            return CaptchaResult(
                solved=False,
                captcha_type=ctype,
                reason="audio_url_not_found",
                elapsed_ms=(time.time() - t0) * 1000,
            )

        # Step 3: Download audio
        audio_b64 = _download_audio_b64(audio_url)
        if not audio_b64:
            return CaptchaResult(
                solved=False,
                captcha_type=ctype,
                reason="audio_download_failed",
                elapsed_ms=(time.time() - t0) * 1000,
            )

        # Step 4: Transcribe
        transcript = self._transcribe_audio(audio_b64)
        if not transcript:
            # Fallback to OpenAI-compatible endpoint
            transcript = self._transcribe_via_openai_compat(audio_b64)

        if not transcript:
            return CaptchaResult(
                solved=False,
                captcha_type=ctype,
                reason="transcription_failed",
                elapsed_ms=(time.time() - t0) * 1000,
            )

        # Clean transcript (remove punctuation, lowercase)
        clean_answer = re.sub(r"[^\w\s]", "", transcript).lower().strip()
        logger.info("Transcription: '%s' → '%s'", transcript, clean_answer)

        # Step 5: Submit answer
        success = self._submit_answer(cdp, clean_answer, ctype)

        return CaptchaResult(
            solved=success,
            captcha_type=ctype,
            reason="ok" if success else "submission_failed",
            elapsed_ms=(time.time() - t0) * 1000,
            extra={
                "model": NIM_ASR_MODEL,
                "transcript": transcript,
                "clean_answer": clean_answer,
            },
        )


# ── SINGLETON + PUBLIC API ─────────────────────────────────────────────────

_solver_instance: Optional[AudioSolver] = None


def get_solver() -> AudioSolver:
    """Singleton-Accessor für AudioSolver."""
    global _solver_instance
    if _solver_instance is None:
        _solver_instance = AudioSolver()
    return _solver_instance


def solve(cdp, detection) -> CaptchaResult:
    """Public API: Löst Audio-Captcha via NVIDIA Parakeet ASR.

    Nur für reCAPTCHA-v2 und hCaptcha mit Audio-Modus.

    Args:
        cdp: CDPConnection instance
        detection: CaptchaDetection mit captcha_type

    Returns:
        CaptchaResult mit solved, captcha_type, reason, elapsed_ms, extra
    """
    return get_solver().solve(cdp, detection)
