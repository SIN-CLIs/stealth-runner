"""SR-49 / Issue #43 — Graph compiled promotion after 10x success.

================================================================================
PURPOSE
================================================================================

After 10 consecutive successful survey runs, freeze the current LangGraph
definition (``survey/graph/graph.py``) as a versioned, read-only artifact
(``survey/graph/compiled/survey_graph_v<TIMESTAMP>.py``, chmod 444) and
append a record to ``logs/graph-promotions.jsonl``.

This is the "production-replay" mechanism: once a graph configuration has
proven itself with 10 clean runs, the exact source is captured so future
replays can run against the *exact* code that earned the money, even if
the live ``graph.py`` evolves afterwards.

================================================================================
PROMOTION CRITERIA (all three must hold)
================================================================================

  C1  >= 10 runs in the window where ``balance_after > balance_before``
      (i.e. real earnings, not zero-balance no-ops).
  C2  Across those runs, ``consecutive_failures < 3`` for every record
      (i.e. no run was delegated to a human / opencode CLI).
  C3  Across those runs, ``errors == []`` for every record
      (no unresolved exceptions in any state).

If any criterion fails, the function returns the list of reasons and does
NOT promote.

================================================================================
DESIGN
================================================================================

A) **Pure-function core.** ``evaluate_runs`` takes a list of state-dicts
   and returns ``PromotionEvaluation``. No I/O, no clock. Trivially testable
   with synthetic fixtures (the plan explicitly calls for this).

B) **Snapshot is a literal copy.** ``compile_snapshot`` copies bytes from
   ``graph.py`` into ``compiled/survey_graph_v<ISO>.py``, then chmods 444.
   We do not transform / minify / strip — what runs in prod must be exactly
   what was reviewed and merged.

C) **chmod 444 is best-effort.** On Windows / certain CI runners, chmod is
   a no-op or fails silently. We log the attempted mode but never raise on
   chmod failure (the file content is the source of truth; immutability is
   a hint, not a security boundary).

D) **Promotion log includes SHA-256 of compiled file**, so a future
   forensic check can detect tampering even if the FS permissions were
   subverted.

E) **CLI is a thin wrapper.** All logic is in pure functions; the CLI just
   wires args -> functions -> exit-code.

Usage::

    # Programmatic
    from survey.graph.promote import promote
    result = promote(runs, graph_source, compiled_dir, log_path)
    if result.promoted:
        print(f"Snapshot: {result.snapshot.path}")

    # CLI (manual / cron)
    python -m survey.graph.promote \\
        --runs-dir survey-cli/logs/runs/ \\
        --graph-source survey-cli/survey/graph/graph.py \\
        --compiled-dir survey-cli/survey/graph/compiled/ \\
        --log survey-cli/logs/graph-promotions.jsonl

Closes #43.
"""

from __future__ import annotations

import argparse
import dataclasses
import datetime
import hashlib
import json
import logging
import os
import shutil
import stat
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

# ── Constants ────────────────────────────────────────────────────────────────

REQUIRED_SUCCESSES = 10
MAX_CONSECUTIVE_FAILURES = 3  # >= 3 means the run was delegated

LOG = logging.getLogger(__name__)

# ── Dataclasses ──────────────────────────────────────────────────────────────


@dataclasses.dataclass(frozen=True)
class PromotionEvaluation:
    """Result of ``evaluate_runs``. Pure data, no I/O."""

    eligible: bool
    n_successes: int
    blocking_reasons: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "eligible": self.eligible,
            "n_successes": self.n_successes,
            "blocking_reasons": list(self.blocking_reasons),
        }


@dataclasses.dataclass(frozen=True)
class CompiledSnapshot:
    """Metadata about a successful graph snapshot."""

    path: Path
    sha256: str
    bytes_written: int
    timestamp: str
    mode_octal: str  # e.g. "0o444"
    chmod_applied: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "path": str(self.path),
            "sha256": self.sha256,
            "bytes_written": self.bytes_written,
            "timestamp": self.timestamp,
            "mode_octal": self.mode_octal,
            "chmod_applied": self.chmod_applied,
        }


