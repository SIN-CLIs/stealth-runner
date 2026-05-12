# Plan: SR-122 — Graph snapshot drift detector

Closes: #122
Branch: `feat/122-graph-drift-detector`
Assignee track: Agent-2 (hygiene / forensics)
Min tests: 10

## Goal

After PR #120 (SR-49) ships, `logs/graph-promotions.jsonl` contains one
record per snapshot. This script answers two questions:

1. Is the live `survey/graph/graph.py` byte-identical to the most recent
   snapshot? (Drift yes/no)
2. If drifted, how stale is the latest snapshot (in days)?

## Acceptance Criteria

1. **New file** `scripts/check_graph_drift.py` (executable, 100755).
2. Pure stdlib (hashlib, json, datetime, argparse, pathlib).
3. CLI surface:
   ```
   python scripts/check_graph_drift.py
       [--graph-source survey-cli/survey/graph/graph.py]   # default
       [--promotion-log survey-cli/logs/graph-promotions.jsonl]
       [--max-age-days N]              # rc=1 if newest > N days old
       [--exit-non-zero-on-drift]      # rc=1 if current != newest
       [--json]                        # JSON output instead of text
       [--quiet]                       # exit code only
   ```
4. Default mode: print drift status + age, exit 0 always.
5. `--exit-non-zero-on-drift`: exit 1 if `sha256(graph.py) != newest snapshot sha256`.
6. `--max-age-days N`: exit 1 if newest snapshot is older than N days.
7. **Edge cases handled:**
   - Promotion log missing entirely → exit 2 (config error), explicit message
   - Promotion log empty → exit 2 with hint "no snapshots recorded yet"
   - graph.py missing → exit 2

## File Boundaries

### MUST modify / create

- `scripts/check_graph_drift.py` (NEW, executable)
- `scripts/tests/test_check_graph_drift.py` (NEW)

### MUST NOT touch

- `survey-cli/survey/graph/**` (don't even read promote.py — pure stdlib,
  self-contained)
- `survey-cli/survey/learn/**`
- `scripts/check_audit_log_schema.py`
- `scripts/check_inbox_log_schema.py`
- Existing `.github/workflows/**`

### Plan-file deletion (rule A4)

Delete `_plans/122-graph-drift-detector.md` in the same commit.

## Conflict Surface

- Depends on PR #120 being merged. If #120 is still open, this PR MUST
  rebase on `main` after #120 lands (NOT on the feat/43 branch — keep
  history linear).
- No conflict with PR #114 / #118 / #119.

## Test Minimum

10 tests in `scripts/tests/test_check_graph_drift.py`:

| # | What |
|---|------|
| T1 | sha256 of identical file → no drift |
| T2 | sha256 of differing file → drift detected |
| T3 | Snapshot age computed from ISO timestamp in log |
| T4 | `--max-age-days` honored: just-promoted → rc=0 |
| T5 | `--max-age-days` honored: 30-day-old → rc=1 |
| T6 | `--exit-non-zero-on-drift` honored on drift → rc=1 |
| T7 | `--exit-non-zero-on-drift` honored on no-drift → rc=0 |
| T8 | Missing promotion log → rc=2 with clear message on stderr |
| T9 | Empty promotion log → rc=2 with "no snapshots recorded yet" |
| T10 | `--json` produces parseable JSON with required fields |

## Hand-off Notes for Agent-2

- The newest snapshot is the LAST line of the JSONL (append-only). Don't
  re-sort — trust the append order.
- Each promotion record schema (from SR-49):
  ```
  {"event": "graph_promotion", "timestamp": "...",
   "snapshot": {"path": "...", "sha256": "...", "bytes_written": N,
                "timestamp": "20260512T120000Z", "mode_octal": "0o444",
                "chmod_applied": true}}
  ```
- "Age" should be computed from `snapshot.timestamp` (file-level UTC),
  NOT the outer `record.timestamp` (log-write time). They are usually
  identical but the file-level one is the canonical promotion clock.
- DO NOT import from `survey.graph.promote` — keep this script
  importable as a standalone, even without the survey-cli package installed.

## Out of Scope

- Automatic snapshot creation when drift detected.
- Slack/email alerting.
- CI integration (separate issue if/when we want PR gating on this).
