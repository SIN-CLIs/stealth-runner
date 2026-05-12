#!/usr/bin/env python3
# =============================================================================
# SR-108: Read-only hygiene script — flag aging open pattern-suggestions.
#
# WHY THIS FILE EXISTS
# --------------------
# After #56 (LLM-Phase-2 suggester) and #102 (source-aware batch-review) the
# `pattern-suggestions-*.jsonl` inbox has a lifecycle: open -> accepted/
# rejected. `survey learn status` (#104) shows a human-at-the-terminal the
# CURRENT distribution. This script is the MACHINE-SIDE complement: a
# read-only diagnostic that flags open records older than N days, suitable
# for cron/CI hygiene jobs.
#
# CONTRACT
# --------
# - Reads only. NEVER writes to disk, NEVER mutates input files.
# - Default mode: exit 0 always (read-only diagnostic).
# - `--exit-non-zero-if-stale`: exit 1 iff stale_count > 0 (CI/alert mode).
# - `--json`: machine-parseable JSON to stdout.
#
# DESIGN
# ------
# Standalone — does NOT import `from survey.learn import ...`. The scripts/
# tree is sys-admin/hygiene territory and must run without the survey-cli
# package installed. JSONL parsing is trivial; no code-reuse needed.
#
# NORMALIZATION (consistent with `survey/learn/status.py` for #104)
# - Records missing `status` count as "open".
# - Records missing `source` count as "substring".
# - Records missing `first_seen` are NOT counted as stale (defensive — no
#   false positives on legacy records from pre-aggregator-versioning).
# - `first_seen` is the canonical age field; `created_at` and `ts` are NOT
#   accepted as aliases here (single-source-of-truth for stale-detection;
#   if a record has only `created_at`, that is treated as missing first_seen
#   and the record is skipped from stale-counting).
#
# FILE SELECTION
# - Globs `pattern-suggestions-*.jsonl` in the logs dir.
# - SKIPS `*-accepted.jsonl` and `*-rejected.jsonl` (those are output sinks,
#   not the live inbox).
# =============================================================================
"""scripts/triage_stale_suggestions.py — flag aging open pattern-suggestions.

CLI:
    python scripts/triage_stale_suggestions.py
        [--logs DIR]                # default: survey-cli/logs
        [--age-days N]              # default: 14
        [--filter-source X]         # all / substring / llm
        [--exit-non-zero-if-stale]  # rc=1 if stale > 0
        [--json]                    # JSON output to stdout

Closes #108 (machine-side hygiene complement to #104).
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import sys
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Tuple

# Public helpers (also imported by tests).
__all__ = [
    "iter_records",
    "parse_first_seen",
    "is_stale",
    "triage",
    "format_human",
    "format_json",
    "main",
]


# -- Constants ---------------------------------------------------------------

DEFAULT_LOGS_DIR = "survey-cli/logs"
DEFAULT_AGE_DAYS = 14
INPUT_GLOB = "pattern-suggestions-*.jsonl"
# Output sinks from review.py — NOT live inbox; skip during scan.
SKIP_SUFFIXES = ("-accepted.jsonl", "-rejected.jsonl")


# -- Pure helpers ------------------------------------------------------------


def parse_first_seen(value: Any) -> Optional[datetime]:
    """Parse an ISO8601-ish timestamp into a tz-aware UTC datetime.

    Returns None if value is missing, None, empty, or unparseable. We accept
    the trailing 'Z' shorthand for UTC (datetime.fromisoformat only learned
    that on Python 3.11; we normalize defensively for older 3.10 as well).
    """
    if not value or not isinstance(value, str):
        return None
    s = value.strip()
    if not s:
        return None
    # Normalize trailing "Z" -> "+00:00" for fromisoformat across versions.
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    # Naive datetimes are assumed UTC (logs are produced server-side UTC).
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt


def _normalize(record: Dict[str, Any]) -> Dict[str, Any]:
    """Apply defensive defaults consistent with `survey/learn/status.py`."""
    out = dict(record)
    if not out.get("status"):
        out["status"] = "open"
    if not out.get("source"):
        out["source"] = "substring"
    return out


def is_stale(
    record: Dict[str, Any],
    now: datetime,
    age_days: int,
) -> Tuple[bool, Optional[int]]:
    """Decide whether a (normalized) record is stale.

    Returns (stale, age_days_int_or_None). A record is stale iff:
      - status == "open"
      - first_seen parses to a valid datetime
      - (now - first_seen).days > age_days

    A record without a parseable first_seen is NEVER stale (defensive).
    A closed record (accepted/rejected) is NEVER stale.
    """
    if record.get("status") != "open":
        return (False, None)
    fs = parse_first_seen(record.get("first_seen"))
    if fs is None:
        return (False, None)
    age = (now - fs).days
    return (age > age_days, age)


def iter_records(logs_dir: str) -> Iterable[Tuple[str, Dict[str, Any]]]:
    """Yield (filepath, record) for every JSONL line in the inbox glob.

    Skips output-sink files (`*-accepted.jsonl`, `*-rejected.jsonl`).
    Malformed JSON lines are silently skipped (telemetry files can have
    half-flushed tails after crashes — we tolerate, never re-raise).
    """
    pattern = os.path.join(logs_dir, INPUT_GLOB)
    for path in sorted(glob.glob(pattern)):
        if any(path.endswith(suf) for suf in SKIP_SUFFIXES):
            continue
        try:
            with open(path, "r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if not isinstance(rec, dict):
                        continue
                    yield path, rec
        except OSError:
            # Unreadable file: skip but do not abort the whole triage.
            continue


# -- Triage core -------------------------------------------------------------


def triage(
    logs_dir: str,
    age_days: int,
    filter_source: str,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Run a triage pass and return a JSON-serializable summary dict.

    Args:
        logs_dir: directory containing pattern-suggestions-*.jsonl files.
        age_days: threshold; (now - first_seen) MUST be > age_days to count.
        filter_source: "all" | "substring" | "llm".
        now: injected for deterministic tests. Defaults to datetime.now(UTC).
    """
    if now is None:
        now = datetime.now(timezone.utc)

    files_scanned: set = set()
    total_open = 0
    stale_records: List[Dict[str, Any]] = []

    for path, raw in iter_records(logs_dir):
        files_scanned.add(path)
        rec = _normalize(raw)

        # Source filter applies to ALL counters (including total_open) so
        # the "percent stale" is meaningful inside the filtered view.
        if filter_source != "all" and rec.get("source") != filter_source:
            continue

        if rec.get("status") == "open":
            total_open += 1

        stale, age = is_stale(rec, now=now, age_days=age_days)
        if stale:
            stale_records.append({
                "age_days": age,
                "source": rec.get("source"),
                "family": rec.get("suggested_family") or "<NEW>",
                "role": rec.get("role", "?"),
                "label": rec.get("normalized_label", ""),
                "count": rec.get("count", 0),
                "first_seen": rec.get("first_seen"),
            })

    stale_records.sort(key=lambda r: r["age_days"] or 0, reverse=True)

    stale_count = len(stale_records)
    if total_open > 0:
        stale_percent = round((stale_count / total_open) * 100.0, 1)
    else:
        stale_percent = 0.0
    oldest = stale_records[0]["age_days"] if stale_records else None

    return {
        "threshold_days": age_days,
        "filter_source": filter_source,
        "logs_dir": logs_dir,
        "files_scanned": len(files_scanned),
        "total_open": total_open,
        "stale_count": stale_count,
        "stale_percent": stale_percent,
        "oldest_age_days": oldest,
        "stale_records": stale_records,
    }


