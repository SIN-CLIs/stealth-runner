"""SR-109 #109 — tests fuer ``survey.learn.audit`` + ``survey learn audit`` CLI.

Layout (mirror SR-104 #104 test_learn_status.py):
  - TestSummarizeAudit       - pure summarize_audit-Verhalten
  - TestNormalizers          - _normalize_* helper-Korrektheit
  - TestFilters              - passes_filters + combination
  - TestFormatters           - format_human_report + report_to_json
  - TestCmdAudit             - integration via cli_mod.main()
  - TestReadOnlyAudit        - command oeffnet keine Datei mit w/a/x/+

Audit-record-Schema (verifiziert apply.py:595-655):
  applied:               {decision, family, keyword, source, confidence,
                          model, prompt_hash, timestamp}
  rejected_by_gate:      {decision, reason, entry}
  rejected_by_reviewer:  {decision, entry}
  rejected_by_ast:       {decision, reason, entry}
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

# Ensure survey-cli/ is on sys.path so ``survey.learn`` imports work
_HERE = os.path.dirname(os.path.abspath(__file__))
_PKG_ROOT = os.path.normpath(os.path.join(_HERE, ".."))
if _PKG_ROOT not in sys.path:
    sys.path.insert(0, _PKG_ROOT)

from survey.learn import cli as cli_mod  # noqa: E402
from survey.learn.audit import (  # noqa: E402
    AuditFilters,
    AuditReport,
    _extract_timestamp,
    _normalize_decision,
    _normalize_family,
    _normalize_label,
    _normalize_source,
    format_human_report,
    passes_filters,
    report_to_json,
    summarize_audit,
)


# -- record factories --------------------------------------------------------


def _applied(
    *,
    family="phone",
    keyword="telefonnummer",
    source="substring",
    confidence=0.85,
    model=None,
    prompt_hash=None,
    timestamp="2026-05-10T12:00:00+00:00",
) -> dict:
    """Build an applied-record matching apply.py:audit_records.append."""
    return {
        "decision": "applied",
        "family": family,
        "keyword": keyword,
        "source": source,
        "confidence": confidence,
        "model": model,
        "prompt_hash": prompt_hash,
        "timestamp": timestamp,
    }


def _rejected(
    *,
    decision="rejected_by_gate",
    reason="confidence below gate",
    role="textbox",
    normalized_label="haushaltsgrosse",
    suggested_family="household_size",
    source="llm",
    first_seen="2026-05-09T08:00:00+00:00",
    extra_entry=None,
) -> dict:
    """Build a reject-record. entry mirrors apply.py:InboxEntry.__dict__."""
    entry = {
        "role": role,
        "normalized_label": normalized_label,
        "suggested_family": suggested_family,
        "source": source,
        "first_seen": first_seen,
    }
    if extra_entry:
        entry.update(extra_entry)
    rec = {"decision": decision, "entry": entry}
    if reason and decision != "rejected_by_reviewer":
        rec["reason"] = reason
    return rec


# -- pure-function tests -----------------------------------------------------


class TestSummarizeAudit(unittest.TestCase):
    def test_empty_input_zero_counts(self):
        report = summarize_audit([])
        self.assertEqual(report.total_records, 0)
        self.assertEqual(dict(report.by_decision), {})
        self.assertIsNone(report.first_applied_iso)
        self.assertIsNone(report.last_applied_iso)
        self.assertFalse(report.has_applied())

    def test_by_decision_counts_all_four_types(self):
        recs = [
            _applied(),
            _applied(),
            _rejected(decision="rejected_by_gate"),
            _rejected(decision="rejected_by_reviewer", reason=None),
            _rejected(decision="rejected_by_ast", reason="duplicate keyword"),
        ]
        report = summarize_audit(recs, files_scanned=1)
        self.assertEqual(report.total_records, 5)
        self.assertEqual(report.by_decision["applied"], 2)
        self.assertEqual(report.by_decision["rejected_by_gate"], 1)
        self.assertEqual(report.by_decision["rejected_by_reviewer"], 1)
        self.assertEqual(report.by_decision["rejected_by_ast"], 1)
        self.assertTrue(report.has_applied())

    def test_by_source_applied_excludes_rejects(self):
        recs = [
            _applied(source="substring"),
            _applied(source="llm"),
            _applied(source="llm"),
            _rejected(source="llm"),  # rejected with source=llm in entry
        ]
        report = summarize_audit(recs)
        self.assertEqual(report.by_source_applied["substring"], 1)
        self.assertEqual(report.by_source_applied["llm"], 2)
        # rejects must not contribute to by_source_applied
        self.assertEqual(sum(report.by_source_applied.values()), 3)

    def test_families_applied_counts_only_applied(self):
        recs = [
            _applied(family="phone"),
            _applied(family="phone"),
            _applied(family="income"),
            _rejected(suggested_family="phone"),
        ]
        report = summarize_audit(recs)
        self.assertEqual(report.families_applied["phone"], 2)
        self.assertEqual(report.families_applied["income"], 1)
        self.assertNotIn("household_size", report.families_applied)

    def test_top_n_truncation_in_formatter_not_summarize(self):
        # 6 distinct families, top=2 should still leave 6 in Counter
        recs = [_applied(family=f"fam_{i}") for i in range(6)]
        report = summarize_audit(recs)
        self.assertEqual(len(report.families_applied), 6)
        # JSON output truncates
        js = report_to_json(report, top=2)
        self.assertEqual(len(js["top_families_applied"]), 2)

    def test_by_model_only_counts_applied_with_nonempty_model(self):
        recs = [
            _applied(model="openai/gpt-5-mini"),
            _applied(model="openai/gpt-5-mini"),
            _applied(model="anthropic/claude-opus-4.6"),
            _applied(model=None),  # substring records have model=None
            _applied(model=""),  # empty string is also no-model
        ]
        report = summarize_audit(recs)
        self.assertEqual(report.by_model["openai/gpt-5-mini"], 2)
        self.assertEqual(report.by_model["anthropic/claude-opus-4.6"], 1)
        self.assertEqual(sum(report.by_model.values()), 3)

    def test_time_range_first_and_last_applied(self):
        recs = [
            _applied(timestamp="2026-05-01T08:00:00+00:00"),
            _applied(timestamp="2026-05-10T12:00:00+00:00"),
            _applied(timestamp="2026-05-05T15:30:00+00:00"),
        ]
        report = summarize_audit(recs)
        self.assertEqual(report.first_applied_iso, "2026-05-01T08:00:00+00:00")
        self.assertEqual(report.last_applied_iso, "2026-05-10T12:00:00+00:00")

    def test_files_scanned_passthrough(self):
        report = summarize_audit([], files_scanned=7)
        self.assertEqual(report.files_scanned, 7)


# -- Normalizers --------------------------------------------------------------


class TestNormalizers(unittest.TestCase):
    def test_normalize_decision_default_applied_when_missing(self):
        # Defensive default; apply.py always writes decision in practice
        self.assertEqual(_normalize_decision({}), "applied")
        self.assertEqual(_normalize_decision({"decision": "applied"}), "applied")
        self.assertEqual(_normalize_decision({"decision": "rejected_by_gate"}), "rejected_by_gate")

    def test_normalize_source_falls_back_to_entry_then_substring(self):
        # Top-level wins
        self.assertEqual(_normalize_source({"source": "llm"}), "llm")
        # Falls back to entry.source for rejects
        self.assertEqual(_normalize_source({"entry": {"source": "llm"}}), "llm")
        # Default substring when source is missing everywhere
        self.assertEqual(_normalize_source({}), "substring")
        self.assertEqual(_normalize_source({"entry": {}}), "substring")

    def test_normalize_family_falls_back_to_entry_then_none(self):
        # Top-level wins
        self.assertEqual(_normalize_family({"family": "phone"}), "phone")
        # Falls back to entry.suggested_family for rejects
        self.assertEqual(
            _normalize_family({"entry": {"suggested_family": "income"}}),
            "income",
        )
        # None when missing -- audit-specific behaviour (status.py uses
        # "<NEW>" but here we keep None to skip the bucket entirely)
        self.assertIsNone(_normalize_family({}))
        self.assertIsNone(_normalize_family({"entry": {}}))

    def test_normalize_label_applied_vs_rejected(self):
        # Applied: keyword direct, role=""
        self.assertEqual(
            _normalize_label({"keyword": "telefonnummer"}),
            ("", "telefonnummer"),
        )
        # Rejected: extract from entry
        rej = _rejected(role="textbox", normalized_label="hausgr")
        self.assertEqual(_normalize_label(rej), ("textbox", "hausgr"))
        # No label anywhere -> None
        self.assertIsNone(_normalize_label({"entry": {}}))

    def test_extract_timestamp_priority_chain(self):
        # 1) top-level timestamp wins
        rec = {
            "timestamp": "2026-05-10T12:00:00+00:00",
            "entry": {"first_seen": "2026-04-01T00:00:00+00:00"},
        }
        dt = _extract_timestamp(rec)
        self.assertEqual(dt, datetime(2026, 5, 10, 12, 0, tzinfo=timezone.utc))
        # 2) Falls back to entry.first_seen
        rec2 = {"entry": {"first_seen": "2026-04-01T00:00:00+00:00"}}
        dt2 = _extract_timestamp(rec2)
        self.assertEqual(dt2, datetime(2026, 4, 1, 0, 0, tzinfo=timezone.utc))
        # 3) Naive datetime gets utc-attached
        rec3 = {"timestamp": "2026-05-10T12:00:00"}
        dt3 = _extract_timestamp(rec3)
        self.assertIsNotNone(dt3)
        self.assertEqual(dt3.tzinfo, timezone.utc)
        # 4) Unparseable -> None
        rec4 = {"timestamp": "not-an-iso"}
        self.assertIsNone(_extract_timestamp(rec4))
        # 5) Missing entirely -> None
        self.assertIsNone(_extract_timestamp({}))


# -- Filters -----------------------------------------------------------------


class TestFilters(unittest.TestCase):
    def test_filter_decision_excludes_other_decisions(self):
        f = AuditFilters(decision="applied")
        self.assertTrue(passes_filters(_applied(), f))
        self.assertFalse(passes_filters(_rejected(), f))

    def test_filter_source_excludes_other_sources(self):
        f = AuditFilters(source="llm")
        self.assertFalse(passes_filters(_applied(source="substring"), f))
        self.assertTrue(passes_filters(_applied(source="llm"), f))
        # Reject with entry.source=llm -> included
        self.assertTrue(passes_filters(_rejected(source="llm"), f))

    def test_filter_family_excludes_other_families(self):
        f = AuditFilters(family="phone")
        self.assertTrue(passes_filters(_applied(family="phone"), f))
        self.assertFalse(passes_filters(_applied(family="income"), f))
        # Reject with entry.suggested_family=phone -> included
        self.assertTrue(passes_filters(_rejected(suggested_family="phone"), f))

    def test_filter_since_excludes_older_and_missing(self):
        f = AuditFilters(since=datetime(2026, 5, 5, tzinfo=timezone.utc))
        self.assertTrue(passes_filters(_applied(timestamp="2026-05-10T00:00:00+00:00"), f))
        self.assertFalse(passes_filters(_applied(timestamp="2026-05-01T00:00:00+00:00"), f))
        # Records with NO timestamp anywhere are excluded
        no_ts = {"decision": "applied", "family": "x", "keyword": "y", "source": "substring"}
        self.assertFalse(passes_filters(no_ts, f))

    def test_filters_compose_with_AND(self):
        f = AuditFilters(decision="applied", source="llm")
        self.assertTrue(passes_filters(_applied(source="llm"), f))
        self.assertFalse(passes_filters(_applied(source="substring"), f))
        self.assertFalse(passes_filters(_rejected(source="llm"), f))


# -- Formatters --------------------------------------------------------------


class TestFormatters(unittest.TestCase):
    def test_format_human_report_empty(self):
        out = format_human_report(AuditReport())
        # Header always present
        self.assertIn("audit summary", out)
        self.assertIn("0 file(s)", out)
        self.assertIn("0 record(s)", out)
        # No sections beyond the header for empty report
        self.assertNotIn("By decision", out)
        self.assertNotIn("By source", out)

    def test_format_human_report_full(self):
        recs = [
            _applied(family="phone", keyword="telefonnummer", source="substring"),
            _applied(
                family="phone", keyword="mobilnummer", source="llm", model="openai/gpt-5-mini"
            ),
            _rejected(decision="rejected_by_gate"),
        ]
        report = summarize_audit(recs, files_scanned=1)
        out = format_human_report(report, top=5)
        self.assertIn("By decision:", out)
        self.assertIn("applied", out)
        self.assertIn("rejected_by_gate", out)
        self.assertIn("By source (applied only):", out)
        self.assertIn("Top families (applied):", out)
        self.assertIn("phone", out)
        self.assertIn("Top labels (applied", out)
        self.assertIn("Top LLM models used", out)
        self.assertIn("openai/gpt-5-mini", out)
        self.assertIn("Time-range", out)

    def test_report_to_json_schema(self):
        recs = [_applied(), _rejected()]
        report = summarize_audit(recs, files_scanned=2)
        js = report_to_json(report, top=5)
        self.assertIsInstance(js, dict)
        # Must be JSON-roundtrippable
        json.loads(json.dumps(js))
        self.assertEqual(js["files_scanned"], 2)
        self.assertEqual(js["total_records"], 2)
        self.assertIn("by_decision", js)
        self.assertIn("by_source_applied", js)
        self.assertIn("top_families_applied", js)
        self.assertIn("top_labels_applied", js)
        self.assertIn("by_model", js)
        # Top-N applied
        self.assertLessEqual(len(js["top_families_applied"]), 5)


# -- Integration via CLI -----------------------------------------------------


class _AuditFixture:
    """Stages a logs/ dir with one or more learn-applied-*.jsonl."""

    def __init__(self, file_map: dict):
        self.td = tempfile.mkdtemp(prefix="audit-")
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


def _run_audit(fx, *args):
    buf_out = io.StringIO()
    buf_err = io.StringIO()
    with mock.patch.object(sys, "stdout", buf_out), mock.patch.object(sys, "stderr", buf_err):
        rc = cli_mod.main(
            [
                "audit",
                "--logs",
                fx.logs,
                *args,
            ]
        )
    return rc, buf_out.getvalue(), buf_err.getvalue()


class TestCmdAudit(unittest.TestCase):
    def test_multi_file_scan_finds_all_learn_applied(self):
        fx = _AuditFixture(
            {
                "learn-applied-20260501T120000Z.jsonl": [_applied(family="a")],
                "learn-applied-20260502T120000Z.jsonl": [_applied(family="b")],
                # Status files in same dir should be ignored
                "pattern-suggestions-20260501.jsonl": [{"role": "x"}],
            }
        )
        try:
            rc, out, _ = _run_audit(fx)
            self.assertEqual(rc, 0)
            self.assertIn("2 file(s)", out)
            self.assertIn("2 record(s)", out)
        finally:
            fx.cleanup()

    def test_single_input_overrides_multi_scan(self):
        fx = _AuditFixture(
            {
                "learn-applied-20260501T120000Z.jsonl": [_applied(family="a")],
                "learn-applied-20260502T120000Z.jsonl": [_applied(family="b")],
            }
        )
        try:
            single = fx.file("learn-applied-20260501T120000Z.jsonl")
            rc, out, _ = _run_audit(fx, "--input", single)
            self.assertEqual(rc, 0)
            self.assertIn("1 file(s)", out)
            self.assertIn("1 record(s)", out)
        finally:
            fx.cleanup()

    def test_empty_logs_dir_exits_zero(self):
        fx = _AuditFixture({})
        try:
            rc, out, _ = _run_audit(fx)
            self.assertEqual(rc, 0)
            self.assertIn("no learn-applied", out)
        finally:
            fx.cleanup()

    def test_json_flag_emits_parseable_json(self):
        fx = _AuditFixture(
            {
                "learn-applied-20260501T120000Z.jsonl": [
                    _applied(),
                    _rejected(),
                ],
            }
        )
        try:
            rc, out, _ = _run_audit(fx, "--json")
            self.assertEqual(rc, 0)
            doc = json.loads(out)
            self.assertEqual(doc["files_scanned"], 1)
            self.assertEqual(doc["total_records"], 2)
            self.assertEqual(doc["by_decision"]["applied"], 1)
            self.assertEqual(doc["by_decision"]["rejected_by_gate"], 1)
        finally:
            fx.cleanup()

    def test_filter_decision_applied_excludes_rejects(self):
        fx = _AuditFixture(
            {
                "learn-applied-x.jsonl": [
                    _applied(),
                    _rejected(decision="rejected_by_gate"),
                    _rejected(decision="rejected_by_ast"),
                ],
            }
        )
        try:
            rc, out, _ = _run_audit(fx, "--filter-decision", "applied", "--json")
            self.assertEqual(rc, 0)
            doc = json.loads(out)
            self.assertEqual(doc["total_records"], 1)
            self.assertEqual(doc["by_decision"]["applied"], 1)
            self.assertNotIn("rejected_by_gate", doc["by_decision"])
        finally:
            fx.cleanup()

    def test_filter_source_llm_excludes_substring(self):
        fx = _AuditFixture(
            {
                "learn-applied-x.jsonl": [
                    _applied(source="substring"),
                    _applied(source="llm", model="openai/gpt-5-mini"),
                    _applied(source="llm"),
                ],
            }
        )
        try:
            rc, out, _ = _run_audit(fx, "--filter-source", "llm", "--json")
            self.assertEqual(rc, 0)
            doc = json.loads(out)
            self.assertEqual(doc["total_records"], 2)
            self.assertEqual(doc["by_source_applied"]["llm"], 2)
            self.assertNotIn("substring", doc["by_source_applied"])
        finally:
            fx.cleanup()

    def test_filter_family_excludes_other_families(self):
        fx = _AuditFixture(
            {
                "learn-applied-x.jsonl": [
                    _applied(family="phone"),
                    _applied(family="phone"),
                    _applied(family="income"),
                ],
            }
        )
        try:
            rc, out, _ = _run_audit(fx, "--filter-family", "phone", "--json")
            self.assertEqual(rc, 0)
            doc = json.loads(out)
            self.assertEqual(doc["total_records"], 2)
            fams = {x["family"] for x in doc["top_families_applied"]}
            self.assertEqual(fams, {"phone"})
        finally:
            fx.cleanup()

    def test_since_filter_excludes_older_and_unparseable(self):
        fx = _AuditFixture(
            {
                "learn-applied-x.jsonl": [
                    _applied(timestamp="2026-05-10T12:00:00+00:00"),
                    _applied(timestamp="2026-04-01T00:00:00+00:00"),
                    # record without timestamp -> excluded by --since
                    {
                        "decision": "applied",
                        "family": "no_ts",
                        "keyword": "x",
                        "source": "substring",
                    },
                ],
            }
        )
        try:
            rc, out, _ = _run_audit(fx, "--since", "2026-05-01T00:00:00Z", "--json")
            self.assertEqual(rc, 0)
            doc = json.loads(out)
            self.assertEqual(doc["total_records"], 1)
        finally:
            fx.cleanup()

    def test_top_n_limits_lists(self):
        fx = _AuditFixture(
            {
                "learn-applied-x.jsonl": [
                    _applied(family=f"fam_{i}", keyword=f"k_{i}") for i in range(8)
                ],
            }
        )
        try:
            rc, out, _ = _run_audit(fx, "--top", "3", "--json")
            self.assertEqual(rc, 0)
            doc = json.loads(out)
            self.assertEqual(doc["total_records"], 8)
            self.assertEqual(len(doc["top_families_applied"]), 3)
            self.assertEqual(len(doc["top_labels_applied"]), 3)
        finally:
            fx.cleanup()

    def test_unparseable_since_falls_back_to_no_filter(self):
        fx = _AuditFixture(
            {
                "learn-applied-x.jsonl": [_applied(), _applied()],
            }
        )
        try:
            rc, out, err = _run_audit(fx, "--since", "not-a-date", "--json")
            self.assertEqual(rc, 0)
            doc = json.loads(out)
            # Filter was ignored -> all records counted
            self.assertEqual(doc["total_records"], 2)
            self.assertIn("--since", err)
        finally:
            fx.cleanup()


# -- Read-only audit ---------------------------------------------------------


class TestReadOnlyAudit(unittest.TestCase):
    """audit command MUST NOT write any files."""

    def test_audit_never_opens_files_for_writing(self):
        fx = _AuditFixture(
            {
                "learn-applied-x.jsonl": [_applied()],
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
                rc, _, _ = _run_audit(fx)

            self.assertEqual(rc, 0)
            self.assertEqual(write_modes, [], f"audit leaked write opens: {write_modes}")
            # No new files appeared
            files_after = set(os.listdir(fx.logs))
            self.assertEqual(files_after, {"learn-applied-x.jsonl"})
        finally:
            fx.cleanup()


if __name__ == "__main__":
    unittest.main(verbosity=2)
