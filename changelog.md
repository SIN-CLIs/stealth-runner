# changelog.md — Changelog Stealth Suite

> **Zweck**: Jede signifikante Änderung wird hier mit Datum und Referenz dokumentiert.
> Format: `YYYY-MM-DD | Typ | Beschreibung | Issue/PR`

---

## 2026-05-06 — NEXT-GEN: 4 Root Causes Fixed + Crash-Tested

### P0: Pre-Qualifier Handling
- Fixed: run_loop() now calls handle_pre_qualifier() instead of skipping pre-qualifiers
- Added: message_button to CPX API POST (required for API acceptance)
- Added: pre-qualifier failure cache, started_count tracking
- Tests: 13 (test_prequalifier.py), LIVE-verified: 6/6 pre-qualifiers processed

### P1: Stealth Injection (Anti-Detection)
- Added: create_blank_tab(), inject_stealth_to_tab(), navigate_tab() to chrome.py
- Added: 12-module stealth bundle (251 lines) via Page.addScriptToEvaluateOnNewDocument
- Tests: 19 (test_stealth.py), LIVE-verified: [STEALTH] ✅ Injected stealth JS into tab

### P1: CDPConnection (Retry + Reconnect + ID Routing)
- Added: survey/cdp_client.py (229 lines) — sync wrapper with exponential backoff
- Retry: 5 attempts, 0.3→4.8s backoff, auto-reconnect on "No such target"
- Integrated: runner.py _refresh_tab_ws(), execute.py BatchExecutor.execute()
- Tests: 15 (test_cdp_client.py), LIVE-verified: 0 "No such target id" errors

### P3: Balance Read Timing
- Fixed: balance_before read BEFORE tab creation (was AFTER → dashboard WS stale)
- Added: try/except wrapper, max(0, earned) to prevent negatives
- Tests: 5 (test_balance.py), LIVE-verified: [BALANCE] Before: 2.23€

### Bonus Fixes
- read_page_text + detect_error_page added as static methods to BatchExecutor
- Pre-qualifier failure cache avoids redundant CPX API calls

### Metrics
- 282 total tests (52 new), 0 regressions
- 1 survey completed in production: 36.3s, 3 iterations, status=completed
- Balance before/after tracking verified

## 2026-05-05

