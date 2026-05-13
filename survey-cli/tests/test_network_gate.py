"""
Tests for survey/reliability/network_gate.py and survey/runner_policy.py (SR-174).

Coverage:
    - wait_for_network_quiet returns immediately when network is already quiet.
    - Times out and emits `network_never_quiet` when a request never finishes.
    - Per-provider behavior diverges as designed (pollfish strict, cint loose).
    - Provider-Override beats lookup.
    - Event-emitter exceptions never propagate out of the gate.
    - Raises if tracker is not attached.
"""

from __future__ import annotations

import asyncio
import unittest
from typing import Any

from survey.reliability.network_gate import (
    GateResult,
    wait_for_network_quiet,
)
from survey.runner_policy import (
    DEFAULT_PROVIDER,
    NetworkTuning,
    PROVIDER_NETWORK_TUNING,
    get_network_tuning,
)
from survey.network.cdp_network_tracker import CdpNetworkTracker

# Reuse the fake page from the tracker tests.
from tests.test_cdp_network_tracker import FakePage  # type: ignore[import-not-found]


# ---------------------------------------------------------------------------
# runner_policy
# ---------------------------------------------------------------------------


class TestRunnerPolicy(unittest.TestCase):
    def test_known_provider_lookup(self):
        t = get_network_tuning("pollfish")
        self.assertEqual(t.max_pending_requests, 0)
        self.assertEqual(t.network_quiet_ms, 100)

    def test_cint_allows_two_pending(self):
        """Regression: cint is dauer-chatty; max_pending must be > 0."""
        t = get_network_tuning("cint")
        self.assertGreaterEqual(t.max_pending_requests, 1)
        self.assertNotEqual(t.max_pending_requests, 0)

    def test_pollfish_vs_cint_differ(self):
        pol = get_network_tuning("pollfish")
        cint = get_network_tuning("cint")
        self.assertNotEqual(pol.max_pending_requests, cint.max_pending_requests)

    def test_unknown_provider_falls_back_to_default(self):
        t = get_network_tuning("never-heard-of-this-one")
        default = PROVIDER_NETWORK_TUNING[DEFAULT_PROVIDER]
        self.assertEqual(t, default)

    def test_none_provider_falls_back_to_default(self):
        t = get_network_tuning(None)
        self.assertEqual(t, PROVIDER_NETWORK_TUNING[DEFAULT_PROVIDER])

    def test_case_and_whitespace_normalized(self):
        a = get_network_tuning("  POLLFISH  ")
        b = get_network_tuning("pollfish")
        self.assertEqual(a, b)

    def test_override_short_circuits(self):
        ov = NetworkTuning(network_quiet_ms=1, max_pending_requests=99, max_wait_ms=50)
        t = get_network_tuning("pollfish", override=ov)
        self.assertIs(t, ov)


# ---------------------------------------------------------------------------
# wait_for_network_quiet
# ---------------------------------------------------------------------------


