# Plan: Issue #43 (SR-49) — Graph compiled promotion after 10x success

> Temporary planning file. **DELETE in the same PR that closes #43.**

## Goal
After 10 consecutive successful runs of a survey provider, freeze the current graph as a versioned, read-only artifact for production replay.

## Implementation Checklist
- [ ] Add `survey-cli/survey/graph/promote.py` with promotion criteria:
      - 10 successes (balance_after > balance_before)
      - 0 delegated runs (consecutive_failures < 3 in all)
      - 0 unresolved errors in state.errors
- [ ] Compile current graph definition → `survey-cli/survey/graph/compiled/survey_graph_v<TIMESTAMP>.py`
- [ ] `chmod 444` on the compiled file (read-only)
- [ ] Promotion log: `logs/graph-promotions.jsonl`
- [ ] Test: synthetic 10x success → assert compiled file exists + mode 444

## Acceptance Criteria
- Promotion runs only after criteria met
- Compiled files are immutable (444)
- Promotion log records SHA of compiled file

## Files Affected
- `survey-cli/survey/graph/promote.py` (new)
- `survey-cli/survey/graph/compiled/` (new dir)
- `tests/test_graph_promotion.py` (new)

## Cleanup
After PR merge: `git rm _plans/43-graph-compiled-promotion.md`.
