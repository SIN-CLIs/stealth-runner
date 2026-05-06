"""Bridge adapter: backward-compatible GoCaptchaSolver API → new CDP engine.

The old GoCaptchaSolver class (py-packages/captchas/gocaptcha.py) used:
  - JS dispatchEvent(PointerEvent) → isTrusted: false → always blocked
  - style.left manipulation → visual illusion, no real drag
  - cua-driver page execute_javascript → Apple Events, not CDP

This bridge provides the SAME public API (observe, reason, act, verify, correct, solve)
but routes through the new CDP-based pipeline under the hood.

Usage:
    from stealth_captcha.bridge import GoCaptchaSolver
    solver = GoCaptchaSolver(cdp_ws="ws://127.0.0.1:9222/...")
    result = await solver.solve(max_retries=3)
    # result == {"solved": True, "attempts": 1, ...}

For NEW code, use SlideCaptchaSolver directly instead.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

from stealth_captcha.cdp.client import CDPClient, CDPSession
from stealth_captcha.cdp.targets import create_tab
from stealth_captcha.config import get_settings
from stealth_captcha.primitives import (
    GapDetector,
    HitTester,
    TrajectoryGenerator,
    Verifier,
    VerifyOutcome,
)
from stealth_captcha.solver.slide import SlideCaptchaSolver
from stealth_captcha.stealth import StealthInjector


@dataclass
class GoCaptchaSolver:
    """Backward-compatible GoCaptchaSolver using the new CDP engine.

    Old API (kept for compatibility):
        solver = GoCaptchaSolver(pid, wid)  # ← PID/WID IGNORED, CDP used instead
        solver.observe()   → dict
        solver.reason()    → dict
        solver.act(plan)   → bool
        solver.verify()    → str
        solver.correct()   → dict
        solver.solve()     → dict

    New behavior:
        Connects via CDP (not cua-driver), uses Input.dispatchMouseEvent
        with Bezier trajectory, stealth injection, and DOM verify.

    Pass cdp_ws to pre-connect, or it will auto-connect on first use.
    """

    pid: int = 0  # Unused — kept for API compat
    wid: int = 0  # Unused — kept for API compat
    cdp_ws: str | None = None
    target_url: str | None = None

    # Internal state
    _client: CDPClient | None = None
    _session: CDPSession | None = None
    _last_plan: dict[str, Any] | None = None
    _slide_solver: SlideCaptchaSolver | None = None

    async def _ensure_connected(self) -> CDPSession:
        """Auto-connect to CDP if not already connected."""
        if self._session is not None:
            return self._session

        settings = get_settings()

        # Discover or create WebSocket URL
        if not self.cdp_ws:
            from stealth_captcha.cdp.targets import get_browser_ws

            ws_url = await get_browser_ws(settings.cdp.host, settings.cdp.port)
        else:
            ws_url = self.cdp_ws

        self._client = await CDPClient.connect(ws_url, timeout_s=settings.cdp.connect_timeout_s)

        # Create tab and navigate
        target = await create_tab(
            self.target_url or "about:blank",
            host=settings.cdp.host,
            port=settings.cdp.port,
        )
        self._session = await self._client.attach(target.target_id)

        # Stealth inject
        injector = StealthInjector(settings.stealth)
        await injector.install(self._session)

        if self.target_url:
            await self._session.send("Page.enable")
            await self._session.send("Page.navigate", {"url": self.target_url})
            await asyncio.sleep(2)

        self._slide_solver = SlideCaptchaSolver(settings=settings)
        return self._session

    # ── Old API methods ─────────────────────────────────────────────

    def observe(self) -> dict[str, Any]:
        """Observe the captcha state via DOM (old API: synchronous wrapper)."""
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(self._observe_async())

    async def _observe_async(self) -> dict[str, Any]:
        session = await self._ensure_connected()
        gap_detector = GapDetector(session)
        try:
            gap = await gap_detector.detect()
            return {
                "block": {
                    "x": gap.block_box[0],
                    "y": gap.block_box[1],
                    "w": gap.block_box[2],
                    "h": gap.block_box[3],
                },
                "slide": {
                    "x": gap.target_box[0],
                    "y": gap.target_box[1],
                    "w": gap.target_box[2],
                    "h": gap.target_box[3],
                    "right": gap.target_box[0] + gap.target_box[2],
                },
            }
        except Exception as e:
            return {"error": str(e)}

    def reason(self, obs: dict[str, Any]) -> dict[str, Any]:
        """Calculate drag plan from observation."""
        if not obs or "error" in obs:
            return {"error": "no captcha found"}

        b = obs.get("block", {})
        s = obs.get("slide", {})

        from_x = b.get("x", 0) + b.get("w", 0) // 2
        from_y = b.get("y", 0) + b.get("h", 0) // 2
        to_x = s.get("right", 0) - b.get("w", 0) // 2 - 2
        to_y = s.get("y", 0) + s.get("h", 0) // 2
        distance = s.get("right", 0) - b.get("x", 0) - b.get("w", 0)

        plan = {
            "from_x": from_x,
            "from_y": from_y,
            "to_x": to_x,
            "to_y": to_y,
            "distance": distance,
            "reasoning": (
                f"Block at ({b.get('x')},{b.get('y')}) {b.get('w')}x{b.get('h')}, "
                f"drag {distance}px right"
            ),
        }
        self._last_plan = plan
        return plan

    def act(self, plan: dict[str, Any]) -> bool:
        """Execute the drag (old API: synchronous wrapper)."""
        if "error" in plan:
            return False
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(self._act_async(plan))

    async def _act_async(self, plan: dict[str, Any]) -> bool:
        session = await self._ensure_connected()
        slide = self._slide_solver
        if not slide:
            return False

        hit = HitTester(session)
        try:
            hit_result = await hit.ensure_topmost(".gc-drag-block")
        except Exception:
            return False

        try:
            gen = TrajectoryGenerator(get_settings().trajectory)
            points = gen.generate(
                start=(plan["from_x"], plan["from_y"]),
                end=(plan["to_x"], plan["to_y"]),
            )
            await slide._dispatch(session, points)
            return True
        finally:
            await hit.restore(hit_result)

    def verify(self) -> str:
        """Check if the captcha block moved (old API: synchronous)."""
        loop = asyncio.get_event_loop()
        result = loop.run_until_complete(self._verify_async())
        return "MOVED" if result else "NOT_MOVED"

    async def _verify_async(self) -> bool:
        session = await self._ensure_connected()
        verifier = Verifier(session)
        try:
            outcome = await verifier.wait(timeout_s=3.0)
            return outcome == VerifyOutcome.SUCCESS
        except Exception:
            return False

    def correct(self, plan: dict[str, Any], offset: int = 5) -> dict[str, Any]:
        """Offset the drag plan for retry."""
        plan["from_x"] += offset
        plan["to_x"] += offset
        self._last_plan = plan
        return plan

    def solve(self, max_retries: int = 3) -> dict[str, Any]:
        """Full solve pipeline (old API: synchronous).

        Returns dict with keys: solved, result, attempts, plan.
        """
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(self._solve_async(max_retries))

    async def _solve_async(self, max_retries: int) -> dict[str, Any]:
        session = await self._ensure_connected()
        slide = self._slide_solver
        if not slide:
            return {"solved": False, "error": "solver not initialized", "attempts": 0}

        result = await slide.solve(session)

        base = {
            "solved": result.outcome.value == "success",
            "attempts": result.attempts,
        }
        if result.detail:
            base["detail"] = result.detail
        if self._last_plan:
            base["plan"] = self._last_plan
        return base

    async def close(self) -> None:
        """Clean up CDP connection."""
        if self._client:
            await self._client.aclose()
            self._client = None
            self._session = None
