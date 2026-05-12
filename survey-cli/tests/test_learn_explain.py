"""SR-112 #112 — tests fuer ``survey.learn.explain`` + CLI subcommand.

Layout (mirror SR-104/#109 test files):
  - TestNormalizers         — pure-helper-Korrektheit (5 tests)
  - TestDetectMode          — auto-detection regeln (3 tests)
  - TestRecordMatches       — match-mode dispatch (5 tests)
  - TestFindExplanations    — pipeline integration (6 tests)
  - TestFormatters          — human + JSON formatters (3 tests)
  - TestCmdExplain          — integration via cli_mod.main() (8 tests)
  - TestReadOnlyExplain     — mock-builtins.open: no write (1 test)

Total: 31 tests (deutlich ueber den geforderten 16+).
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

_HERE = os.path.dirname(os.path.abspath(__file__))
_PKG_ROOT = os.path.normpath(os.path.join(_HERE, ".."))
if _PKG_ROOT not in sys.path:
    sys.path.insert(0, _PKG_ROOT)

from survey.learn import cli as cli_mod  # noqa: E402
from survey.learn.explain import (  # noqa: E402
    Explanation,  # noqa: F401  (re-exported for documentation)
    _extract_timestamp,
    _normalize_decision,
    _normalize_family,
    _normalize_label,
    _normalize_source,
    detect_match_mode,
    find_explanations,
    format_human_report,
    record_matches,
    report_to_json,
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
    file_origin="learn-applied-20260510T120000Z.jsonl",
) -> dict:
    """An applied-record matching apply.py:audit_records.append schema.

    ``file_origin`` is attached as ``__file__`` (the same internal dunder
    key the CLI uses).
    """
    return {
        "decision": "applied",
        "family": family,
        "keyword": keyword,
        "source": source,
        "confidence": confidence,
        "model": model,
        "prompt_hash": prompt_hash,
        "timestamp": timestamp,
        "__file__": file_origin,
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
    file_origin="learn-applied-20260509T080000Z.jsonl",
) -> dict:
    """A reject-record with the apply.py:InboxEntry.__dict__ shape."""
    entry = {
        "role": role,
        "normalized_label": normalized_label,
        "suggested_family": suggested_family,
        "source": source,
        "first_seen": first_seen,
    }
    rec = {
        "decision": decision,
        "entry": entry,
        "__file__": file_origin,
    }
    if reason and decision != "rejected_by_reviewer":
        rec["reason"] = reason
    return rec


# -- Normalizers -------------------------------------------------------------


class TestNormalizers(unittest.TestCase):
    def test_normalize_decision_defaults_applied(self):
        self.assertEqual(_normalize_decision({}), "applied")
        self.assertEqual(_normalize_decision({"decision": "rejected_by_gate"}), "rejected_by_gate")

    def test_normalize_source_fallback_chain(self):
        self.assertEqual(_normalize_source({"source": "llm"}), "llm")
        self.assertEqual(_normalize_source({"entry": {"source": "llm"}}), "llm")
        self.assertEqual(_normalize_source({}), "substring")

    def test_normalize_family_returns_none_when_missing(self):
        self.assertEqual(_normalize_family({"family": "phone"}), "phone")
        self.assertEqual(
            _normalize_family({"entry": {"suggested_family": "income"}}),
            "income",
        )
        self.assertIsNone(_normalize_family({"entry": {}}))

    def test_normalize_label_applied_vs_rejected(self):
        # Applied: keyword direct, role from entry (or None)
        self.assertEqual(
            _normalize_label({"keyword": "telefonnummer"}),
            (None, "telefonnummer"),
        )
        # Rejected: role + normalized_label from entry
        rej = _rejected()
        role, label = _normalize_label(rej)
        self.assertEqual(role, "textbox")
        self.assertEqual(label, "haushaltsgrosse")
        # Neither -> (None, None)
        self.assertEqual(_normalize_label({"entry": {}}), (None, None))

    def test_extract_timestamp_priority_and_naive_utc(self):
        rec = {"timestamp": "2026-05-10T12:00:00+00:00"}
        self.assertEqual(_extract_timestamp(rec), datetime(2026, 5, 10, 12, 0, tzinfo=timezone.utc))
        # Fall back to entry.first_seen
        rec2 = {"entry": {"first_seen": "2026-05-01T00:00:00+00:00"}}
        self.assertEqual(_extract_timestamp(rec2), datetime(2026, 5, 1, 0, 0, tzinfo=timezone.utc))
        # Naive -> utc attached
        rec3 = {"timestamp": "2026-05-10T12:00:00"}
        dt3 = _extract_timestamp(rec3)
        self.assertEqual(dt3.tzinfo, timezone.utc)
        # Unparseable
        self.assertIsNone(_extract_timestamp({"timestamp": "not-iso"}))
        # Missing entirely
        self.assertIsNone(_extract_timestamp({}))


# -- Mode auto-detect --------------------------------------------------------


class TestDetectMode(unittest.TestCase):
    def test_query_with_colon_is_label_mode(self):
        self.assertEqual(detect_match_mode("textbox:phone"), "label")
        self.assertEqual(detect_match_mode("select:gender"), "label")

    def test_query_without_colon_is_keyword_mode(self):
        self.assertEqual(detect_match_mode("phone"), "keyword")
        self.assertEqual(detect_match_mode("telefonnummer"), "keyword")

    def test_empty_query_defaults_to_keyword(self):
        # Edge case: empty query, no colon, falls to keyword default
        self.assertEqual(detect_match_mode(""), "keyword")


# -- Match dispatch ----------------------------------------------------------


class TestRecordMatches(unittest.TestCase):
    def test_keyword_mode_case_insensitive_substring(self):
        rec = _applied(keyword="TelefonNummer")
        # Lowercase query matches uppercase keyword (case-insensitive)
        self.assertTrue(record_matches(rec, "telefon", "keyword"))
        self.assertTrue(record_matches(rec, "nummer", "keyword"))
        self.assertFalse(record_matches(rec, "xyz", "keyword"))

    def test_keyword_mode_also_matches_reject_normalized_label(self):
        rej = _rejected(normalized_label="HausGrosse")
        # keyword mode falls through to entry.normalized_label for rejects
        self.assertTrue(record_matches(rej, "haus", "keyword"))
        self.assertFalse(record_matches(rej, "telefon", "keyword"))

    def test_family_mode_substring(self):
        self.assertTrue(record_matches(_applied(family="phone_number"), "phone", "family"))
        self.assertFalse(record_matches(_applied(family="income"), "phone", "family"))
        # Also matches reject's entry.suggested_family
        self.assertTrue(
            record_matches(_rejected(suggested_family="income_household"), "income", "family")
        )

    def test_label_mode_role_colon_label(self):
        rej = _rejected(role="textbox", normalized_label="phone-mobile")
        self.assertTrue(record_matches(rej, "textbox:phone", "label"))
        self.assertFalse(record_matches(rej, "select:phone", "label"))
        # label-only query (no role part) matches if label substring hits
        self.assertTrue(record_matches(rej, "phone", "label"))

    def test_auto_mode_routes_via_detect_mode(self):
        rej = _rejected(role="textbox", normalized_label="phone-mobile")
        # With colon -> label mode
        self.assertTrue(record_matches(rej, "textbox:phone", "auto"))
        # Without -> keyword mode
        self.assertTrue(record_matches(rej, "phone-mobile", "auto"))


# -- Pipeline ----------------------------------------------------------------


class TestFindExplanations(unittest.TestCase):
    def test_empty_input_returns_empty(self):
        self.assertEqual(find_explanations([], "anything"), [])

    def test_default_excludes_rejects(self):
        recs = [
            _applied(keyword="phone-x"),
            _rejected(normalized_label="phone-y"),
        ]
        result = find_explanations(recs, "phone")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].decision, "applied")

    def test_include_rejects_flips_inclusion(self):
        recs = [
            _applied(keyword="phone-x"),
            _rejected(normalized_label="phone-y"),
        ]
        result = find_explanations(recs, "phone", include_rejects=True)
        self.assertEqual(len(result), 2)

    def test_newest_first_sorting(self):
        recs = [
            _applied(timestamp="2026-05-01T00:00:00+00:00", keyword="phone-1"),
            _applied(timestamp="2026-05-10T00:00:00+00:00", keyword="phone-2"),
            _applied(timestamp="2026-05-05T00:00:00+00:00", keyword="phone-3"),
        ]
        result = find_explanations(recs, "phone", limit=10)
        self.assertEqual([e.keyword for e in result], ["phone-2", "phone-3", "phone-1"])

    def test_records_without_timestamp_sort_to_end(self):
        recs = [
            _applied(keyword="phone-noT", timestamp=None),
            _applied(keyword="phone-yes", timestamp="2026-05-10T00:00:00+00:00"),
        ]
        # Remove timestamp from first
        recs[0].pop("timestamp", None)
        result = find_explanations(recs, "phone", limit=10)
        self.assertEqual(result[0].keyword, "phone-yes")
        self.assertEqual(result[1].keyword, "phone-noT")
        self.assertIsNone(result[1].timestamp_iso)

    def test_limit_truncates_after_sort(self):
        recs = [
            _applied(timestamp=f"2026-05-{i:02d}T00:00:00+00:00", keyword=f"phone-{i}")
            for i in range(1, 11)
        ]
        result = find_explanations(recs, "phone", limit=3)
        self.assertEqual(len(result), 3)
        # Newest 3: phone-10, phone-9, phone-8
        self.assertEqual(result[0].keyword, "phone-10")
        self.assertEqual(result[2].keyword, "phone-8")


# -- Formatters --------------------------------------------------------------


class TestFormatters(unittest.TestCase):
    def test_human_report_no_match_emits_friendly_message(self):
        out = format_human_report(
            [],
            query="nope",
            match_mode="keyword",
            limit=5,
            include_rejects=False,
        )
        self.assertIn("explain query: 'nope'", out)
        self.assertIn("No audit-record matched", out)

    def test_human_report_with_matches_renders_blocks(self):
        recs = [_applied(model="openai/gpt-5-mini")]
        result = find_explanations(recs, "telefon")
        out = format_human_report(
            result,
            query="telefon",
            match_mode="keyword",
            limit=5,
            include_rejects=False,
        )
        self.assertIn("Found 1 audit-record(s)", out)
        self.assertIn("family:", out)
        self.assertIn("phone", out)
        self.assertIn("source:", out)
        self.assertIn("confidence:", out)
        self.assertIn("openai/gpt-5-mini", out)
        self.assertIn("log-file:", out)

    def test_json_report_schema_complete(self):
        recs = [_applied()]
        result = find_explanations(recs, "telefon")
        doc = report_to_json(
            result,
            query="telefon",
            match_mode="keyword",
            limit=5,
            include_rejects=False,
        )
        # Roundtrip
        json.loads(json.dumps(doc))
        self.assertEqual(doc["query"], "telefon")
        self.assertEqual(doc["match_mode"], "keyword")
        self.assertEqual(doc["limit"], 5)
        self.assertFalse(doc["include_rejects"])
        self.assertEqual(doc["total_matches"], 1)
        self.assertIsInstance(doc["explanations"], list)
        e = doc["explanations"][0]
        for key in (
            "decision",
            "family",
            "keyword",
            "role",
            "label",
            "source",
            "confidence",
            "model",
            "prompt_hash",
            "timestamp",
            "log_file",
            "reason",
        ):
            self.assertIn(key, e)


# -- Integration via CLI -----------------------------------------------------


class _ExplainFixture:
    """Stages a logs/ dir with one or more learn-applied-*.jsonl."""

    def __init__(self, file_map: dict):
        self.td = tempfile.mkdtemp(prefix="explain-")
        self.logs = os.path.join(self.td, "logs")
        os.makedirs(self.logs)
        for fname, recs in file_map.items():
            path = os.path.join(self.logs, fname)
            with open(path, "w") as f:
                for r in recs:
                    # Strip the test-only ``__file__`` key before writing;
                    # CLI re-attaches it from path.basename
                    rec = {k: v for k, v in r.items() if k != "__file__"}
                    f.write(json.dumps(rec) + "\n")

    def cleanup(self):
        import shutil

        shutil.rmtree(self.td, ignore_errors=True)

    def file(self, name: str) -> str:
        return os.path.join(self.logs, name)


def _run_explain(fx, query, *args):
    buf_out = io.StringIO()
    buf_err = io.StringIO()
    with mock.patch.object(sys, "stdout", buf_out), mock.patch.object(sys, "stderr", buf_err):
        rc = cli_mod.main(
            [
                "explain",
                query,
                "--logs",
                fx.logs,
                *args,
            ]
        )
    return rc, buf_out.getvalue(), buf_err.getvalue()


class TestCmdExplain(unittest.TestCase):
    def test_multi_file_scan_finds_all_learn_applied(self):
        fx = _ExplainFixture(
            {
                "learn-applied-20260501T120000Z.jsonl": [_applied(keyword="phone-a")],
                "learn-applied-20260502T120000Z.jsonl": [_applied(keyword="phone-b")],
                # Status files in same dir ignored
                "pattern-suggestions-20260501.jsonl": [{"role": "x"}],
            }
        )
        try:
            rc, out, _ = _run_explain(fx, "phone")
            self.assertEqual(rc, 0)
            self.assertIn("Found 2 audit-record(s)", out)
        finally:
            fx.cleanup()

    def test_single_input_overrides_multi_scan(self):
        fx = _ExplainFixture(
            {
                "learn-applied-A.jsonl": [_applied(keyword="phone-a")],
                "learn-applied-B.jsonl": [_applied(keyword="phone-b")],
            }
        )
        try:
            single = fx.file("learn-applied-A.jsonl")
            rc, out, _ = _run_explain(fx, "phone", "--input", single)
            self.assertEqual(rc, 0)
            self.assertIn("Found 1 audit-record(s)", out)
            self.assertIn("phone-a", out)
        finally:
            fx.cleanup()

    def test_empty_logs_dir_exits_zero(self):
        fx = _ExplainFixture({})
        try:
            rc, out, _ = _run_explain(fx, "anything")
            self.assertEqual(rc, 0)
            self.assertIn("no learn-applied", out)
        finally:
            fx.cleanup()

    def test_json_flag_emits_parseable(self):
        fx = _ExplainFixture(
            {
                "learn-applied-x.jsonl": [_applied(keyword="phone-x")],
            }
        )
        try:
            rc, out, _ = _run_explain(fx, "phone", "--json")
            self.assertEqual(rc, 0)
            doc = json.loads(out)
            self.assertEqual(doc["query"], "phone")
            self.assertEqual(doc["match_mode"], "keyword")
            self.assertEqual(doc["total_matches"], 1)
        finally:
            fx.cleanup()

    def test_by_family_overrides_auto_detect(self):
        fx = _ExplainFixture(
            {
                "learn-applied-x.jsonl": [
                    _applied(family="phone", keyword="telefon"),
                    _applied(family="income", keyword="phone-home"),
                ],
            }
        )
        try:
            # Without --by, "phone" hits keywords. With --by family, only
            # records whose family contains "phone" match.
            rc, out, _ = _run_explain(fx, "phone", "--by", "family", "--json")
            self.assertEqual(rc, 0)
            doc = json.loads(out)
            self.assertEqual(doc["match_mode"], "family")
            self.assertEqual(doc["total_matches"], 1)
            self.assertEqual(doc["explanations"][0]["family"], "phone")
        finally:
            fx.cleanup()

    def test_limit_truncates_in_json(self):
        fx = _ExplainFixture(
            {
                "learn-applied-x.jsonl": [
                    _applied(timestamp=f"2026-05-{i:02d}T00:00:00+00:00", keyword=f"phone-{i}")
                    for i in range(1, 11)
                ],
            }
        )
        try:
            rc, out, _ = _run_explain(fx, "phone", "--limit", "3", "--json")
            self.assertEqual(rc, 0)
            doc = json.loads(out)
            self.assertEqual(len(doc["explanations"]), 3)
            # Note: total_matches reflects the returned (post-limit) count
            # in this implementation (the json formatter takes len(explanations))
            self.assertEqual(doc["total_matches"], 3)
        finally:
            fx.cleanup()

    def test_include_rejects_flag(self):
        fx = _ExplainFixture(
            {
                "learn-applied-x.jsonl": [
                    _applied(keyword="phone-app"),
                    _rejected(normalized_label="phone-rej"),
                ],
            }
        )
        try:
            # Default: applied-only
            rc, out, _ = _run_explain(fx, "phone", "--json")
            doc = json.loads(out)
            self.assertEqual(doc["total_matches"], 1)
            # With flag: both
            rc, out, _ = _run_explain(fx, "phone", "--include-rejects", "--json")
            doc = json.loads(out)
            self.assertEqual(doc["total_matches"], 2)
        finally:
            fx.cleanup()

    def test_log_file_origin_attached_to_explanations(self):
        fx = _ExplainFixture(
            {
                "learn-applied-20260510T120000Z.jsonl": [_applied(keyword="phone-x")],
            }
        )
        try:
            rc, out, _ = _run_explain(fx, "phone", "--json")
            self.assertEqual(rc, 0)
            doc = json.loads(out)
            self.assertEqual(
                doc["explanations"][0]["log_file"], "learn-applied-20260510T120000Z.jsonl"
            )
        finally:
            fx.cleanup()


# -- Read-only --------------------------------------------------------------


class TestReadOnlyExplain(unittest.TestCase):
    """explain command MUST NOT write any file."""

    def test_explain_never_opens_for_writing(self):
        fx = _ExplainFixture(
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
                rc, _, _ = _run_explain(fx, "phone")

            self.assertEqual(rc, 0)
            self.assertEqual(write_modes, [], f"explain leaked write opens: {write_modes}")
            files_after = set(os.listdir(fx.logs))
            self.assertEqual(files_after, {"learn-applied-x.jsonl"})
        finally:
            fx.cleanup()


if __name__ == "__main__":
    unittest.main(verbosity=2)
