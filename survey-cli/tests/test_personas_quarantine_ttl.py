"""Tests for SR-247 — TTL extension of personas_quarantine.

Covers:
  • ttl_seconds field is persisted + roundtripped (schema-2)
  • is_quarantined() returns False for TTL-expired entries (no write)
  • list_active() filters out TTL-expired entries (no write)
  • sweep_expired() persists release records with auto reason
  • sweep_expired() ignores no-TTL, not-yet-expired, already-released
  • backward compat: schema-1 files without ttl_seconds load with None
  • quarantine() validates ttl_seconds > 0
  • re-quarantine of an active entry updates ttl_seconds and preserves
    quarantined_at
  • release() preserves ttl_seconds in the audit record

unittest-only — no pytest dependency.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

from survey.reliability.personas_quarantine import (
    PersonaNotQuarantined,
    QuarantineEntry,
    is_quarantined,
    list_active,
    quarantine,
    release,
    sweep_expired,
)
from survey.reliability.personas_quarantine import (
    get as quarantine_get,
)


class TtlPersistenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_quarantine_persists_ttl_seconds(self) -> None:
        entry = quarantine(
            "p1",
            "drift",
            ttl_seconds=3600,
            store_root=self.root,
            now=1000,
        )
        self.assertEqual(entry.ttl_seconds, 3600)
        self.assertEqual(entry.expires_at(), 1000 + 3600)
        # Roundtrip on disk.
        loaded = quarantine_get("p1", store_root=self.root)
        self.assertEqual(loaded.ttl_seconds, 3600)
        self.assertEqual(loaded.schema_version, 2)

    def test_quarantine_without_ttl_keeps_legacy_behavior(self) -> None:
        entry = quarantine("p2", "drift", store_root=self.root, now=1000)
        self.assertIsNone(entry.ttl_seconds)
        self.assertIsNone(entry.expires_at())
        # Without TTL, is_active_at(any) should mirror is_active().
        self.assertTrue(entry.is_active())
        self.assertTrue(entry.is_active_at(now=999_999_999))

    def test_quarantine_rejects_zero_or_negative_ttl(self) -> None:
        with self.assertRaises(ValueError):
            quarantine("p3", "drift", ttl_seconds=0, store_root=self.root)
        with self.assertRaises(ValueError):
            quarantine("p3", "drift", ttl_seconds=-5, store_root=self.root)

    def test_requarantine_updates_ttl_but_preserves_quarantined_at(self) -> None:
        first = quarantine(
            "p4", "drift", ttl_seconds=10, store_root=self.root, now=1000
        )
        self.assertEqual(first.ttl_seconds, 10)
        self.assertEqual(first.quarantined_at, 1000)

        second = quarantine(
            "p4",
            "drift again",
            ttl_seconds=999,
            store_root=self.root,
            now=2000,
        )
        # quarantined_at preserved (audit), ttl updated to new value.
        self.assertEqual(second.quarantined_at, 1000)
        self.assertEqual(second.ttl_seconds, 999)
        self.assertEqual(second.reason, "drift again")


class TtlReadPathTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_is_quarantined_false_after_ttl_expiry(self) -> None:
        quarantine("p1", "drift", ttl_seconds=60, store_root=self.root, now=1000)
        # Within TTL → still quarantined.
        self.assertTrue(is_quarantined("p1", store_root=self.root, now=1059))
        # At exact expiry boundary → no longer quarantined.
        self.assertFalse(is_quarantined("p1", store_root=self.root, now=1060))
        # Way past expiry → still no.
        self.assertFalse(is_quarantined("p1", store_root=self.root, now=99_999_999))

    def test_is_quarantined_does_not_mutate_disk_on_expiry(self) -> None:
        """Read-path call must NEVER write."""
        quarantine("p1", "drift", ttl_seconds=10, store_root=self.root, now=1000)
        path = self.root / "p1.json"
        original_mtime = path.stat().st_mtime_ns

        # Trigger many expired reads.
        for _ in range(10):
            self.assertFalse(is_quarantined("p1", store_root=self.root, now=2000))

        # File mtime must be unchanged.
        self.assertEqual(path.stat().st_mtime_ns, original_mtime)
        # Released_at must still be None on disk (lazy expiry).
        on_disk = json.loads(path.read_text("utf-8"))
        self.assertIsNone(on_disk["released_at"])

    def test_list_active_filters_ttl_expired(self) -> None:
        quarantine("p1", "drift", ttl_seconds=60, store_root=self.root, now=1000)
        quarantine("p2", "drift", ttl_seconds=120, store_root=self.root, now=1000)
        quarantine("p3", "drift", store_root=self.root, now=1000)  # no TTL

        # At t=1100: p1 expired (1000+60=1060), p2 active (1000+120=1120), p3 active.
        active_at_1100 = list_active(store_root=self.root, now=1100)
        ids = {e.persona_id for e in active_at_1100}
        self.assertEqual(ids, {"p2", "p3"})

        # At t=2000: only p3 (no TTL) remains.
        active_at_2000 = list_active(store_root=self.root, now=2000)
        ids = {e.persona_id for e in active_at_2000}
        self.assertEqual(ids, {"p3"})


class SweepExpiredTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_sweep_expired_writes_release_record(self) -> None:
        quarantine("p1", "drift", ttl_seconds=60, store_root=self.root, now=1000)

        swept = sweep_expired(store_root=self.root, now=2000)
        self.assertEqual(len(swept), 1)
        self.assertEqual(swept[0].persona_id, "p1")
        self.assertEqual(swept[0].released_at, 2000)
        self.assertEqual(swept[0].release_reason, "ttl_expired:auto")
        self.assertEqual(swept[0].ttl_seconds, 60)  # preserved for audit

        # On-disk state matches.
        on_disk = quarantine_get("p1", store_root=self.root)
        self.assertEqual(on_disk.released_at, 2000)
        self.assertEqual(on_disk.release_reason, "ttl_expired:auto")

        # is_quarantined now returns False even at "now=1000" (released_at wins).
        self.assertFalse(is_quarantined("p1", store_root=self.root, now=1000))

    def test_sweep_expired_skips_no_ttl_entries(self) -> None:
        quarantine("p1", "drift", store_root=self.root, now=1000)
        swept = sweep_expired(store_root=self.root, now=99_999_999)
        self.assertEqual(swept, [])
        self.assertTrue(is_quarantined("p1", store_root=self.root, now=99_999_999))

    def test_sweep_expired_skips_not_yet_expired(self) -> None:
        quarantine("p1", "drift", ttl_seconds=600, store_root=self.root, now=1000)
        swept = sweep_expired(store_root=self.root, now=1100)
        self.assertEqual(swept, [])

    def test_sweep_expired_skips_already_released(self) -> None:
        quarantine("p1", "drift", ttl_seconds=60, store_root=self.root, now=1000)
        release("p1", "manual review", store_root=self.root, now=1500)

        swept = sweep_expired(store_root=self.root, now=99_999_999)
        self.assertEqual(swept, [])

        # The manual release must NOT be overwritten.
        on_disk = quarantine_get("p1", store_root=self.root)
        self.assertEqual(on_disk.release_reason, "manual review")
        self.assertEqual(on_disk.released_at, 1500)

    def test_sweep_expired_uses_custom_reason(self) -> None:
        quarantine("p1", "drift", ttl_seconds=60, store_root=self.root, now=1000)
        swept = sweep_expired(
            store_root=self.root,
            now=2000,
            release_reason="ttl_expired:nightly_cron",
        )
        self.assertEqual(swept[0].release_reason, "ttl_expired:nightly_cron")

    def test_sweep_expired_idempotent(self) -> None:
        quarantine("p1", "drift", ttl_seconds=60, store_root=self.root, now=1000)
        first = sweep_expired(store_root=self.root, now=2000)
        second = sweep_expired(store_root=self.root, now=2000)
        self.assertEqual(len(first), 1)
        self.assertEqual(second, [])  # second sweep finds nothing to do

    def test_sweep_expired_handles_multiple_entries(self) -> None:
        quarantine("p1", "drift", ttl_seconds=60, store_root=self.root, now=1000)
        quarantine("p2", "drift", ttl_seconds=120, store_root=self.root, now=1000)
        quarantine("p3", "drift", store_root=self.root, now=1000)  # no TTL

        # At t=1100, only p1 is expired.
        swept = sweep_expired(store_root=self.root, now=1100)
        self.assertEqual(len(swept), 1)
        self.assertEqual(swept[0].persona_id, "p1")

        # p2 and p3 still active.
        self.assertTrue(is_quarantined("p2", store_root=self.root, now=1100))
        self.assertTrue(is_quarantined("p3", store_root=self.root, now=1100))


class BackwardCompatTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_schema1_file_without_ttl_loads_as_no_ttl(self) -> None:
        """A pre-SR-247 (schema 1) file must load with ttl_seconds=None."""
        legacy_payload: dict[str, Any] = {
            "persona_id": "old-persona",
            "reason": "drift",
            "judge_scores": {"compliance": 0.4},
            "quarantined_at": 1000,
            "released_at": None,
            "release_reason": "",
            "schema_version": 1,
        }
        path = self.root / "old-persona.json"
        path.write_text(json.dumps(legacy_payload), encoding="utf-8")

        loaded = quarantine_get("old-persona", store_root=self.root)
        self.assertIsNone(loaded.ttl_seconds)
        self.assertIsNone(loaded.expires_at())
        self.assertEqual(loaded.schema_version, 1)
        # Legacy entries are eternally active (until manually released).
        self.assertTrue(is_quarantined("old-persona", store_root=self.root, now=99_999_999))

    def test_schema1_file_survives_sweep(self) -> None:
        """sweep_expired must NOT release legacy entries (no TTL = no auto-release)."""
        legacy_payload: dict[str, Any] = {
            "persona_id": "old-persona",
            "reason": "drift",
            "judge_scores": {},
            "quarantined_at": 1000,
            "released_at": None,
            "release_reason": "",
            "schema_version": 1,
        }
        path = self.root / "old-persona.json"
        path.write_text(json.dumps(legacy_payload), encoding="utf-8")

        swept = sweep_expired(store_root=self.root, now=99_999_999)
        self.assertEqual(swept, [])

    def test_corrupt_ttl_value_falls_back_to_none(self) -> None:
        """A negative or zero ttl_seconds in a stale manifest is treated as None."""
        bad_payload: dict[str, Any] = {
            "persona_id": "weird",
            "reason": "drift",
            "judge_scores": {},
            "quarantined_at": 1000,
            "released_at": None,
            "release_reason": "",
            "ttl_seconds": -42,
            "schema_version": 2,
        }
        path = self.root / "weird.json"
        path.write_text(json.dumps(bad_payload), encoding="utf-8")

        loaded = quarantine_get("weird", store_root=self.root)
        self.assertIsNone(loaded.ttl_seconds)


class ReleasePreservesTtlTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_manual_release_keeps_ttl_for_audit(self) -> None:
        """release() must persist ttl_seconds so the audit record is complete."""
        quarantine("p1", "drift", ttl_seconds=60, store_root=self.root, now=1000)
        released = release("p1", "false positive", store_root=self.root, now=1100)
        self.assertEqual(released.ttl_seconds, 60)

        # On-disk roundtrip
        on_disk = quarantine_get("p1", store_root=self.root)
        self.assertEqual(on_disk.ttl_seconds, 60)
        self.assertEqual(on_disk.release_reason, "false positive")

    def test_release_raises_for_already_released(self) -> None:
        quarantine("p1", "drift", ttl_seconds=60, store_root=self.root, now=1000)
        sweep_expired(store_root=self.root, now=2000)
        with self.assertRaises(PersonaNotQuarantined):
            release("p1", "manual", store_root=self.root, now=3000)


if __name__ == "__main__":
    unittest.main()
