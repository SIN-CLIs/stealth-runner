"""
test_learn_status.py
=====================

SR-104 #104 — Tests fuer den read-only inbox dashboard:

  - TestSummarizeInbox    pure-function aggregation (10 tests)
  - TestFilters           pure-function predicate (4 tests)
  - TestFormatters        human + JSON output shapes (3 tests)
  - TestCmdStatus         integration via main() entry point (6 tests)
  - TestReadOnlyAudit     CLI never opens files with "w"/"a" (1 test)

Total: 24 tests.
"""

from __future__ import annotations

import io
import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
PARENT = os.path.dirname(HERE)
if PARENT not in sys.path:
    sys.path.insert(0, PARENT)

from survey.learn import (  # noqa: E402
    StatusFilters,
    format_human_report,
    passes_filters,
    report_to_json,
    summarize_inbox,
)
from survey.learn import cli as cli_mod  # noqa: E402


def _rec(**overrides) -> dict:
    base = {
        "role": "textbox",
        "normalized_label": "telefonnummer",
        "count": 3,
        "sample_labels": ["Telefonnummer"],
        "suggested_family": "phone",
        "confidence": 0.5,
        "source": "substring",
        "status": "open",
        "first_seen": "2026-05-01T12:00:00+00:00",
    }
    base.update(overrides)
    return base


# ────────────────────────────────────────────────────────────────────────────
# TestSummarizeInbox
# ────────────────────────────────────────────────────────────────────────────


class TestSummarizeInbox(unittest.TestCase):
    NOW = datetime(2026, 5, 12, 0, 0, 0, tzinfo=timezone.utc)

    def test_empty_input_yields_zero_counts(self):
        r = summarize_inbox([], now=self.NOW)
        self.assertEqual(r.total_records, 0)
        self.assertEqual(list(r.by_status), [])
        self.assertIsNone(r.oldest_open_iso)
        self.assertFalse(r.has_open())

    def test_mixed_status_counted_correctly(self):
        recs = [
            _rec(normalized_label="a", status="open"),
            _rec(normalized_label="b", status="accepted"),
            _rec(normalized_label="c", status="rejected"),
            _rec(normalized_label="d", status="open"),
        ]
        r = summarize_inbox(recs, now=self.NOW)
        self.assertEqual(r.total_records, 4)
        self.assertEqual(r.by_status["open"], 2)
        self.assertEqual(r.by_status["accepted"], 1)
        self.assertEqual(r.by_status["rejected"], 1)
        self.assertTrue(r.has_open())

    def test_missing_status_treated_as_open(self):
        rec = _rec()
        del rec["status"]
        r = summarize_inbox([rec], now=self.NOW)
        self.assertEqual(r.by_status["open"], 1)

    def test_missing_source_treated_as_substring(self):
        rec = _rec()
        del rec["source"]
        r = summarize_inbox([rec], now=self.NOW)
        self.assertEqual(r.by_source_open["substring"], 1)
        self.assertEqual(r.by_source_open.get("llm", 0), 0)

    def test_source_breakdown_only_for_open_records(self):
        recs = [
            _rec(normalized_label="a", source="llm", status="open"),
            _rec(normalized_label="b", source="llm", status="accepted"),
            _rec(normalized_label="c", source="substring", status="open"),
        ]
        r = summarize_inbox(recs, now=self.NOW)
        # by_source_open ignores accepted (only open contributes)
        self.assertEqual(r.by_source_open["llm"], 1)
        self.assertEqual(r.by_source_open["substring"], 1)
        self.assertEqual(sum(r.by_source_open.values()), 2)

    def test_no_family_records_get_new_bucket(self):
        recs = [
            _rec(normalized_label="a", suggested_family=None),
            _rec(normalized_label="b", suggested_family=""),
            _rec(normalized_label="c", suggested_family="phone"),
        ]
        r = summarize_inbox(recs, now=self.NOW)
        self.assertEqual(r.families_open["<NEW>"], 2)
        self.assertEqual(r.families_open["phone"], 1)

    def test_labels_open_aggregates_count_field(self):
        """labels_open accumulates `count`, not +1 per record."""
        recs = [
            _rec(role="textbox", normalized_label="phone", count=5),
            _rec(role="textbox", normalized_label="phone", count=3),
            _rec(role="textbox", normalized_label="email", count=2),
        ]
        r = summarize_inbox(recs, now=self.NOW)
        self.assertEqual(r.labels_open[("textbox", "phone")], 8)
        self.assertEqual(r.labels_open[("textbox", "email")], 2)

    def test_oldest_open_iso_picks_smallest_first_seen(self):
        recs = [
            _rec(normalized_label="newest", first_seen="2026-05-10T00:00:00+00:00"),
            _rec(normalized_label="oldest", first_seen="2026-04-22T14:33:01+00:00"),
            _rec(normalized_label="middle", first_seen="2026-05-01T00:00:00+00:00"),
        ]
        r = summarize_inbox(recs, now=self.NOW)
        self.assertEqual(r.oldest_open_iso, "2026-04-22T14:33:01+00:00")
        self.assertEqual(r.oldest_open_age_days, 19)

    def test_oldest_ignores_non_open_records(self):
        recs = [
            _rec(
                normalized_label="ancient_accepted",
                status="accepted",
                first_seen="2026-01-01T00:00:00+00:00",
            ),
            _rec(
                normalized_label="recent_open",
                status="open",
                first_seen="2026-05-10T00:00:00+00:00",
            ),
        ]
        r = summarize_inbox(recs, now=self.NOW)
        # ancient_accepted ist nicht open -> nicht beruecksichtigt
        self.assertEqual(r.oldest_open_iso, "2026-05-10T00:00:00+00:00")

    def test_oldest_handles_missing_timestamps(self):
        rec = _rec()
        del rec["first_seen"]
        r = summarize_inbox([rec], now=self.NOW)
        self.assertIsNone(r.oldest_open_iso)
        self.assertIsNone(r.oldest_open_age_days)


