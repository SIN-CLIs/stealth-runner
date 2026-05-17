"""SR-240: Trajectory eval harness for the survey-graph end-to-end loop.

================================================================================
PURPOSE
================================================================================

Drive a frozen golden set of completed-and-attempted survey trajectories
through `survey.reliability.trajectory_judge.TrajectoryJudge` with a
deterministic mock LLM backend, aggregate the four canonical scores
(compliance / efficiency / accuracy / coherence), and gate the build on
configured thresholds.

This is the third eval harness in the codebase (after `match_field` and
`learn_suggester`). It follows the SAME contract:

  1. Frozen golden JSONL — golden updates only via PR review.
  2. Deterministic mock backend usable from CI without API keys / network.
  3. Threshold gates that exit non-zero on regression.
  4. JSON report on disk for retro / dashboards.

================================================================================
WHY A MOCK BACKEND IS THE RIGHT THING IN CI
================================================================================

The real Judge calls a frontier LLM (gpt-4o-mini-class). On every PR that
would burn tokens AND non-determinism — a model upgrade or a temperature
glitch could turn the eval red without any code change in this repo.

Instead we substitute a `RuleBasedJudgeBackend` that scores trajectories
by deterministic heuristics:

  - compliance ↑ when no_dom_change rate is low and no `human_delegate`
    in the trail
  - efficiency ↑ when the iteration count is close to the action count
    (no idle waits / no excessive retries)
  - accuracy ↑ when the expected_outcome matches detect_completion's
    final outcome and no qualification-block events appear
  - coherence ↑ when iteration numbers are monotonically increasing and
    actions follow a plausible click→fill→click pattern

The mock is regression-sensitive: if someone ships a buggy PR that adds
junk events to the trajectory shape, the eval will see lower scores and
fail. The mock is NOT a quality measurement of the real LLM Judge — that
is what `--live` mode is for, gated behind workflow_dispatch.

================================================================================
USAGE
================================================================================

From the survey-cli/ directory:

    # Default: deterministic mock, fail on threshold miss.
    python -m evals.trajectory.run_eval

    # Strict mode (per-trajectory min_score >= threshold):
    python -m evals.trajectory.run_eval --threshold 0.65 --per-trajectory

    # Live mode (real LLM, only on workflow_dispatch):
    python -m evals.trajectory.run_eval --live

EXIT CODES
----------
  0  All thresholds met.
  1  At least one threshold missed (regression).
  2  Config / IO error (e.g. golden file missing).

CI RUNS THIS WITH `--exit-non-zero-on-threshold-miss` (the default).
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence

# Allow `python -m evals.trajectory.run_eval` AND
# `python evals/trajectory/run_eval.py`.
_HERE = Path(__file__).resolve().parent
_SURVEY_CLI_DIR = _HERE.parent.parent
if str(_SURVEY_CLI_DIR) not in sys.path:
    sys.path.insert(0, str(_SURVEY_CLI_DIR))

from survey.reliability.trajectory_judge import (  # noqa: E402
    JudgeConfig,
    JudgeError,
    JudgeScoreCard,
    SCORE_FIELDS,
    TrajectoryJudge,
)


# ── PATHS / DEFAULTS ─────────────────────────────────────────────────────────


DEFAULT_GOLDEN = _HERE / "trajectories.golden.jsonl"
DEFAULT_REPORT = _HERE / "last-report.json"

# Aggregate-mean threshold across the entire corpus. Tuned on the bundled
# 10 golden trajectories: a clean run scores ~0.85, a fully degraded run
# scores ~0.30 — 0.65 sits comfortably in the regression-detect band.
DEFAULT_AGGREGATE_THRESHOLD = 0.65

# Per-trajectory minimum: any single trajectory whose min(scores) drops
# below this is reported as a regression candidate. Off by default
# because the mock backend can produce one low score on screen-outs by
# design (efficiency punishes early termination).
DEFAULT_PER_TRAJECTORY_THRESHOLD = 0.45


# ── PROMPT (mock-only; real Judge loads from prompts/trajectory_audit.txt) ───


_MOCK_PROMPT = (
    "Synthetic prompt for the deterministic mock backend. Real-Judge "
    "callers use load_default_prompt() from trajectory_judge instead."
)


# ── DETERMINISTIC MOCK BACKEND ───────────────────────────────────────────────


class RuleBasedJudgeBackend:
    """Deterministic LLM substitute that scores by trajectory shape.

    The four scores are computed from observable trajectory features so
    a regression in the graph's behaviour (more retries, mis-routed
    completion, qualification blocks slipping through) shifts the score
    in a predictable direction. Tests pin the exact arithmetic.
    """

    def __init__(self, gold_outcome: str | None = None) -> None:
        self.gold_outcome = gold_outcome or ""

    def __call__(self, prompt: str) -> str:
        # The injected prompt body is `<system>\n\n---\nTRAJECTORY (JSON):\n[...]`.
        # Extract the JSON tail.
        marker = "TRAJECTORY (JSON):\n"
        idx = prompt.find(marker)
        if idx < 0:
            return _scored_response(0.5, 0.5, 0.5, 0.5, "no trajectory in prompt")
        tail = prompt[idx + len(marker) :].strip()
        try:
            trajectory = json.loads(tail)
        except json.JSONDecodeError:
            return _scored_response(0.4, 0.4, 0.4, 0.4, "unparseable JSON tail")

        scores = _score_trajectory(trajectory, self.gold_outcome)
        return _scored_response(
            scores["compliance"],
            scores["efficiency"],
            scores["accuracy"],
            scores["coherence"],
            scores["rationale"],
        )


def _scored_response(
    compliance: float,
    efficiency: float,
    accuracy: float,
    coherence: float,
    rationale: str,
) -> str:
    return json.dumps(
        {
            "compliance": _clamp(compliance),
            "efficiency": _clamp(efficiency),
            "accuracy": _clamp(accuracy),
            "coherence": _clamp(coherence),
            "rationale": rationale[:200],
        }
    )


def _clamp(x: float) -> float:
    if x < 0.0:
        return 0.0
    if x > 1.0:
        return 1.0
    return float(x)


def _score_trajectory(
    trajectory: Sequence[dict[str, Any]],
    gold_outcome: str,
) -> dict[str, Any]:
    """Pure heuristic scorer — kept here so unit tests can exercise it
    without an LLM call.

    The four signals correspond to the four canonical Judge dimensions:

    - compliance: rate of `no_dom_change == False` clicks and absence of
      delegated/human_delegate steps.
    - efficiency: 1 - (retries / total_decide_steps). Capped to [0, 1].
    - accuracy: did the trail end with the expected outcome and no
      qualification-block telemetry?
    - coherence: are iteration numbers strictly non-decreasing, and is
      the final node a recognised terminal node?
    """
    if not trajectory:
        return {
            "compliance": 0.0,
            "efficiency": 0.0,
            "accuracy": 0.0,
            "coherence": 0.0,
            "rationale": "empty trajectory",
        }

    decide_steps = [s for s in trajectory if s.get("node") == "decide"]
    total_decide = max(1, len(decide_steps))
    no_dom_change_steps = sum(1 for s in decide_steps if s.get("no_dom_change"))
    failed_steps = sum(1 for s in decide_steps if s.get("success") is False)
    retried_steps = sum(1 for s in decide_steps if s.get("attempts", 1) > 1)
    delegated_count = sum(1 for s in trajectory if s.get("node") == "human_delegate")
    qualif_blocks = sum(
        1 for s in trajectory if "qualification_block" in (s.get("event") or "")
    )

    # Compliance: penalise failed clicks and any human_delegate jump.
    compliance = 1.0 - (failed_steps / total_decide) * 0.6 - (delegated_count * 0.4)

    # Efficiency: penalise retries.
    efficiency = 1.0 - (retried_steps / total_decide) * 0.5 - (no_dom_change_steps / total_decide) * 0.4

    # Accuracy: did we end where we should?
    final = trajectory[-1]
    final_outcome = (final.get("outcome") or "").strip()
    if gold_outcome and final_outcome:
        accuracy_match = 1.0 if final_outcome == gold_outcome else 0.3
    else:
        # No gold ground-truth → reward "completed" outcomes neutrally,
        # punish errors.
        accuracy_match = (
            0.85 if final_outcome == "completed"
            else 0.6 if final_outcome == "screen_out"
            else 0.4
        )
    accuracy = accuracy_match - (qualif_blocks * 0.2)

    # Coherence: iteration numbers monotonic, terminal node sane.
    iters = [s.get("iteration", 0) for s in trajectory if "iteration" in s]
    monotonic = all(b >= a for a, b in zip(iters, iters[1:]))
    terminal_ok = final.get("node") in {"detect_completion", "human_delegate"}
    coherence = (0.7 if monotonic else 0.4) + (0.3 if terminal_ok else 0.0)

    rationale = (
        f"decide_steps={total_decide}, failed={failed_steps}, retries={retried_steps}, "
        f"no_dom_change={no_dom_change_steps}, delegated={delegated_count}, "
        f"qualif_blocks={qualif_blocks}, final={final.get('node')}/{final_outcome!r}, "
        f"monotonic={monotonic}"
    )

    return {
        "compliance": compliance,
        "efficiency": efficiency,
        "accuracy": accuracy,
        "coherence": coherence,
        "rationale": rationale,
    }


# ── HARNESS ──────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class TrajectoryRecord:
    """One golden record loaded from `trajectories.golden.jsonl`."""

    record_id: str
    provider: str
    expected_outcome: str
    trajectory: list[dict[str, Any]]


@dataclass
class _AggregateReport:
    per_record: list[dict[str, Any]] = field(default_factory=list)
    threshold: float = DEFAULT_AGGREGATE_THRESHOLD
    per_trajectory_threshold: float = 0.0  # 0 = disabled
    aggregate_mean: dict[str, float] = field(default_factory=dict)
    overall_mean: float = 0.0
    threshold_pass: bool = False
    per_trajectory_violations: list[str] = field(default_factory=list)
    backend: str = "mock"
    started_at: str = ""
    finished_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "backend": self.backend,
            "threshold": self.threshold,
            "per_trajectory_threshold": self.per_trajectory_threshold,
            "aggregate_mean": self.aggregate_mean,
            "overall_mean": self.overall_mean,
            "threshold_pass": self.threshold_pass,
            "per_trajectory_violations": self.per_trajectory_violations,
            "per_record_count": len(self.per_record),
            "per_record": self.per_record,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
        }


def load_golden(path: Path) -> list[TrajectoryRecord]:
    """Read the JSONL golden file. Raises FileNotFoundError if missing."""
    records: list[TrajectoryRecord] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        obj = json.loads(line)
        records.append(
            TrajectoryRecord(
                record_id=str(obj.get("id") or ""),
                provider=str(obj.get("provider") or ""),
                expected_outcome=str(obj.get("expected_outcome") or ""),
                trajectory=list(obj.get("trajectory") or []),
            )
        )
    if not records:
        raise ValueError(f"golden file is empty: {path}")
    return records


def run_eval(
    golden_path: Path = DEFAULT_GOLDEN,
    *,
    aggregate_threshold: float = DEFAULT_AGGREGATE_THRESHOLD,
    per_trajectory_threshold: float = 0.0,
    backend_name: str = "mock",
    judge_factory=None,
) -> _AggregateReport:
    """Run the full eval and return an aggregate report.

    Args:
        golden_path: JSONL file path, see DEFAULT_GOLDEN.
        aggregate_threshold: minimum overall mean across all trajectories.
        per_trajectory_threshold: if > 0, every trajectory must clear this
            on min(scores). Off by default — screen-outs naturally score
            lower on efficiency.
        backend_name: tag in the report (mock | live).
        judge_factory: callable (TrajectoryRecord) -> TrajectoryJudge for
            tests that want to inject behaviour. Defaults to a per-record
            rule-based judge.

    Returns:
        _AggregateReport. Caller decides exit code based on .threshold_pass.
    """
    started = _dt.datetime.now(_dt.timezone.utc).isoformat()
    records = load_golden(golden_path)

    per_record: list[dict[str, Any]] = []
    field_totals = {f: 0.0 for f in SCORE_FIELDS}
    n = 0
    violations: list[str] = []

    for rec in records:
        judge = judge_factory(rec) if judge_factory else _default_judge(rec)
        try:
            card = judge.audit(rec.trajectory)
        except JudgeError as exc:
            per_record.append(
                {
                    "id": rec.record_id,
                    "provider": rec.provider,
                    "expected_outcome": rec.expected_outcome,
                    "error": f"{type(exc).__name__}: {exc}",
                    "scores": None,
                    "min_score": 0.0,
                }
            )
            violations.append(rec.record_id)
            continue

        scores = card.to_dict()
        for f in SCORE_FIELDS:
            field_totals[f] += float(scores[f])
        n += 1

        per_record.append(
            {
                "id": rec.record_id,
                "provider": rec.provider,
                "expected_outcome": rec.expected_outcome,
                "scores": {f: scores[f] for f in SCORE_FIELDS},
                "rationale": scores.get("rationale", "")[:240],
                "min_score": card.min_score(),
                "mean_score": card.mean_score(),
            }
        )
        if per_trajectory_threshold > 0 and card.min_score() < per_trajectory_threshold:
            violations.append(rec.record_id)

    aggregate_mean = {f: field_totals[f] / n if n else 0.0 for f in SCORE_FIELDS}
    overall_mean = sum(aggregate_mean.values()) / len(SCORE_FIELDS) if aggregate_mean else 0.0
    aggregate_pass = overall_mean >= aggregate_threshold
    per_traj_pass = (
        per_trajectory_threshold <= 0.0 or not violations
    )
    threshold_pass = aggregate_pass and per_traj_pass

    return _AggregateReport(
        per_record=per_record,
        threshold=aggregate_threshold,
        per_trajectory_threshold=per_trajectory_threshold,
        aggregate_mean=aggregate_mean,
        overall_mean=overall_mean,
        threshold_pass=threshold_pass,
        per_trajectory_violations=violations,
        backend=backend_name,
        started_at=started,
        finished_at=_dt.datetime.now(_dt.timezone.utc).isoformat(),
    )


def _default_judge(rec: TrajectoryRecord) -> TrajectoryJudge:
    """Build a Judge wired to the deterministic mock backend, scoped to
    the gold expected_outcome of this record."""
    backend = RuleBasedJudgeBackend(gold_outcome=rec.expected_outcome)
    return TrajectoryJudge(
        llm_callable=backend,
        prompt=_MOCK_PROMPT,
        config=JudgeConfig(require_rationale=True),
        model_name=f"mock-rulebased[{rec.provider}]",
    )


# ── REPORT WRITER + CLI ──────────────────────────────────────────────────────


def write_report(report: _AggregateReport, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(report.to_dict(), indent=2, sort_keys=True), encoding="utf-8")


def _print_summary(report: _AggregateReport) -> None:
    print("=" * 72)
    print("trajectory eval summary")
    print("=" * 72)
    print(f"backend             {report.backend}")
    print(f"records audited     {len(report.per_record)}")
    print(f"aggregate threshold {report.threshold:.3f}")
    print(f"overall mean        {report.overall_mean:.3f}  "
          f"({'PASS' if report.threshold_pass else 'FAIL'})")
    for f, v in report.aggregate_mean.items():
        print(f"  {f:11s}      {v:.3f}")
    if report.per_trajectory_threshold > 0:
        print(f"per-trajectory min  {report.per_trajectory_threshold:.3f}")
    if report.per_trajectory_violations:
        print(f"violations          {report.per_trajectory_violations}")
    print("=" * 72)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument(
        "--golden",
        default=str(DEFAULT_GOLDEN),
        help=f"Path to JSONL golden set (default: {DEFAULT_GOLDEN})",
    )
    parser.add_argument(
        "--report",
        default=str(DEFAULT_REPORT),
        help=f"Where to write the JSON report (default: {DEFAULT_REPORT})",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=DEFAULT_AGGREGATE_THRESHOLD,
        help=f"Aggregate-mean threshold (default: {DEFAULT_AGGREGATE_THRESHOLD})",
    )
    parser.add_argument(
        "--per-trajectory",
        action="store_true",
        help="Also enforce a per-trajectory min-score gate.",
    )
    parser.add_argument(
        "--per-trajectory-threshold",
        type=float,
        default=DEFAULT_PER_TRAJECTORY_THRESHOLD,
        help=(
            "Min(scores) any single trajectory must clear when "
            "--per-trajectory is set "
            f"(default: {DEFAULT_PER_TRAJECTORY_THRESHOLD})"
        ),
    )
    parser.add_argument(
        "--exit-non-zero-on-threshold-miss",
        action="store_true",
        default=True,
        help="(default true) exit code 1 on threshold miss; --no-exit-non-zero to disable.",
    )
    parser.add_argument(
        "--no-exit-non-zero-on-threshold-miss",
        dest="exit_non_zero_on_threshold_miss",
        action="store_false",
        help="Always exit 0 even on threshold miss (advisory mode).",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="UNUSED in this PR — wired for SR-241 live judge integration.",
    )
    args = parser.parse_args(argv)

    golden_path = Path(args.golden)
    if not golden_path.is_file():
        sys.stderr.write(f"golden file not found: {golden_path}\n")
        return 2

    if args.live:
        # SR-241 will land the live judge wiring. Until then we refuse
        # the flag explicitly so a CI misconfig cannot silently degrade
        # to mock and pass when it should not.
        sys.stderr.write(
            "--live is not implemented yet (planned: SR-241). "
            "Run without --live for the deterministic mock evaluator.\n"
        )
        return 2

    report = run_eval(
        golden_path,
        aggregate_threshold=args.threshold,
        per_trajectory_threshold=(
            args.per_trajectory_threshold if args.per_trajectory else 0.0
        ),
        backend_name="mock",
    )

    write_report(report, Path(args.report))
    _print_summary(report)

    if not report.threshold_pass and args.exit_non_zero_on_threshold_miss:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
