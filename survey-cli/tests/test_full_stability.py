"""Tests for survey.reliability.full_stability (SR-246).

Covers all four verdict branches, DOM-first ordering, short-circuit on
DOM timeout, metric_dict completeness, and tracker-not-attached propagation.
"""

from __future__ import annotations

import asyncio
import unittest
from dataclasses import dataclass
from typing import Optional

from survey.network.cdp_network_tracker import NetworkActivity
from survey.reliability.full_stability import (
    FullStabilityReport,
    FullStabilityVerdict,
    wait_for_full_stability,
)
from survey.reliability.network_gate import GateResult
from survey.reliability.stability import StabilityConfig
from survey.runner_policy import NetworkTuning


# ── Fakes ────────────────────────────────────────────────────────────────────


def _make_quiet_activity(pending: int = 0, age_ms: int = 9999) -> NetworkActivity:
    """Build a NetworkActivity that satisfies is_quiet() with default tuning."""
    return NetworkActivity(
        pending_count=pending,
        last_response_ts=0.0,
        last_response_age_ms=age_ms,
        total_started=10,
        total_finished=10 - pending,
        beacons_filtered=0,
    )


def _make_busy_activity() -> NetworkActivity:
    return NetworkActivity(
        pending_count=5,
        last_response_ts=0.0,
        last_response_age_ms=0,
        total_started=20,
        total_finished=15,
        beacons_filtered=0,
    )


@dataclass
class FakeTracker:
    """Minimal stub that satisfies the duck-typed tracker contract.

    Tracks how many times activity() was called so we can assert that
    DOM-timeout short-circuits without consulting the network half.
    """

    activity_value: NetworkActivity
    is_attached: bool = True
    activity_calls: int = 0

    def activity(self) -> NetworkActivity:
        self.activity_calls += 1
        return self.activity_value


def _stable_hasher_factory() -> object:
    """Hasher that returns the same value every time → DOM converges fast."""

    async def _h() -> str:
        return "stable-hash"

    return _h


def _changing_hasher_factory() -> object:
    """Hasher whose value changes every call → DOM never converges."""
    counter = {"n": 0}

    async def _h() -> str:
        counter["n"] += 1
        return f"hash-{counter['n']}"

    return _h


# ── Tests ────────────────────────────────────────────────────────────────────


