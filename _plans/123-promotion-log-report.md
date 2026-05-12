# Plan: SR-123 — Promotion log aggregator / markdown report

Closes: #123
Branch: `feat/123-promotion-log-report`
Assignee track: Agent-2 (observability)
Min tests: 12

## Goal

Read `logs/graph-promotions.jsonl` and emit aggregations:

- Promotion count overall + last 30 days
- Per-week count buckets
- Average inter-promotion interval (median + mean)
- Unique sha256s (dedup count)
- Duplicate-sha256 detection (same code re-promoted → suspicious)
- Newest / oldest snapshot timestamps

## Acceptance Criteria

1. **New file** `scripts/graph_promotion_report.py` (executable, 100755).
2. Pure stdlib (json, datetime, argparse, statistics, collections, pathlib).
3. CLI surface:
   ```
   python scripts/graph_promotion_report.py
       [--log survey-cli/logs/graph-promotions.jsonl]
       [--last-days N]            # filter to records within N days
       [--json]                   # JSON instead of markdown
       [--quiet]                  # exit code only
   ```
4. Default output: Markdown report to stdout, suitable for pasting into
   a PR comment or weekly digest. Sections:
   - `## Summary` (count, window)
   - `## Cadence` (per-week histogram, median interval)
   - `## SHA-256 Distribution` (unique count, duplicates list if any)
5. Empty log: exit 0, print "No promotions recorded" (NOT an error —
   a brand-new repo has zero promotions, that's fine).
6. Missing log file: exit 2 with explicit message.
7. Duplicate-sha256 detection: if the same sha256 appears > 1 time,
   list each occurrence with timestamp (forensics: did we promote
   identical code twice?).

## File Boundaries

### MUST modify / create

- `scripts/graph_promotion_report.py` (NEW, executable)
- `scripts/tests/test_graph_promotion_report.py` (NEW)

### MUST NOT touch

- `survey-cli/**` (especially `survey/graph/promote.py`)
- Other `scripts/check_*.py` files
- `.github/workflows/**`

### Plan-file deletion (rule A4)

Delete `_plans/123-promotion-log-report.md` in the same commit.

## Conflict Surface

- Depends on PR #120 (SR-49) for the JSONL schema. If #120 not yet
  merged, the JSONL format is still finalized in #120's source — use
  the schema documented in that PR.
- No conflict with SR-121 or SR-122 (different scripts, different tests).
- All three (#121/#122/#123) can be developed in parallel by the same
  agent; no shared files.

## Test Minimum

12 tests in `scripts/tests/test_graph_promotion_report.py`:

| # | What |
|---|------|
| T1 | Empty log → "No promotions recorded", rc=0 |
| T2 | Missing log file → rc=2 |
| T3 | Single promotion → count=1, no cadence stats |
| T4 | Multiple promotions → correct count |
| T5 | `--last-days N` filters older records out |
| T6 | Inter-promotion interval: median computed correctly |
| T7 | Inter-promotion interval: mean computed correctly |
| T8 | Unique sha256 count |
| T9 | Duplicate sha256 detection: flagged in output |
| T10 | No duplicates: section says "all snapshots unique" |
| T11 | Markdown output has required section headers |
| T12 | `--json` output parseable, has required fields |

## Hand-off Notes for Agent-2

- Time parsing: snapshot timestamps are `%Y%m%dT%H%M%SZ` format (from
  SR-49's `_utc_timestamp`). Outer record timestamps are full ISO-8601.
  Use the outer record timestamp for "newest/oldest" since that's the
  log-write order; use snapshot timestamp for forensic comparison.
- Markdown should be GitHub-flavored (tables work, code fences with
  triple-backticks).
- DO NOT depend on PyYAML, pandas, or any non-stdlib library.
- Treat the JSONL as append-only and source-of-truth — don't try to
  reconcile with the filesystem.

## Out of Scope

- Auto-posting the report to Slack / GH PR comments.
- HTML output.
- Trend forecasting / predictions.
- Web dashboard.
