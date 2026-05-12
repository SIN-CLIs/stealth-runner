# Plan: Issue #96 — Promote OPERATIONAL RULES to top of AGENTS.md

> Temporary planning file. **DELETE in the same PR that closes #96.**
> Tracking issue: https://github.com/SIN-CLIs/stealth-runner/issues/96

## Context
Today's session surfaced several painful but valuable lessons (most importantly: a hard-delete of 49 MDs that violated the "nothing is deleted, only migrated" rule). The agent currently has no top-level rule book — sinrules.md content lives only in the LEGACY archive at the bottom of AGENTS.md and is therefore invisible during normal operation.

## Goal
Insert a new section `## OPERATIONAL RULES (READ FIRST — applies to every agent action)` directly **after the STATUS INDEX** so it is in the first ~100 lines of AGENTS.md. The section must combine:
- **Part A — Session-Hardened Rules**: 10 rules distilled from today's lessons (delete-discipline, plan-file lifecycle, root-MD rule, STATUS INDEX maintenance, GitHub-API workflow, etc.).
- **Part B — Historical Golden Rules**: 13 distilled rules (R1-R13) and key architectural decisions from the historical sinrules.md, condensed (~50-80 lines, not the 400-line verbatim).
- **Part C — Conflict Markers**: Explicitly flag known contradictions (e.g. `src/stealth_survey/` is both PRIMARY in §3.1 of sinrules and "INTENTIONALLY DELETED" in §9 — agent must defer to current code in `survey-cli/survey/`).

## In Scope
- New top-level RULES section in AGENTS.md
- STATUS INDEX row for #96
- CHANGELOG.md entry
- This plan file deleted in the same commit

## Out of Scope
- Re-litigating historical decisions — only codify what is actionable now.
- Removing the LEGACY (RESTORE PASS — #95) sinrules section — it stays for full traceability.

## Implementation Checklist
- [ ] Compose Part A (10 session-hardened rules in directive form: "MUST / NEVER / ALWAYS")
- [ ] Compose Part B (R1-R13 distilled into a single table + brief commentary)
- [ ] Compose Part C (known contradictions and current source of truth)
- [ ] Insert directly after the STATUS INDEX block
- [ ] Update STATUS INDEX: add `#96 DONE` row
- [ ] CHANGELOG entry
- [ ] Single atomic commit via Git Data API
- [ ] Delete this plan file

## Acceptance Criteria
- New section is at most ~150 lines, fits within the first 250 lines of AGENTS.md.
- Every rule is actionable (verb-led, testable).
- Cross-references point to either a code symbol (`file::symbol`) or a STATUS-INDEX issue.

## Cleanup
After PR merge: this file is removed in the same commit (`git rm _plans/96-operational-rules.md`).
