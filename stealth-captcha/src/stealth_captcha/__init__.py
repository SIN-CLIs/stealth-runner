"""Stealth Captcha — Production-grade CDP-based captcha solver for Stealth Suite.

Architecture:
  Launch Chrome (--remote-debugging-port) → CDP connect → stealth-inject →
  hit-test target → detect gap via DOM → generate Bezier trajectory →
  stream Input.dispatchMouseEvent → verify → persist to experience memory.

Solves GoCaptcha, NetEase, GeeTest v3/v4 slides, PureSpectrum drag-drop,
and text/OCR captchas. Zero vision-model dependency for coordinates
(getBoundingClientRect is ground truth, 100× more accurate than VLM).
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
