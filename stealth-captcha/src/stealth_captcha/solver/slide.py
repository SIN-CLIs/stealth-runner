"""GoCaptcha / NetEase / GeeTest v3/v4 slide captcha solver.

Pipeline (matches the ACT step in @stealth/core):
  1. Stealth-inject via Page.addScriptToEvaluateOnNewDocument
  2. Hit-test .gc-drag-block → neutralize overlays
  3. Gap detection via DOM getBoundingClientRect (100x more accurate than vision)
  4. Episodic memory lookup (Agent-S3 pattern) → reuse successful trajectories
  5. Fresh Bezier trajectory if no memory hit
  6. Stream CDP Input.dispatchMouseEvent (trusted element-level PointerEvents)
  7. DOM polling for success/failure
  8. Persist trajectory to episodic memory on success

Key insight: CDP Input.dispatchMouseEvent is the only method that produces
BOTH trusted events AND element-level dispatch simultaneously.
"""

from __future__ import annotations

import asyncio
import secrets
import time
from dataclasses import dataclass

from tenacity import (
    AsyncRetrying,
    retry_if_not_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from stealth_captcha.cdp.client import CDPSession
from stealth_captcha.config import Settings, get_settings
from stealth_captcha.exceptions import (
    CaptchaError,
    HitTestError,
    SolverFailedError,
    VerifyTimeoutError,
)
from stealth_captcha.memory import ExperienceMemory, TrajectoryRecord
from stealth_captcha.primitives import (
    GapDetector,
    HitTester,
    TrajectoryGenerator,
    TrajectoryPoint,
    Verifier,
    VerifyOutcome,
)
from stealth_captcha.solver.base import BaseSolver, SolveOutcome, SolveResult
from stealth_captcha.stealth import StealthInjector
from stealth_captcha.telemetry import get_logger

log = get_logger(__name__)


@dataclass(slots=True)
class SlideCaptchaSolver(BaseSolver):
    """Slide captcha solver with CDP Input.dispatchMouseEvent.

    Usage:
        solver = SlideCaptchaSolver()
        result = await solver.solve(session)
        if result.outcome == SolveOutcome.SUCCESS:
            print("Captcha solved!")
    """

    settings: Settings | None = None

    # Configurable selectors (overridable per provider)
    block_selector: str = ".gc-drag-block"
    target_selector: str = ".gc-drag-target"
    success_selectors: tuple[str, ...] = (
        ".gc-success",
        ".gc-status-success",
        "[data-captcha-status='success']",
        ".yidun--success",
        ".gt_success",
        ".geetest_success",
    )
    failure_selectors: tuple[str, ...] = (
        ".gc-fail",
        ".gc-status-fail",
        "[data-captcha-status='fail']",
        ".yidun--fail",
        ".gt_fail",
        ".geetest_fail",
    )
    captcha_type: str = "slide"

    # Internal (initialized in __post_init__)
    memory: ExperienceMemory | None = None

    def __post_init__(self) -> None:
        if self.settings is None:
            self.settings = get_settings()
        if self.memory is None:
            self.memory = ExperienceMemory(self.settings.memory)

    async def solve(self, session: CDPSession) -> SolveResult:
        """Solve a slide captcha. Retries with exponential backoff on failure.

        Args:
            session: CDP session attached to the page.

        Returns:
            SolveResult indicating success, failure, or unknown.
        """
        mem = self.memory
        if mem is None:
            raise SolverFailedError("ExperienceMemory not initialized")

        await mem.init()
        started = time.monotonic()
        attempts = 0
        last_error: Exception | None = None

        try:
            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(self.settings.solver.max_retries),
                wait=wait_exponential(
                    multiplier=self.settings.solver.retry_backoff_base_s,
                    max=8.0,
                ),
                retry=retry_if_not_exception_type(SolverFailedError),
                reraise=True,
            ):
                with attempt:
                    attempts = attempt.retry_state.attempt_number
                    try:
                        outcome = await self._attempt(session, attempts)
                    except HitTestError as e:
                        log.warning("hit_test_failed", attempt=attempts, error=str(e))
                        raise CaptchaError(f"Hit-test failed: {e}") from e
                    except VerifyTimeoutError as e:
                        log.warning("verify_timeout", attempt=attempts)
                        raise CaptchaError(f"Verify timeout: {e}") from e

                    if outcome == SolveOutcome.SUCCESS:
                        return SolveResult(
                            outcome=SolveOutcome.SUCCESS,
                            attempts=attempts,
                            duration_s=time.monotonic() - started,
                        )
                    if outcome == SolveOutcome.FAILURE:
                        raise CaptchaError("Captcha rejected the drag (failure signal)")
                    # UNKNOWN → retry
                    raise CaptchaError("Verification did not resolve")
        except CaptchaError as e:
            last_error = e

        return SolveResult(
            outcome=SolveOutcome.FAILURE,
            attempts=attempts,
            duration_s=time.monotonic() - started,
            detail=str(last_error) if last_error else None,
        )

    async def _attempt(self, session: CDPSession, attempt_no: int) -> SolveOutcome:
        """Single solve attempt — the core pipeline."""
        log.info("slide_attempt", n=attempt_no)

        # 1. Stealth inject (idempotent — safe to call multiple times)
        injector = StealthInjector(self.settings.stealth)
        await injector.install(session)

        # 2. Hit-test: neutralize overlays
        hit_tester = HitTester(session)
        hit_result = await hit_tester.ensure_topmost(self.block_selector)

        try:
            # 3. Gap detection via DOM
            gap_detector = GapDetector(
                session,
                self.block_selector,
                self.target_selector,
            )
            gap = await gap_detector.detect()

            # 4. Trajectory: episodic memory first, or generate fresh
            mem = self.memory
            if mem is None:
                raise SolverFailedError("Memory not available")

            host = await self._page_host(session)
            similar = await mem.find_similar(
                host=host,
                captcha_type=self.captcha_type,
                delta_x=gap.delta_x,
                tolerance_px=self.settings.memory.similarity_threshold_px,
            )

            if similar:
                log.info("trajectory_from_memory", count=len(similar))
                base = secrets.choice(similar)
                points = self._replay_with_fresh_jitter(base)
            else:
                generator = TrajectoryGenerator(self.settings.trajectory)
                points = generator.generate(
                    start=hit_result.center,
                    end=(
                        hit_result.center[0] + gap.delta_x,
                        hit_result.center[1] + gap.delta_y,
                    ),
                )

            # 5. Stream CDP Input.dispatchMouseEvent
            await self._dispatch(session, points)

            # 6. Verify via DOM polling
            verifier = Verifier(
                session,
                success_selectors=self.success_selectors,
                failure_selectors=self.failure_selectors,
            )
            try:
                outcome = await verifier.wait(
                    timeout_s=self.settings.solver.verify_timeout_s,
                    poll_interval_s=self.settings.solver.verify_poll_interval_s,
                )
            except VerifyTimeoutError:
                return SolveOutcome.UNKNOWN

            # 7. Persist to memory on success
            if outcome == VerifyOutcome.SUCCESS:
                await mem.record(
                    TrajectoryRecord(
                        host=host,
                        captcha_type=self.captcha_type,
                        delta_x=gap.delta_x,
                        delta_y=gap.delta_y,
                        duration_ms=points[-1].t_ms,
                        sample_count=len(points),
                        points=[(p.t_ms, p.x, p.y) for p in points],
                        success=True,
                    )
                )
                return SolveOutcome.SUCCESS

            return SolveOutcome.FAILURE

        finally:
            # Always restore overlays
            await hit_tester.restore(hit_result)

    async def _dispatch(
        self,
        session: CDPSession,
        points: list[TrajectoryPoint],
    ) -> None:
        """Stream Input.dispatchMouseEvent for the trajectory.

        Event sequence: mousePressed → N×mouseMoved → mouseReleased
        All events have button:"left", buttons:1, pointerType:"mouse".

        This is the critical path: CDP dispatchMouseEvent produces trusted
        PointerEvents that reach the element-level handler—something neither
        CGEvent (blocked by hit-test overlay) nor JS dispatchEvent (untrusted)
        can achieve.
        """
        if not points:
            return

        first = points[0]

        # mousePressed at trajectory start
        await session.send(
            "Input.dispatchMouseEvent",
            {
                "type": "mousePressed",
                "x": round(first.x, 1),
                "y": round(first.y, 1),
                "button": "left",
                "buttons": 1,
                "clickCount": 1,
                "pointerType": "mouse",
                "force": 0.5,
            },
        )

        prev_t = first.t_ms
        # All intermediate mouseMoved events
        for p in points[1:-1]:
            wait_s = max(0.0, (p.t_ms - prev_t) / 1000.0)
            if wait_s > 0.0:
                await asyncio.sleep(wait_s)
            await session.send(
                "Input.dispatchMouseEvent",
                {
                    "type": "mouseMoved",
                    "x": round(p.x, 1),
                    "y": round(p.y, 1),
                    "button": "left",
                    "buttons": 1,
                    "pointerType": "mouse",
                    "force": 0.5,
                },
            )
            prev_t = p.t_ms

        # mouseReleased at target
        last = points[-1]
        wait_s = max(0.0, (last.t_ms - prev_t) / 1000.0)
        if wait_s > 0.0:
            await asyncio.sleep(wait_s)

        await session.send(
            "Input.dispatchMouseEvent",
            {
                "type": "mouseMoved",
                "x": round(last.x, 1),
                "y": round(last.y, 1),
                "button": "left",
                "buttons": 1,
                "pointerType": "mouse",
            },
        )
        await session.send(
            "Input.dispatchMouseEvent",
            {
                "type": "mouseReleased",
                "x": round(last.x, 1),
                "y": round(last.y, 1),
                "button": "left",
                "buttons": 0,
                "clickCount": 1,
                "pointerType": "mouse",
            },
        )

        log.info(
            "cdp_drag_complete",
            points=len(points),
            start=(round(first.x), round(first.y)),
            end=(round(last.x), round(last.y)),
            duration_ms=round(last.t_ms),
        )

    async def _page_host(self, session: CDPSession) -> str:
        """Get the current page's hostname."""
        result = await session.send(
            "Runtime.evaluate",
            {
                "expression": "location.hostname || 'unknown'",
                "returnByValue": True,
                "awaitPromise": False,
            },
        )
        return str(result.get("result", {}).get("value") or "unknown")

    @staticmethod
    def _replay_with_fresh_jitter(record: TrajectoryRecord) -> list[TrajectoryPoint]:
        """Replay a memory trajectory with fresh micro-jitter.

        The base path is preserved, but each point gets new ±2px jitter
        so the trajectory is never byte-identical to a previous one.
        """
        import random as _random

        rng = _random.Random(secrets.randbits(64))
        return [
            TrajectoryPoint(
                t,
                x + rng.uniform(-1.0, 1.0),
                y + rng.uniform(-2.0, 2.0),
            )
            for t, x, y in record.points
        ]
