# Plan: Issue #57 (SR-58) — `survey learn apply` CLI with AST roundtrip

> Temporary planning file. **DELETE in the same PR that closes #57.**

## Goal
Manual, audited apply path for accepted matcher patterns. Modifies `FIELD_PATTERNS` via AST roundtrip (never regex on source). `_AUTO_APPLY` stays False.

## Implementation Checklist
- [ ] CLI: `survey learn apply <inbox.jsonl> [--dry-run] [--approve-all|--interactive]`
- [ ] Validate confidence: substring ≥0.7, LLM ≥0.85
- [ ] AST roundtrip on `survey/profile_loader.py::FIELD_PATTERNS`
- [ ] Audit log: `logs/learn-applied-{run_id}.jsonl` (timestamp, pattern, source, reviewer)
- [ ] Test suite green pre AND post apply, else auto-rollback
- [ ] `_AUTO_APPLY = False` invariant preserved
- [ ] Test: `tests/test_learn_apply.py` roundtrip (inbox → diff → green tests)

## Acceptance Criteria
- Dry-run prints diff without writing
- Interactive mode asks per entry
- `--approve-all` records reviewer hash in audit log
- Failing post-apply tests → rollback to pre-state

## Files Affected
- `survey-cli/survey/learn/cli.py` (extend)
- `survey-cli/survey/learn/apply.py` (new)
- `tests/test_learn_apply.py` (new)

## Cleanup
After PR merge: `git rm _plans/57-survey-learn-apply.md`.
