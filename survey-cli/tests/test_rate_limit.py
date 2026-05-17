"""Tests for survey.reliability.rate_limit (SR-251).

Pure unit tests via injectable now_fn / sleep_fn — no real time.sleep,
deterministic, fast. unittest-only.
"""

from __future__ import annotations

import threading
import unittest

from survey.reliability.rate_limit import TokenBucket


# ── Fake clock ───────────────────────────────────────────────────────────────


class _FakeClock:
    """Caller advances time explicitly via .advance(seconds)."""

    def __init__(self, start: float = 0.0) -> None:
        self._t = start
        self.sleeps: list[float] = []

    def now(self) -> float:
        return self._t

    def sleep(self, s: float) -> None:
        # Record + advance. Tests verify acquire() doesn't sleep more
        # than necessary.
        self.sleeps.append(s)
        self._t += s

    def advance(self, s: float) -> None:
        self._t += s


# ── Construction / validation ────────────────────────────────────────────────


class ConstructionTests(unittest.TestCase):
    def test_default_initial_tokens_equals_capacity(self) -> None:
        b = TokenBucket(capacity=10, refill_rate=1)
        self.assertEqual(b.available_tokens(), 10.0)

    def test_explicit_initial_tokens_zero(self) -> None:
        b = TokenBucket(capacity=10, refill_rate=0, initial_tokens=0)
        self.assertEqual(b.available_tokens(), 0.0)

    def test_capacity_must_be_positive(self) -> None:
        with self.assertRaises(ValueError):
            TokenBucket(capacity=0, refill_rate=1)
        with self.assertRaises(ValueError):
            TokenBucket(capacity=-5, refill_rate=1)

    def test_refill_rate_must_be_non_negative(self) -> None:
        with self.assertRaises(ValueError):
            TokenBucket(capacity=10, refill_rate=-1)

    def test_initial_tokens_out_of_range_rejected(self) -> None:
        with self.assertRaises(ValueError):
            TokenBucket(capacity=10, refill_rate=1, initial_tokens=-1)
        with self.assertRaises(ValueError):
            TokenBucket(capacity=10, refill_rate=1, initial_tokens=11)


# ── try_acquire (non-blocking) ───────────────────────────────────────────────


class TryAcquireTests(unittest.TestCase):
    def test_acquires_until_empty_then_denies(self) -> None:
        clock = _FakeClock()
        b = TokenBucket(
            capacity=3, refill_rate=0, now_fn=clock.now, sleep_fn=clock.sleep
        )
        self.assertTrue(b.try_acquire())
        self.assertTrue(b.try_acquire())
        self.assertTrue(b.try_acquire())
        self.assertFalse(b.try_acquire())
        self.assertFalse(b.try_acquire())

    def test_refill_replenishes_over_time(self) -> None:
        clock = _FakeClock()
        b = TokenBucket(
            capacity=10, refill_rate=2, now_fn=clock.now, sleep_fn=clock.sleep
        )
        # Drain.
        for _ in range(10):
            self.assertTrue(b.try_acquire())
        self.assertFalse(b.try_acquire())
        # 1 second → refill 2 tokens.
        clock.advance(1)
        self.assertTrue(b.try_acquire())
        self.assertTrue(b.try_acquire())
        self.assertFalse(b.try_acquire())

    def test_refill_capped_at_capacity(self) -> None:
        clock = _FakeClock()
        b = TokenBucket(
            capacity=5, refill_rate=10, now_fn=clock.now, sleep_fn=clock.sleep
        )
        # Drain 1.
        b.try_acquire()
        self.assertEqual(b.available_tokens(), 4.0)
        # Wait 100s — refill would add 1000 but cap is 5.
        clock.advance(100)
        self.assertEqual(b.available_tokens(), 5.0)

    def test_acquire_more_than_capacity_always_denies(self) -> None:
        b = TokenBucket(capacity=5, refill_rate=1)
        self.assertFalse(b.try_acquire(tokens=6))
        # No tokens consumed.
        self.assertEqual(b.available_tokens(), 5.0)
        stats = b.stats()
        self.assertEqual(stats["total_denied"], 1)
        self.assertEqual(stats["total_acquired"], 0)

    def test_acquire_zero_tokens_is_noop_and_succeeds(self) -> None:
        b = TokenBucket(capacity=5, refill_rate=1)
        self.assertTrue(b.try_acquire(tokens=0))
        self.assertEqual(b.available_tokens(), 5.0)
        # Zero-acquire shouldn't bump stats either.
        self.assertEqual(b.stats()["total_acquired"], 0)

    def test_fractional_tokens_allowed(self) -> None:
        clock = _FakeClock()
        b = TokenBucket(
            capacity=1, refill_rate=1, now_fn=clock.now, sleep_fn=clock.sleep
        )
        self.assertTrue(b.try_acquire(0.5))
        self.assertAlmostEqual(b.available_tokens(), 0.5, places=5)
        self.assertTrue(b.try_acquire(0.5))
        self.assertFalse(b.try_acquire(0.1))


