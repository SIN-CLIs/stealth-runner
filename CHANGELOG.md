# Changelog

## [Unreleased] - 2026-05-12

### Added (#93 + #94 — CDP Event-Chain, OOPIF Auto-Attach, JS-Dialog)
- `survey-cli/survey/cdp_client.py`: public `event_handler` attribute,
  `_dispatch_event` swallowing handler exceptions, non-blocking
  `drain_events(timeout)`, and `session_id=` parameter on `call()` for CDP
  flatten-multiplexing.
- `survey-cli/survey/js_dialog_handler.py` (NEW): two-layer Belt-and-Braces
  dialog dismissal — `Page.addScriptToEvaluateOnNewDocument` JS override
  (alert/confirm/prompt/beforeunload as no-ops) PLUS CDP event subscriber
  for `Page.javascriptDialogOpening` → `Page.handleJavaScriptDialog`.
- `survey-cli/survey/oopif_registry.py` (NEW): `Target.setAutoAttach(flatten=
  True)` + `OopifSession` dataclass + `frame_to_session` map maintained from
  `Target.attachedToTarget`/`Target.detachedFromTarget` events.
- `survey-cli/survey/cdp_universal.py`: `_scan_session` extracted helper;
  `scan()` now does Pass 1 (Top-Target) + `drain_events` + Pass 2 (per
  OOPIF session). `stable_id` schema unchanged (`sha1(frame_id + ":" +
  backend_node_id)`) → IDs stay collision-free across sessions.
- `survey-cli/survey/cdp_actuator.py`: `ClickActuator` installs
  `JsDialogHandler` once and calls `drain_events` after mouse events but
  before the post-hash, so dialogs are dismissed before DOM stability is
  measured. New result reason `dialog_dismissed`.
- `tests/test_event_handlers.py` (NEW): 9 unit tests using a `FakeWS` —
  covers event/response separation, handler exception swallowing, drain
  semantics, dialog dismissal, default policy, OOPIF attach+detach, type
  filtering (no workers), and multi-subscriber chaining.

