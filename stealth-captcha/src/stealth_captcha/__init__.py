"""Stealth Captcha — Production-grade CDP-based captcha solver for Stealth Suite.

WARUM: Jeder Survey-Run trifft auf Captchas. Ohne automatische Lösung
bricht der Flow ab. Dieses Paket bietet CDP-basierte Solver für alle
gebräuchlichen Captcha-Typen (GoCaptcha, NetEase, GeeTest, PureSpectrum,
Text/OCR). Keine Vision-Modelle für Koordinaten — DOM ist Ground-Truth.

ARCHITEKTUR: 7-Stufen-Pipeline:
  Launch Chrome (--remote-debugging-port) → CDP connect → stealth-inject →
  hit-test target → detect gap via DOM → generate Bezier trajectory →
  stream Input.dispatchMouseEvent → verify → persist to experience memory.
getBoundingClientRect ist 100× genauer als VLM (Research 2026-05-05).
Exportiert alle public APIs (Settings, Exceptions, Solvers, Primitives).

BANNED METHODS — NIEMALS VERWENDEN:
❌ playstealth launch
❌ webauto-nodriver — ABSOLUT BANNED
❌ cua-driver click (raw index)
❌ --remote-allow-origins=* (ohne Quotes)
❌ /tmp/heypiggy-bot (fixed profile)
❌ Hardcoded PIDs
❌ pkill -f "Google Chrome"
❌ killall Google Chrome
❌ skylight-cli click --element-index
"""

from stealth_captcha.config import Settings, get_settings
from stealth_captcha.exceptions import (
    CaptchaError,
    CDPCommandError,
    CDPConnectionError,
    GapDetectionError,
    HitTestError,
    SolverFailedError,
    StealthInjectionError,
    TrajectoryError,
    VerifyTimeoutError,
)
from stealth_captcha.solver.base import SolveOutcome, SolveResult
from stealth_captcha.solver.drag_drop import DragDropCaptchaSolver
from stealth_captcha.solver.slide import SlideCaptchaSolver
from stealth_captcha.solver.text import TextCaptchaSolver

__all__ = [
    # Config
    "Settings",
    "get_settings",
    # Exceptions
    "CaptchaError",
    "CDPConnectionError",
    "CDPCommandError",
    "HitTestError",
    "GapDetectionError",
    "StealthInjectionError",
    "SolverFailedError",
    "VerifyTimeoutError",
    "TrajectoryError",
    # Solvers
    "SlideCaptchaSolver",
    "TextCaptchaSolver",
    "DragDropCaptchaSolver",
    # Results
    "SolveOutcome",
    "SolveResult",
]

__version__ = "2.0.0"
