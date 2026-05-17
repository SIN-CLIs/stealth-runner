"""Tests for survey.reliability.circuit_breaker (SR-253).

Pure unit tests via injectable now_fn — no real time.sleep, deterministic.
unittest-only.
"""

from __future__ import annotations

import threading
import unittest

from survey.reliability.circuit_breaker import (
    CircuitBreaker,
    CircuitOpenError,
)


class _FakeClock:
    def __init__(self, start: float = 0.0) -> None:
        self._t = start

    def now(self) -> float:
        return self._t

    def advance(self, s: float) -> None:
        self._t += s


# ── Construction ─────────────────────────────────────────────────────────────


class ConstructionTests(unittest.TestCase):
    def test_starts_closed(self) -> None:
        b = CircuitBreaker()
        self.assertEqual(b.state, "closed")
        self.assertEqual(b.consecutive_failures, 0)

    def test_failure_threshold_min_1(self) -> None:
        with self.assertRaises(ValueError):
            CircuitBreaker(failure_threshold=0)

    def test_cooldown_must_be_positive(self) -> None:
        with self.assertRaises(ValueError):
            CircuitBreaker(cooldown_s=0)
        with self.assertRaises(ValueError):
            CircuitBreaker(cooldown_s=-5)

    def test_success_threshold_min_1(self) -> None:
        with self.assertRaises(ValueError):
            CircuitBreaker(success_threshold=0)


# ── State transitions ────────────────────────────────────────────────────────


class StateTransitionTests(unittest.TestCase):
    def test_closed_to_open_on_threshold(self) -> None:
        clock = _FakeClock()
        b = CircuitBreaker(failure_threshold=3, cooldown_s=10, now_fn=clock.now)
        b.record_failure()
        b.record_failure()
        self.assertEqual(b.state, "closed")
        b.record_failure()
        self.assertEqual(b.state, "open")

    def test_success_in_closed_resets_streak(self) -> None:
        b = CircuitBreaker(failure_threshold=3)
        b.record_failure()
        b.record_failure()
        b.record_success()
        self.assertEqual(b.consecutive_failures, 0)
        b.record_failure()
        b.record_failure()
        # Need 3 in a row from now, not 2 + earlier.
        self.assertEqual(b.state, "closed")

    def test_open_to_half_open_after_cooldown(self) -> None:
        clock = _FakeClock()
        b = CircuitBreaker(failure_threshold=1, cooldown_s=30, now_fn=clock.now)
        b.record_failure()
        self.assertEqual(b.state, "open")
        clock.advance(29.99)
        self.assertEqual(b.state, "open")
        clock.advance(0.02)  # past cooldown
        self.assertEqual(b.state, "half_open")

    def test_half_open_success_closes_with_threshold_1(self) -> None:
        clock = _FakeClock()
        b = CircuitBreaker(
            failure_threshold=1,
            cooldown_s=10,
            success_threshold=1,
            now_fn=clock.now,
        )
        b.record_failure()
        clock.advance(11)
        # state read forces transition to half_open
        self.assertEqual(b.state, "half_open")
        b.record_success()
        self.assertEqual(b.state, "closed")
        self.assertEqual(b.consecutive_failures, 0)

    def test_half_open_requires_success_threshold(self) -> None:
        clock = _FakeClock()
        b = CircuitBreaker(
            failure_threshold=1,
            cooldown_s=10,
            success_threshold=3,
            now_fn=clock.now,
        )
        b.record_failure()
        clock.advance(11)
        self.assertEqual(b.state, "half_open")
        b.record_success()
        self.assertEqual(b.state, "half_open")  # still 1/3
        b.record_success()
        self.assertEqual(b.state, "half_open")  # still 2/3
        b.record_success()
        self.assertEqual(b.state, "closed")  # 3/3 -> closed

    def test_half_open_failure_reopens_with_fresh_cooldown(self) -> None:
        clock = _FakeClock()
        b = CircuitBreaker(failure_threshold=1, cooldown_s=10, now_fn=clock.now)
        b.record_failure()
        clock.advance(11)
        self.assertEqual(b.state, "half_open")
        b.record_failure()
        self.assertEqual(b.state, "open")
        # Cooldown reset → must wait full 10s again
        clock.advance(9.99)
        self.assertEqual(b.state, "open")
        clock.advance(0.02)
        self.assertEqual(b.state, "half_open")


# ── allow_request / call ─────────────────────────────────────────────────────