class WaitForFullStabilityTests(unittest.IsolatedAsyncioTestCase):
    async def test_stable_verdict_when_dom_converges_and_network_quiet(self) -> None:
        tracker = FakeTracker(activity_value=_make_quiet_activity())
        report = await wait_for_full_stability(
            hasher=_stable_hasher_factory(),
            tracker=tracker,
            stability_config=StabilityConfig(stability_ms=1, max_wait_ms=200, samples=2),
            network_tuning=NetworkTuning(
                network_quiet_ms=10, max_pending_requests=0, max_wait_ms=100
            ),
        )
        self.assertEqual(report.verdict, "stable")
        self.assertEqual(report.dom_report.verdict, "stable")
        self.assertIsNotNone(report.network_result)
        assert report.network_result is not None  # for type-checker
        self.assertTrue(report.network_result.quiet)
        self.assertFalse(report.network_result.timed_out)

    async def test_dom_timeout_short_circuits_network_call(self) -> None:
        tracker = FakeTracker(activity_value=_make_quiet_activity())
        report = await wait_for_full_stability(
            hasher=_changing_hasher_factory(),
            tracker=tracker,
            stability_config=StabilityConfig(stability_ms=5, max_wait_ms=30, samples=3),
            network_tuning=NetworkTuning(
                network_quiet_ms=10, max_pending_requests=0, max_wait_ms=100
            ),
        )
        self.assertEqual(report.verdict, "dom_timeout")
        self.assertEqual(report.dom_report.verdict, "timeout")
        self.assertIsNone(report.network_result)
        # Critical: tracker.activity() was NEVER called when DOM short-circuits.
        self.assertEqual(
            tracker.activity_calls,
            0,
            "Network half must be skipped on dom_timeout",
        )

    async def test_network_timeout_when_dom_ok_but_network_busy(self) -> None:
        tracker = FakeTracker(activity_value=_make_busy_activity())
        report = await wait_for_full_stability(
            hasher=_stable_hasher_factory(),
            tracker=tracker,
            stability_config=StabilityConfig(stability_ms=1, max_wait_ms=200, samples=2),
            network_tuning=NetworkTuning(
                network_quiet_ms=10, max_pending_requests=0, max_wait_ms=20
            ),
        )
        self.assertEqual(report.verdict, "network_timeout")
        self.assertEqual(report.dom_report.verdict, "stable")
        self.assertIsNotNone(report.network_result)
        assert report.network_result is not None
        self.assertFalse(report.network_result.quiet)
        self.assertTrue(report.network_result.timed_out)

    async def test_explicit_tuning_overrides_provider_lookup(self) -> None:
        """When both provider AND network_tuning are supplied, tuning wins.

        We pass a `provider` that maps to strict tuning (max_pending=0)
        and a `tuning` that allows more pending. With activity reporting
        2 pending requests + recent response, only the lenient tuning
        accepts as quiet.
        """
        recent_quiet = NetworkActivity(
            pending_count=2,
            last_response_ts=0.0,
            last_response_age_ms=500,
            total_started=10,
            total_finished=8,
            beacons_filtered=0,
        )
        tracker = FakeTracker(activity_value=recent_quiet)
        report = await wait_for_full_stability(
            hasher=_stable_hasher_factory(),
            tracker=tracker,
            stability_config=StabilityConfig(stability_ms=1, max_wait_ms=200, samples=2),
            network_tuning=NetworkTuning(
                network_quiet_ms=10, max_pending_requests=5, max_wait_ms=50
            ),
            provider="pollfish",  # strict default — would have timed out
        )
        self.assertEqual(report.verdict, "stable")

    async def test_provider_lookup_used_when_no_tuning_supplied(self) -> None:
        tracker = FakeTracker(activity_value=_make_quiet_activity())
        report = await wait_for_full_stability(
            hasher=_stable_hasher_factory(),
            tracker=tracker,
            stability_config=StabilityConfig(stability_ms=1, max_wait_ms=200, samples=2),
            provider="pollfish",
        )
        # Pollfish default is strict (max_pending=0, quiet=100ms). Activity
        # reports pending=0 + age=9999ms → already quiet.
        self.assertEqual(report.verdict, "stable")

    async def test_tracker_not_attached_raises_runtime_error(self) -> None:
        tracker = FakeTracker(activity_value=_make_quiet_activity(), is_attached=False)
        with self.assertRaises(RuntimeError):
            await wait_for_full_stability(
                hasher=_stable_hasher_factory(),
                tracker=tracker,
                stability_config=StabilityConfig(
                    stability_ms=1, max_wait_ms=50, samples=2
                ),
                network_tuning=NetworkTuning(
                    network_quiet_ms=10, max_pending_requests=0, max_wait_ms=50
                ),
            )

    async def test_metric_dict_full_when_stable(self) -> None:
        tracker = FakeTracker(activity_value=_make_quiet_activity())
        report = await wait_for_full_stability(
            hasher=_stable_hasher_factory(),
            tracker=tracker,
            stability_config=StabilityConfig(stability_ms=1, max_wait_ms=200, samples=2),
            network_tuning=NetworkTuning(
                network_quiet_ms=10, max_pending_requests=0, max_wait_ms=100
            ),
        )
        m = report.metric_dict()
        self.assertEqual(m["verdict"], "stable")
        self.assertIn("dom_verdict", m)
        self.assertIn("dom_samples_taken", m)
        self.assertIn("network_quiet", m)
        self.assertIn("network_pending_count", m)
        self.assertNotIn("network_skipped", m)

    async def test_metric_dict_marks_skipped_on_dom_timeout(self) -> None:
        tracker = FakeTracker(activity_value=_make_quiet_activity())
        report = await wait_for_full_stability(
            hasher=_changing_hasher_factory(),
            tracker=tracker,
            stability_config=StabilityConfig(stability_ms=2, max_wait_ms=15, samples=3),
            network_tuning=NetworkTuning(
                network_quiet_ms=10, max_pending_requests=0, max_wait_ms=100
            ),
        )
        m = report.metric_dict()
        self.assertEqual(m["verdict"], "dom_timeout")
        self.assertEqual(m["network_quiet"], False)
        self.assertEqual(m["network_skipped"], True)
        self.assertNotIn("network_waited_ms", m)

    async def test_event_emitter_is_invoked_on_network_timeout(self) -> None:
        events: list[tuple[str, dict]] = []

        async def emit(name: str, payload: dict) -> None:
            events.append((name, payload))

        tracker = FakeTracker(activity_value=_make_busy_activity())
        report = await wait_for_full_stability(
            hasher=_stable_hasher_factory(),
            tracker=tracker,
            stability_config=StabilityConfig(stability_ms=1, max_wait_ms=200, samples=2),
            network_tuning=NetworkTuning(
                network_quiet_ms=10, max_pending_requests=0, max_wait_ms=20
            ),
            on_event=emit,
        )
        self.assertEqual(report.verdict, "network_timeout")
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0][0], "network_never_quiet")

    async def test_event_emitter_failure_does_not_break_facade(self) -> None:
        async def boom(name: str, payload: dict) -> None:
            raise RuntimeError("emitter dead")

        tracker = FakeTracker(activity_value=_make_busy_activity())
        # Must NOT raise — emitter failure is absorbed by the network gate.
        report = await wait_for_full_stability(
            hasher=_stable_hasher_factory(),
            tracker=tracker,
            stability_config=StabilityConfig(stability_ms=1, max_wait_ms=200, samples=2),
            network_tuning=NetworkTuning(
                network_quiet_ms=10, max_pending_requests=0, max_wait_ms=20
            ),
            on_event=boom,
        )
        self.assertEqual(report.verdict, "network_timeout")

    async def test_dom_first_ordering_visible_in_elapsed_ms(self) -> None:
        """Sanity: total elapsed_ms ≥ dom_elapsed_ms (network is never negative)."""
        tracker = FakeTracker(activity_value=_make_quiet_activity())
        report = await wait_for_full_stability(
            hasher=_stable_hasher_factory(),
            tracker=tracker,
            stability_config=StabilityConfig(stability_ms=1, max_wait_ms=200, samples=2),
            network_tuning=NetworkTuning(
                network_quiet_ms=10, max_pending_requests=0, max_wait_ms=100
            ),
        )
        self.assertGreaterEqual(report.elapsed_ms, report.dom_report.elapsed_ms)


if __name__ == "__main__":
    unittest.main()
