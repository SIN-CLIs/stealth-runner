# Plan: Issues #30 + #31 — GitNexus Reindex + Impact Gate (DEFERRED)

> Temporary planning file. **DELETE in the same PR that closes both #30 and #31.**

## Decision: DEFER until GitNexus is in active use across the survey-solver project.

Reason: GitNexus is an infrastructure-level tool not currently wired into stealth-runner CI. Spending engineering cycles on cross-repo cron + pre-commit gates would not advance the Survey-Solver completion target (#88).

## Re-trigger conditions
- [ ] When GitNexus is integrated into ≥1 active stealth-runner CI workflow, re-open #30 and #31
- [ ] Until then, these issues stay in STATUS INDEX as `DEFERRED` with a link to this plan

## If/when re-activated
- **#30** — Periodic re-index across all stealth repos via GitHub Action (cron)
- **#31** — Pre-commit hook calling `detect_changes` for risk classification

## Cleanup
After both issues closed (now, as DEFERRED) OR after re-activation completes: `git rm _plans/30-31-gitnexus-deferred.md`.
