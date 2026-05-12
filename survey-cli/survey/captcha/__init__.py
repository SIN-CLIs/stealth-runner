"""Captcha detection and solving (SR-68, SR-138)."""

from .drag_drop_solver import solve_puzzle
from .fallback_chain import (
    CaptchaUnsolvedError,
    FallbackChain,
    StepTrace,
    solve_with_fallback,
)

__all__ = [
    "solve_puzzle",
    "CaptchaUnsolvedError",
    "FallbackChain",
    "StepTrace",
    "solve_with_fallback",
]
