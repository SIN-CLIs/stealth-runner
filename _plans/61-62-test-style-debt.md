# Plan: Issues #61 + #62 — Test-Debt + Style-Debt batched cleanup

> Temporary planning file. **DELETE in the same PR that closes both #61 and #62.**

## Goal
Remove all `--ignore`-flags from CI for ruff and pytest so the canonical CI commands are clean. Tracked together because they touch the same files and the same CI matrix.

## #62 — Test-Debt (10 ignored test files, 37 failures)
- [ ] `test_in_page_modal.py` — needs real browser → document as `@pytest.mark.real_browser` and skip in CI; do not delete
- [ ] `test_security.py` — fix module-import issue
- [ ] `test_run_survey.py` — triage; either fix or mark deprecated with reason in docstring
- [ ] `test_chrome_launcher.py` — triage
- [ ] `test_prequalifier.py` — triage
- [ ] `test_opener.py` — triage
- [ ] `test_tool_fill_survey.py` — triage
- [ ] `test_open_survey_verified.py` — triage
- [ ] `test_balance.py` — triage
- [ ] `test_action_selector.py` — triage

## #61 — Style-Debt (E501/E701/E702)
- [ ] `ruff format` autofix (E501) — diff-review for semantic safety
- [ ] Manual E701 fixes (21 findings) — `if x: y` → `if x:\n    y`
- [ ] Manual E702 — most are JS-in-Python-strings (false positives); add `# noqa: E702` with reason comment
- [ ] Target: `ruff check survey-cli/survey --select E,W,F` runs without `--ignore` flags

## Acceptance Criteria
- CI commands: `pytest survey-cli/tests -q` (no `--ignore` flags) AND `ruff check survey-cli/survey --select E,W,F` (no `--ignore` flags) both green
- AGENTS.md §13.8.1 SR-62 and SR-63 → DONE

## Files Affected
- 10 test files in `survey-cli/tests/`
- Multiple `survey-cli/survey/**.py` for ruff fixes
- CI workflow `.github/workflows/*.yml`

## Cleanup
After both issues closed: `git rm _plans/61-62-test-style-debt.md`.
