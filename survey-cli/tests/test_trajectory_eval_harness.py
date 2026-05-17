"""Tests for evals.trajectory.run_eval (SR-240).

Scope: pin the deterministic mock backend's scoring rules and the
harness orchestration. We do NOT exercise the real LLM Judge here —
that's covered by `test_trajectory_judge.py`.

These tests are the regression seatbelt for the CI gate. If anyone
weakens the threshold or changes the rule-based heuristic in a way
that makes a regressed graph pass, one of these tests fails first.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


from evals.trajectory.run_eval import (
    DEFAULT_AGGREGATE_THRESHOLD,
    DEFAULT_GOLDEN,
    RuleBasedJudgeBackend,
    TrajectoryRecord,
    _score_trajectory,
    load_golden,
    main,
    run_eval,
)


class TestRuleBasedScoring(unittest.TestCase):
    """Pin the heuristic so a future PR cannot silently relax it."""

    def test_clean_completed_run_scores_high(self) -> None:
        traj = [
            {"node": "open_survey", "action": "navigate", "success": True,
             "no_dom_change": False, "iteration": 0},
            {"node": "decide", "stable_id": "a", "action": "click",
             "success": True, "no_dom_change": False, "iteration": 1},
            {"node": "decide", "stable_id": "b", "action": "fill",
             "success": True, "no_dom_change": False, "iteration": 2},
            {"node": "detect_completion", "outcome": "completed",
             "success": True, "iteration": 3},
        ]
        s = _score_trajectory(traj, gold_outcome="completed")
        self.assertGreaterEqual(s["compliance"], 0.95)
        self.assertGreaterEqual(s["efficiency"], 0.95)
        self.assertGreaterEqual(s["accuracy"], 0.95)
        self.assertGreaterEqual(s["coherence"], 0.95)

    def test_retries_drag_efficiency_down(self) -> None:
        traj = [
            {"node": "decide", "action": "click", "success": False,
             "no_dom_change": True, "iteration": 1},
            {"node": "decide", "action": "click", "success": True,
             "no_dom_change": False, "iteration": 2, "attempts": 2},
            {"node": "detect_completion", "outcome": "completed",
             "iteration": 3, "success": True},
        ]
        s = _score_trajectory(traj, gold_outcome="completed")
        # Compliance MUST take a hit because step 1 failed.
        self.assertLess(s["compliance"], 1.0)
        # Efficiency MUST take a hit because step 2 retried.
        self.assertLess(s["efficiency"], 1.0)

    def test_human_delegate_punishes_compliance_hard(self) -> None:
        traj = [
            {"node": "decide", "action": "click", "success": True,
             "iteration": 1, "no_dom_change": False},
            {"node": "human_delegate", "iteration": 2},
        ]
        s = _score_trajectory(traj, gold_outcome="completed")
        # Single delegated step shaves 0.4 off compliance.
        self.assertLess(s["compliance"], 0.7)

    def test_outcome_mismatch_drops_accuracy(self) -> None:
        traj = [
            {"node": "decide", "action": "click", "success": True,
             "no_dom_change": False, "iteration": 1},
            {"node": "detect_completion", "outcome": "screen_out",
             "success": True, "iteration": 2},
        ]
        # Gold says completed; we got screen_out → accuracy = 0.3.
        s = _score_trajectory(traj, gold_outcome="completed")
        self.assertLess(s["accuracy"], 0.5)

    def test_qualification_block_event_punishes_accuracy(self) -> None:
        traj = [
            {"node": "decide", "action": "click", "success": True,
             "no_dom_change": False, "iteration": 1},
            {"node": "decide", "event": "qualification_block",
             "iteration": 2, "success": True, "no_dom_change": False},
            {"node": "detect_completion", "outcome": "completed",
             "iteration": 3, "success": True},
        ]
        s = _score_trajectory(traj, gold_outcome="completed")
        # Two qualification-block hits would zero accuracy out; one shaves 0.2.
        self.assertLess(s["accuracy"], 1.0)

    def test_non_monotonic_iterations_drop_coherence(self) -> None:
        traj = [
            {"node": "decide", "iteration": 5, "success": True,
             "no_dom_change": False, "action": "click"},
            {"node": "decide", "iteration": 1, "success": True,
             "no_dom_change": False, "action": "click"},
            {"node": "detect_completion", "outcome": "completed",
             "iteration": 2, "success": True},
        ]
        s = _score_trajectory(traj, gold_outcome="completed")
        # Coherence gets the "non-monotonic" penalty (0.4 base + 0.3 terminal).
        self.assertLess(s["coherence"], 0.85)


class TestRuleBasedBackendIO(unittest.TestCase):
    def test_backend_emits_strict_judge_compatible_json(self) -> None:
        backend = RuleBasedJudgeBackend(gold_outcome="completed")
        traj = [
            {"node": "decide", "action": "click", "success": True,
             "no_dom_change": False, "iteration": 1},
            {"node": "detect_completion", "outcome": "completed",
             "success": True, "iteration": 2},
        ]
        prompt = (
            "system\n\n---\nTRAJECTORY (JSON):\n"
            + json.dumps(traj)
            + "\n"
        )
        raw = backend(prompt)
        parsed = json.loads(raw)
        for f in ("compliance", "efficiency", "accuracy", "coherence", "rationale"):
            self.assertIn(f, parsed)
        for f in ("compliance", "efficiency", "accuracy", "coherence"):
            self.assertGreaterEqual(parsed[f], 0.0)
            self.assertLessEqual(parsed[f], 1.0)

    def test_backend_handles_corrupt_prompt_gracefully(self) -> None:
        backend = RuleBasedJudgeBackend(gold_outcome="completed")
        raw = backend("totally not a Judge prompt")
        parsed = json.loads(raw)
        # Falls back to mid-band scores rather than crashing.
        self.assertEqual(set(parsed.keys()), {"compliance", "efficiency",
                                              "accuracy", "coherence",
                                              "rationale"})


# ── Harness orchestration ─────────────────────────────────────────────────────


class TestRunEval(unittest.TestCase):
    def test_default_golden_passes_aggregate_threshold(self) -> None:
        """The bundled golden set is supposed to be a regression seatbelt
        for the CURRENT graph. If this test fails, either the heuristic
        was relaxed (bug) or the golden set drifted (please update it
        with explicit reasoning in the PR description)."""
        report = run_eval(DEFAULT_GOLDEN, aggregate_threshold=DEFAULT_AGGREGATE_THRESHOLD)
        self.assertTrue(report.threshold_pass)
        self.assertGreaterEqual(report.overall_mean, DEFAULT_AGGREGATE_THRESHOLD)
        # Every record must contribute scores; no JudgeError surprises.
        for rec in report.per_record:
            self.assertIsNone(rec.get("error"))

    def test_violation_when_threshold_set_too_high(self) -> None:
        report = run_eval(DEFAULT_GOLDEN, aggregate_threshold=0.999)
        self.assertFalse(report.threshold_pass)

    def test_per_trajectory_gate_off_by_default(self) -> None:
        report = run_eval(DEFAULT_GOLDEN, aggregate_threshold=0.0)
        self.assertEqual(report.per_trajectory_violations, [])
        self.assertEqual(report.per_trajectory_threshold, 0.0)

    def test_per_trajectory_gate_catches_low_outliers(self) -> None:
        # Set the gate above the score the rule-based backend gives a
        # screen-out. There is exactly one screen-out in the bundled
        # corpus where efficiency drops below 0.6 due to the early
        # detect_completion. We assert the violation list is non-empty.
        report = run_eval(
            DEFAULT_GOLDEN,
            aggregate_threshold=0.0,
            per_trajectory_threshold=0.99,  # absurdly high to force a hit
        )
        self.assertFalse(report.threshold_pass)
        self.assertTrue(report.per_trajectory_violations)

    def test_main_returns_zero_on_pass(self) -> None:
        rc = main([
            "--threshold", "0.50",
            "--report", str(Path(_temp_dir(self)) / "report.json"),
        ])
        self.assertEqual(rc, 0)

    def test_main_returns_one_on_threshold_miss(self) -> None:
        rc = main([
            "--threshold", "0.999",
            "--report", str(Path(_temp_dir(self)) / "report.json"),
        ])
        self.assertEqual(rc, 1)

    def test_main_returns_two_on_missing_golden(self) -> None:
        rc = main(["--golden", "/nonexistent/path.jsonl"])
        self.assertEqual(rc, 2)

    def test_main_refuses_live_until_sr241(self) -> None:
        rc = main(["--live"])
        self.assertEqual(rc, 2)

    def test_report_file_is_written_and_well_formed(self) -> None:
        out = Path(_temp_dir(self)) / "report.json"
        rc = main(["--threshold", "0.50", "--report", str(out)])
        self.assertEqual(rc, 0)
        body = json.loads(out.read_text(encoding="utf-8"))
        self.assertIn("aggregate_mean", body)
        self.assertIn("per_record", body)
        self.assertEqual(body["backend"], "mock")
        self.assertGreater(body["per_record_count"], 0)


class TestLoadGolden(unittest.TestCase):
    def test_skips_blank_and_comment_lines(self) -> None:
        with TemporaryDirectory() as tmp:
            p = Path(tmp) / "g.jsonl"
            p.write_text(
                "\n# comment line\n"
                + json.dumps({
                    "id": "a",
                    "provider": "x",
                    "expected_outcome": "completed",
                    "trajectory": [{"node": "decide", "iteration": 1,
                                     "success": True, "no_dom_change": False,
                                     "action": "click"}],
                }) + "\n",
                encoding="utf-8",
            )
            recs = load_golden(p)
            self.assertEqual(len(recs), 1)
            self.assertIsInstance(recs[0], TrajectoryRecord)

    def test_empty_file_raises(self) -> None:
        with TemporaryDirectory() as tmp:
            p = Path(tmp) / "g.jsonl"
            p.write_text("\n# only comments\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                load_golden(p)


def _temp_dir(test: unittest.TestCase) -> str:
    tmp = TemporaryDirectory()
    test.addCleanup(tmp.cleanup)
    return tmp.name


if __name__ == "__main__":
    unittest.main()
