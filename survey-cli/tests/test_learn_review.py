"""
test_learn_review.py
=====================

SR-102 #102 — Tests fuer die source-aware batch-review:
  - TestPlanAction      pure-function decision matrix (12 tests)
  - TestApplyStatus     status-flip helper (3 tests)
  - TestFormatDisplay   display-string includes phase-2 fields (3 tests)
  - TestCmdReview       end-to-end via main() entry: 6 integration tests
"""

from __future__ import annotations

import io
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
PARENT = os.path.dirname(HERE)
if PARENT not in sys.path:
    sys.path.insert(0, PARENT)

from survey.learn import (  # noqa: E402
    ReviewRules,
    apply_status,
    format_display_line,
    normalize_source,
    partition_records,
    plan_action,
)
from survey.learn import cli as cli_mod  # noqa: E402


def _rec(**overrides) -> dict:
    """Helper: minimal valid suggestion-record."""
    base = {
        "role": "textbox",
        "normalized_label": "test label",
        "count": 3,
        "sample_labels": ["Test Label"],
        "suggested_family": "phone",
        "confidence": 0.5,
        "source": "substring",
        "status": "open",
    }
    base.update(overrides)
    return base


# ────────────────────────────────────────────────────────────────────────────
# TestPlanAction
# ────────────────────────────────────────────────────────────────────────────


class TestPlanAction(unittest.TestCase):
    def test_default_rules_returns_ask(self):
        self.assertEqual(plan_action(_rec(), ReviewRules()), "ask")

    def test_status_already_accepted_short_circuits(self):
        self.assertEqual(
            plan_action(_rec(status="accepted"), ReviewRules()),
            "already_done",
        )

    def test_status_already_rejected_short_circuits(self):
        self.assertEqual(
            plan_action(_rec(status="rejected"), ReviewRules()),
            "already_done",
        )

    def test_filter_open_only_disabled_processes_any_status(self):
        self.assertEqual(
            plan_action(_rec(status="accepted"), ReviewRules(filter_open_only=False)),
            "ask",
        )

    def test_filter_source_substring_skips_llm_records(self):
        self.assertEqual(
            plan_action(_rec(source="llm"), ReviewRules(filter_source="substring")),
            "filtered",
        )

    def test_filter_source_llm_skips_substring_records(self):
        self.assertEqual(
            plan_action(_rec(source="substring"), ReviewRules(filter_source="llm")),
            "filtered",
        )

    def test_auto_accept_substring_above_threshold(self):
        rec = _rec(source="substring", confidence=0.95)
        rules = ReviewRules(auto_accept_substring_above=0.9)
        self.assertEqual(plan_action(rec, rules), "accept")

    def test_auto_accept_substring_below_threshold_falls_through(self):
        rec = _rec(source="substring", confidence=0.85)
        rules = ReviewRules(auto_accept_substring_above=0.9)
        self.assertEqual(plan_action(rec, rules), "ask")

    def test_auto_accept_does_not_affect_llm(self):
        rec = _rec(source="llm", confidence=0.99)
        rules = ReviewRules(auto_accept_substring_above=0.9)
        self.assertEqual(plan_action(rec, rules), "ask")

    def test_auto_reject_llm_below_threshold(self):
        rec = _rec(source="llm", confidence=0.5)
        rules = ReviewRules(auto_reject_llm_below=0.85)
        self.assertEqual(plan_action(rec, rules), "reject")

    def test_auto_reject_llm_above_threshold_falls_through(self):
        rec = _rec(source="llm", confidence=0.9)
        rules = ReviewRules(auto_reject_llm_below=0.85)
        self.assertEqual(plan_action(rec, rules), "ask")

    def test_non_interactive_filters_records_without_auto_match(self):
        rec = _rec(source="substring", confidence=0.5)
        rules = ReviewRules(
            non_interactive=True,
            auto_accept_substring_above=0.9,  # NOT met
        )
        self.assertEqual(plan_action(rec, rules), "filtered")

    def test_non_interactive_still_applies_auto_rules(self):
        rec = _rec(source="substring", confidence=0.95)
        rules = ReviewRules(
            non_interactive=True,
            auto_accept_substring_above=0.9,
        )
        self.assertEqual(plan_action(rec, rules), "accept")

    def test_rule_priority_idempotency_before_filter(self):
        """already_done wins over source-filter (consistency: don't surface
        what's already done, regardless of filter)."""
        rec = _rec(status="accepted", source="llm")
        self.assertEqual(
            plan_action(rec, ReviewRules(filter_source="substring")),
            "already_done",
        )

    def test_missing_source_normalizes_to_substring(self):
        rec = _rec()
        del rec["source"]
        self.assertEqual(normalize_source(rec), "substring")
        rules = ReviewRules(auto_accept_substring_above=0.4)
        self.assertEqual(plan_action(rec, rules), "accept")

    def test_partition_records_returns_tuples(self):
        rules = ReviewRules(filter_source="llm")
        records = [
            _rec(source="substring"),
            _rec(source="llm", confidence=0.5),
            _rec(source="llm", status="rejected"),
        ]
        out = partition_records(records, rules)
        self.assertEqual([a for _, a in out], ["filtered", "ask", "already_done"])