# ── acquire (blocking) ───────────────────────────────────────────────────────


class BlockingAcquireTests(unittest.TestCase):
    def test_acquire_immediate_when_tokens_available(self) -> None:
        clock = _FakeClock()
        b = TokenBucket(
            capacity=3, refill_rate=1, now_fn=clock.now, sleep_fn=clock.sleep
        )
        self.assertTrue(b.acquire(max_wait_s=10))
        # No sleep needed.
        self.assertEqual(clock.sleeps, [])

    def test_acquire_waits_for_refill_then_succeeds(self) -> None:
        clock = _FakeClock()
        b = TokenBucket(
            capacity=2,
            refill_rate=1,  # 1 token per second
            initial_tokens=0,
            now_fn=clock.now,
            sleep_fn=clock.sleep,
        )
        # Acquire blocks until 1 token is refilled.
        self.assertTrue(b.acquire(max_wait_s=5))
        # Should have slept ~1s (in one or two sleep calls).
        total_sleep = sum(clock.sleeps)
        self.assertGreaterEqual(total_sleep, 0.99)
        self.assertLess(total_sleep, 1.5)

    def test_acquire_times_out_when_refill_too_slow(self) -> None:
        clock = _FakeClock()
        b = TokenBucket(
            capacity=10,
            refill_rate=0.1,  # 1 token per 10s
            initial_tokens=0,
            now_fn=clock.now,
            sleep_fn=clock.sleep,
        )
        # Want 1 token, refill takes 10s, deadline 2s → timeout.
        self.assertFalse(b.acquire(tokens=1, max_wait_s=2))
        # Should not exceed deadline.
        self.assertLessEqual(sum(clock.sleeps), 2.05)

    def test_acquire_with_zero_max_wait_falls_back_to_try_acquire(self) -> None:
        clock = _FakeClock()
        b = TokenBucket(
            capacity=1, refill_rate=1, initial_tokens=0,
            now_fn=clock.now, sleep_fn=clock.sleep,
        )
        # No initial tokens, refill rate 1/s, but max_wait=0 → no sleep.
        self.assertFalse(b.acquire(max_wait_s=0))
        self.assertEqual(clock.sleeps, [])

    def test_acquire_returns_false_when_unsatisfiable(self) -> None:
        """capacity=2, refill_rate=0, want 5 → infinite wait → return False."""
        clock = _FakeClock()
        b = TokenBucket(
            capacity=2, refill_rate=0,
            now_fn=clock.now, sleep_fn=clock.sleep,
        )
        self.assertFalse(b.acquire(tokens=5, max_wait_s=100))
        # No sleep should have happened — we detected unsatisfiable upfront.
        self.assertEqual(clock.sleeps, [])

    def test_acquire_zero_tokens_succeeds_without_sleeping(self) -> None:
        clock = _FakeClock()
        b = TokenBucket(
            capacity=1, refill_rate=0, initial_tokens=0,
            now_fn=clock.now, sleep_fn=clock.sleep,
        )
        self.assertTrue(b.acquire(tokens=0, max_wait_s=10))
        self.assertEqual(clock.sleeps, [])


# ── time_until / available_tokens ────────────────────────────────────────────


