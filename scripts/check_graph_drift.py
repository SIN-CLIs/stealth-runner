#!/usr/bin/env python3
# =============================================================================
# SR-122: Graph snapshot drift detector.
#
# WHY THIS FILE EXISTS
# --------------------
# After SR-49 (PR #120) shipped, every call to survey.graph.promote
# appends a record to logs/graph-promotions.jsonl describing the latest
# promoted snapshot of survey/graph/graph.py (path, sha256, byte-count,
# UTC promotion timestamp, octal mode, chmod-applied flag).
#
# This script answers two operational questions WITHOUT touching the
# survey-cli package (stdlib-only, importable as a standalone tool):
#
#   1. Has the live survey/graph/graph.py drifted away from the most
#      recent recorded snapshot? (i.e. did someone edit graph.py after
#      the last promotion, breaking the "snapshot is the truth" rule?)
#   2. How stale is the newest snapshot? (i.e. should we re-promote?)
#
# It is the GRAPH-DRIFT-GUARD. Runs as ad-hoc CLI today; future SR-121
# may wire it into CI. Read-only by contract: it NEVER writes to disk
# and NEVER mutates input files.
#
# CONTRACT
# --------
# - Default mode: print drift status + age, exit 0 always.
# - `--exit-non-zero-on-drift`: exit 1 iff sha256 mismatch.
# - `--max-age-days N`: exit 1 iff newest snapshot is older than N days.
# - `--json`: machine-parseable JSON output to stdout (no human prose).
# - `--quiet`: suppress stdout entirely; exit code only.
# - Config errors (missing log, empty log, missing graph.py) → exit 2.
#
# DESIGN
# ------
# Standalone — does NOT import from survey.graph.promote even though
# that module also computes the same sha256. The scripts/ tree is
# sys-admin/hygiene territory and MUST run without the survey-cli
# package installed. JSONL parsing is trivial; no code-reuse needed.
#
# PROMOTION RECORD SCHEMA (frozen, from SR-49)
# --------
#   {"event": "graph_promotion",
#    "timestamp": "<log-write ISO8601>",
#    "snapshot": {
#      "path": "<snapshot file path>",
#      "sha256": "<64-hex-char digest>",
#      "bytes_written": <int>,
#      "timestamp": "<promotion clock, compact UTC: YYYYMMDDTHHMMSSZ>",
#      "mode_octal": "0o444",
#      "chmod_applied": <bool>
#     }}
#
# Age is computed from `snapshot.timestamp` (file-level UTC, canonical
# promotion clock), NOT the outer `record.timestamp` (log-write time).
# Newest snapshot = LAST line of the JSONL (append-only by contract).
# =============================================================================
"""scripts/check_graph_drift.py — detect graph.py drift vs last snapshot.

CLI:
    python scripts/check_graph_drift.py
        [--graph-source survey-cli/survey/graph/graph.py]
        [--promotion-log survey-cli/logs/graph-promotions.jsonl]
        [--max-age-days N]
        [--exit-non-zero-on-drift]
        [--json]
        [--quiet]

Closes #122 (graph snapshot drift detector).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# Public helpers (also imported by tests).
__all__ = [
    "sha256_of_file",
    "parse_snapshot_timestamp",
    "read_newest_snapshot",
    "compute_drift",
    "format_human",
    "format_json",
    "main",
]


# -- Constants ---------------------------------------------------------------

DEFAULT_GRAPH_SOURCE = "survey-cli/survey/graph/graph.py"
DEFAULT_PROMOTION_LOG = "survey-cli/logs/graph-promotions.jsonl"

# Exit codes (mirrors SR-113/SR-117 convention).
EXIT_OK = 0
EXIT_DRIFT_OR_STALE = 1
EXIT_CONFIG_ERROR = 2

# Snapshot-clock format: compact UTC, e.g. "20260512T120000Z".
SNAPSHOT_TS_FORMAT = "%Y%m%dT%H%M%SZ"


# -- Pure helpers ------------------------------------------------------------


def sha256_of_file(path: Path) -> str:
    """Return the hex sha256 digest of the file at *path*.

    Streams in 64 KiB chunks so the script stays memory-bounded even if
    graph.py grows unexpectedly large.
    """
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_snapshot_timestamp(value: Any) -> datetime | None:
    """Parse the compact UTC snapshot timestamp (YYYYMMDDTHHMMSSZ).

    Returns a timezone-aware UTC datetime, or None if the value is not
    a parseable string in the expected format.
    """
    if not isinstance(value, str):
        return None
    s = value.strip()
    if not s:
        return None
    try:
        dt = datetime.strptime(s, SNAPSHOT_TS_FORMAT)
    except (ValueError, TypeError):
        return None
    return dt.replace(tzinfo=UTC)


def read_newest_snapshot(
    log_path: Path,
) -> tuple[dict[str, Any] | None, str | None]:
    """Return (newest_snapshot_dict, error_message).

    Walks the JSONL append-log and keeps the LAST successfully-parsed
    record whose top-level key "snapshot" is a dict. We trust append
    order (no re-sorting). Returns (None, "<msg>") on any failure mode
    the caller should surface as a config-error (rc=2):

      - file missing
      - file present but contains no parseable snapshot record
    """
    if not log_path.exists():
        return None, f"promotion log not found: {log_path}"

    newest: dict[str, Any] | None = None
    try:
        with log_path.open("r", encoding="utf-8") as f:
            for raw in f:
                line = raw.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    # Skip malformed lines; we only need the newest
                    # well-formed snapshot. Drift detection should not
                    # be blocked by an unrelated bad line.
                    continue
                if isinstance(record, dict) and isinstance(record.get("snapshot"), dict):
                    newest = record["snapshot"]
    except OSError as e:
        return None, f"cannot read promotion log {log_path}: {e}"

    if newest is None:
        return None, "no snapshots recorded yet"
    return newest, None


def compute_drift(
    graph_path: Path,
    log_path: Path,
    now: datetime | None = None,
) -> tuple[dict[str, Any], str | None]:
    """Compute drift result, returning (result_dict, error_message).

    On error_message != None the result_dict is still populated with
    whatever facts we have, but the caller MUST treat it as rc=2.

    The result_dict shape is the canonical JSON output (also used by
    the human formatter) with keys:
      - drift          (bool|None)
      - current_sha256 (str|None)
      - snapshot_sha256 (str|None)
      - snapshot_path  (str|None)
      - snapshot_timestamp (str|None)
      - age_days       (float|None)
      - graph_source   (str)
      - promotion_log  (str)
    """
    if now is None:
        now = datetime.now(UTC)

    result: dict[str, Any] = {
        "drift": None,
        "current_sha256": None,
        "snapshot_sha256": None,
        "snapshot_path": None,
        "snapshot_timestamp": None,
        "age_days": None,
        "graph_source": str(graph_path),
        "promotion_log": str(log_path),
    }

    if not graph_path.exists():
        return result, f"graph source not found: {graph_path}"

    result["current_sha256"] = sha256_of_file(graph_path)

    snapshot, err = read_newest_snapshot(log_path)
    if err is not None:
        return result, err

    # snapshot is guaranteed non-None here.
    assert snapshot is not None
    result["snapshot_sha256"] = snapshot.get("sha256")
    result["snapshot_path"] = snapshot.get("path")
    result["snapshot_timestamp"] = snapshot.get("timestamp")

    snap_sha = snapshot.get("sha256")
    if isinstance(snap_sha, str):
        result["drift"] = result["current_sha256"] != snap_sha

    parsed = parse_snapshot_timestamp(snapshot.get("timestamp"))
    if parsed is not None:
        delta = now - parsed
        result["age_days"] = delta.total_seconds() / 86400.0

    return result, None


def format_human(result: dict[str, Any], error: str | None) -> str:
    """Human-readable single-block report."""
    if error is not None:
        return f"✗ ERROR: {error}"

    lines = []
    drift = result.get("drift")
    if drift is False:
        lines.append("✓ No drift — live graph.py matches newest snapshot.")
    elif drift is True:
        lines.append("✗ DRIFT — live graph.py differs from newest snapshot.")
    else:
        lines.append("? Drift status unknown (snapshot sha256 missing).")

    age = result.get("age_days")
    if age is None:
        lines.append("  age: unknown (snapshot timestamp missing or invalid)")
    else:
        lines.append(f"  age: {age:.2f} days since last promotion")

    cur = result.get("current_sha256")
    snap = result.get("snapshot_sha256")
    lines.append(f"  current sha256:  {cur}")
    lines.append(f"  snapshot sha256: {snap}")
    snap_ts = result.get("snapshot_timestamp")
    if snap_ts:
        lines.append(f"  snapshot timestamp: {snap_ts}")
    snap_path = result.get("snapshot_path")
    if snap_path:
        lines.append(f"  snapshot path:      {snap_path}")
    return "\n".join(lines)


def format_json(result: dict[str, Any], error: str | None) -> str:
    """JSON output. `error` is None on success."""
    payload = dict(result)
    payload["error"] = error
    payload["ok"] = error is None
    return json.dumps(payload, indent=2, sort_keys=True)


def main(argv: list[str] | None = None) -> int:
    """Main entry point. Returns a process exit code."""
    parser = argparse.ArgumentParser(
        description=(
            "Detect drift between live survey/graph/graph.py and the "
            "newest snapshot recorded in graph-promotions.jsonl."
        ),
    )
    parser.add_argument(
        "--graph-source",
        default=DEFAULT_GRAPH_SOURCE,
        help=f"Path to live graph.py (default: {DEFAULT_GRAPH_SOURCE})",
    )
    parser.add_argument(
        "--promotion-log",
        default=DEFAULT_PROMOTION_LOG,
        help=f"Path to promotion JSONL (default: {DEFAULT_PROMOTION_LOG})",
    )
    parser.add_argument(
        "--max-age-days",
        type=float,
        default=None,
        help="Exit 1 if newest snapshot is older than N days.",
    )
    parser.add_argument(
        "--exit-non-zero-on-drift",
        action="store_true",
        help="Exit 1 if sha256(graph.py) != newest snapshot sha256.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit JSON instead of human-readable text.",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress stdout; exit code only.",
    )
    args = parser.parse_args(argv)

    graph_path = Path(args.graph_source)
    log_path = Path(args.promotion_log)

    result, error = compute_drift(graph_path, log_path)

    if not args.quiet:
        if args.json:
            print(format_json(result, error))
        else:
            print(format_human(result, error))

    if error is not None:
        # Config error → always rc=2, regardless of other flags.
        return EXIT_CONFIG_ERROR

    if args.exit_non_zero_on_drift and result.get("drift") is True:
        return EXIT_DRIFT_OR_STALE

    if args.max_age_days is not None:
        age = result.get("age_days")
        if age is not None and age > args.max_age_days:
            return EXIT_DRIFT_OR_STALE

    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
