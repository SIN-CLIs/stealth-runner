# Plan: Repo Cleanup — Remove Legacy MD & Stray Assets

> Temporary planning file. **DELETE in the same PR that closes the cleanup issue.**

## Goal
Reduce root-level noise. AGENTS.md is the single source of truth. Everything else duplicates, contradicts, or is dead.

## Files to KEEP at root
- `AGENTS.md` (agent brain)
- `README.md` (user-facing entry)
- `CONTRIBUTING.md` (GitHub convention)
- `SUPPORT.md` (GitHub convention)
- `LICENSE` (if present)

## Files to DELETE from root
Plan files (already implemented, info migrated to AGENTS.md):
- `plan-sr-29-ps-captcha-ocr.md`
- `plan-sr-32-provider-detect.md`
- `plan-sr-33-persona-system.md`
- `plan-sr-34-test-suite.md`
- `plan-sr-35-chrome-safety.md`
- `plan-sr-36-docs-cleanup.md`
- `plan-sr-37-skylight-compact.md`

Legacy / duplicated docs (info already in AGENTS.md or obsolete):
- `INTEGRATION_PLAN.md`, `STATUS.md`, `ULTIMATE-PLAN.md`
- `anti-learn.md`, `api.md`, `architecture.md`, `banned.md`, `benchmarks.md`
- `brain.md`, `bugs.md`, `changelog.md`, `commands.md`, `design.md`
- `faq.md`, `fix.md`, `goal.md`, `graph-report.md`, `graph-report-template.md`
- `graphify.md`, `history.md`, `infisical.md`, `issues.md`, `learn.md`
- `opencode.md`, `roadmap.md`, `security.md`, `sinrules.md`
- `session-log-2026-05-06.md`, `session-log-2026-05-07.md`, `session-versager.md`
- `state.md`, `successful.md`, `testing.md`, `troubleshooting.md`, `usage.md`
- `registry.md`, `registry-actuation.md`, `registry-credentials.md`, `registry-google.md`
- `registry-graphify.md`, `registry-macos.md`, `registry-perception.md`
- `registry-skills.md`, `registry-surveys.md`
- `tool-manifest.md`, `tool-registry.md`

Stray binary assets in root:
- `2captcha.com__lemin_2026-05-03_22-59-15.jpg`
- `2captcha.com__lemin_2026-05-03_23-00-40.jpg`
- `2captcha.com__lemin_2026-05-03_23-00-55.jpg`
- `2captcha.com__lemin_2026-05-03_23-00-59.jpg`
- `skylight_screenshot.png`
- `vision_input.jpg`

## Pre-Deletion Checks
- [ ] `grep -r "filename" .` for each candidate; if referenced by code/CI, migrate critical info into AGENTS.md FIRST.
- [ ] Confirm no GitHub Actions workflow consumes these paths.
- [ ] Confirm README.md does not link to them (fix links if it does).

## Execution
- [ ] Migration commit(s) for any unique non-duplicate content into AGENTS.md.
- [ ] Single deletion commit listing all removed files.

## Acceptance Criteria
- Root contains only the KEEP-list MDs and source/asset directories.
- AGENTS.md retains every unique piece of information from deleted files.
- CI green; README links valid.

## Cleanup
After PR merge: `git rm _plans/repo-cleanup.md` (in the same PR).
