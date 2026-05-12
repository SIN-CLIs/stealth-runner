# Plan: Issue #56 (SR-57) — FCTC-ES Phase 2: LLM-Suggester for matcher misses

> Temporary planning file. **DELETE in the same PR that closes #56.**

## Goal
When exact (1.0) and substring (0.7) matchers fail, ask an LLM to map the question text → profile field. Threshold 0.85, inbox-only (no auto-apply per `_AUTO_APPLY=False`).

## Implementation Checklist
- [ ] Add `survey-cli/survey/learn/suggester.py::suggest_via_llm(miss, profile_schema)`
- [ ] Trigger ONLY after exact + substring fail
- [ ] Use AI Gateway: `openai/gpt-5-mini` (zero-config)
- [ ] Confidence threshold 0.85, else discard
- [ ] Inbox entry includes: `source: "llm"`, `model`, `prompt_hash`
- [ ] If `AI_GATEWAY_API_KEY` missing → skip cleanly (no crash)
- [ ] Test: `tests/test_learn_llm_suggester.py` with mocked LLM client

## Acceptance Criteria
- Synthetic miss "Wie viele Personen wohnen in Ihrem Haushalt?" → suggests `household_size` with ≥0.85 confidence
- Inbox entry contains required metadata fields
- No crash when API key absent

## Depends On
- #53 (SR-55, FCTC-ES Phase 1) — DONE in PR #54
- Eval-Harness (SR-56) as regression gate

## Files Affected
- `survey-cli/survey/learn/suggester.py`
- `tests/test_learn_llm_suggester.py` (new)

## Cleanup
After PR merge: `git rm _plans/56-llm-suggester.md`.
