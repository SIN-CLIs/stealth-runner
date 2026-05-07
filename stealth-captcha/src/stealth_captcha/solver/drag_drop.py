"""Drag-drop puzzle captcha solver (PureSpectrum, FunCaptcha-style).

WARUM: PureSpectrum und FunCaptcha nutzen Puzzle-Captchas bei denen ein
Stück in eine Drop-Zone gezogen werden muss (multi-achsig, nicht nur Slide).
Ohne Solver blockiert der Survey-Flow an dieser Stelle dauerhaft.

ARCHITEKTUR: TrajectoryGenerator erzeugt menschenähnliche Drag-Pfade.
CDP Input.dispatchMouseEvent (mousePressed → mouseMoved → mouseReleased)
wird für jedes (source, target)-Paar ausgeführt.
Verifier prüft Erfolg über DOM-Change oder Success-Indicator.

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

from __future__ import annotations

import time
from dataclasses import dataclass

from stealth_captcha.cdp.client import CDPSession
from stealth_captcha.config import Settings, get_settings
from stealth_captcha.primitives import (
    HitTester,
    TrajectoryGenerator,
    Verifier,
    VerifyOutcome,
)
from stealth_captcha.solver.base import BaseSolver, SolveOutcome, SolveResult
from stealth_captcha.solver.slide import SlideCaptchaSolver
from stealth_captcha.telemetry import get_logger

log = get_logger(__name__)


@dataclass(slots=True)
class DragDropCaptchaSolver(BaseSolver):
    """Solves drag-drop puzzle captchas with multiple piece-place pairs.

    Usage:
        solver = DragDropCaptchaSolver(pairs=[
            (".piece-1", ".slot-1"),
            (".piece-2", ".slot-2"),
        ])
        result = await solver.solve(session)
    """

    pairs: list[tuple[str, str]]
    settings: Settings | None = None

    def __post_init__(self) -> None:
        if self.settings is None:
            self.settings = get_settings()

    async def solve(self, session: CDPSession) -> SolveResult:
        """Drag each source piece to its target slot.

        Args:
            session: CDP session attached to the page.

        Returns:
            SolveResult indicating success, failure, or unknown.
        """
        started = time.monotonic()
        verifier = Verifier(session)

        # Proxy to share CDP dispatch logic
        slide = SlideCaptchaSolver(settings=self.settings)

        for idx, (src_sel, dst_sel) in enumerate(self.pairs):
            log.info("drag_drop_pair", index=idx, source=src_sel, target=dst_sel)

            hit = HitTester(session)
            src_hit = await hit.ensure_topmost(src_sel)
            try:
                dst_hit = await hit.ensure_topmost(dst_sel)
                try:
                    generator = TrajectoryGenerator(self.settings.trajectory)
                    points = generator.generate(
                        start=src_hit.center,
                        end=dst_hit.center,
                    )
                    await slide._dispatch(session, points)
                finally:
                    await hit.restore(dst_hit)
            finally:
                await hit.restore(src_hit)

        # Final verification
        try:
            outcome = await verifier.wait(
                timeout_s=self.settings.solver.verify_timeout_s,
            )
        except Exception:  # noqa: BLE001
            return SolveResult(
                SolveOutcome.UNKNOWN,
                len(self.pairs),
                time.monotonic() - started,
            )

        if outcome == VerifyOutcome.SUCCESS:
            return SolveResult(
                SolveOutcome.SUCCESS,
                len(self.pairs),
                time.monotonic() - started,
            )
        return SolveResult(
            SolveOutcome.FAILURE,
            len(self.pairs),
            time.monotonic() - started,
        )
