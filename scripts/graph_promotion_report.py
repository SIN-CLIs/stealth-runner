#!/usr/bin/env python3
"""
SR-123 graph_promotion_report.py

Aggregate `survey-cli/logs/graph-promotions.jsonl` (written by SR-49 /
PR #120) into a human-readable markdown report (default) or a JSON
payload (`--json`).

The promotion log is append-only, one JSON record per line, written by
`survey.graph.promote.promote_snapshot`. A record looks like:

    {
      "event": "graph_promotion",
      "timestamp": "<iso-8601 with offset>",     # log-write order
      "snapshot": {
        "path": "<relative path>",
        "sha256": "<64-hex>",
        "bytes_written": <int>,
        "timestamp": "<YYYYMMDDTHHMMSSZ>",       # forensic snapshot ts
        "mode_octal": "0o444",
        "chmod_applied": <bool>
      }
    }

Newest / oldest are computed from the **outer** record timestamp
(log-write order). The snapshot timestamp is used only for forensic
display.

CLI:

    python scripts/graph_promotion_report.py
        [--log survey-cli/logs/graph-promotions.jsonl]
        [--last-days N]      # filter to records within N days of "now"
        [--json]             # JSON instead of markdown
        [--quiet]            # suppress stdout; rc only

Exit codes follow the SR-113 / SR-117 / SR-122 convention:
    0  ok (also: empty log — a brand-new repo has zero promotions)
    1  reserved (no failure mode currently maps to 1)
    2  config error (missing log file, malformed argv)

Pure stdlib. No third-party imports.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import Counter, defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_LOG_PATH = Path("survey-cli/logs/graph-promotions.jsonl")
EXIT_OK = 0
EXIT_CONFIG_ERROR = 2

SNAPSHOT_TS_FMT = "%Y%m%dT%H%M%SZ"  # SR-49 _utc_timestamp() format


# ---------------------------------------------------------------------------
# Pure helpers (no I/O, no argv, easy to unit-test)
# ---------------------------------------------------------------------------


def parse_record_timestamp(raw: str) -> datetime | None:
    """Parse the outer ISO-8601 record timestamp into an aware UTC datetime.

    Returns None if the string is missing or unparseable. Accepts the
    common ISO variants (`...+00:00`, `...Z`, with/without fractional
    seconds).
    """
    if not raw:
        return None
    s = raw.strip()
    # datetime.fromisoformat in 3.11+ accepts trailing Z; for safety on
    # older interpreters we normalise.
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def parse_snapshot_timestamp(raw: str) -> datetime | None:
    """Parse the inner snapshot timestamp (YYYYMMDDTHHMMSSZ)."""
    if not raw:
        return None
    try:
        dt = datetime.strptime(raw, SNAPSHOT_TS_FMT)
    except (ValueError, TypeError):
        return None
    return dt.replace(tzinfo=UTC)


def iter_records(log_path: Path) -> list[dict[str, Any]]:
    """Yield parsed records from a JSONL file.

    - Skips blank lines.
    - Skips malformed JSON lines (defensive: an external tool could
      truncate the file mid-write).
    - Skips records whose `event` is not `graph_promotion`.
    """
    records: list[dict[str, Any]] = []
    with log_path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(obj, dict):
                continue
            if obj.get("event") != "graph_promotion":
                continue
            records.append(obj)
    return records


def filter_last_days(
    records: list[dict[str, Any]],
    last_days: int,
    now: datetime,
) -> list[dict[str, Any]]:
    """Return records whose outer timestamp is within `last_days` of now.

    Records with unparseable / missing outer timestamps are dropped.
    """
    cutoff = now - timedelta(days=last_days)
    kept: list[dict[str, Any]] = []
    for r in records:
        dt = parse_record_timestamp(r.get("timestamp", ""))
        if dt is None:
            continue
        if dt >= cutoff:
            kept.append(r)
    return kept


def compute_intervals_seconds(records: list[dict[str, Any]]) -> list[float]:
    """Return the sorted-by-time list of gaps (in seconds) between
    consecutive promotions. Empty / single-record input yields [].
    """
    timestamps: list[datetime] = []
    for r in records:
        dt = parse_record_timestamp(r.get("timestamp", ""))
        if dt is not None:
            timestamps.append(dt)
    if len(timestamps) < 2:
        return []
    timestamps.sort()
    return [(timestamps[i] - timestamps[i - 1]).total_seconds() for i in range(1, len(timestamps))]


def week_bucket(dt: datetime) -> str:
    """Map a datetime to an ISO `YYYY-Www` week-bucket label."""
    iso_year, iso_week, _ = dt.isocalendar()
    return f"{iso_year:04d}-W{iso_week:02d}"


def aggregate(records: list[dict[str, Any]], now: datetime) -> dict[str, Any]:
    """Compute the full aggregation payload from a list of records.

    Returns a dict suitable for both markdown rendering and JSON output.
    """
    total = len(records)

    # Newest / oldest based on outer (log-write) timestamp.
    outer_dts: list[tuple[datetime, dict[str, Any]]] = []
    for r in records:
        dt = parse_record_timestamp(r.get("timestamp", ""))
        if dt is not None:
            outer_dts.append((dt, r))
    outer_dts.sort(key=lambda pair: pair[0])

    newest_dt = outer_dts[-1][0] if outer_dts else None
    oldest_dt = outer_dts[0][0] if outer_dts else None
    newest_record = outer_dts[-1][1] if outer_dts else None

    # Last-30-days count.
    cutoff_30d = now - timedelta(days=30)
    last_30d_count = sum(1 for dt, _ in outer_dts if dt >= cutoff_30d)

    # Cadence (intervals).
    intervals = compute_intervals_seconds(records)
    median_s = statistics.median(intervals) if intervals else None
    mean_s = statistics.fmean(intervals) if intervals else None

    # Per-week histogram (chronological).
    week_counts: dict[str, int] = defaultdict(int)
    for dt, _ in outer_dts:
        week_counts[week_bucket(dt)] += 1
    week_hist = [{"week": w, "count": week_counts[w]} for w in sorted(week_counts)]

    # SHA-256 distribution.
    shas = [
        (r.get("snapshot") or {}).get("sha256", "")
        for r in records
        if isinstance(r.get("snapshot"), dict)
    ]
    sha_counter = Counter(s for s in shas if s)
    unique_sha_count = len(sha_counter)
    duplicates: list[dict[str, Any]] = []
    for sha, count in sha_counter.items():
        if count > 1:
            occurrences: list[str] = []
            for r in records:
                snap = r.get("snapshot") or {}
                if snap.get("sha256") == sha:
                    occurrences.append(r.get("timestamp", ""))
            duplicates.append(
                {
                    "sha256": sha,
                    "count": count,
                    "occurrences": occurrences,
                }
            )
    duplicates.sort(key=lambda d: (-d["count"], d["sha256"]))

    return {
        "total": total,
        "last_30d_count": last_30d_count,
        "newest_timestamp": (newest_dt.isoformat().replace("+00:00", "Z") if newest_dt else None),
        "oldest_timestamp": (oldest_dt.isoformat().replace("+00:00", "Z") if oldest_dt else None),
        "newest_snapshot": ((newest_record or {}).get("snapshot") if newest_record else None),
        "median_interval_seconds": median_s,
        "mean_interval_seconds": mean_s,
        "weeks": week_hist,
        "unique_sha256": unique_sha_count,
        "duplicates": duplicates,
        "generated_at": now.isoformat().replace("+00:00", "Z"),
    }


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def _humanize_seconds(seconds: float) -> str:
    """Render a duration in a compact form: '12s', '3m 04s', '2h 17m',
    '5d 03h'. Always non-negative input.
    """
    if seconds < 60:
        return f"{seconds:.0f}s"
    if seconds < 3600:
        m, s = divmod(int(seconds), 60)
        return f"{m}m {s:02d}s"
    if seconds < 86400:
        h, rem = divmod(int(seconds), 3600)
        m = rem // 60
        return f"{h}h {m:02d}m"
    d, rem = divmod(int(seconds), 86400)
    h = rem // 3600
    return f"{d}d {h:02d}h"


def render_markdown(agg: dict[str, Any], log_path: Path) -> str:
    """Render the aggregation as a GitHub-flavored Markdown report."""
    lines: list[str] = []
    lines.append("# Graph Promotion Log Report")
    lines.append("")
    lines.append(f"_Source:_ `{log_path}`")
    lines.append(f"_Generated:_ `{agg['generated_at']}`")
    lines.append("")

    # Summary
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- Total promotions: **{agg['total']}**")
    lines.append(f"- Last 30 days: **{agg['last_30d_count']}**")
    if agg["oldest_timestamp"]:
        lines.append(f"- Oldest promotion: `{agg['oldest_timestamp']}`")
    if agg["newest_timestamp"]:
        lines.append(f"- Newest promotion: `{agg['newest_timestamp']}`")
    if agg["newest_snapshot"]:
        snap = agg["newest_snapshot"]
        sha = snap.get("sha256", "")
        sha_short = sha[:12] if sha else "(missing)"
        lines.append(
            f"- Newest snapshot sha256: `{sha_short}…` (`{snap.get('bytes_written', '?')}` bytes)"
        )
    lines.append("")

    # Cadence
    lines.append("## Cadence")
    lines.append("")
    if agg["median_interval_seconds"] is None:
        lines.append("_Not enough data for cadence stats (need 2+ promotions)._")
    else:
        lines.append(
            f"- Median inter-promotion interval: "
            f"**{_humanize_seconds(agg['median_interval_seconds'])}**"
        )
        lines.append(
            f"- Mean inter-promotion interval: "
            f"**{_humanize_seconds(agg['mean_interval_seconds'])}**"
        )
    lines.append("")

    if agg["weeks"]:
        lines.append("### Per-week histogram")
        lines.append("")
        lines.append("| Week | Count |")
        lines.append("|---|---|")
        for entry in agg["weeks"]:
            lines.append(f"| `{entry['week']}` | {entry['count']} |")
        lines.append("")

    # SHA-256 distribution
    lines.append("## SHA-256 Distribution")
    lines.append("")
    lines.append(f"- Unique sha256 values: **{agg['unique_sha256']}**")
    if agg["duplicates"]:
        lines.append("")
        lines.append("### Duplicate sha256 (same code re-promoted)")
        lines.append("")
        lines.append("| sha256 (short) | count | occurrences |")
        lines.append("|---|---|---|")
        for dup in agg["duplicates"]:
            sha_short = dup["sha256"][:12]
            occ = ", ".join(f"`{t}`" for t in dup["occurrences"])
            lines.append(f"| `{sha_short}…` | {dup['count']} | {occ} |")
    else:
        lines.append("- All snapshots unique (no duplicate sha256 detected).")
    lines.append("")

    return "\n".join(lines)


def render_json(agg: dict[str, Any], log_path: Path) -> str:
    payload = dict(agg)
    payload["log_path"] = str(log_path)
    return json.dumps(payload, indent=2, sort_keys=True)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="graph_promotion_report",
        description=(
            "Aggregate survey-cli/logs/graph-promotions.jsonl into a "
            "markdown or JSON report (count, cadence, sha-distribution)."
        ),
    )
    p.add_argument(
        "--log",
        type=Path,
        default=DEFAULT_LOG_PATH,
        help=f"Path to JSONL promotion log (default: {DEFAULT_LOG_PATH}).",
    )
    p.add_argument(
        "--last-days",
        type=int,
        default=None,
        metavar="N",
        help=(
            "Restrict aggregation to records within the last N days "
            "(measured against the outer record timestamp)."
        ),
    )
    p.add_argument(
        "--json",
        action="store_true",
        help="Emit JSON instead of Markdown.",
    )
    p.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress stdout; exit code only.",
    )
    return p


def _emit(out_text: str, *, quiet: bool, stream: Any) -> None:
    if quiet:
        return
    stream.write(out_text)
    if not out_text.endswith("\n"):
        stream.write("\n")


def main(argv: list[str] | None = None, *, now: datetime | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    now = now or datetime.now(UTC)

    log_path: Path = args.log

    if not log_path.exists():
        if not args.quiet:
            sys.stderr.write(f"error: promotion log not found: {log_path}\n")
        return EXIT_CONFIG_ERROR

    records = iter_records(log_path)

    if not records:
        # Empty log = brand-new repo. Not an error.
        if args.json:
            payload = {
                "log_path": str(log_path),
                "total": 0,
                "message": "No promotions recorded",
                "generated_at": now.isoformat().replace("+00:00", "Z"),
            }
            _emit(
                json.dumps(payload, indent=2, sort_keys=True), quiet=args.quiet, stream=sys.stdout
            )
        else:
            _emit(
                f"# Graph Promotion Log Report\n\n"
                f"_Source:_ `{log_path}`\n\n"
                f"No promotions recorded.\n",
                quiet=args.quiet,
                stream=sys.stdout,
            )
        return EXIT_OK

    if args.last_days is not None:
        if args.last_days < 0:
            sys.stderr.write("error: --last-days must be >= 0\n")
            return EXIT_CONFIG_ERROR
        records = filter_last_days(records, args.last_days, now)

    agg = aggregate(records, now)

    if args.json:
        _emit(render_json(agg, log_path), quiet=args.quiet, stream=sys.stdout)
    else:
        _emit(render_markdown(agg, log_path), quiet=args.quiet, stream=sys.stdout)

    return EXIT_OK


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
