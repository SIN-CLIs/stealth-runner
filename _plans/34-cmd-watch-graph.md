# Plan: Issue #34 (SR-40) — cmd_watch → LangGraph invoke

> Temporary planning file. **DELETE in the same PR that closes #34.**
> Tracking issue: https://github.com/SIN-CLIs/stealth-runner/issues/34
> **BLOCKED by SR-39 (cmd_run graph integration).** Plan kept ready.

## Goal
Replace the "dumb daemon" cmd_watch path (which calls SurveyRunner directly) with a LangGraph-based background task — gains: NIM-decision per page, learning, telemetry.

## Implementation Checklist
- [ ] Verify SR-39 status (cmd_run graph integration) — must be DONE first
- [ ] Refactor `survey-cli/survey.py::cmd_watch` to dispatch via `create_graph().invoke(state)`
- [ ] Move loop into FastAPI BackgroundTask for 24/7 operation
- [ ] Remove old `survey_runner` direct call sites (preserve as deprecation shim for one release)
- [ ] Update AGENTS.md to flag old path as DEPRECATED

## Acceptance Criteria
- `survey watch --start` spawns FastAPI BackgroundTask running `graph.invoke()`
- No code path remains where SurveyRunner is called directly outside graph nodes
- Telemetry: every watch-iteration emits structured run-state to logs

## Files Affected
- `survey-cli/survey.py` (~300 LOC refactor)
- `survey-cli/survey/graph/api.py` (FastAPI background task wrapper)

## Cleanup
After PR merge: `git rm _plans/34-cmd-watch-graph.md`.
