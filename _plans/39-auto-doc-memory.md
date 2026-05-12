# Plan: Issue #39 (SR-45) — Auto-Doc + stealth-memory integration

> Temporary planning file. **DELETE in the same PR that closes #39.**
> Tracking issue: https://github.com/SIN-CLIs/stealth-runner/issues/39

## Goal
After every survey run, persist the outcome + provider + error trace to `stealth-memory` so the agent learns across sessions. Replaces the old `learn.md` / `anti-learn.md` flow (those are now in AGENTS.md LEGACY archive per #95).

## Implementation Checklist
- [ ] In `survey-cli/survey/graph/nodes.py::detect_completion_node`, on terminal state:
      - Compute success boolean (`balance_after > balance_before`)
      - Build outcome record: `{run_id, provider, success, error, ts, page_count, duration_ms}`
      - Persist via `stealth_memory.client.append_outcome(record)`
- [ ] If `stealth-memory` lib unavailable, fall back to local JSONL: `logs/outcomes/<run_id>.jsonl`
- [ ] No more writes to legacy `learn.md` / `anti-learn.md` (those are archived in AGENTS.md)
- [ ] AGENTS.md STATUS INDEX line updated to DONE on merge

## Acceptance Criteria
- A successful run produces an outcome record retrievable via `stealth_memory.client.list_recent()`
- Failed run produces a record with `success=False` and error class
- No regressions in graph end-to-end test

## Files Affected
- `survey-cli/survey/graph/nodes.py` (~40 LOC in `detect_completion_node`)
- `tests/test_graph_completion_memory.py` (new)

## Cleanup
After PR merge: `git rm _plans/39-auto-doc-memory.md`.