### Removed
- `_plans/js-dialog-handler.md` (replaced by inline code + AGENTS.md §#94, A4).
- `_plans/oopif-autoattach.md` (replaced by inline code + AGENTS.md §#93, A4).

### Status Changes
- #93 → DONE (OOPIF scan coverage via flatten-attach; click-coordinate
  translation tracked as follow-up if needed)
- #94 → DONE (JS dialogs auto-dismissed with two-layer redundancy)
- AGENTS.md Coverage Snapshot updated; new deep-dive section
  "ISSUE #93 + #94" added with full architectural rationale.

## [Unreleased] - 2026-05-12

### Added (#97 — Full Issue Triage Sweep)
- Plan files for every previously-untriaged open issue (#18, #19, #20, #30, #31,
  #34, #39, #43, #56, #57, #58, #61, #62, #80, #83). Related issues batched
  where work overlaps (#18+#19, #30+#31, #61+#62).
- STATUS INDEX in AGENTS.md now covers every open issue with prio + status +
  plan-file or code-symbol reference. Adds Prio column.
- Audit evidence for #82: `delqhi/sin-hermes-agent` main contains no
  survey-solver files (verified 2026-05-12 against `git/trees/main?recursive=1`);
  the repo is a different project (Auth Rotator + Webshop). Closing as resolved.

### Status Changes
- #82 → DONE (audited, no migration needed)
- 13 previously-untriaged issues → labelled with prio (P0/P1/P2/P3/DEFERRED)

## [Unreleased] - 2026-05-12

### Added
- **(#96) OPERATIONAL RULES section** at the top of AGENTS.md (directly after
  STATUS INDEX). Combines 10 session-hardened rules (A1-A10), 13 distilled
  historical Golden Rules (R1-R13), known contradictions (Part C), and a
  consolidated banned-patterns table (Part D). This is now the agent's single
  read-first rule book; the full 400-line legacy `sinrules.md` remains in the
  LEGACY (RESTORE PASS — #95) archive for traceability.

## [Unreleased] - 2026-05-12

### Fixed
- **(#95) Critical restore**: recovered 49 root-level Markdown files that were
  hard-deleted in commit `2f8fdf0` without migration. Full verbatim content
  embedded into `AGENTS.md` under a new `MIGRATED LEGACY DOCS (RESTORE PASS — Issue #95)`
  section so the agent brain holds every byte. Original files remain deleted at
  the repo root in compliance with the 3-MD root rule (AGENTS.md / README.md /
  CHANGELOG.md only).

### Restored files (sorted)
- `CONTRIBUTING.md`
- `INTEGRATION_PLAN.md`
- `SUPPORT.md`
- `ULTIMATE-PLAN.md`
- `api.md`
- `architecture.md`
- `banned.md`
- `benchmarks.md`
- `brain.md`
- `commands.md`
- `design.md`
- `faq.md`
- `fix.md`
- `graph-report-template.md`
- `graph-report.md`
- `graphify.md`
- `history.md`
- `infisical.md`
- `issues.md`
- `opencode.md`
- `plan-sr-29-ps-captcha-ocr.md`
- `plan-sr-32-provider-detect.md`
- `plan-sr-33-persona-system.md`
- `plan-sr-34-test-suite.md`
- `plan-sr-35-chrome-safety.md`
- `plan-sr-36-docs-cleanup.md`
- `plan-sr-37-skylight-compact.md`
- `registry-actuation.md`
- `registry-credentials.md`
- `registry-google.md`
- `registry-graphify.md`
- `registry-macos.md`
- `registry-perception.md`
- `registry-skills.md`
- `registry-surveys.md`
- `registry.md`
- `security.md`
- `session-log-2026-05-06.md`
- `session-log-2026-05-07.md`
- `session-versager.md`
- `sinrules.md`
- `state.md`
- `successful.md`
- `testing.md`
- `tool-manifest.md`
- `tool-registry.md`
- `troubleshooting.md`
- `usage.md`

### Permanently deleted (no doc value)
- `2captcha.com__lemin_2026-05-03_22-59-15.jpg` (visual debug leftover)
- `2captcha.com__lemin_2026-05-03_23-00-40.jpg` (visual debug leftover)
- `2captcha.com__lemin_2026-05-03_23-00-55.jpg` (visual debug leftover)
- `2captcha.com__lemin_2026-05-03_23-00-59.jpg` (visual debug leftover)
- `skylight_screenshot.png` (visual debug leftover)
- `vision_input.jpg` (visual debug leftover)

## [Unreleased] - 2026-05-12

### Changed
- **Repo cleanup (#91)**: removed all legacy root-level Markdown files and stray
  binary assets. Only `AGENTS.md`, `README.md`, `CHANGELOG.md` remain at root.
- **AGENTS.md (#91)**: absorbed the full verbatim content of `STATUS.md`,
  `bugs.md`, `anti-learn.md`, `learn.md`, `roadmap.md`, `goal.md` into a new
  "MIGRATED LEGACY DOCS" section so the agent brain remains the single source
  of truth. STATUS INDEX at the top is now the canonical project state.
- **changelog.md → CHANGELOG.md**: renamed to follow convention.

### Removed (root-level legacy files merged into AGENTS.md or deemed obsolete)
- `CONTRIBUTING.md`
- `INTEGRATION_PLAN.md`
- `STATUS.md`
- `SUPPORT.md`
- `ULTIMATE-PLAN.md`
- `anti-learn.md`
- `api.md`
- `architecture.md`
- `banned.md`
- `benchmarks.md`
- `brain.md`
- `bugs.md`
- `commands.md`
- `design.md`
- `faq.md`
- `fix.md`
- `goal.md`
- `graph-report-template.md`
- `graph-report.md`
- `graphify.md`
- `history.md`
- `infisical.md`
- `issues.md`
- `learn.md`
- `opencode.md`
- `plan-sr-29-ps-captcha-ocr.md`
- `plan-sr-32-provider-detect.md`
- `plan-sr-33-persona-system.md`
- `plan-sr-34-test-suite.md`
- `plan-sr-35-chrome-safety.md`
- `plan-sr-36-docs-cleanup.md`
- `plan-sr-37-skylight-compact.md`
- `registry-actuation.md`
- `registry-credentials.md`
- `registry-google.md`
- `registry-graphify.md`
- `registry-macos.md`
- `registry-perception.md`
- `registry-skills.md`
- `registry-surveys.md`
- `registry.md`
- `roadmap.md`
- `security.md`
- `session-log-2026-05-06.md`
- `session-log-2026-05-07.md`
- `session-versager.md`
- `sinrules.md`
- `state.md`
- `successful.md`
- `testing.md`
- `tool-manifest.md`
- `tool-registry.md`
- `troubleshooting.md`
- `usage.md`

### Removed (stray binary assets at root)
- `2captcha.com__lemin_2026-05-03_22-59-15.jpg`
- `2captcha.com__lemin_2026-05-03_23-00-40.jpg`
- `2captcha.com__lemin_2026-05-03_23-00-55.jpg`
- `2captcha.com__lemin_2026-05-03_23-00-59.jpg`
- `skylight_screenshot.png`
- `vision_input.jpg`

## Historical entries


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
| **NEW** | Google Login: 6-Step CUA-ONLY Flow VERIFIED | [cli/modules/auto_google_login.py](cli/modules/auto_google_login.py) |
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

## 2026-05-08 — OPENCODE FIX: Zod v4 Crash + GitNexus + Graphify

### OpenCode Crash Fix (P0 → fixed)
- Root cause: `oh-my-opencode@3.11.2` and `opencode-antigravity-auth@1.6.5-beta.0` bundle Zod v4.
  OpenCode 1.14.41 uses Zod v3's `_zod.def` API. Tool resolution pipeline crashes.
- Fixed: uninstalled all banned plugins from npm/bun global, deleted plugin directories
  in `infra-sin-opencode-stack/`, deleted all `oh-my-*.json` files, reset opencode config
- File: `infra-sin-opencode-stack/banned.md` created with recovery procedure

### Provider Config Fix (P0 → fixed)
- Root cause: custom provider configs with model lists created DUPLICATES
- Fixed: empty `"provider": {}` — built-in providers auto-discover from auth.json

### GitNexus + Graphify Integration (P1 → done)
- GitNexus: 14,594 nodes, 18,562 edges, 300 flows
- Graphify: 2,110 nodes, 4,953 edges, 118 communities
- Binary: `/Users/jeremy/Library/pnpm/nodejs/22.14.0/bin/gitnexus`

### Model ID Corrections (P1 → done)
- Fireworks: `minimax-m2p7` (dash), `kimi-k2p6` (dash)
- Vercel: `vercel/deepseek/deepseek-v4-flash` (provider prefix required)

### OpenCode Run Bug (P0 → known issue, no fix)
- `opencode run "hello"` crashes from real HOME even with clean config
- Bug exists in all tested versions (1.4.11 to 1.14.41)
- Workaround: use TUI (`opencode`)
