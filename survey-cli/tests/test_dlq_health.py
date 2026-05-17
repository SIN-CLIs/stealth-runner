"""Tests for survey.observability.dlq_health (SR-248).

Pure-function tests over synthetic DLQRecord lists. No filesystem I/O.
unittest-only.
"""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from survey.observability.dlq_health import (
    DlqHealth,
    PendingAgeStats,
    aggregate_health,
)
from survey.reliability.dlq import DLQRecord


# ── Fixtures ────────────────────────────────────────────────────────────────


_NOW = datetime(2026, 5, 17, 12, 0, 0, tzinfo=timezone.utc)


def _record(
    *,
    status: str = "pending",
    error_class: str = "SelectorTimeout",
    provider: str = "pollfish",
    attempt_count: int = 2,
    age_seconds: int = 0,
    rid: str = "dlq-test",
) -> DLQRecord:
    """Build a synthetic DLQRecord whose timestamp is now - age_seconds."""
    ts_dt = _NOW - timedelta(seconds=age_seconds)
    # dlq.py emits isoformat() + "Z" — replicate that wire shape.
    ts_str = ts_dt.replace(tzinfo=None).isoformat() + "Z"
    return DLQRecord(
        id=rid,
        ts=ts_str,
        survey_id="abc",
        persona_id="p1",
        provider=provider,
        url="https://example.com/survey/abc",
        error_class=error_class,
        error_message="boom",
        attempt_count=attempt_count,
        context={},
        status=status,
    )


# ── Tests ───────────────────────────────────────────────────────────────────


class EmptyAndSingleTests(unittest.TestCase):
    def test_empty_input_yields_zero_filled_health(self) -> None:
        h = aggregate_health([], now=_NOW)
        self.assertEqual(h.total, 0)
        self.assertEqual(h.by_status, {})
        self.assertEqual(h.by_error_class, {})
        self.assertEqual(h.by_provider, {})
        self.assertEqual(h.pending.count, 0)
        self.assertEqual(h.pending.p50_age_seconds, 0)
        self.assertEqual(h.pending.p95_age_seconds, 0)
        self.assertEqual(h.pending.older_than_24h, 0)
        self.assertTrue(h.is_healthy())
        self.assertEqual(h.alarm_reasons, [])

    def test_single_pending_record_quantiles(self) -> None:
        h = aggregate_health([_record(age_seconds=120)], now=_NOW)
        self.assertEqual(h.pending.count, 1)
        self.assertEqual(h.pending.p50_age_seconds, 120)
        self.assertEqual(h.pending.p95_age_seconds, 120)
        self.assertEqual(h.pending.newest_age_seconds, 120)
        self.assertEqual(h.pending.oldest_age_seconds, 120)


class CountsTests(unittest.TestCase):
    def test_by_status_counts(self) -> None:
        records = [
            _record(status="pending"),
            _record(status="pending"),
            _record(status="replayed"),
            _record(status="discarded"),
        ]
        h = aggregate_health(records, now=_NOW)
        self.assertEqual(h.by_status, {"pending": 2, "replayed": 1, "discarded": 1})
        self.assertEqual(h.total, 4)

    def test_by_error_class_counts(self) -> None:
        records = [
            _record(error_class="SelectorTimeout"),
            _record(error_class="SelectorTimeout"),
            _record(error_class="BalanceCheckError"),
        ]
        h = aggregate_health(records, now=_NOW)
        self.assertEqual(
            h.by_error_class,
            {"SelectorTimeout": 2, "BalanceCheckError": 1},
        )

    def test_by_provider_counts(self) -> None:
        records = [
            _record(provider="pollfish"),
            _record(provider="cint"),
            _record(provider="pollfish"),
        ]
        h = aggregate_health(records, now=_NOW)
        self.assertEqual(h.by_provider, {"pollfish": 2, "cint": 1})

    def test_attempt_buckets_grouping(self) -> None:
        records = [
            _record(attempt_count=1),
            _record(attempt_count=2),
            _record(attempt_count=2),
            _record(attempt_count=3),
            _record(attempt_count=4),
            _record(attempt_count=5),
            _record(attempt_count=42),
        ]
        h = aggregate_health(records, now=_NOW)
        self.assertEqual(
            h.attempt_buckets,
            {"1": 1, "2": 2, "3": 1, "4+": 3},
        )

    def test_unknown_provider_and_error_class_get_underscore_unknown(self) -> None:
        # Provider/error_class can be empty after partial parse failures.
        records = [_record(provider="", error_class="")]
        h = aggregate_health(records, now=_NOW)
        self.assertIn("_unknown", h.by_provider)
        self.assertIn("_unknown", h.by_error_class)