# -- Formatters --------------------------------------------------------------


def format_human(summary: Dict[str, Any]) -> str:
    """Render the human-readable report (single string, newline-separated)."""
    lines: List[str] = []
    lines.append(
        f"[triage] scanning {summary['logs_dir']}/{INPUT_GLOB}"
    )
    lines.append(
        f"[triage] threshold: {summary['threshold_days']} days, "
        f"source filter: {summary['filter_source']}"
    )
    lines.append("")
    if summary["stale_count"] == 0:
        lines.append(
            f"No stale open records "
            f"(total open scanned: {summary['total_open']})."
        )
        return "\n".join(lines)

    lines.append(
        f"Stale open records (older than {summary['threshold_days']} days):"
    )
    for r in summary["stale_records"]:
        label = (r["label"] or "")[:40]
        lines.append(
            f"  age={r['age_days']}d  "
            f"source={r['source']:<9}  "
            f"family={(r['family'] or '<NEW>'):<18}  "
            f"label={label!r}  "
            f"count={r['count']}"
        )
    lines.append("")
    lines.append(
        f"Total stale: {summary['stale_count']} of "
        f"{summary['total_open']} open records "
        f"({summary['stale_percent']}%)"
    )
    if summary["oldest_age_days"] is not None:
        lines.append(f"Oldest: {summary['oldest_age_days']} days")
    return "\n".join(lines)


def format_json(summary: Dict[str, Any]) -> str:
    """Render summary as 2-space-indented JSON."""
    return json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True)


# -- CLI ---------------------------------------------------------------------


def _build_argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="triage_stale_suggestions",
        description=(
            "Read-only hygiene scan over pattern-suggestions-*.jsonl. "
            "Flags open records older than --age-days."
        ),
    )
    p.add_argument(
        "--logs",
        default=DEFAULT_LOGS_DIR,
        help=f"Directory to scan (default: {DEFAULT_LOGS_DIR})",
    )
    p.add_argument(
        "--age-days",
        type=int,
        default=DEFAULT_AGE_DAYS,
        help=f"Age threshold in days (default: {DEFAULT_AGE_DAYS})",
    )
    p.add_argument(
        "--filter-source",
        choices=("all", "substring", "llm"),
        default="all",
        help="Filter records by source field (default: all)",
    )
    p.add_argument(
        "--exit-non-zero-if-stale",
        action="store_true",
        help="Exit 1 if at least one stale record is found (CI/alert mode)",
    )
    p.add_argument(
        "--json",
        action="store_true",
        help="Emit JSON to stdout instead of human-readable text",
    )
    return p


def main(argv: Optional[List[str]] = None) -> int:
    args = _build_argparser().parse_args(argv)
    summary = triage(
        logs_dir=args.logs,
        age_days=args.age_days,
        filter_source=args.filter_source,
    )
    if args.json:
        print(format_json(summary))
    else:
        print(format_human(summary))

    if args.exit_non_zero_if_stale and summary["stale_count"] > 0:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
