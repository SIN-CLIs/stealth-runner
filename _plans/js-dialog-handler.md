# Plan: Scanner Hardening — Page.javascriptDialogOpening Handler

> Temporary planning file. **DELETE in the same PR that closes the hardening issue.**

## Goal
Prevent the agent from hanging when a survey or captcha triggers `alert()`, `confirm()`, `prompt()`, or `beforeunload`. Today there is no handler; Chrome blocks the UI until manual action.

## Implementation Checklist
- [ ] In `cdp_actuator.py` bootstrap, subscribe to `Page.javascriptDialogOpening`.
- [ ] Auto-dismiss policy:
      - `alert`        → `Page.handleJavaScriptDialog(accept=True)`
      - `confirm`      → accept (safe default for surveys; document rationale)
      - `prompt`       → accept with empty string; emit WARNING log
      - `beforeunload` → accept (allow agent-initiated navigation)
- [ ] Record every dialog in `ActionResult.dialogs: list[DialogEvent]` (`type`, `message`, `accepted`, `prompt_text`, `ts`).
- [ ] Inline-document the policy decision so future agents understand the trade-off.
- [ ] Update AGENTS.md STATUS INDEX.

## Acceptance Criteria
- Synthetic page that calls `confirm("proceed?")` mid-flow does not block the agent.
- `ActionResult.dialogs` reflects the event.
- Configurable override hook for tests that want to refuse a dialog.

## Files Affected
- `survey-cli/survey/cdp_actuator.py`
- `AGENTS.md`
- `tests/test_js_dialog.py` (new)

## Test Plan
- Unit: simulate `Page.javascriptDialogOpening` event → assert handle call.
- Integration: local HTML fires `confirm` on button click; agent proceeds.

## Cleanup
After PR merge: `git rm _plans/js-dialog-handler.md`.