# ────────────────────────────────────────────────────────────────────────────
# TestFilters
# ────────────────────────────────────────────────────────────────────────────


class TestFilters(unittest.TestCase):
    def test_filter_source_llm_excludes_substring(self):
        rec = _rec(source="substring")
        self.assertFalse(passes_filters(rec, StatusFilters(source="llm")))
        self.assertTrue(passes_filters(rec, StatusFilters(source="substring")))
        self.assertTrue(passes_filters(rec, StatusFilters(source="all")))

    def test_filter_status_open_excludes_others(self):
        rec = _rec(status="accepted")
        self.assertFalse(passes_filters(rec, StatusFilters(status="open")))
        self.assertTrue(passes_filters(rec, StatusFilters(status="accepted")))

    def test_combined_filters_and_compose(self):
        rec = _rec(source="llm", status="open")
        filters = StatusFilters(source="llm", status="open")
        self.assertTrue(passes_filters(rec, filters))
        # mismatch on either field -> False
        self.assertFalse(passes_filters(rec, StatusFilters(source="substring", status="open")))
        self.assertFalse(passes_filters(rec, StatusFilters(source="llm", status="accepted")))

    def test_summarize_inbox_respects_filters(self):
        recs = [
            _rec(normalized_label="a", source="llm", status="open"),
            _rec(normalized_label="b", source="substring", status="open"),
            _rec(normalized_label="c", source="llm", status="accepted"),
        ]
        # Filter to llm-only
        r = summarize_inbox(recs, filters=StatusFilters(source="llm"))
        self.assertEqual(r.total_records, 2)
        self.assertEqual(r.by_status["open"], 1)
        self.assertEqual(r.by_status["accepted"], 1)


# ────────────────────────────────────────────────────────────────────────────
# TestFormatters
# ────────────────────────────────────────────────────────────────────────────


