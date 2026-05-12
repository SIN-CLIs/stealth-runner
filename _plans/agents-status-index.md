# Plan: AGENTS.md — Add Compact STATUS INDEX at Top

> Temporary planning file. **DELETE in the same PR that closes the meta issue.**

## Goal
Any LLM agent reading AGENTS.md should know within the first 30 lines what is DONE / IN-PROGRESS / BLOCKED / NEXT, and where the relevant code lives.

## Implementation
Insert immediately under the first heading of `AGENTS.md`, before any narrative:

```
## STATUS INDEX (machine-readable, update on every PR)

| Issue | Status      | Code Location / Plan                                           |
|-------|-------------|---------------------------------------------------------------|
| #84   | DONE        | survey-cli/survey/cdp_actuator.py::_wait_for_dom_stable        |
| #85   | DONE        | survey-cli/survey/cdp_actuator.py (no_dom_change retry, 4x exp) |
| #86   | DONE        | survey-cli/survey/cdp_actuator.py::_wait_for_position_stable   |
| #87   | PLANNED     | _plans/87-form-validation.md                                  |
| #88   | EPIC        | (this file)                                                   |
| #91   | PLANNED     | _plans/repo-cleanup.md                                        |
| #93   | PLANNED     | _plans/oopif-autoattach.md                                    |
| #94   | PLANNED     | _plans/js-dialog-handler.md                                   |
```

## Rules
- Update entry on every PR that changes the status of a tracked work item.
- One line per entry. Always point to a code symbol (`file::function`) or a plan file.

## Acceptance Criteria
- New `STATUS INDEX` section exists in AGENTS.md, directly under the top heading.
- All current issues #84-#88 + new hardening issues are listed.
- Status reflects reality (#84/#85/#86 are DONE in code).

## Cleanup
After PR merge: `git rm _plans/agents-status-index.md`.