| Typ | Beschreibung | Referenz |
|-----|-------------|----------|
| **FIX** | Persona Age Bug: hartcodiertes Alter 42 → date_of_birth="1993-11-13", Alter dynamisch berechnet (32) | [fix.md](fix.md#hartcodiertes-alter) |
| **FIX** | persona_manager.py: DEFAULT_PERSONA age entfernt, date_of_birth hinzugefügt, education→Meister | [persona_manager.py](../playstealth-cli/playstealth_actions/persona_manager.py) |
| **FIX** | jeremy_schulze.json: 6 Felder befüllt (date_of_birth, city, postal_code, employment, education, household) | [jeremy_schulze.json](../A2A-SIN-Worker-heypiggy/profiles/jeremy_schulze.json) |
| **FIX** | sinrules.md: webauto/skylight/CDP klare Abgrenzung dokumentiert | [sinrules.md](sinrules.md#6) |
| **NEW** | /commands Reorganisation: 7 Provider-Subdirectories, cmd-rules.md mit 14 Regeln | [cmd-rules.md](commands/cmd-rules.md) |
| **NEW** | cua-driver/click-survey-card.md: Survey Cards via CUA klickbar (AXGroup → AXPress) | [click-survey-card.md](commands/cua-driver/click-survey-card.md) |
| **NEW** | End-to-End Survey Test: Login→Card→Consent→Frage→Disqualifikation (1 Zyklus) | [history.md](history.md) |
| **NEW** | registry.md: Master Command Registry mit Category-Registries | [registry.md](registry.md) |
| **NEW** | history.md: Session History Log initialisiert | [history.md](history.md) |
| **NEW** | roadmap.md: Stealth Suite Meilensteine definiert | [roadmap.md](roadmap.md) |
| **NEW** | registry-perception.md + registry-actuation.md angelegt | [registry-perception.md](registry-perception.md) |
| **NEW** | 6 Explore Agents: 10 SIN-CLIs Repos gescannt, alle CLI-Commands dokumentiert | [history.md](history.md#2026-05-05) |

| 2026-05-05 | **NEW** | CaptchaSolver Modul: Slide-Captcha via cua-driver drag + AppleEvents JS | [cli/modules/captcha_solver.py](cli/modules/captcha_solver.py) |
| 2026-05-05 | **FIX** | Koordinaten-Bug: Window-Position dynamisch statt hardcoded (73,70) | [commands/captcha/solve-slide.md](commands/captcha/solve-slide.md) |
| 2026-05-05 | **NEW** | Text-Captcha via pixtral-large Vision (Mistral API) | [commands/captcha/solve-text.md](commands/captcha/solve-text.md) |
| 2026-05-05 | **BANNED** | cliclick (Mausbewegung) + CDP dispatchEvent | [banned.md](banned.md) |

## 2026-05-04

| Typ | Beschreibung | Referenz |
|-----|-------------|----------|
| **FIX** | Skylight-cli Widersprüche in AGENTS.md, sinrules.md, brain.md behoben | [AGENTS.md](AGENTS.md) |
| **NEW** | Banned Commands: pyautogui, pynput, coordinates, applescript, skylight, webauto, CDP | [banned.md](banned.md) |
| **NEW** | Google Login PASSKEY Flow: 7-Step Dokumentation | [google/login-flow.md](commands/google/login-flow.md) |
| **NEW** | macOS Recovery Mode als SECRET WAY dokumentiert | [macos-recovery-mode.md](commands/macos-recovery-mode.md) |
| **NEW** | Infisical EU Login + Secrets dokumentiert | [infisical/](commands/infisical/) |

## 2026-05-03

| Typ | Beschreibung | Referenz |
|-----|-------------|----------|
| **NEW** | CUA-ONLY Trinity Architektur aktiviert | [AGENTS.md](AGENTS.md) |
| **NEW** | Heypiggy Credentials dokumentiert | [heypiggy/credentials.md](commands/heypiggy/credentials.md) |
| **NEW** | Session Manager Launch dokumentiert | [session-manager/launch.md](commands/session-manager/launch.md) |

## 2026-05-07 — LIVE CRASH-TEST: 10+ Discoveries, 5 Fixes, 0 Payouts

### Balance Fix (P3 → fixed)
- Fixed: read_balance() no longer returns 125€ (Level progress) instead of 2.23€
- Root cause: Math.max() of all € values on page picked up Level progress
- Fix: filter by value range (1.0-1000) + context check for "Level"/"Min" keywords
- File: survey-cli/survey/scanner.py, read_balance()

### React Form Fill (P1 → fixed)
- Fixed: React-controlled inputs now accept values via native setter
- Root cause: .value = 'X' silent failure on React synthetic events
- Fix: Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(el, val)
- Alternative: document.execCommand('insertText', false, val)

### Stacked Modals (P1 → fixed)
- Fixed: 7-9 layered modals at identical coordinates on heypiggy dashboard
- Fix: Close all "Schließen" buttons via JS before survey interaction

### Survey Tab Detection (P0 → discovered)
- Discovered: Surveys open in NEW Chrome tabs (Qualtrics/Samplicio URLs)
- CDP was connected to wrong tab for 90% of session
- Fix approach: check tab count via /json before/after clickSurvey()

### Qualtrics Language Select (P1 → discovered)
- Discovered: Language picker is <select class="Q_lang"> dropdown, not clickable labels
- Must use selectedIndex + dispatchEvent('change')

### Documentation
- learn.md §Q: 8 crash-test discoveries
- fix.md: 5 new fixes documented
- issues.md: 11 SOTA-formatted GitHub issues created
- session-log-2026-05-07.md: full timeline
- sessions/2026-05-07.md: architecture flow + root causes
- 19 stealth repos synced with learn.md §Q + fix.md #5-#9

### Tests
- 362 pass, 4 skipped
- test_snapshot.py: all mocks updated to dict format for new element responses
