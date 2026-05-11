"""
================================================================================
CAPTCHA ROUTES — FastAPI Endpoints für Captcha-Solver (SR-74, SR-75)
================================================================================

ENDPOINTS:
  POST /captcha/slide           — Slide Puzzle Solver (GoCaptcha, NetEase, GeeTest)
  POST /captcha/text            — Text Captcha Solver (OCR + LLM Vision)
  POST /captcha/angular-drag-drop — Angular CDK Drag-Drop (PureSpectrum)

ARCHITEKTUR:
  Client → FastAPI Router → stealth-captcha/solver/* → CDPSession → Chrome

WARUM EIGENE ROUTES?
  - Captcha-Solver sind UNABHÄNGIG vom Survey-Flow
  - Andere Services (Auth, Scraping) könnten Captchas brauchen
  - Klare API-Trennung: /survey/* für Surveys, /captcha/* für Captchas

BANNED METHODS — NIEMALS VERWENDEN (siehe /banned.md):
  ❌ playstealth launch
  ❌ webauto-nodriver — ABSOLUT BANNED
  ❌ hardcoded PIDs
  ❌ pkill -f "Google Chrome"
================================================================================
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Literal, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

# Path setup für stealth-captcha
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "stealth-captcha" / "src"))


# ═══════════════════════════════════════════════════════════════════════════════
# PYDANTIC SCHEMAS
# ═══════════════════════════════════════════════════════════════════════════════


class SlideCaptchaRequest(BaseModel):
    """Request für POST /captcha/slide."""
    cdp_ws_url: str = Field(..., description="CDP WebSocket URL")
    block_selector: str = Field(default=".gc-drag-block", description="Drag-Element Selector")
    target_selector: str = Field(default=".gc-drag-target", description="Drop-Target Selector")
    max_retries: int = Field(default=3, ge=1, le=10, description="Maximale Retries")


class SlideCaptchaResponse(BaseModel):
    """Response für POST /captcha/slide."""
    status: Literal["ok", "error"] = Field(description="Ergebnis-Status")
    solved: bool = Field(description="Ob das Captcha gelöst wurde")
    attempts: int = Field(default=1, description="Anzahl der Versuche")
    elapsed_ms: float = Field(default=0.0, description="Laufzeit in ms")
    reason: str = Field(default="", description="Details")


class TextCaptchaRequest(BaseModel):
    """Request für POST /captcha/text."""
    cdp_ws_url: str = Field(..., description="CDP WebSocket URL")
    image_selector: str = Field(default="img.captcha-image, .captcha-image img", description="Captcha-Bild Selector")
    input_selector: str = Field(default="input[name='captcha'], input.captcha-input", description="Text-Input Selector")
    submit_selector: str = Field(default="button[type='submit'], .captcha-submit", description="Submit-Button Selector")
    model: str = Field(default="pixtral-large", description="Vision-Modell für OCR")


class TextCaptchaResponse(BaseModel):
    """Response für POST /captcha/text."""
    status: Literal["ok", "error"] = Field(description="Ergebnis-Status")
    solved: bool = Field(description="Ob das Captcha gelöst wurde")
    solution: Optional[str] = Field(default=None, description="Erkannter Text")
    confidence: float = Field(default=0.0, description="Konfidenz 0.0-1.0")
    elapsed_ms: float = Field(default=0.0, description="Laufzeit in ms")
    reason: str = Field(default="", description="Details")


class AngularDragDropRequest(BaseModel):
    """Request für POST /captcha/angular-drag-drop."""
    cdp_ws_url: str = Field(..., description="CDP WebSocket URL")
    target_number: Optional[str] = Field(default=None, description="Ziel-Zahl (auto-detect wenn None)")


class AngularDragDropResponse(BaseModel):
    """Response für POST /captcha/angular-drag-drop."""
    status: Literal["solved", "failed", "blocked"] = Field(description="Ergebnis-Status")
    number: Optional[str] = Field(default=None, description="Die gezogene Zahl")
    error: Optional[str] = Field(default=None, description="Fehler-Details")
    elapsed_ms: float = Field(default=0.0, description="Laufzeit in ms")


# ═══════════════════════════════════════════════════════════════════════════════
# ROUTER
# ═══════════════════════════════════════════════════════════════════════════════

router = APIRouter(prefix="/captcha", tags=["captcha"])


# ═══════════════════════════════════════════════════════════════════════════════
# LAZY-LOADERS
# ═══════════════════════════════════════════════════════════════════════════════


def _get_slide_solver():
    """Lazy-Load SlideCaptchaSolver."""
    try:
        from stealth_captcha.solver.slide import SlideCaptchaSolver
        from stealth_captcha.solver.base import SolveOutcome
        return SlideCaptchaSolver, SolveOutcome
    except ImportError as e:
        raise RuntimeError(f"SlideCaptchaSolver requires stealth-captcha: {e}") from e


def _get_text_solver():
    """Lazy-Load TextCaptchaSolver."""
    try:
        from stealth_captcha.solver.text import TextCaptchaSolver, PixtralLargeOCR
        from stealth_captcha.solver.base import SolveOutcome
        return TextCaptchaSolver, PixtralLargeOCR, SolveOutcome
    except ImportError as e:
        raise RuntimeError(f"TextCaptchaSolver requires stealth-captcha: {e}") from e


def _get_cdp_session(ws_url: str):
    """Erstellt eine CDPSession."""
    try:
        from stealth_captcha.cdp.client import CDPSession
        return CDPSession(ws_url)
    except ImportError:
        from survey.cdp_client import CDPConnection
        
        class _AsyncCDPAdapter:
            """Adapter: sync CDPConnection → async CDPSession API."""
            def __init__(self, ws_url: str):
                self._sync_cdp = CDPConnection(ws_url)
                self._connected = False
            
            async def __aenter__(self):
                self._sync_cdp.connect()
                self._connected = True
                return self
            
            async def __aexit__(self, *args):
                if self._connected:
                    self._sync_cdp.close()
            
            async def send(self, method: str, params: dict | None = None, **kwargs) -> dict:
                return self._sync_cdp.call(method, params or {})
        
        return _AsyncCDPAdapter(ws_url)


# ═══════════════════════════════════════════════════════════════════════════════
# ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════


@router.post("/slide", response_model=SlideCaptchaResponse)
async def solve_slide_captcha(req: SlideCaptchaRequest) -> SlideCaptchaResponse:
    """
    Löst ein Slide-Captcha (GoCaptcha, NetEase, GeeTest v3/v4).

    Workflow:
    1. CDP-Session öffnen
    2. Stealth-Inject (Anti-Detection)
    3. Gap-Detection via DOM
    4. Trajectory aus memory ODER fresh Bezier
    5. CDP Input.dispatchMouseEvent
    6. DOM-Polling für success/failure
    """
    start = time.monotonic()
    
    try:
        SlideCaptchaSolver, SolveOutcome = _get_slide_solver()
    except RuntimeError as e:
        return SlideCaptchaResponse(status="error", solved=False, reason=str(e), 
                                    elapsed_ms=(time.monotonic() - start) * 1000)
    
    try:
        solver = SlideCaptchaSolver(
            block_selector=req.block_selector,
            target_selector=req.target_selector,
        )
        session = _get_cdp_session(req.cdp_ws_url)
        
        async with session:
            result = await solver.solve(session)
        
        return SlideCaptchaResponse(
            status="ok" if result.outcome == SolveOutcome.SUCCESS else "error",
            solved=result.outcome == SolveOutcome.SUCCESS,
            attempts=result.attempts,
            elapsed_ms=result.duration_s * 1000,
            reason=result.detail or ("solved" if result.outcome == SolveOutcome.SUCCESS else "failed")
        )
    except Exception as e:
        return SlideCaptchaResponse(status="error", solved=False, 
                                    reason=f"exception: {type(e).__name__}: {e}",
                                    elapsed_ms=(time.monotonic() - start) * 1000)


@router.post("/text", response_model=TextCaptchaResponse)
async def solve_text_captcha(req: TextCaptchaRequest) -> TextCaptchaResponse:
    """
    Löst ein Text-Captcha via OCR + LLM Vision.

    Workflow:
    1. Screenshot des Captcha-Bildes
    2. Base64-PNG an Pixtral Large senden
    3. Erkannten Text in Input tippen
    4. Submit klicken
    """
    start = time.monotonic()
    
    try:
        TextCaptchaSolver, PixtralLargeOCR, SolveOutcome = _get_text_solver()
    except RuntimeError as e:
        return TextCaptchaResponse(status="error", solved=False, reason=str(e),
                                   elapsed_ms=(time.monotonic() - start) * 1000)
    
    try:
        backend = PixtralLargeOCR()
        solver = TextCaptchaSolver(
            backend=backend,
            image_selector=req.image_selector,
            input_selector=req.input_selector,
            submit_selector=req.submit_selector,
        )
        session = _get_cdp_session(req.cdp_ws_url)
        
        async with session:
            result = await solver.solve(session)
        
        return TextCaptchaResponse(
            status="ok" if result.outcome == SolveOutcome.SUCCESS else "error",
            solved=result.outcome == SolveOutcome.SUCCESS,
            solution=result.detail,
            confidence=0.9 if result.outcome == SolveOutcome.SUCCESS else 0.0,
            elapsed_ms=result.duration_s * 1000,
            reason="solved" if result.outcome == SolveOutcome.SUCCESS else (result.detail or "failed")
        )
    except Exception as e:
        return TextCaptchaResponse(status="error", solved=False,
                                   reason=f"exception: {type(e).__name__}: {e}",
                                   elapsed_ms=(time.monotonic() - start) * 1000)


@router.post("/angular-drag-drop", response_model=AngularDragDropResponse)
async def solve_angular_drag_drop(req: AngularDragDropRequest) -> AngularDragDropResponse:
    """
    Löst ein Angular CDK Drag-Drop Puzzle (PureSpectrum "Zahl X").

    Multi-Approach:
    1. Playwright raw mouse API
    2. CDP Input.dispatchMouseEvent
    3. Synthetic PointerEvents mit delays
    4. HTML5 Drag-and-Drop API
    """
    start = time.monotonic()
    
    try:
        from stealth_captcha.solver.drag_drop_angular import solve_drag_puzzle_new
    except ImportError as e:
        return AngularDragDropResponse(status="failed", error=f"Import failed: {e}",
                                       elapsed_ms=(time.monotonic() - start) * 1000)
    
    try:
        result = solve_drag_puzzle_new(req.cdp_ws_url)
        return AngularDragDropResponse(
            status=result.status,
            number=result.number,
            error=result.error,
            elapsed_ms=(time.monotonic() - start) * 1000
        )
    except Exception as e:
        return AngularDragDropResponse(status="failed", 
                                       error=f"exception: {type(e).__name__}: {e}",
                                       elapsed_ms=(time.monotonic() - start) * 1000)