class PendingOnlyAgeTests(unittest.TestCase):
    def test_replayed_and_discarded_excluded_from_age_stats(self) -> None:
        records = [
            _record(status="pending", age_seconds=100),
            _record(status="replayed", age_seconds=99999),
            _record(status="discarded", age_seconds=88888),
        ]
        h = aggregate_health(records, now=_NOW)
        self.assertEqual(h.pending.count, 1)
        self.assertEqual(h.pending.oldest_age_seconds, 100)
        self.assertEqual(h.pending.newest_age_seconds, 100)

    def test_p50_p95_with_uniform_distribution(self) -> None:
        # Ages: 10, 20, 30, ..., 100  (10 records)
        records = [
            _record(age_seconds=age) for age in (10, 20, 30, 40, 50, 60, 70, 80, 90, 100)
        ]
        h = aggregate_health(records, now=_NOW)
        # Linear-interp quantile on 10 sorted values:
        #   p50 → pos 4.5 → midway between 50 and 60 → 55
        #   p95 → pos 8.55 → 90 + 0.55*(100-90) ≈ 95.5
        # The exact integer result of the p95 path depends on float
        # arithmetic in `0.95*(10-1) - 8` — accept either 95 or 96.
        self.assertEqual(h.pending.p50_age_seconds, 55)
        self.assertIn(h.pending.p95_age_seconds, (95, 96))

    def test_older_than_24h_count(self) -> None:
        day = 24 * 3600
        records = [
            _record(age_seconds=100),
            _record(age_seconds=day - 5),  # below threshold
            _record(age_seconds=day + 5),  # above threshold
            _record(age_seconds=3 * day),  # above threshold
        ]
        h = aggregate_health(records, now=_NOW)
        self.assertEqual(h.pending.older_than_24h, 2)
        self.assertEqual(h.pending.count, 4)

    def test_clock_skew_negative_age_clamped_to_zero(self) -> None:
        """If a record is 'in the future', age clamps to 0."""
        future = _record(age_seconds=-3600, rid="future")
        h = aggregate_health([future], now=_NOW)
        self.assertEqual(h.pending.newest_age_seconds, 0)
        self.assertEqual(h.pending.oldest_age_seconds, 0)

    def test_unparseable_timestamp_does_not_crash(self) -> None:
        rec = _record()
        # Mutate ts to something junk.
        rec.ts = "not-a-timestamp"
        h = aggregate_health([rec], now=_NOW)
        self.assertEqual(h.pending.count, 1)
        self.assertEqual(h.pending.oldest_age_seconds, 0)


class AlarmReasonTests(unittest.TestCase):
    def test_pending_backlog_alarm_above_threshold(self) -> None:
        records = [_record(age_seconds=10) for _ in range(25)]
        h = aggregate_health(records, now=_NOW, pending_threshold=20)
        self.assertFalse(h.is_healthy())
        joined = " ".join(h.alarm_reasons)
        self.assertIn("pending_backlog", joined)
        self.assertIn("25", joined)

    def test_pending_backlog_no_alarm_at_or_below_threshold(self) -> None:
        records = [_record(age_seconds=10) for _ in range(20)]
        h = aggregate_health(records, now=_NOW, pending_threshold=20)
        self.assertTrue(h.is_healthy())

    def test_oldest_pending_alarm_above_threshold_hours(self) -> None:
        records = [
            _record(age_seconds=49 * 3600, rid="old"),
            _record(age_seconds=10, rid="fresh"),
        ]
        h = aggregate_health(records, now=_NOW, oldest_pending_hours=48)
        self.assertFalse(h.is_healthy())
        joined = " ".join(h.alarm_reasons)
        self.assertIn("oldest_pending", joined)

    def test_oldest_pending_no_alarm_under_threshold(self) -> None:
        records = [_record(age_seconds=47 * 3600)]
        h = aggregate_health(records, now=_NOW, oldest_pending_hours=48)
        self.assertTrue(h.is_healthy())

    def test_both_alarms_fire_simultaneously(self) -> None:
        records = [_record(age_seconds=99 * 3600) for _ in range(30)]
        h = aggregate_health(
            records,
            now=_NOW,
            pending_threshold=10,
            oldest_pending_hours=24,
        )
        self.assertFalse(h.is_healthy())
        self.assertEqual(len(h.alarm_reasons), 2)

    def test_replayed_records_do_not_trigger_pending_backlog(self) -> None:
        records = [_record(status="replayed", age_seconds=10) for _ in range(50)]
        h = aggregate_health(records, now=_NOW, pending_threshold=10)
        self.assertTrue(h.is_healthy())


class SerializationTests(unittest.TestCase):
    def test_to_dict_is_json_safe(self) -> None:
        import json

        records = [
            _record(status="pending", age_seconds=100),
            _record(status="replayed", age_seconds=200),
        ]
        h = aggregate_health(records, now=_NOW)
        d = h.to_dict()
        # Round-trip through JSON to assert no exotic types.
        roundtrip = json.loads(json.dumps(d))
        self.assertEqual(roundtrip["total"], 2)
        self.assertEqual(roundtrip["pending"]["count"], 1)
        self.assertIn("is_healthy", roundtrip)
        self.assertIsInstance(roundtrip["alarm_reasons"], list)

    def test_to_dict_includes_is_healthy(self) -> None:
        h = aggregate_health([], now=_NOW)
        self.assertTrue(h.to_dict()["is_healthy"])

        records = [_record(age_seconds=10) for _ in range(100)]
        h2 = aggregate_health(records, now=_NOW, pending_threshold=10)
        self.assertFalse(h2.to_dict()["is_healthy"])


class TimezoneTests(unittest.TestCase):
    def test_naive_now_is_treated_as_utc(self) -> None:
        naive_now = datetime(2026, 5, 17, 12, 0, 0)  # no tzinfo
        h = aggregate_health(
            [_record(age_seconds=100)],
            now=naive_now,
        )
        self.assertEqual(h.pending.oldest_age_seconds, 100)

    def test_utcnow_isoformat_with_z_suffix_parses(self) -> None:
        """Confirm we tolerate the legacy 'Z' suffix written by dlq.py."""
        rec = _record(age_seconds=300)
        # Already has trailing 'Z' from helper; this just asserts parser
        # didn't choke (would manifest as oldest_age_seconds=0).
        h = aggregate_health([rec], now=_NOW)
        self.assertEqual(h.pending.oldest_age_seconds, 300)


if __name__ == "__main__":
    unittest.main()
