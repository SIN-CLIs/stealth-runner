"""Solver implementations for different captcha types.

WARUM: Jeder Captcha-Typ (Slide, Drag-Drop, Text/OCR) braucht eine
spezialisierte Logik, aber dieselbe Pipeline. Dieses Paket bündelt
alle Solver und stellt die gemeinsame API (solve(session) → SolveResult)
bereit. Neue Solver können hinzugefügt werden ohne bestehende zu brechen.

ARCHITEKTUR: Package-Root. Exportiert BaseSolver, SolveOutcome, SolveResult,
SlideCaptchaSolver, DragDropCaptchaSolver, TextCaptchaSolver.
Jeder Solver implementiert die 7-Stufen-Pipeline (Inject → Hit-Test →
Gap-Detect → Memory/Trajectory → CDP-Drag → Verify → Persist).

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