class TestWaitForNetworkQuiet(unittest.TestCase):
    def test_returns_quickly_when_already_quiet(self):
        async def run() -> GateResult:
            page = FakePage()
            async with CdpNetworkTracker(page) as tracker:
                return await wait_for_network_quiet(
                    tracker,
                    tuning=NetworkTuning(
                        network_quiet_ms=10, max_pending_requests=0, max_wait_ms=200
                    ),
                )

        result = asyncio.run(run())
        self.assertTrue(result.quiet)
        self.assertFalse(result.timed_out)
        # No prior response -> age requirement auto-satisfied -> very fast.
        self.assertLess(result.waited_ms, 200)

    def test_times_out_when_request_never_finishes(self):
        emitted: list[tuple[str, dict]] = []

        async def emit(event: str, payload: dict) -> None:
            emitted.append((event, payload))

        async def run() -> GateResult:
            page = FakePage()
            async with CdpNetworkTracker(page) as tracker:
                # Fire request but never finish it.
                page.fake_session.fire(
                    "Network.requestWillBeSent",
                    {
                        "requestId": "r-stuck",
                        "request": {"url": "https://api.example/slow"},
                    },
                )
                return await wait_for_network_quiet(
                    tracker,
                    tuning=NetworkTuning(
                        network_quiet_ms=50,
                        max_pending_requests=0,
                        max_wait_ms=80,
                    ),
                    provider="pollfish",
                    on_event=emit,
                )

        result = asyncio.run(run())
        self.assertFalse(result.quiet)
        self.assertTrue(result.timed_out)
        self.assertGreaterEqual(result.waited_ms, 80)
        # Force-proceed contract: event was emitted.
        self.assertEqual(len(emitted), 1)
        self.assertEqual(emitted[0][0], "network_never_quiet")
        payload = emitted[0][1]
        self.assertEqual(payload["pending_count"], 1)
        self.assertEqual(payload["provider"], "pollfish")

    def test_returns_quiet_after_pending_request_finishes(self):
        async def run() -> GateResult:
            page = FakePage()
            async with CdpNetworkTracker(page) as tracker:
                page.fake_session.fire(
                    "Network.requestWillBeSent",
                    {
                        "requestId": "r",
                        "request": {"url": "https://api.example/x"},
                    },
                )

                async def finish_soon() -> None:
                    await asyncio.sleep(0.020)
                    page.fake_session.fire("Network.loadingFinished", {"requestId": "r"})

                asyncio.create_task(finish_soon())
                return await wait_for_network_quiet(
                    tracker,
                    tuning=NetworkTuning(
                        network_quiet_ms=10,
                        max_pending_requests=0,
                        max_wait_ms=500,
                    ),
                )

        result = asyncio.run(run())
        self.assertTrue(result.quiet)
        self.assertFalse(result.timed_out)

    def test_cint_tolerates_two_chatty_beacons(self):
        """Per-provider override: cint allows 2 in-flight; gate settles."""

        async def run() -> GateResult:
            page = FakePage()
            async with CdpNetworkTracker(page) as tracker:
                # 2 real requests pending (simulating cint's steady-state).
                for i in (1, 2):
                    page.fake_session.fire(
                        "Network.requestWillBeSent",
                        {
                            "requestId": f"cint-{i}",
                            "request": {"url": f"https://respondent.cint.com/poll/{i}"},
                        },
                    )
                return await wait_for_network_quiet(
                    tracker, provider="cint"
                )

        result = asyncio.run(run())
        # cint allows max_pending_requests=2, so 2 pending = quiet.
        self.assertTrue(result.quiet)
        self.assertEqual(result.final_activity.pending_count, 2)

    def test_pollfish_does_not_tolerate_one_pending(self):
        """Same scenario as cint, but with pollfish strict (0 pending allowed)."""

        async def run() -> GateResult:
            page = FakePage()
            async with CdpNetworkTracker(page) as tracker:
                page.fake_session.fire(
                    "Network.requestWillBeSent",
                    {
                        "requestId": "p-1",
                        "request": {"url": "https://api.pollfish.com/v1/x"},
                    },
                )
                return await wait_for_network_quiet(
                    tracker,
                    tuning=NetworkTuning(
                        network_quiet_ms=50,
                        max_pending_requests=0,
                        max_wait_ms=80,
                    ),
                    provider="pollfish",
                )

        result = asyncio.run(run())
        self.assertFalse(result.quiet)
        self.assertTrue(result.timed_out)

    def test_emitter_exception_does_not_propagate(self):
        async def bad_emit(event: str, payload: dict) -> None:
            raise RuntimeError("emitter blew up")

        async def run() -> GateResult:
            page = FakePage()
            async with CdpNetworkTracker(page) as tracker:
                page.fake_session.fire(
                    "Network.requestWillBeSent",
                    {"requestId": "r", "request": {"url": "https://api.example/x"}},
                )
                return await wait_for_network_quiet(
                    tracker,
                    tuning=NetworkTuning(
                        network_quiet_ms=10, max_pending_requests=0, max_wait_ms=30
                    ),
                    on_event=bad_emit,
                )

        # No exception escapes the gate.
        result = asyncio.run(run())
        self.assertTrue(result.timed_out)

    def test_raises_if_tracker_not_attached(self):
        async def run() -> Any:
            page = FakePage()
            tracker = CdpNetworkTracker(page)
            # Note: NOT attached.
            return await wait_for_network_quiet(tracker, provider="pollfish")

        with self.assertRaises(RuntimeError):
            asyncio.run(run())

    def test_tuning_override_wins_over_provider(self):
        """When both tuning and provider are given, tuning wins."""

        async def run() -> GateResult:
            page = FakePage()
            async with CdpNetworkTracker(page) as tracker:
                # cint normally allows 2 pending; override forces strict 0.
                page.fake_session.fire(
                    "Network.requestWillBeSent",
                    {"requestId": "x", "request": {"url": "https://api.example/x"}},
                )
                return await wait_for_network_quiet(
                    tracker,
                    tuning=NetworkTuning(
                        network_quiet_ms=10, max_pending_requests=0, max_wait_ms=30
                    ),
                    provider="cint",
                )

        result = asyncio.run(run())
        self.assertTrue(result.timed_out)


if __name__ == "__main__":
    unittest.main()