# ────────────────────────────────────────────────────────────────────────────
# TestApplyStatus
# ────────────────────────────────────────────────────────────────────────────


class TestApplyStatus(unittest.TestCase):
    def test_accept_sets_accepted(self):
        out = apply_status(_rec(), "accept")
        self.assertEqual(out["status"], "accepted")

    def test_reject_sets_rejected(self):
        out = apply_status(_rec(), "reject")
        self.assertEqual(out["status"], "rejected")

    def test_other_actions_leave_status_unchanged(self):
        rec = _rec(status="open")
        for act in ("ask", "filtered", "already_done"):
            out = apply_status(rec, act)
            self.assertEqual(out["status"], "open")

    def test_apply_status_does_not_mutate_input(self):
        rec = _rec()
        apply_status(rec, "accept")
        self.assertEqual(rec["status"], "open")


# ────────────────────────────────────────────────────────────────────────────
# TestFormatDisplay
# ────────────────────────────────────────────────────────────────────────────


class TestFormatDisplay(unittest.TestCase):
    def test_substring_record_shows_source(self):
        s = format_display_line(_rec(source="substring", confidence=0.9))
        self.assertIn("source=substring", s)
        self.assertIn("conf=0.90", s)

    def test_llm_record_shows_model_and_hash(self):
        s = format_display_line(
            _rec(
                source="llm",
                confidence=0.91,
                model="openai/gpt-5-mini",
                prompt_hash="abc123def456",
            )
        )
        self.assertIn("source=llm", s)
        self.assertIn("openai/gpt-5-mini", s)
        self.assertIn("hash=abc123de", s)

    def test_llm_record_truncates_very_long_model_id(self):
        s = format_display_line(
            _rec(
                source="llm",
                model="some-very-long-vendor/extremely-long-model-name-v2.7-rc3",
                prompt_hash="d" * 12,
            )
        )
        # Original model length > 30 — should be truncated with "..."
        self.assertIn("...", s)

    def test_no_family_shows_new_family_needed(self):
        s = format_display_line(_rec(suggested_family=None))
        self.assertIn("NEW family needed", s)


# ────────────────────────────────────────────────────────────────────────────
# TestCmdReview (integration via main() entry)
# ────────────────────────────────────────────────────────────────────────────


class _ReviewFixture:
    """Spins up tmpdir with logs/ + given suggestions JSONL."""

    def __init__(self, records):
        self.td = tempfile.mkdtemp(prefix="review-")
        self.logs = os.path.join(self.td, "logs")
        os.makedirs(self.logs)
        self.suggestions_path = os.path.join(self.logs, "pattern-suggestions-20260512.jsonl")
        with open(self.suggestions_path, "w") as f:
            for r in records:
                f.write(json.dumps(r) + "\n")
        self.accepted_path = os.path.join(self.logs, "pattern-suggestions-accepted.jsonl")
        self.rejected_path = os.path.join(self.logs, "pattern-suggestions-rejected.jsonl")

    def cleanup(self):
        import shutil

        shutil.rmtree(self.td, ignore_errors=True)

    def read_input(self):
        with open(self.suggestions_path) as f:
            return [json.loads(line) for line in f if line.strip()]

    def read_accepted(self):
        if not os.path.exists(self.accepted_path):
            return []
        with open(self.accepted_path) as f:
            return [json.loads(line) for line in f if line.strip()]

    def read_rejected(self):
        if not os.path.exists(self.rejected_path):
            return []
        with open(self.rejected_path) as f:
            return [json.loads(line) for line in f if line.strip()]


def _run_review(fx, *args):
    """Invoke cli.main(["review", ...]) capturing stdout."""
    buf = io.StringIO()
    with mock.patch.object(sys, "stdout", buf):
        rc = cli_mod.main(
            [
                "review",
                "--logs",
                fx.logs,
                "--input",
                fx.suggestions_path,
                *args,
            ]
        )
    return rc, buf.getvalue()