@dataclasses.dataclass(frozen=True)
class PromotionResult:
    """Final result of ``promote``."""

    promoted: bool
    evaluation: PromotionEvaluation
    snapshot: Optional[CompiledSnapshot]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "promoted": self.promoted,
            "evaluation": self.evaluation.to_dict(),
            "snapshot": self.snapshot.to_dict() if self.snapshot else None,
        }


# ── Pure core: evaluate criteria ─────────────────────────────────────────────


def _is_run_clean(run: Dict[str, Any]) -> List[str]:
    """Check a single run against the per-run criteria.

    Returns a list of reasons why this run is NOT clean (empty = clean).
    """
    reasons: List[str] = []

    # C1 per-run: balance_after > balance_before
    balance_before = run.get("balance_before", 0.0)
    balance_after = run.get("balance_after", 0.0)
    if not isinstance(balance_before, (int, float)) or not isinstance(
        balance_after, (int, float)
    ):
        reasons.append("balance_* fields not numeric")
    elif balance_after <= balance_before:
        reasons.append(
            f"no net earnings (balance_after={balance_after} <= "
            f"balance_before={balance_before})"
        )

    # C2: consecutive_failures < 3 (>= 3 means delegated)
    cf = run.get("consecutive_failures", 0)
    if not isinstance(cf, int):
        reasons.append("consecutive_failures not an int")
    elif cf >= MAX_CONSECUTIVE_FAILURES:
        reasons.append(
            f"run was delegated (consecutive_failures={cf} >= "
            f"{MAX_CONSECUTIVE_FAILURES})"
        )

    # C3: errors == []
    errors = run.get("errors", [])
    if not isinstance(errors, list):
        reasons.append("errors field is not a list")
    elif errors:
        reasons.append(f"run has {len(errors)} unresolved error(s)")

    return reasons


def evaluate_runs(runs: Sequence[Dict[str, Any]]) -> PromotionEvaluation:
    """Pure: check if the sequence of runs justifies promotion.

    Args:
      runs: list of SurveyState-shaped dicts. Must contain at least the
            fields ``balance_before``, ``balance_after``,
            ``consecutive_failures``, ``errors``.

    Returns: PromotionEvaluation. ``eligible`` is True iff ALL of:
      - at least REQUIRED_SUCCESSES runs are clean (per ``_is_run_clean``)
      - no clean run had ``consecutive_failures >= 3`` (C2)
      - no clean run had ``len(errors) > 0`` (C3)

    Note: the criteria are conjunctive across the **window** of successful
    runs. We do NOT silently discard "dirty" runs to reach 10 — every run
    in the input list must be clean.
    """
    reasons: List[str] = []
    n_successes = 0
    for i, run in enumerate(runs):
        per_run_problems = _is_run_clean(run)
        if per_run_problems:
            for p in per_run_problems:
                reasons.append(f"run[{i}]: {p}")
        else:
            n_successes += 1

    if n_successes < REQUIRED_SUCCESSES:
        reasons.append(
            f"only {n_successes} clean run(s); need >= {REQUIRED_SUCCESSES}"
        )

    eligible = (not reasons) and n_successes >= REQUIRED_SUCCESSES
    return PromotionEvaluation(
        eligible=eligible,
        n_successes=n_successes,
        blocking_reasons=reasons,
    )


# ── Snapshot creation ────────────────────────────────────────────────────────


def _utc_timestamp(now: Optional[datetime.datetime] = None) -> str:
    """ISO-8601 timestamp safe for filenames (colons replaced with dashes)."""
    if now is None:
        now = datetime.datetime.now(datetime.timezone.utc)
    return now.strftime("%Y%m%dT%H%M%SZ")


