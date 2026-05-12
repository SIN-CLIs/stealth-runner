# Plan: Issue #80 — Agent Qualification + CUA-Fallback Integration

> Temporary planning file. **DELETE in the same PR that closes #80.**
> Tracking issue: https://github.com/SIN-CLIs/stealth-runner/issues/80

## Goal
Eliminate three concrete disqualification causes observed 2026-05-11:
1. Agent picks "möchte nicht angeben" → disqualified
2. Agent gives up on Consent pages instead of using CUA
3. CUA AX-tree empty because tab is not foreground

## Status of subcomponents (verified 2026-05-12)
- [x] `survey-cli/survey/qualification_rules.py` exists with `NEVER_SELECT_PATTERNS` + `is_disqualifying_answer()`
- [ ] Verify wiring into `action_selector` / `decision` path so disqualifying answers are filtered BEFORE submission
- [ ] CUA-Fallback on Consent pages: bring tab to foreground (`Target.activateTarget` + `Page.bringToFront`) before AX-scan
- [ ] Telemetry: log every blocked disqualifying answer with question_text + matched pattern
- [ ] Regression test fixture: synthetic consent page + "prefer not to say" radio group

## Implementation Checklist
- [ ] Audit current call sites of `is_disqualifying_answer` — confirm it runs on EVERY candidate before selection
- [ ] Add `_bring_tab_to_foreground()` helper in `cdp_actuator.py` invoked before AX-scan on Consent/Captcha pages
- [ ] Add `ActionResult.blocked_by_qualification: list[BlockedAnswer]` field
- [ ] Wire telemetry → `logs/qualification-blocks-{run_id}.jsonl`
- [ ] Tests: `tests/test_qualification_filter.py`, `tests/test_cua_foreground.py`

## Acceptance Criteria
- Synthetic "prefer not to say" radio: agent never selects it; chooses next-best answer per persona profile.
- Consent page with iframe + non-foreground tab: CUA produces non-empty AX-tree.
- Telemetry log shows blocked answers with reason.

## Files Affected
- `survey-cli/survey/qualification_rules.py` (extend)
- `survey-cli/survey/action_selector.py` (wire filter)
- `survey-cli/survey/cdp_actuator.py` (foreground helper)
- `survey-cli/survey/__init__.py` (export new types)
- `tests/test_qualification_filter.py` (new)
- `tests/test_cua_foreground.py` (new)

## Cleanup
After PR merge: `git rm _plans/80-agent-qualification.md`.
