# Session Log — 2026-05-07

> **Agent**: stealth-orchestrator (deepseek/deepseek-v4-pro)
> **Repo**: stealth-runner
> **Duration**: ~4h live debugging + documentation

## Summary

10+ critical discoveries during live crash-test on heypiggy.com survey automation. Survey successfully navigated from heypiggy dashboard → Angular pre-survey form → Qualtrics (new tab). Balance fixed. React form filling solved. Zero payouts yet — stuck on Qualtrics language page.

## Key Discoveries

### 1. Surveys Open in NEW Tabs
Survey navigates to external URL (bceconsulting.az1.qualtrics.com) in new Chrome tab. CDP was connected to wrong tab for 90% of session.

### 2. 7-9 Stacked Modals on Dashboard
Welcome bonus, settings, name check, push notifications — all at same z-index and coordinates. Clicking "Nächste" at (600,547) hits "Schließen" instead.

### 3. React Forms Need Native Setter
`.value = 'X'` doesn't trigger React onChange. Must use `Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(el, val)`.

### 4. Qualtrics Language Select is `<select>` Dropdown
`<select class="Q_lang">` with `<option>Deutsch</option>`. NOT clickable labels.

### 5. Balance Bug: 125€ vs 2.23€
`read_balance()` used `Math.max()` — Level progress "125" near € symbol.

### 6. Fill-by-Element-ID Most Reliable
`document.getElementById('Age')`, `getElementById('Zip')` — Angular IDs: mat-input-2, mat-radio-0-input, next_0.

### 7. CDP Input.dispatchMouseEvent for Real Clicks
`element.click()` fails on layered modals. `Input.dispatchMouseEvent` at coordinates works.

### 8. cua-driver Needs --force-renderer-accessibility
0 AX elements without flag. Chrome started by webauto-nodriver lacks it.

## Files Changed

| File | Change |
|------|--------|
| `survey-cli/survey/scanner.py` | Balance read fix — filter by context |
| `survey-cli/survey/snapshot.py` | Modal-center element filtering, dict-format responses |
| `survey-cli/tests/test_snapshot.py` | Updated mocks to dict format |

## Commits

| Hash | Message |
|------|---------|
| `e2a327a` | fix(survey): live debugging marathon — 10+ critical discoveries |
| `4f0a04e` | docs(sota): live debugging discoveries — 8 learnings, 5 fixes, 11 issues |
| `4aa0ad0` | chore(graphify): auto-rebuilt graph after doc updates |

## Test Suite
- 362 pass, 4 skipped
- All snapshot tests updated for new dict format

## Repos Synced
19 stealth repos updated with learn.md §Q + fix.md #5-#9. 18 pushed to GitHub. A2A-SIN-Worker-heypiggy archived (local only).

## GitHub Issues Created
- #26 (P0): Qualtrics loop stuck on language page
- #27 (P0): Completion detection
- #28 (P0): Auto tab switching
- #23 (P1): Form validation errors
- #24 (P1): Anti-stuck loop
- #25 (P1): Element leaf-node filter

## Next Steps
1. Complete Qualtrics loop: answer country + advance past language page
2. Auto-detect new tabs after clickSurvey()
3. Get first payout (EUR > 0)