class TestCmdReview(unittest.TestCase):
    def test_auto_accept_high_conf_substring_only(self):
        fx = _ReviewFixture(
            [
                _rec(normalized_label="a", source="substring", confidence=0.95),
                _rec(normalized_label="b", source="substring", confidence=0.5),
                _rec(normalized_label="c", source="llm", confidence=0.99),
            ]
        )
        try:
            rc, out = _run_review(
                fx,
                "--auto-accept-substring-above",
                "0.9",
                "--non-interactive",
            )
            self.assertEqual(rc, 0)
            self.assertIn("accepted=1", out)
            self.assertIn("rejected=0", out)
            # filtered=2 (the substring=0.5 falls through to filtered via
            # non-interactive; the llm=0.99 has no auto-rule and also
            # filters out).
            self.assertIn("filtered=2", out)
            accepted = fx.read_accepted()
            self.assertEqual(len(accepted), 1)
            self.assertEqual(accepted[0]["normalized_label"], "a")
            self.assertEqual(accepted[0]["status"], "accepted")
        finally:
            fx.cleanup()

    def test_auto_reject_low_conf_llm(self):
        fx = _ReviewFixture(
            [
                _rec(normalized_label="a", source="llm", confidence=0.5),
                _rec(normalized_label="b", source="llm", confidence=0.9),
                _rec(normalized_label="c", source="substring", confidence=0.99),
            ]
        )
        try:
            rc, out = _run_review(
                fx,
                "--auto-reject-llm-below",
                "0.85",
                "--non-interactive",
            )
            self.assertEqual(rc, 0)
            self.assertIn("rejected=1", out)
            rejected = fx.read_rejected()
            self.assertEqual(len(rejected), 1)
            self.assertEqual(rejected[0]["normalized_label"], "a")
            self.assertEqual(rejected[0]["status"], "rejected")
        finally:
            fx.cleanup()

    def test_combined_auto_rules(self):
        fx = _ReviewFixture(
            [
                _rec(normalized_label="hi-sub", source="substring", confidence=0.95),
                _rec(normalized_label="lo-sub", source="substring", confidence=0.4),
                _rec(normalized_label="hi-llm", source="llm", confidence=0.9),
                _rec(normalized_label="lo-llm", source="llm", confidence=0.5),
            ]
        )
        try:
            rc, out = _run_review(
                fx,
                "--auto-accept-substring-above",
                "0.9",
                "--auto-reject-llm-below",
                "0.85",
                "--non-interactive",
            )
            self.assertEqual(rc, 0)
            self.assertIn("accepted=1", out)
            self.assertIn("rejected=1", out)
            self.assertEqual(
                {r["normalized_label"] for r in fx.read_accepted()},
                {"hi-sub"},
            )
            self.assertEqual(
                {r["normalized_label"] for r in fx.read_rejected()},
                {"lo-llm"},
            )
        finally:
            fx.cleanup()

    def test_filter_source_llm_only(self):
        fx = _ReviewFixture(
            [
                _rec(normalized_label="a", source="substring", confidence=0.99),
                _rec(normalized_label="b", source="llm", confidence=0.5),
            ]
        )
        try:
            rc, out = _run_review(
                fx,
                "--filter-source",
                "llm",
                "--auto-reject-llm-below",
                "0.85",
                "--non-interactive",
            )
            self.assertEqual(rc, 0)
            self.assertIn("rejected=1", out)
            self.assertIn("filtered=1", out)
            # Substring record was filtered (NOT accepted) despite high conf
            self.assertEqual(fx.read_accepted(), [])
        finally:
            fx.cleanup()

    def test_idempotent_rerun_changes_nothing(self):
        fx = _ReviewFixture(
            [
                _rec(normalized_label="a", source="substring", confidence=0.99),
            ]
        )
        try:
            _run_review(fx, "--auto-accept-substring-above", "0.9", "--non-interactive")
            len_before = len(fx.read_accepted())
            # Re-run: input file now has status="accepted", should be
            # already_done, no new output.
            rc, out = _run_review(
                fx,
                "--auto-accept-substring-above",
                "0.9",
                "--non-interactive",
            )
            self.assertEqual(rc, 0)
            self.assertEqual(len(fx.read_accepted()), len_before)
            self.assertIn("already_done=1", out)
            self.assertIn("accepted=0", out)
        finally:
            fx.cleanup()

    def test_dry_run_writes_no_files_and_no_status_flip(self):
        fx = _ReviewFixture(
            [
                _rec(normalized_label="a", source="substring", confidence=0.99),
            ]
        )
        try:
            rc, out = _run_review(
                fx,
                "--auto-accept-substring-above",
                "0.9",
                "--non-interactive",
                "--dry-run",
            )
            self.assertEqual(rc, 0)
            self.assertFalse(os.path.exists(fx.accepted_path))
            self.assertFalse(os.path.exists(fx.rejected_path))
            # Input file status untouched
            self.assertEqual(fx.read_input()[0]["status"], "open")
        finally:
            fx.cleanup()

    def test_display_shows_llm_fields_for_llm_records(self):
        """Regression-guard: pre-#102 cmd_review never showed source/model."""
        fx = _ReviewFixture(
            [
                _rec(
                    normalized_label="x",
                    source="llm",
                    confidence=0.7,
                    model="openai/gpt-5-mini",
                    prompt_hash="cafe1234dead",
                ),
            ]
        )
        try:
            rc, out = _run_review(
                fx,
                "--auto-reject-llm-below",
                "0.85",
                "--non-interactive",
            )
            self.assertEqual(rc, 0)
            self.assertIn("openai/gpt-5-mini", out)
            self.assertIn("cafe1234", out)
            self.assertIn("source=llm", out)
        finally:
            fx.cleanup()

    def test_missing_input_returns_1(self):
        fx = _ReviewFixture([])
        try:
            os.remove(fx.suggestions_path)
            rc, _ = _run_review(fx, "--non-interactive")
            self.assertEqual(rc, 1)
        finally:
            fx.cleanup()


if __name__ == "__main__":
    unittest.main(verbosity=2)