class TimeUntilTests(unittest.TestCase):
    def test_time_until_zero_when_already_available(self) -> None:
        b = TokenBucket(capacity=5, refill_rate=1)
        self.assertEqual(b.time_until(3), 0.0)

    def test_time_until_computes_deficit_over_rate(self) -> None:
        clock = _FakeClock()
        b = TokenBucket(
            capacity=10, refill_rate=2, initial_tokens=0,
            now_fn=clock.now, sleep_fn=clock.sleep,
        )
        # Want 4, have 0, rate 2/s → 2s.
        self.assertAlmostEqual(b.time_until(4), 2.0, places=5)

    def test_time_until_inf_when_no_refill(self) -> None:
        b = TokenBucket(capacity=5, refill_rate=0, initial_tokens=0)
        self.assertEqual(b.time_until(3), float("inf"))

    def test_time_until_zero_for_zero_tokens(self) -> None:
        b = TokenBucket(capacity=5, refill_rate=1, initial_tokens=0)
        self.assertEqual(b.time_until(0), 0.0)
        self.assertEqual(b.time_until(-1), 0.0)


# ── Stats ────────────────────────────────────────────────────────────────────


class StatsTests(unittest.TestCase):
    def test_stats_track_acquired_and_denied(self) -> None:
        b = TokenBucket(capacity=2, refill_rate=0)
        self.assertTrue(b.try_acquire())
        self.assertTrue(b.try_acquire())
        self.assertFalse(b.try_acquire())
        self.assertFalse(b.try_acquire())
        s = b.stats()
        self.assertEqual(s["total_acquired"], 2)
        self.assertEqual(s["total_denied"], 2)
        self.assertAlmostEqual(s["ratio_denied"], 0.5, places=5)

    def test_stats_includes_capacity_rate_and_name(self) -> None:
        b = TokenBucket(capacity=5, refill_rate=0.5, name="dlq_replay")
        s = b.stats()
        self.assertEqual(s["capacity"], 5.0)
        self.assertEqual(s["refill_rate"], 0.5)
        self.assertEqual(s["name"], "dlq_replay")

    def test_ratio_denied_zero_when_no_attempts(self) -> None:
        b = TokenBucket(capacity=5, refill_rate=1)
        self.assertEqual(b.stats()["ratio_denied"], 0.0)


# ── Thread safety ────────────────────────────────────────────────────────────


class ThreadSafetyTests(unittest.TestCase):
    def test_concurrent_try_acquire_never_oversells(self) -> None:
        """100 threads each trying 5 acquires → total <= capacity (no refill)."""
        b = TokenBucket(capacity=50, refill_rate=0)
        successes: list[bool] = []
        lock = threading.Lock()

        def worker() -> None:
            local = []
            for _ in range(5):
                local.append(b.try_acquire())
            with lock:
                successes.extend(local)

        threads = [threading.Thread(target=worker) for _ in range(100)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Exactly capacity successes — no over-acquisition.
        self.assertEqual(sum(successes), 50)
        # And the bucket is empty.
        self.assertEqual(b.available_tokens(), 0.0)


# ── Smoke ────────────────────────────────────────────────────────────────────


class RealisticScenarioTests(unittest.TestCase):
    def test_dlq_replay_5_per_minute_burst(self) -> None:
        """Scenario: DLQ replay limited to 5/min with burst-5.

        First 5 calls in a tight loop succeed; 6th fails until next refill.
        """
        clock = _FakeClock()
        bucket = TokenBucket(
            capacity=5,
            refill_rate=5 / 60,
            now_fn=clock.now,
            sleep_fn=clock.sleep,
            name="dlq_replay",
        )
        # Burst of 5 succeeds.
        for _ in range(5):
            self.assertTrue(bucket.try_acquire())
        # 6th denied immediately.
        self.assertFalse(bucket.try_acquire())
        # 12s later → refill ~1 token.
        clock.advance(12)
        self.assertTrue(bucket.try_acquire())
        # Still empty afterwards.
        self.assertFalse(bucket.try_acquire())


if __name__ == "__main__":
    unittest.main()