class CallWrapperTests(unittest.TestCase):
    def test_call_passes_through_when_closed(self) -> None:
        b = CircuitBreaker()
        result = b.call(lambda x: x * 2, 21)
        self.assertEqual(result, 42)

    def test_call_records_success(self) -> None:
        b = CircuitBreaker(failure_threshold=2)
        b.call(lambda: 1)
        s = b.stats()
        self.assertEqual(s["total_successes"], 1)
        self.assertEqual(s["consecutive_failures"], 0)

    def test_call_records_failure_and_reraises(self) -> None:
        b = CircuitBreaker(failure_threshold=3)
        with self.assertRaises(RuntimeError):
            b.call(lambda: (_ for _ in ()).throw(RuntimeError("boom")))
        self.assertEqual(b.consecutive_failures, 1)

    def test_call_short_circuits_in_open_state(self) -> None:
        clock = _FakeClock()
        b = CircuitBreaker(failure_threshold=1, cooldown_s=10, now_fn=clock.now)
        # Trip the breaker.
        b.record_failure()
        called = {"count": 0}

        def fn():
            called["count"] += 1
            return "ok"

        with self.assertRaises(CircuitOpenError) as cm:
            b.call(fn)
        self.assertEqual(called["count"], 0)  # fn was NOT called
        self.assertEqual(cm.exception.name, "")
        self.assertGreater(cm.exception.retry_after_s, 9)

    def test_circuit_open_error_includes_name_and_retry_after(self) -> None:
        clock = _FakeClock()
        b = CircuitBreaker(
            failure_threshold=1,
            cooldown_s=30,
            name="nim",
            now_fn=clock.now,
        )
        b.record_failure()
        try:
            b.call(lambda: 1)
            self.fail("expected CircuitOpenError")
        except CircuitOpenError as exc:
            self.assertEqual(exc.name, "nim")
            self.assertAlmostEqual(exc.retry_after_s, 30.0, delta=0.5)
            self.assertIn("nim", str(exc))
            self.assertIn("OPEN", str(exc))

    def test_exception_predicate_filters_failures(self) -> None:
        """Only exceptions matching the predicate trip the breaker."""

        def is_downstream(exc: Exception) -> bool:
            return isinstance(exc, ConnectionError)

        b = CircuitBreaker(
            failure_threshold=2,
            exception_predicate=is_downstream,
        )

        # ValueError is "client error" → does NOT count
        with self.assertRaises(ValueError):
            b.call(lambda: (_ for _ in ()).throw(ValueError("bad input")))
        with self.assertRaises(ValueError):
            b.call(lambda: (_ for _ in ()).throw(ValueError("bad input")))
        self.assertEqual(b.consecutive_failures, 0)
        self.assertEqual(b.state, "closed")

        # ConnectionError counts → trip after 2
        with self.assertRaises(ConnectionError):
            b.call(lambda: (_ for _ in ()).throw(ConnectionError("down")))
        with self.assertRaises(ConnectionError):
            b.call(lambda: (_ for _ in ()).throw(ConnectionError("down")))
        self.assertEqual(b.state, "open")


# ── allow_request manual mode ────────────────────────────────────────────────


class AllowRequestTests(unittest.TestCase):
    def test_allow_request_true_when_closed(self) -> None:
        b = CircuitBreaker()
        self.assertTrue(b.allow_request())

    def test_allow_request_false_when_open(self) -> None:
        b = CircuitBreaker(failure_threshold=1, cooldown_s=10)
        b.record_failure()
        self.assertFalse(b.allow_request())
        # And the short-circuit counter ticks.
        self.assertEqual(b.stats()["total_short_circuited"], 1)

    def test_allow_request_true_in_half_open(self) -> None:
        clock = _FakeClock()
        b = CircuitBreaker(failure_threshold=1, cooldown_s=10, now_fn=clock.now)
        b.record_failure()
        clock.advance(11)
        self.assertTrue(b.allow_request())


# ── Stats ────────────────────────────────────────────────────────────────────


class StatsTests(unittest.TestCase):
    def test_stats_full_snapshot(self) -> None:
        clock = _FakeClock()
        b = CircuitBreaker(
            failure_threshold=2,
            cooldown_s=15,
            name="nim",
            now_fn=clock.now,
        )
        b.record_success()
        b.record_failure()
        b.record_failure()  # tripped
        s = b.stats()
        self.assertEqual(s["name"], "nim")
        self.assertEqual(s["state"], "open")
        self.assertEqual(s["failure_threshold"], 2)
        self.assertEqual(s["cooldown_s"], 15.0)
        self.assertEqual(s["total_calls"], 3)
        self.assertEqual(s["total_successes"], 1)
        self.assertEqual(s["total_failures"], 2)
        self.assertGreater(s["last_failure_ts"], -1)
        self.assertAlmostEqual(s["retry_after_s"], 15.0, delta=0.1)


# ── Concurrency ──────────────────────────────────────────────────────────────


class ConcurrencyTests(unittest.TestCase):
    def test_concurrent_failures_only_trip_once(self) -> None:
        """Many threads recording simultaneous failures: state still consistent."""
        b = CircuitBreaker(failure_threshold=10, cooldown_s=10)

        def worker() -> None:
            for _ in range(5):
                b.record_failure()

        threads = [threading.Thread(target=worker) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # 100 failures recorded, breaker is open.
        s = b.stats()
        self.assertEqual(s["total_failures"], 100)
        self.assertEqual(s["state"], "open")


# ── Realistic smoke ──────────────────────────────────────────────────────────


class RealisticScenarioTests(unittest.TestCase):
    def test_provider_outage_recovers(self) -> None:
        """Scenario: NIM is down for 30s, then recovers."""
        clock = _FakeClock()
        b = CircuitBreaker(
            failure_threshold=3,
            cooldown_s=30,
            name="nim",
            now_fn=clock.now,
        )

        # 3 failures during outage.
        for _ in range(3):
            with self.assertRaises(RuntimeError):
                b.call(lambda: (_ for _ in ()).throw(RuntimeError("503")))
        self.assertEqual(b.state, "open")

        # During cooldown: every call short-circuits — saves 1000 retries.
        for _ in range(5):
            with self.assertRaises(CircuitOpenError):
                b.call(lambda: (_ for _ in ()).throw(RuntimeError("503")))
        self.assertEqual(b.stats()["total_short_circuited"], 5)

        # Provider recovers — wait out cooldown.
        clock.advance(31)
        self.assertEqual(b.state, "half_open")

        # Probe succeeds → closed.
        result = b.call(lambda: "ok")
        self.assertEqual(result, "ok")
        self.assertEqual(b.state, "closed")


if __name__ == "__main__":
    unittest.main()
