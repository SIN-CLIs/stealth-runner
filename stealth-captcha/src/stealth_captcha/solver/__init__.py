"""Solver implementations for different captcha types.

Each solver follows the same pipeline:
  1. Stealth-inject (idempotent)
  2. Hit-test the target element
  3. Detect gap/geometry via DOM
  4. Look up experience memory OR generate trajectory
  5. Stream Input.dispatchMouseEvent via CDP
  6. Verify success/failure via DOM polling
  7. Persist successful trajectory to memory
"""

from stealth_captcha.solver.base import BaseSolver, SolveOutcome, SolveResult
from stealth_captcha.solver.drag_drop import DragDropCaptchaSolver
from stealth_captcha.solver.slide import SlideCaptchaSolver
from stealth_captcha.solver.text import TextCaptchaSolver

__all__ = [
    "BaseSolver",
    "SolveOutcome",
    "SolveResult",
    "SlideCaptchaSolver",
    "TextCaptchaSolver",
    "DragDropCaptchaSolver",
]
