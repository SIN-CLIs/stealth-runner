"""SR-49 / Issue #43 — Tests for survey.graph.promote.

Covers:
  T01  10x clean runs -> promoted, snapshot exists
  T02  Snapshot file has chmod 444 (POSIX only)
  T03  Snapshot content is byte-identical to source
  T04  Promotion log gets a JSONL entry with sha256
  T05  9 runs -> NOT promoted (insufficient count)
  T06  10 runs but one with consecutive_failures=3 -> NOT promoted
  T07  10 runs but one with errors!=[] -> NOT promoted
  T08  10 runs but one with balance_after == balance_before -> NOT promoted
  T09  Mixed clean/dirty runs: only clean ones count, dirty ones block
  T10  Two promotions in sequence produce two distinct snapshot files
  T11  load_runs_from_dir reads sorted *.json files
  T12  load_runs_from_dir skips malformed JSON without raising
  T13  CLI: --runs-dir + --graph-source + --compiled-dir + --log
        returns 0 on success
  T14  CLI returns 1 when criteria not met
"""

from __future__ import annotations

import datetime
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SURVEY_CLI_DIR = HERE.parent
if str(SURVEY_CLI_DIR) not in sys.path:
    sys.path.insert(0, str(SURVEY_CLI_DIR))

from survey.graph.promote import (  # noqa: E402
    REQUIRED_SUCCESSES,
    append_promotion_log,
    compile_snapshot,
    evaluate_runs,
    load_runs_from_dir,
    promote,
)


# ── Helpers ──────────────────────────────────────────────────────────────────


def clean_run(i: int = 0) -> dict:
    """Build a synthetic clean SurveyState dict."""
    return {
        "balance_before": 2.50,
        "balance_after": 2.50 + 0.50 * (i + 1),  # earned money
        "consecutive_failures": 0,
        "errors": [],
    }


def make_graph_source(tmp: Path) -> Path:
    """Synthesize a fake graph.py file inside ``tmp``."""
    src = tmp / "graph.py"
    src.write_text(
        "# fake graph definition for SR-49 tests\n"
        "def build_graph():\n"
        "    return None\n",
        encoding="utf-8",
    )
    return src


# ── T01-T04: Happy path ─────────────────────────────────────────────────────