def compile_snapshot(
    graph_source: Path,
    compiled_dir: Path,
    *,
    now: Optional[datetime.datetime] = None,
) -> CompiledSnapshot:
    """Copy graph_source -> compiled_dir/survey_graph_v<TIMESTAMP>.py, chmod 444.

    Raises:
      FileNotFoundError: graph_source does not exist
      OSError: compiled_dir cannot be created / written
    """
    graph_source = Path(graph_source)
    compiled_dir = Path(compiled_dir)

    if not graph_source.is_file():
        raise FileNotFoundError(f"graph source not found: {graph_source}")

    compiled_dir.mkdir(parents=True, exist_ok=True)

    ts = _utc_timestamp(now)
    target = compiled_dir / f"survey_graph_v{ts}.py"

    # Use shutil.copy2 so mtime is preserved (forensic value: lets you see
    # which graph.py mtime was alive when the promotion fired).
    shutil.copy2(graph_source, target)
    payload = target.read_bytes()
    sha = hashlib.sha256(payload).hexdigest()

    # Best-effort chmod 444 (r--r--r--). On Windows / some CI runners
    # this may fail silently; never raise.
    chmod_applied = False
    try:
        os.chmod(target, stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
        chmod_applied = True
    except OSError as exc:
        LOG.warning("chmod 444 failed on %s: %s", target, exc)

    return CompiledSnapshot(
        path=target,
        sha256=sha,
        bytes_written=len(payload),
        timestamp=ts,
        mode_octal="0o444",
        chmod_applied=chmod_applied,
    )


# ── Promotion log ────────────────────────────────────────────────────────────


def append_promotion_log(log_path: Path, snapshot: CompiledSnapshot) -> None:
    """Append a JSONL record describing the snapshot."""
    log_path = Path(log_path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "event": "graph_promotion",
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "snapshot": snapshot.to_dict(),
    }
    with log_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


# ── Top-level orchestration ──────────────────────────────────────────────────


def promote(
    runs: Sequence[Dict[str, Any]],
    graph_source: Path,
    compiled_dir: Path,
    log_path: Path,
    *,
    now: Optional[datetime.datetime] = None,
) -> PromotionResult:
    """End-to-end: evaluate criteria, snapshot if eligible, log."""
    evaluation = evaluate_runs(runs)
    if not evaluation.eligible:
        return PromotionResult(
            promoted=False, evaluation=evaluation, snapshot=None
        )

    snapshot = compile_snapshot(graph_source, compiled_dir, now=now)
    append_promotion_log(log_path, snapshot)
    return PromotionResult(
        promoted=True, evaluation=evaluation, snapshot=snapshot
    )


# ── Run loading (optional convenience) ───────────────────────────────────────


def load_runs_from_dir(runs_dir: Path) -> List[Dict[str, Any]]:
    """Read every *.json file from ``runs_dir`` as a state dict.

    Sorted by filename ascending. Skipped files (bad JSON) are logged as
    warnings and excluded; the caller can still see the count through the
    return value's length.
    """
    runs_dir = Path(runs_dir)
    runs: List[Dict[str, Any]] = []
    if not runs_dir.is_dir():
        return runs
    for path in sorted(runs_dir.glob("*.json")):
        try:
            runs.append(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError) as exc:
            LOG.warning("skipped run file %s: %s", path, exc)
    return runs


# ── CLI ──────────────────────────────────────────────────────────────────────


def _parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="SR-49 — promote current graph after 10x success.",
    )
    p.add_argument(
        "--runs-dir",
        required=True,
        type=Path,
        help="Directory of *.json state-dict files (one per run)",
    )
    p.add_argument(
        "--graph-source",
        required=True,
        type=Path,
        help="Path to the live graph.py to snapshot",
    )
    p.add_argument(
        "--compiled-dir",
        required=True,
        type=Path,
        help="Output directory for survey_graph_v<TIMESTAMP>.py",
    )
    p.add_argument(
        "--log",
        required=True,
        type=Path,
        dest="log_path",
        help="Path to graph-promotions.jsonl",
    )
    p.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress stdout summary (exit code only)",
    )
    return p.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = _parse_args(argv)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s :: %(message)s",
    )

    runs = load_runs_from_dir(args.runs_dir)
    result = promote(runs, args.graph_source, args.compiled_dir, args.log_path)

    if not args.quiet:
        print(json.dumps(result.to_dict(), indent=2))

    return 0 if result.promoted else 1


if __name__ == "__main__":
    sys.exit(main())
