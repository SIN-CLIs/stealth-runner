"""SR-101: Self-tests for evals.learn_suggester.run_eval.

Validates the eval-harness itself (NOT the suggester quality — that's what
the harness measures, not what we test here):

  T01  golden-set is parseable + all expected_family values valid
  T02  validate_golden detects bogus expected_family (not in FAMILY_TOKENS)
  T03  validate_golden detects missing required fields
  T04  Phase 1 produces report with required schema fields
  T05  Phase 1 accuracy >= 0.65 on the shipped golden set
  T06  Phase 2 mock produces both phase1 and phase2 sections + lift field
  T07  Phase 2 mock accuracy > Phase 1 accuracy on shipped golden set
  T08  Mock LLM is deterministic (same input -> same output)
  T09  Threshold gate exits 1 with --exit-non-zero-on-threshold-miss + low min
  T10  Threshold gate exits 0 without --exit-non-zero-on-threshold-miss
  T11  Phase 2 without --mock/--live errors out with exit 2
  T12  Missing golden-set file exits with code 2 (config/IO error)
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
PARENT = os.path.dirname(HERE)
if PARENT not in sys.path:
    sys.path.insert(0, PARENT)

# Imports from the eval-harness under test
from evals.learn_suggester.run_eval import (  # noqa: E402
    DEFAULT_GOLDEN,
    _mock_call_llm,
    evaluate,
    load_golden,
    validate_golden,
)
from survey.learn.suggester import FAMILY_TOKENS  # noqa: E402


GOLDEN_PATH = DEFAULT_GOLDEN


class TestGoldenSet(unittest.TestCase):
    """T01-T03: golden-set parsing + validation."""

    def test_T01_golden_set_parseable_and_valid(self):
        records = load_golden(GOLDEN_PATH)
        self.assertGreaterEqual(len(records), 30,
                                "golden set too small")
        errs = validate_golden(records)
        self.assertEqual(errs, [],
                         "golden set has validation errors")

        # Every expected_family must be in FAMILY_TOKENS or None
        for r in records:
            self.assertIn(r["expected_family"],
                          set(FAMILY_TOKENS.keys()) | {None})

        # Every family must have at least 1 positive entry
        seen = {r["expected_family"] for r in records}
        for fam in FAMILY_TOKENS.keys():
            self.assertIn(fam, seen, f"family {fam!r} not covered")

        # There must be at least some negatives
        negatives = sum(1 for r in records if r["expected_family"] is None)
        self.assertGreaterEqual(negatives, 5,
                                "need at least 5 negative records")

    def test_T02_validate_golden_rejects_invalid_family(self):
        bad = [{
            "label": "x", "role": "textbox",
            "expected_family": "DOES_NOT_EXIST",
            "lang": "de", "notes": "",
        }]
        errs = validate_golden(bad)
        self.assertTrue(any("DOES_NOT_EXIST" in e for e in errs),
                        f"expected DOES_NOT_EXIST in errors: {errs}")

    def test_T03_validate_golden_rejects_missing_fields(self):
        bad = [{"label": "x"}]
        errs = validate_golden(bad)
        self.assertTrue(any("missing" in e for e in errs))


class TestPhase1(unittest.TestCase):
    """T04-T05: Phase 1 eval."""

    def setUp(self):
        self.records = load_golden(GOLDEN_PATH)

    def test_T04_phase1_report_has_required_schema(self):
        report = evaluate(self.records, phase=1, use_mock=False)
        for key in [
            "schema_version", "phase", "mode", "timestamp",
            "total", "phase1_correct", "phase1_accuracy",
            "phase1_per_family", "phase1_confusion_top5", "items",
        ]:
            self.assertIn(key, report, f"missing key {key!r}")
        self.assertEqual(report["phase"], 1)
        self.assertEqual(report["mode"], "heuristic")
        self.assertEqual(report["total"], len(self.records))
        self.assertIsInstance(report["phase1_accuracy"], float)
        self.assertGreaterEqual(report["phase1_accuracy"], 0.0)
        self.assertLessEqual(report["phase1_accuracy"], 1.0)

    def test_T05_phase1_accuracy_meets_threshold(self):
        """Phase 1 must >= 0.65 on shipped golden set (eval is healthy)."""
        report = evaluate(self.records, phase=1, use_mock=False)
        self.assertGreaterEqual(
            report["phase1_accuracy"], 0.65,
            f"Phase 1 accuracy {report['phase1_accuracy']} "
            f"is below 0.65 threshold — heuristic regression?",
        )


class TestPhase2Mock(unittest.TestCase):
    """T06-T08: Phase 2 with mock LLM engine."""

    def setUp(self):
        self.records = load_golden(GOLDEN_PATH)

    def test_T06_phase2_report_has_phase2_fields(self):
        report = evaluate(self.records, phase=2, use_mock=True)
        for key in [
            "phase2_correct", "phase2_accuracy", "phase2_lift",
            "phase2_per_family", "phase2_confusion_top5",
        ]:
            self.assertIn(key, report, f"missing key {key!r}")
        self.assertEqual(report["phase"], 2)
        self.assertEqual(report["mode"], "mock")

    def test_T07_phase2_mock_beats_phase1(self):
        """Phase 2 mock should out-perform Phase 1 on shipped golden set.

        Demonstrates that the mock-engine validates a meaningful pipeline
        — Phase 2 contributes signal beyond what Phase 1 catches.
        """
        report = evaluate(self.records, phase=2, use_mock=True)
        self.assertGreater(
            report["phase2_accuracy"], report["phase1_accuracy"],
            f"phase2_lift={report['phase2_lift']} — mock engine "
            f"failed to beat heuristic; pipeline may be broken",
        )

    def test_T08_mock_llm_deterministic(self):
        """Same prompt MUST yield the same response (no randomness, no I/O)."""
        prompt = (
            "Classify the German/English survey question label below into "
            "EXACTLY ONE of the listed profile families. If NONE fits, return "
            "family=null.\n\nLabel: 'Mobilnummer'\n\nFamilies:\n  - phone\n"
        )
        r1 = _mock_call_llm(prompt)
        r2 = _mock_call_llm(prompt)
        self.assertEqual(r1.content, r2.content)
        self.assertEqual(r1.model, r2.model)
        self.assertEqual(r1.prompt_hash, r2.prompt_hash)
        # And the content actually classifies as 'phone'
        parsed = json.loads(r1.content)
        self.assertEqual(parsed["family"], "phone")


class TestCLI(unittest.TestCase):
    """T09-T12: CLI entry-point behavior."""

    def _run(self, *args, cwd=None) -> subprocess.CompletedProcess:
        """Run run_eval CLI as subprocess, return result with exit code."""
        return subprocess.run(
            [sys.executable, "-m", "evals.learn_suggester.run_eval", *args],
            cwd=cwd or PARENT,
            capture_output=True, text=True, timeout=60,
        )

    def test_T09_threshold_gate_exit_1_when_below(self):
        with tempfile.TemporaryDirectory() as d:
            report = os.path.join(d, "rep.json")
            r = self._run(
                "--phase", "1",
                "--min-phase1-accuracy", "0.999",
                "--exit-non-zero-on-threshold-miss",
                "--report", report, "--quiet",
            )
            self.assertEqual(
                r.returncode, 1,
                f"expected exit 1, got {r.returncode}\n"
                f"stdout={r.stdout}\nstderr={r.stderr}",
            )
            self.assertIn("THRESHOLD MISS", r.stderr)

    def test_T10_threshold_gate_exit_0_without_flag(self):
        """Without --exit-non-zero-on-threshold-miss, still exit 0."""
        with tempfile.TemporaryDirectory() as d:
            report = os.path.join(d, "rep.json")
            r = self._run(
                "--phase", "1",
                "--min-phase1-accuracy", "0.999",
                "--report", report, "--quiet",
            )
            self.assertEqual(r.returncode, 0,
                             f"stdout={r.stdout}\nstderr={r.stderr}")
            # But warning still on stderr
            self.assertIn("THRESHOLD MISS", r.stderr)

    def test_T11_phase2_without_mode_exits_2(self):
        with tempfile.TemporaryDirectory() as d:
            r = self._run(
                "--phase", "2",
                "--report", os.path.join(d, "rep.json"),
                "--quiet",
            )
            self.assertEqual(r.returncode, 2,
                             f"stderr={r.stderr}")
            self.assertIn("requires either --mock or --live", r.stderr)

    def test_T12_missing_golden_exits_2(self):
        with tempfile.TemporaryDirectory() as d:
            r = self._run(
                "--phase", "1",
                "--golden", os.path.join(d, "nonexistent.jsonl"),
                "--report", os.path.join(d, "rep.json"),
                "--quiet",
            )
            self.assertEqual(r.returncode, 2)
            self.assertIn("ERROR loading golden set", r.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