class TestHappyPath(unittest.TestCase):

    def test_T01_10x_clean_runs_promote(self):
        runs = [clean_run(i) for i in range(REQUIRED_SUCCESSES)]
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            graph = make_graph_source(tmp)
            result = promote(
                runs, graph, tmp / "compiled", tmp / "logs.jsonl"
            )
            self.assertTrue(
                result.promoted, result.evaluation.blocking_reasons
            )
            self.assertIsNotNone(result.snapshot)
            self.assertTrue(result.snapshot.path.exists())

    def test_T02_snapshot_has_chmod_444(self):
        if os.name != "posix":
            self.skipTest("chmod test only on POSIX")
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            graph = make_graph_source(tmp)
            snap = compile_snapshot(graph, tmp / "compiled")
            mode_bits = snap.path.stat().st_mode & 0o777
            self.assertEqual(mode_bits, 0o444, f"got {oct(mode_bits)}")
            self.assertTrue(snap.chmod_applied)

    def test_T03_snapshot_is_byte_identical(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            graph = make_graph_source(tmp)
            source_bytes = graph.read_bytes()
            snap = compile_snapshot(graph, tmp / "compiled")
            snapshot_bytes = snap.path.read_bytes()
        self.assertEqual(source_bytes, snapshot_bytes)

    def test_T04_log_record_has_sha256(self):
        runs = [clean_run(i) for i in range(REQUIRED_SUCCESSES)]
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            graph = make_graph_source(tmp)
            log_path = tmp / "logs" / "graph-promotions.jsonl"
            result = promote(runs, graph, tmp / "compiled", log_path)
            self.assertTrue(result.promoted)
            content = log_path.read_text(encoding="utf-8").strip()
            record = json.loads(content)
            self.assertEqual(record["event"], "graph_promotion")
            self.assertEqual(
                record["snapshot"]["sha256"], result.snapshot.sha256
            )
            self.assertEqual(len(record["snapshot"]["sha256"]), 64)


# ── T05-T08: Criterion-blocked cases ────────────────────────────────────────


class TestBlockingCriteria(unittest.TestCase):

    def test_T05_only_9_runs_blocks(self):
        runs = [clean_run(i) for i in range(REQUIRED_SUCCESSES - 1)]
        ev = evaluate_runs(runs)
        self.assertFalse(ev.eligible)
        self.assertEqual(ev.n_successes, 9)
        self.assertTrue(any("need >=" in r for r in ev.blocking_reasons))

    def test_T06_delegated_run_blocks(self):
        runs = [clean_run(i) for i in range(REQUIRED_SUCCESSES)]
        runs[3]["consecutive_failures"] = 3  # delegated
        ev = evaluate_runs(runs)
        self.assertFalse(ev.eligible)
        self.assertTrue(
            any("delegated" in r for r in ev.blocking_reasons),
            ev.blocking_reasons,
        )

    def test_T07_unresolved_error_blocks(self):
        runs = [clean_run(i) for i in range(REQUIRED_SUCCESSES)]
        runs[5]["errors"] = [{"type": "TimeoutError", "where": "node_x"}]
        ev = evaluate_runs(runs)
        self.assertFalse(ev.eligible)
        self.assertTrue(
            any("unresolved error" in r for r in ev.blocking_reasons),
            ev.blocking_reasons,
        )

    def test_T08_zero_earnings_blocks(self):
        runs = [clean_run(i) for i in range(REQUIRED_SUCCESSES)]
        runs[7]["balance_after"] = runs[7]["balance_before"]
        ev = evaluate_runs(runs)
        self.assertFalse(ev.eligible)
        self.assertTrue(
            any("no net earnings" in r for r in ev.blocking_reasons),
            ev.blocking_reasons,
        )


# ── T09-T10: Edge cases ─────────────────────────────────────────────────────


class TestEdgeCases(unittest.TestCase):

    def test_T09_mixed_runs_block(self):
        """A single dirty run anywhere in the input blocks promotion."""
        runs = [clean_run(i) for i in range(REQUIRED_SUCCESSES + 5)]
        runs[12]["errors"] = [{"oops": True}]
        ev = evaluate_runs(runs)
        self.assertFalse(ev.eligible)
        # 15 input, 14 clean, 1 dirty
        self.assertEqual(ev.n_successes, REQUIRED_SUCCESSES + 4)

    def test_T10_two_promotions_produce_two_files(self):
        runs = [clean_run(i) for i in range(REQUIRED_SUCCESSES)]
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            graph = make_graph_source(tmp)
            compiled = tmp / "compiled"
            log = tmp / "logs.jsonl"

            t1 = datetime.datetime(
                2026, 5, 12, 10, 0, 0, tzinfo=datetime.timezone.utc
            )
            t2 = datetime.datetime(
                2026, 5, 12, 11, 0, 0, tzinfo=datetime.timezone.utc
            )
            r1 = promote(runs, graph, compiled, log, now=t1)
            r2 = promote(runs, graph, compiled, log, now=t2)

            self.assertTrue(r1.promoted)
            self.assertTrue(r2.promoted)
            self.assertNotEqual(r1.snapshot.path, r2.snapshot.path)
            # Both exist
            self.assertTrue(r1.snapshot.path.exists())
            self.assertTrue(r2.snapshot.path.exists())
            # Log has two records
            lines = [
                l for l in log.read_text(encoding="utf-8").splitlines()
                if l.strip()
            ]
            self.assertEqual(len(lines), 2)


# ── T11-T12: Loader helpers ─────────────────────────────────────────────────


class TestLoaders(unittest.TestCase):

    def test_T11_load_runs_from_dir_sorted(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            for i, run in enumerate(
                [clean_run(0), clean_run(1), clean_run(2)]
            ):
                (tmp / f"run-{i:03d}.json").write_text(json.dumps(run))
            loaded = load_runs_from_dir(tmp)
        self.assertEqual(len(loaded), 3)
        # Sorted by filename ascending -> first run has i=0
        self.assertAlmostEqual(loaded[0]["balance_after"], 3.00, places=2)
        self.assertAlmostEqual(loaded[2]["balance_after"], 4.00, places=2)

    def test_T12_load_runs_skips_malformed(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            (tmp / "good.json").write_text(json.dumps(clean_run()))
            (tmp / "bad.json").write_text("{ not valid json")
            loaded = load_runs_from_dir(tmp)
        self.assertEqual(len(loaded), 1)


# ── T13-T14: CLI subprocess ─────────────────────────────────────────────────


class TestCLI(unittest.TestCase):

    def _run_cli(self, *args, cwd):
        return subprocess.run(
            [sys.executable, "-m", "survey.graph.promote", *args],
            cwd=cwd, capture_output=True, text=True, timeout=30,
        )

    def test_T13_cli_returns_0_on_success(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            runs_dir = tmp / "runs"
            runs_dir.mkdir()
            for i in range(REQUIRED_SUCCESSES):
                (runs_dir / f"run-{i:03d}.json").write_text(
                    json.dumps(clean_run(i))
                )
            graph = make_graph_source(tmp)
            r = self._run_cli(
                "--runs-dir", str(runs_dir),
                "--graph-source", str(graph),
                "--compiled-dir", str(tmp / "compiled"),
                "--log", str(tmp / "logs.jsonl"),
                "--quiet",
                cwd=str(SURVEY_CLI_DIR),
            )
        self.assertEqual(
            r.returncode, 0,
            f"stdout={r.stdout}\nstderr={r.stderr}",
        )

    def test_T14_cli_returns_1_when_blocked(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            runs_dir = tmp / "runs"
            runs_dir.mkdir()
            # Only 3 runs -> blocked
            for i in range(3):
                (runs_dir / f"run-{i:03d}.json").write_text(
                    json.dumps(clean_run(i))
                )
            graph = make_graph_source(tmp)
            r = self._run_cli(
                "--runs-dir", str(runs_dir),
                "--graph-source", str(graph),
                "--compiled-dir", str(tmp / "compiled"),
                "--log", str(tmp / "logs.jsonl"),
                "--quiet",
                cwd=str(SURVEY_CLI_DIR),
            )
        self.assertEqual(r.returncode, 1)


# ── append_promotion_log direct test ────────────────────────────────────────


class TestAppendLog(unittest.TestCase):

    def test_append_log_creates_parent_dir(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            graph = make_graph_source(tmp)
            snap = compile_snapshot(graph, tmp / "compiled")
            log_path = tmp / "nested" / "subdir" / "promo.jsonl"
            append_promotion_log(log_path, snap)
            self.assertTrue(log_path.exists())
            record = json.loads(log_path.read_text(encoding="utf-8").strip())
            self.assertEqual(record["event"], "graph_promotion")


if __name__ == "__main__":
    unittest.main(verbosity=2)