class TestFormatters(unittest.TestCase):
    def test_human_report_omits_empty_sections(self):
        report = summarize_inbox([])
        s = format_human_report(report)
        self.assertIn("0 record", s)
        # No 'By status' / 'By source' headers for empty inbox
        self.assertNotIn("By status:", s)
        self.assertNotIn("By source", s)

    def test_human_report_renders_all_sections_with_data(self):
        recs = [
            _rec(normalized_label="phone-de", suggested_family="phone", source="llm", count=4),
            _rec(
                normalized_label="phone-en", suggested_family="phone", source="substring", count=2
            ),
            _rec(
                normalized_label="other",
                suggested_family=None,
                source="substring",
                count=1,
                status="accepted",
            ),
        ]
        report = summarize_inbox(recs, files_scanned=1)
        s = format_human_report(report)
        self.assertIn("By status:", s)
        self.assertIn("By source (open records only):", s)
        self.assertIn("Top families (open records):", s)
        self.assertIn("Top labels", s)
        self.assertIn("phone", s)

    def test_json_report_is_serializable_and_complete(self):
        recs = [_rec()]
        report = summarize_inbox(recs)
        j = report_to_json(report, top=5)
        # Round-trip through json module
        out = json.dumps(j)
        parsed = json.loads(out)
        self.assertIn("total_records", parsed)
        self.assertIn("by_status", parsed)
        self.assertIn("top_families_open", parsed)
        self.assertIn("top_labels_open", parsed)
        # top-N truncation applied
        self.assertLessEqual(len(parsed["top_families_open"]), 5)


# ────────────────────────────────────────────────────────────────────────────
# TestCmdStatus (integration)
# ────────────────────────────────────────────────────────────────────────────


class _StatusFixture:
    """Stages a logs/ dir with one or more pattern-suggestions-*.jsonl."""

    def __init__(self, file_map: dict):
        self.td = tempfile.mkdtemp(prefix="status-")
        self.logs = os.path.join(self.td, "logs")
        os.makedirs(self.logs)
        for fname, recs in file_map.items():
            path = os.path.join(self.logs, fname)
            with open(path, "w") as f:
                for r in recs:
                    f.write(json.dumps(r) + "\n")

    def cleanup(self):
        import shutil

        shutil.rmtree(self.td, ignore_errors=True)

    def file(self, name: str) -> str:
        return os.path.join(self.logs, name)


def _run_status(fx, *args):
    buf_out = io.StringIO()
    buf_err = io.StringIO()
    with mock.patch.object(sys, "stdout", buf_out), mock.patch.object(sys, "stderr", buf_err):
        rc = cli_mod.main(
            [
                "status",
                "--logs",
                fx.logs,
                *args,
            ]
        )
    return rc, buf_out.getvalue(), buf_err.getvalue()


