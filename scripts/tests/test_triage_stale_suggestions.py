# =============================================================================
# Tests for `scripts/triage_stale_suggestions.py` (SR-108).
#
# CONTRACT UNDER TEST (8+ cases):
#   1. Empty input            -> exit 0, stale_count == 0
#   2. No stale records       -> exit 0, stale_count == 0
#   3. Stale records (default mode) -> exit 0 (read-only diagnostic)
#   4. --exit-non-zero-if-stale + stale -> exit 1
#   5. --exit-non-zero-if-stale + none  -> exit 0
#   6. --filter-source llm    excludes substring stale records
#   7. Records w/o first_seen are NOT stale (defensive — no false positives)
#   8. --json output is parseable + has expected schema
#   9. Closed records (status=accepted/rejected) are NEVER stale
#
# READ-ONLY AUDIT (10th test, recommended in plan):
#   - Script never opens any path with a write mode ("w"/"a"/"x"/"+").
#     We monkey-patch builtins.open and assert all calls use read-only modes.
#
# Run:
#     python -m pytest scripts/tests/test_triage_stale_suggestions.py -q
# or:
#     python -m unittest scripts.tests.test_triage_stale_suggestions
# =============================================================================

from __future__ import annotations

import builtins
import importlib.util
import io
import json
import shutil
import sys
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

# Load the script by file path (it's a script, not a package member). Same
# pattern as scripts/tests/test_check_banned_patterns.py.
_HERE = Path(__file__).resolve()
_SCRIPT = _HERE.parent.parent / "triage_stale_suggestions.py"
_spec = importlib.util.spec_from_file_location(
    "triage_stale_suggestions",
    _SCRIPT,
)
assert _spec is not None and _spec.loader is not None
triage_mod = importlib.util.module_from_spec(_spec)
sys.modules["triage_stale_suggestions"] = triage_mod
_spec.loader.exec_module(triage_mod)  # type: ignore[union-attr]


# -- Fixture helpers ---------------------------------------------------------


def _iso(dt: datetime) -> str:
    """ISO-8601 UTC with trailing Z."""
    return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _write_jsonl(path: Path, records):
    with open(path, "w", encoding="utf-8") as fh:
        for r in records:
            fh.write(json.dumps(r) + "\n")


def _record(
    *,
    status="open",
    source="substring",
    days_old=0,
    family="phone",
    label="telefonnummer",
    count=1,
    first_seen_override=None,
):
    """Build a pattern-suggestions record with sensible defaults."""
    now = datetime.now(UTC)
    fs = first_seen_override
    if fs is None:
        fs = _iso(now - timedelta(days=days_old)) if days_old is not None else None
    rec = {
        "role": "textbox",
        "normalized_label": label,
        "suggested_family": family,
        "confidence": 0.9,
        "source": source,
        "status": status,
        "count": count,
    }
    if fs is not None:
        rec["first_seen"] = fs
    return rec


# -- Test cases --------------------------------------------------------------


class TriageStaleSuggestionsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="sr108_"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    # 1. Empty input -- no JSONL files at all.
    def test_empty_logs_dir_exits_zero_stale_zero(self):
        rc = triage_mod.main(
            [
                "--logs",
                str(self.tmp),
                "--exit-non-zero-if-stale",
            ]
        )
        self.assertEqual(rc, 0)

    # 2. Fresh open records -- none stale.
    def test_no_stale_records_exits_zero(self):
        f = self.tmp / "pattern-suggestions-2026-05-12.jsonl"
        _write_jsonl(
            f,
            [
                _record(days_old=3),
                _record(days_old=10, label="email"),
            ],
        )
        rc = triage_mod.main(
            [
                "--logs",
                str(self.tmp),
                "--age-days",
                "14",
                "--exit-non-zero-if-stale",
            ]
        )
        self.assertEqual(rc, 0)

    # 3. Stale records found in DEFAULT mode -> exit 0 (read-only diagnostic).
    def test_stale_default_mode_exits_zero(self):
        f = self.tmp / "pattern-suggestions-2026-05-12.jsonl"
        _write_jsonl(
            f,
            [
                _record(days_old=22),
                _record(days_old=5),
            ],
        )
        rc = triage_mod.main(["--logs", str(self.tmp), "--age-days", "14"])
        self.assertEqual(rc, 0, "default mode is always read-only diagnostic")

    # 4. --exit-non-zero-if-stale with stale -> exit 1.
    def test_exit_nonzero_when_stale(self):
        f = self.tmp / "pattern-suggestions-2026-05-12.jsonl"
        _write_jsonl(f, [_record(days_old=22)])
        rc = triage_mod.main(
            [
                "--logs",
                str(self.tmp),
                "--age-days",
                "14",
                "--exit-non-zero-if-stale",
            ]
        )
        self.assertEqual(rc, 1)

    # 5. --exit-non-zero-if-stale with NO stale -> exit 0.
    def test_exit_zero_when_no_stale_with_flag(self):
        f = self.tmp / "pattern-suggestions-2026-05-12.jsonl"
        _write_jsonl(f, [_record(days_old=5)])
        rc = triage_mod.main(
            [
                "--logs",
                str(self.tmp),
                "--age-days",
                "14",
                "--exit-non-zero-if-stale",
            ]
        )
        self.assertEqual(rc, 0)

    # 6. --filter-source llm excludes substring stale records.
    def test_filter_source_llm_excludes_substring_stale(self):
        f = self.tmp / "pattern-suggestions-2026-05-12.jsonl"
        _write_jsonl(
            f,
            [
                _record(days_old=30, source="substring", label="mobil"),
                _record(days_old=30, source="llm", label="haushalt"),
            ],
        )
        # Use the pure helper directly for deterministic count assertions.
        now = datetime.now(UTC)
        summary_llm = triage_mod.triage(
            logs_dir=str(self.tmp),
            age_days=14,
            filter_source="llm",
            now=now,
        )
        self.assertEqual(summary_llm["stale_count"], 1)
        self.assertEqual(summary_llm["stale_records"][0]["source"], "llm")

        summary_sub = triage_mod.triage(
            logs_dir=str(self.tmp),
            age_days=14,
            filter_source="substring",
            now=now,
        )
        self.assertEqual(summary_sub["stale_count"], 1)
        self.assertEqual(summary_sub["stale_records"][0]["source"], "substring")

        summary_all = triage_mod.triage(
            logs_dir=str(self.tmp),
            age_days=14,
            filter_source="all",
            now=now,
        )
        self.assertEqual(summary_all["stale_count"], 2)

    # 7. Records without first_seen are NEVER stale (defensive).
    def test_records_without_first_seen_not_stale(self):
        f = self.tmp / "pattern-suggestions-2026-05-12.jsonl"
        _write_jsonl(
            f,
            [
                # No first_seen at all (legacy record).
                {"role": "textbox", "normalized_label": "x", "status": "open"},
                # Empty first_seen string.
                {
                    "role": "textbox",
                    "normalized_label": "y",
                    "status": "open",
                    "first_seen": "",
                },
                # Malformed first_seen.
                {
                    "role": "textbox",
                    "normalized_label": "z",
                    "status": "open",
                    "first_seen": "not-a-date",
                },
            ],
        )
        summary = triage_mod.triage(
            logs_dir=str(self.tmp),
            age_days=1,
            filter_source="all",
        )
        self.assertEqual(summary["stale_count"], 0)
        # But they still count as open records.
        self.assertEqual(summary["total_open"], 3)

    # 8. --json output is parseable and has expected schema.
    def test_json_output_schema(self):
        f = self.tmp / "pattern-suggestions-2026-05-12.jsonl"
        _write_jsonl(
            f,
            [
                _record(days_old=22, label="mobilnummer"),
                _record(days_old=3, label="fresh"),
            ],
        )

        captured = io.StringIO()
        old_stdout = sys.stdout
        sys.stdout = captured
        try:
            rc = triage_mod.main(
                [
                    "--logs",
                    str(self.tmp),
                    "--age-days",
                    "14",
                    "--json",
                ]
            )
        finally:
            sys.stdout = old_stdout

        self.assertEqual(rc, 0)
        parsed = json.loads(captured.getvalue())
        expected_keys = {
            "threshold_days",
            "filter_source",
            "logs_dir",
            "files_scanned",
            "total_open",
            "stale_count",
            "stale_percent",
            "oldest_age_days",
            "stale_records",
        }
        self.assertEqual(set(parsed.keys()), expected_keys)
        self.assertEqual(parsed["threshold_days"], 14)
        self.assertEqual(parsed["filter_source"], "all")
        self.assertEqual(parsed["total_open"], 2)
        self.assertEqual(parsed["stale_count"], 1)
        self.assertEqual(parsed["oldest_age_days"], 22)
        self.assertEqual(len(parsed["stale_records"]), 1)
        rec0 = parsed["stale_records"][0]
        for k in ("age_days", "source", "family", "role", "label", "count", "first_seen"):
            self.assertIn(k, rec0)

    # 9. Closed records (status=accepted/rejected) are NEVER stale.
    def test_closed_records_never_stale(self):
        f = self.tmp / "pattern-suggestions-2026-05-12.jsonl"
        _write_jsonl(
            f,
            [
                _record(days_old=99, status="accepted"),
                _record(days_old=99, status="rejected"),
                _record(days_old=99, status="open", label="genuine_stale"),
            ],
        )
        summary = triage_mod.triage(
            logs_dir=str(self.tmp),
            age_days=14,
            filter_source="all",
        )
        self.assertEqual(summary["stale_count"], 1)
        self.assertEqual(
            summary["stale_records"][0]["label"],
            "genuine_stale",
        )

    # 10. READ-ONLY AUDIT: script never opens any file in write mode.
    def test_script_never_opens_files_for_writing(self):
        f = self.tmp / "pattern-suggestions-2026-05-12.jsonl"
        _write_jsonl(f, [_record(days_old=22)])

        real_open = builtins.open
        write_mode_chars = {"w", "a", "x", "+"}
        offenders = []

        def audit_open(file, mode="r", *args, **kwargs):
            mode_chars = set(mode)
            if mode_chars & write_mode_chars:
                offenders.append((str(file), mode))
            return real_open(file, mode, *args, **kwargs)

        builtins.open = audit_open
        try:
            # Reset internal state: re-load? No — `triage` reads via open
            # only. Invoke the pure function (avoid argparse / main print).
            triage_mod.triage(
                logs_dir=str(self.tmp),
                age_days=14,
                filter_source="all",
            )
        finally:
            builtins.open = real_open

        self.assertEqual(
            offenders,
            [],
            f"triage_stale_suggestions opened a file in write mode: {offenders}",
        )

    # 11. Output-sink files (*-accepted.jsonl, *-rejected.jsonl) are skipped.
    def test_skips_output_sink_files(self):
        # An "open record" in an output-sink file should not be counted.
        sink = self.tmp / "pattern-suggestions-accepted.jsonl"
        _write_jsonl(sink, [_record(days_old=99, label="should_be_ignored")])
        # Empty inbox.
        inbox = self.tmp / "pattern-suggestions-2026-05-12.jsonl"
        _write_jsonl(inbox, [])

        summary = triage_mod.triage(
            logs_dir=str(self.tmp),
            age_days=14,
            filter_source="all",
        )
        self.assertEqual(summary["stale_count"], 0)
        self.assertEqual(summary["total_open"], 0)
        # files_scanned counts only the inbox file (because the sink has
        # zero parseable records, but more importantly we never opened it).
        # The empty inbox yields zero records, so files_scanned is 0 too.
        self.assertEqual(summary["files_scanned"], 0)

    # 12. Records without explicit status default to "open" (#104 parity).
    def test_record_without_status_defaults_open(self):
        f = self.tmp / "pattern-suggestions-2026-05-12.jsonl"
        # status field is absent — normalizer should treat as "open".
        legacy = {
            "role": "textbox",
            "normalized_label": "phone",
            "first_seen": _iso(datetime.now(UTC) - timedelta(days=22)),
            "source": "substring",
        }
        _write_jsonl(f, [legacy])
        summary = triage_mod.triage(
            logs_dir=str(self.tmp),
            age_days=14,
            filter_source="all",
        )
        self.assertEqual(summary["total_open"], 1)
        self.assertEqual(summary["stale_count"], 1)


class TriageMalformedInputTests(unittest.TestCase):
    """Robustness: malformed JSONL lines must not abort the scan."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="sr108_malformed_"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_malformed_lines_are_silently_skipped(self):
        f = self.tmp / "pattern-suggestions-2026-05-12.jsonl"
        with open(f, "w", encoding="utf-8") as fh:
            fh.write("not-json-at-all\n")
            fh.write("{}\n")  # parseable but no fields -> open, no first_seen
            fh.write("\n")  # blank
            fh.write('"a-string"\n')  # parses but not a dict -> skipped
            fh.write(
                json.dumps(
                    {
                        "role": "textbox",
                        "normalized_label": "phone",
                        "first_seen": (datetime.now(UTC) - timedelta(days=22)).strftime(
                            "%Y-%m-%dT%H:%M:%SZ"
                        ),
                    }
                )
                + "\n"
            )
        summary = triage_mod.triage(
            logs_dir=str(self.tmp),
            age_days=14,
            filter_source="all",
        )
        # `{}` and the genuine record are both counted as open (status
        # defaults to "open"), but only the genuine one has first_seen.
        self.assertEqual(summary["total_open"], 2)
        self.assertEqual(summary["stale_count"], 1)


if __name__ == "__main__":
    unittest.main()
