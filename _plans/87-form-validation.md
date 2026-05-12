# Plan: Issue #87 — Form Validation Detection

> Temporary planning file. **DELETE in the same PR that closes #87.**
> Tracking issue: https://github.com/SIN-CLIs/stealth-runner/issues/87

## Goal
Detect required-but-empty fields BEFORE clicking submit, and detect validation errors AFTER submit, so the agent never wastes a submission and can self-correct.

## In Scope
- Pre-submit scan: enumerate elements with `required`, `aria-required="true"`, `[data-required]`, role-based required indicators (radiogroup, checkbox group min/max).
- Filled-state check via existing scanner snapshot (value, checked, selected).
- Post-submit error detection: `role="alert"`, `aria-invalid="true"`, common error classes (`.error`, `.invalid`, `.has-error`, `.field-error`).
- New `ValidationReport` dataclass returned by submit-path actions.
- Retry hook: on validation failure, re-scan + retry mapping (uses #85 retry infra).

## Out of Scope
- LLM-based question re-mapping (covered by #56).
- Captcha / 2FA flows.
- Multi-page wizard cross-page validation (separate issue if needed).

## Implementation Checklist
- [ ] Add `_scan_required_fields(snapshot)` in `cdp_actuator.py`.
- [ ] Add `_detect_validation_errors(snapshot)` in `cdp_actuator.py`.
- [ ] Add `ValidationReport` dataclass: `missing: list[ElementRef]`, `invalid: list[ElementRef]`, `errors: list[ErrorMessage]`.
- [ ] Wire into `submit()` / `click_submit()`: pre-check + post-check.
- [ ] Extend `ActionResult` with `validation_report: Optional[ValidationReport]`.
- [ ] Inline docstrings on every new symbol.
- [ ] Add row to AGENTS.md STATUS INDEX.

## Acceptance Criteria
- Pre-submit: missing required fields returned with stable element IDs.
- Post-submit: validation errors captured even when URL does not change.
- All existing tests pass; new test in `tests/test_form_validation.py` covers required + aria-required + data-required.

## Files Affected
- `survey-cli/survey/cdp_actuator.py`
- `survey-cli/survey/__init__.py`
- `AGENTS.md`
- `tests/test_form_validation.py` (new)

## Test Plan
- Unit: synthetic CDP responses for required/aria-required/data-required.
- Integration: local HTML fixture with mixed required field types.
- E2E: smoke-run against archived survey HTML.

## Cleanup
After PR merge: `git rm _plans/87-form-validation.md` (in the same PR).