class TestCmdStatus(unittest.TestCase):
    def test_multi_file_scan_finds_all_pattern_suggestions(self):
        fx = _StatusFixture(
            {
                "pattern-suggestions-20260501.jsonl": [_rec(normalized_label="a")],
                "pattern-suggestions-20260502.jsonl": [_rec(normalized_label="b")],
                # accepted/rejected files should be ignored
                "pattern-suggestions-accepted.jsonl": [
                    _rec(normalized_label="z", status="accepted")
                ],
            }
        )
        try:
            rc, out, _ = _run_status(fx)
            self.assertEqual(rc, 0)
            self.assertIn("2 file(s)", out)
            self.assertIn("2 record(s)", out)
        finally:
            fx.cleanup()

    def test_single_input_overrides_multi_scan(self):
        fx = _StatusFixture(
            {
                "pattern-suggestions-20260501.jsonl": [_rec(normalized_label="a")],
                "pattern-suggestions-20260502.jsonl": [_rec(normalized_label="b")],
            }
        )
        try:
            single = fx.file("pattern-suggestions-20260501.jsonl")
            rc, out, _ = _run_status(fx, "--input", single)
            self.assertEqual(rc, 0)
            self.assertIn("1 file(s)", out)
            self.assertIn("1 record(s)", out)
        finally:
            fx.cleanup()

    def test_json_output_is_parseable(self):
        fx = _StatusFixture(
            {
                "pattern-suggestions-20260501.jsonl": [
                    _rec(normalized_label="a", source="llm"),
                    _rec(normalized_label="b", source="substring"),
                ],
            }
        )
        try:
            rc, out, _ = _run_status(fx, "--json")
            self.assertEqual(rc, 0)
            parsed = json.loads(out)
            self.assertEqual(parsed["total_records"], 2)
            self.assertEqual(parsed["by_status"]["open"], 2)
        finally:
            fx.cleanup()

    def test_require_empty_exit_1_with_open_records(self):
        fx = _StatusFixture(
            {
                "pattern-suggestions-20260501.jsonl": [_rec(status="open")],
            }
        )
        try:
            rc, _, err = _run_status(fx, "--require-empty")
            self.assertEqual(rc, 1)
            self.assertIn("--require-empty", err)
            self.assertIn("open record", err)
        finally:
            fx.cleanup()

    def test_require_empty_exit_0_when_all_resolved(self):
        fx = _StatusFixture(
            {
                "pattern-suggestions-20260501.jsonl": [
                    _rec(status="accepted"),
                    _rec(normalized_label="b", status="rejected"),
                ],
            }
        )
        try:
            rc, _, _ = _run_status(fx, "--require-empty")
            self.assertEqual(rc, 0)
        finally:
            fx.cleanup()

    def test_require_empty_exit_0_after_filter_excludes_open(self):
        """Pattern: filter on source=llm; only substring records are open."""
        fx = _StatusFixture(
            {
                "pattern-suggestions-20260501.jsonl": [
                    _rec(normalized_label="a", source="substring", status="open"),
                    _rec(normalized_label="b", source="llm", status="accepted"),
                ],
            }
        )
        try:
            rc, _, _ = _run_status(fx, "--require-empty", "--filter-source", "llm")
            # After filter only the llm-accepted record remains -> no open
            self.assertEqual(rc, 0)
        finally:
            fx.cleanup()

    def test_no_input_files_returns_zero_without_require_empty(self):
        fx = _StatusFixture({})
        try:
            rc, out, _ = _run_status(fx)
            self.assertEqual(rc, 0)
            self.assertIn("no pattern-suggestions", out)
        finally:
            fx.cleanup()

    def test_no_input_files_returns_one_with_require_empty(self):
        """Edge: empty logs dir + --require-empty.

        Interpretation: keine Inbox da -> bilanziell ist nichts 'open'.
        Aktuell returnt code 1 (siehe cmd_status). Wir dokumentieren das
        bewusst: --require-empty erwartet eine zu inspizierende Inbox."""
        fx = _StatusFixture({})
        try:
            rc, _, _ = _run_status(fx, "--require-empty")
            self.assertEqual(rc, 1)
        finally:
            fx.cleanup()


# ────────────────────────────────────────────────────────────────────────────
# TestReadOnlyAudit
# ────────────────────────────────────────────────────────────────────────────


class TestReadOnlyAudit(unittest.TestCase):
    """status command MUST NOT write any files."""

    def test_status_never_opens_files_for_writing(self):
        fx = _StatusFixture(
            {
                "pattern-suggestions-20260501.jsonl": [_rec()],
            }
        )
        try:
            real_open = open
            write_modes = []

            def tracking_open(file, mode="r", *args, **kwargs):
                if any(m in mode for m in ("w", "a", "x", "+")):
                    write_modes.append((str(file), mode))
                return real_open(file, mode, *args, **kwargs)

            with mock.patch("builtins.open", side_effect=tracking_open):
                rc, _, _ = _run_status(fx)

            self.assertEqual(rc, 0)
            # No writes triggered anywhere in cmd_status
            self.assertEqual(write_modes, [], f"status leaked write opens: {write_modes}")
            # And no derived files were created in the logs dir
            self.assertFalse(os.path.exists(fx.file("pattern-suggestions-accepted.jsonl")))
            self.assertFalse(os.path.exists(fx.file("pattern-suggestions-rejected.jsonl")))
        finally:
            fx.cleanup()


if __name__ == "__main__":
    unittest.main(verbosity=2)
