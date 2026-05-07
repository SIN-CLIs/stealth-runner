# Issues — Stealth-Runner SOTA (2026-05-07)

> **Live Debugging Session 2026-05-07** — All issues discovered during survey loop execution.
> **Assignee**: `stealth-orchestrator` (default) | **Repo**: [stealth-runner](https://github.com/SIN-CLIs/stealth-runner) | **Board**: [GitHub Projects](https://github.com/orgs/SIN-CLIs/projects)

---

## Open Issues (11)

---

### #1: Qualtrics survey loop stuck on language page
**Priority**: P0 | **Labels**: `bug`, `providers` | **Component**: execute, snapshot
**Status**: OPEN | **Found**: 2026-05-07 | **Assignee**: stealth-orchestrator
**Blocking**: Payouts — cant complete any Qualtrics survey

**Problem**: Clicking "Deutschland" country option via CDP `Input.dispatchMouseEvent` does not advance the survey. The Qualtrics `>>` (next) button is not detected by element scan because the leaf-node walker skips it.
**Expected**: Country radio selection + `>>` click advances to next page.
**Actual**: 50 iterations wasted clicking same element; `.NextButton` not found in snapshot.
**Files**: `survey-cli/survey/execute.py`, `survey-cli/survey/snapshot.py`, `survey-cli/survey/providers/qualtrics.py`
**Fix approach**: Add Qualtrics-specific `.NextButton` selector + proper radio selection via `.LabelWrapper` click + broader element scan including parent containers.

---

### #2: Survey completion not detected
**Priority**: P0 | **Labels**: `bug`, `runner` | **Component**: runner, scanner
**Status**: OPEN | **Found**: 2026-05-07 | **Assignee**: stealth-orchestrator
**Blocking**: Payouts — no balance verification after completing survey

**Problem**: After completing all survey questions and reaching the end, the runner does not detect completion. No payout verification triggers. Balance diff check never runs.
**Expected**: Detection of completion keywords ("Vielen Dank", "Thank you", "Survey Complete") + automatic balance diff check across all tabs.
**Actual**: Runner stays in question-loop, eventually times out.
**Files**: `survey-cli/survey/runner.py`, `survey-cli/survey/scanner.py`, `src/stealth_survey/survey_agent.py`
**Fix approach**: Add completion keyword detection via `document.body.innerText` scan across all tabs, then trigger balance diff via `survey.py balance` subcommand.

---

### #3: Tab switching not automated in run_survey()
**Priority**: P0 | **Labels**: `bug`, `runner` | **Component**: runner, cdp_client
**Status**: OPEN | **Found**: 2026-05-07 | **Assignee**: stealth-orchestrator
**Blocking**: Payouts — survey opens in new tab, runner stuck on old tab

**Problem**: Manual tab detection via `list_tabs` works, but `run_survey()` does not auto-switch when a survey opens in a new tab. The CDP connection stays on the dashboard tab while the survey is running in a different tab.
**Expected**: Automatic CDP reconnection to the tab containing the active survey URL.
**Actual**: Runner executes actions on wrong tab (dashboard), survey tab ignored.
**Files**: `survey-cli/survey/runner.py`, `survey-cli/survey/cdp_client.py`
**Fix approach**: Add URL-change watcher + auto `switch_tab` in `run_survey()` main loop, reconnect CDP WebSocket to new target.

---

### #4: Form validation errors not handled
**Priority**: P1 | **Labels**: `bug`, `execute` | **Component**: execute, nim_client
**Status**: OPEN | **Found**: 2026-05-07 | **Assignee**: stealth-orchestrator

**Problem**: Validation error `"Value must be something like '53'"` on age field. No retry logic with adjusted value. Survey disqualifies after invalid input.
**Expected**: Parse validation message, extract expected format/range, adjust value, retry automatically.
**Actual**: Invalid value submitted, survey screen-out or page stuck.
**Files**: `survey-cli/survey/execute.py`, `src/stealth_survey/nim_client.py`
**Fix approach**: Add `parse_validation_error()` that extracts hint from error text + `adjust_value()` that corrects the input + retry loop (max 3 attempts).

---

### #5: Anti-stuck loop on language selection
**Priority**: P1 | **Labels**: `bug`, `runner` | **Component**: runner, snapshot
**Status**: OPEN | **Found**: 2026-05-07 | **Assignee**: stealth-orchestrator

**Problem**: 50 iterations wasted clicking same element on language selection page. No mechanism to detect that the page state hasn't changed and break the infinite loop.
**Expected**: State hash comparison detects same page → breaks loop after N unchanged iterations.
**Actual**: Infinite retry loop burns CDP calls and wastes session time.
**Files**: `survey-cli/survey/runner.py`, `survey-cli/survey/snapshot.py`, `src/stealth_survey/survey_agent.py`
**Fix approach**: Add `state_hash = md5(visible_text + element_count)` — if hash unchanged for 3+ iterations, trigger escape (skip page or switch strategy).

---

### #6: Element leaf-node filter too aggressive
**Priority**: P1 | **Labels**: `bug`, `snapshot` | **Component**: snapshot, execute
**Status**: OPEN | **Found**: 2026-05-07 | **Assignee**: stealth-orchestrator

**Problem**: TextNode walker returns 0 results on Qualtrics page because it only targets leaf-level text nodes. Qualtrics buttons and labels are nested in `.LabelWrapper` and `.ChoiceStructure` containers that are filtered out.
**Expected**: Element scan finds all interactive elements regardless of nesting depth.
**Actual**: 0 elements returned → runner has nothing to interact with.
**Files**: `survey-cli/survey/snapshot.py`, `src/stealth_survey/compact_snapshot.py`
**Fix approach**: Broaden element scan to include parent containers (`.LabelWrapper`, `.ChoiceStructure`, `.InputText`) — not just leaf text nodes.

---

### #7: cua-driver unavailable without accessibility flag
**Priority**: P2 | **Labels**: `architecture`, `chrome` | **Component**: chrome, cua
**Status**: OPEN | **Found**: 2026-05-07 | **Assignee**: stealth-orchestrator

**Problem**: Chrome lacks `--force-renderer-accessibility` flag when launched, causing cua-driver AX-Tree to return 0 children. cua-driver is the legacy fallback and must work.
**Expected**: Chrome always launched with `--force-renderer-accessibility` and `--remote-allow-origins="*"`.
**Actual**: `playstealth launch` does not set accessibility flag; manual Chrome launch required.
**Files**: `survey-cli/survey/chrome.py`
**Fix approach**: Add Chrome launch wrapper that always includes `--force-renderer-accessibility --remote-allow-origins="*"`, validate AX-Tree after launch.

---

### #8: No provider-specific Qualtrics commands
**Priority**: P2 | **Labels**: `enhancement`, `providers` | **Component**: execute, providers
**Status**: OPEN | **Found**: 2026-05-07 | **Assignee**: stealth-orchestrator

**Problem**: `execute.py` has `qualtrics`/`tolunastart`/`strat7` dispatch but the JS selectors don't match actual Qualtrics DOM elements (`.NextButton`, `.LabelWrapper`, `.ChoiceStructure`).
**Expected**: Provider-specific JS commands that match actual DOM on each platform.
**Actual**: Generic `document.querySelectorAll('button')` fails to find Qualtrics next button.
**Files**: `survey-cli/survey/execute.py`, `survey-cli/survey/providers/qualtrics.py`
**Fix approach**: Update `PROVIDER_COMMANDS` dict with Qualtrics-specific selectors: `.NextButton` for advance, `.LabelWrapper` for radio click, `.ChoiceStructure` for matrix questions.

---

### #9: Balance read timing issue
**Priority**: P2 | **Labels**: `bug`, `scanner` | **Component**: scanner, runner
**Status**: OPEN | **Found**: 2026-05-07 | **Assignee**: stealth-orchestrator

**Problem**: After dashboard reload, balance reads `0.00€` temporarily (DOM not updated yet). No retry logic. Runner assumes payout failed and aborts.
**Expected**: Retry balance read with exponential backoff until stable non-zero value.
**Actual**: First read returns 0.00€ → false negative on payout detection.
**Files**: `survey-cli/survey/scanner.py`, `survey-cli/survey/runner.py`
**Fix approach**: Add `read_balance_with_backoff()` — retry up to 5× with 2s, 4s, 8s backoff until value > 0 or stabilizes.

---

### #10: Graphify auto-rebuild on every commit
**Priority**: P3 | **Labels**: `enhancement`, `ci` | **Component**: hooks
**Status**: OPEN | **Found**: 2026-05-07 | **Assignee**: stealth-orchestrator

**Problem**: Pre-commit hook rebuilds the full graphify visualization on every commit, including non-Python file changes (`.md`, `.json`, `.yml`). This adds ~3s latency to every commit.
**Expected**: Selective rebuild only when `.py` files in `survey-cli/` or `src/` change.
**Actual**: Full graph rebuild on every commit regardless of changed file types.
**Files**: `.pre-commit-config.yaml`, `scripts/graphify.py`
**Fix approach**: Filter pre-commit hook to only trigger on `*.py` file changes in relevant directories.

---

### #11: Test coverage gap — in-page vs new-tab
**Priority**: P3 | **Labels**: `testing`, `runner` | **Component**: tests
**Status**: OPEN | **Found**: 2026-05-07 | **Assignee**: stealth-orchestrator

**Problem**: No integration test for the tab switching flow. Surveys that open in new tabs (vs in-page modals) have no automated coverage.
**Expected**: Integration test that simulates survey opening in new tab, verifies CDP reconnection, tab switch, and question answering.
**Actual**: Only in-page modal tests exist (`test_in_page_modal.py`).
**Files**: `survey-cli/tests/` (new: `test_tab_switching.py`)
**Fix approach**: Create `test_tab_switching.py` with mock CDP + multi-tab scenario, verify `run_survey()` auto-detects and switches.

---

## Summary

| Priority | Count | Issues |
|----------|-------|--------|
| P0 (Critical — blocking payouts) | 3 | #1 Qualtrics lang page, #2 completion detection, #3 tab switching |
| P1 (High — quality of life) | 3 | #4 validation errors, #5 anti-stuck loop, #6 leaf-node filter |
| P2 (Medium — architecture) | 3 | #7 accessibility flag, #8 Qualtrics selectors, #9 balance timing |
| P3 (Low — nice to have) | 2 | #10 graphify rebuild, #11 tab switching test |

## Component Affected

| Component | Issues |
|-----------|--------|
| **runner** (`runner.py`, `survey_agent.py`) | #2, #3, #5, #9 |
| **execute** (`execute.py`, `batch_executor.py`) | #1, #4, #8 |
| **snapshot** (`snapshot.py`, `compact_snapshot.py`) | #1, #5, #6 |
| **providers** (`qualtrics.py`, `toluna.py`) | #1, #8 |
| **scanner** (`scanner.py`) | #2, #9 |
| **chrome** (`chrome.py`) | #7 |
| **nim** (`nim_client.py`) | #4 |
| **cdp** (`cdp_client.py`) | #3 |
| **tests** | #11 |
| **hooks** | #10 |

---

## Completed (Historical Reference)

| Issue | Status | Priority | Title |
|-------|--------|----------|-------|
| SR-11 | done | P0 | CI/CD — GitHub Actions, Pre-Commit, Auto-Release |
| SR-12 | done | P0 | Test Suite — Unit, Integration, E2E |
| SR-13 | done | P1 | Survey Provider Adapter — Samplicio.us, Cint, Nfield |
| SR-14 | done | P1 | Audio Capture Module — BlackHole + ffmpeg + Omni |
| SR-15 | done | P2 | Captcha Solving — Simple, GeeTest v4, Lemin Puzzle |
| SR-16 | done | P2 | Error Recovery — Disqualification, Modal Error, Timeout |
| SR-17 | done | P0 | CUA-ONLY Migration — skylight-cli → cua-driver |
| SR-18 | done | P0 | stealth-session — Warm Daemon for <50ms Command Execution |
| SR-19 | done | P0 | stealth-axiom — 3-Tier Hierarchical Model Router |
| SR-20 | done | P0 | RecursiveMAS — RecursiveLink + Survey MAS Pipeline |
| SR-21 | done | P0 | stealth-sota — Chaos/Security/Healing/Observability/Determinism |
| SR-22 | done | P0 | stealth-core + stealth-dynamic — Basis-Klassen + Dynamic Engine |
| SR-23 | done | P0 | stealth-memory — Eternal Memory |
| SR-24 | done | P0 | E2E Test: GoCaptcha Slide with Real Browser |
| SR-25 | done | P1 | README.md + CLI Documentation for @stealth/captcha |
| SR-26 | done | P1 | Unit Tests: CDP Client + HitTester + Memory |
| SR-27 | done | P2 | stealth-suite: Incident Resolution + Monitoring |

### Previously Active (Merged into SOTA above)

| Issue | Status | Title |
|-------|--------|-------|
| SR-28 | deferred → #1, #6, #8 | CDP Survey Module |
| SR-29 | blocked | PureSpectrum CAPTCHA OCR Solver |
| SR-30 | deferred → #2, #9 | Dashboard Poller + Auto-Loop |
| SR-31 | pending | Flow Compiler FCTES |
| SR-32 | merged → #1, #8 | Provider Auto-Detect Engine |
| SR-33 | done | Persona System |
| SR-34 | merged → #11 | Survey Flow Test Suite |
| SR-35 | merged → #7 | Chrome Lease Manager + Safety |
| SR-36 | deferred | Generated Docs De-Duplication |
| SR-37 | done | OpenCode Fix: Zod v4 Crash + GitNexus + Graphify |

---

## New Issues (2026-05-08 Automated Analysis)

---

### #12: Login-Loop Failure — 0 Surveys seit Tagen
**Priority**: P0 | **Labels**: `bug`, `login` | **Component**: survey.py, auto_google_login.py
**Status**: OPEN | **Found**: 2026-05-08 | **Assignee**: stealth-orchestrator
**Blocking**: Payouts — Watch-Loop wiederholt "Not logged in" endlos

**Problem**: Watch-Loop (`cmd_watch()`) fails 100% with identical pattern: "NEUE TAB! Aber NICHT eingeloggt! Login first:". `surveys_completed: 0` since 2026-05-07 06:53.
**Root Causes** (4 hypotheses):
1. Chrome Accessibility not active — `ensure_accessibility()` warns but continues
2. cua-driver daemon not running — `start_cua_daemon()` called but not verified
3. Google OAuth popup not detected — wrong tab detected
4. Keychain Auto-Fill inactive — "Fortfahren" button missing, password field appears instead

**Fix approach**: Hard-stop on accessibility failure, daemon health-check, OAuth tab detection, Keychain fallback path. See `issues/001-login-loop-failure.md`

---

### #13: Daemon State Management — No Auto-Recovery
**Priority**: P0 | **Labels**: `bug`, `daemon` | **Component**: survey.py, session_manager.py
**Status**: OPEN | **Found**: 2026-05-08 | **Assignee**: stealth-orchestrator
**Blocking**: All CUA operations — no daemon = no login = no surveys

**Problem**: `~/.stealth/daemon_state.json` shows `running: false` since 2026-05-07 06:53. Watch-Loop checks if Chrome is running but NOT if cua-driver daemon is running. No auto-restart on crash.
**Fix approach**: `DaemonManager` class with state machine (STOPPED → STARTING → HEALTHY → DEGRADED → FAILED), auto-restart with exponential backoff, health-check via `list_windows`. See `issues/002-daemon-state-management.md`

---

### #14: Chrome Startup Flags Not Enforced
**Priority**: P0 | **Labels**: `bug`, `chrome` | **Component**: auto_google_login.py, session_manager.py
**Status**: OPEN | **Found**: 2026-05-08 | **Assignee**: stealth-orchestrator
**Blocking**: CUA operations — AX-Tree empty without `--force-renderer-accessibility`

**Problem**: `playstealth launch` does NOT set `--force-renderer-accessibility` → AX-Tree empty. `--remote-allow-origins=*` (without quotes) → zsh expands `*` → Chrome fails to start. Fixed profile path `/tmp/heypiggy-bot` corrupts after restart.
**Fix approach**: `ChromeLauncher` class with post-start verification (CDP reachable? AX-Tree has elements? Flags in cmdline?), timestamped profile paths, hard enforcement of required flags. See `issues/003-chrome-startup-flags.md`

---

### #15: Session File Corruption — 2965 Files with 2 Bytes
**Priority**: P1 | **Labels**: `bug`, `session` | **Component**: opencode sessions
**Status**: OPEN | **Found**: 2026-05-08 | **Assignee**: stealth-orchestrator

**Problem**: `~/.local/share/opencode/sessions/` contains 2965 files, each only 2 bytes. No session history, no error analysis possible, no learning data for agents.
**Fix approach**: Session-write verification (file size > 100 bytes + JSON validation), session-cleanup with backup (archive before delete), monitoring alert on empty sessions. See `issues/004-session-file-corruption.md`

---

### #16: Code-Completeness-Verification Missing
**Priority**: P0 | **Labels**: `enhancement`, `ci` | **Component**: scripts, pre-commit
**Status**: OPEN | **Found**: 2026-05-08 | **Assignee**: stealth-orchestrator

**Problem**: No automated check ensures: (1) every function has docstring, (2) every constant has `WARUM` comment, (3) every action has verify-step, (4) every file has BANNED-methods header, (5) every public function has ≥3 tests, (6) no hardcoded credentials/PIDs.
**Fix approach**: `scripts/verify_completeness.py` — pre-commit hook blocking commits with banned patterns, hardcoded PIDs, missing docstrings. See `issues/005-code-completeness-verification.md`

---

### #17: NIM Runtime Failures — No Fallback Strategy
**Priority**: P0 | **Labels**: `bug`, `nim` | **Component**: survey_agent.py, nim_client.py
**Status**: OPEN | **Found**: 2026-05-08 | **Assignee**: stealth-orchestrator
**Blocking**: Payouts — NIM failure = 0 surveys when `use_nim=True`

**Problem**: `NIMSurveyClient.decide()` has no timeout/error handling. On API key expired, rate limit, or network error → Survey loop fails completely. No fallback to auto-pilot.
**Fix approach**: `NIMSurveyClient` with retry (1s, 2s, 4s backoff), error-type differentiation (401 = permanent, 429 = retry), `available` property with auto-recovery after 5min. `SurveyAgent.run_survey()` falls back to `_simple_actions()` after 3 consecutive NIM failures. See `issues/006-nim-runtime-failures.md`

---

## Summary (All 17 Issues)

| Priority | Count | Issues |
|----------|-------|--------|
| P0 (Critical — blocking payouts) | 9 | #1-3 Qualtrics/completion/tabs, #12 Login-loop, #13 Daemon, #14 Chrome-flags, #16 Code-verification, #17 NIM-fallback |
| P1 (High — quality of life) | 5 | #4 Validation errors, #5 Anti-stuck loop, #6 Leaf-node filter, #15 Session corruption |
| P2 (Medium — architecture) | 2 | #7 Accessibility flag, #8 Qualtrics selectors |
| P3 (Low — nice to have) | 1 | #11 Tab switching test |

### Survey Routing Status

| Provider | Status | Payout |
|----------|--------|--------|
| Qualtrics (HUK) | blocked (#1) | +0.38€ |
| TolunaStart | partial (#4) | +0.09€ |
| Strat7 Audiences | ok | +0.03-0.09€ |
| Brand Ambassador | ok | +0.02€ |
| Insights-Today | screen-out | — |
| PureSpectrum | blocked (CAPTCHA) | 12 IDs |
| surveyrouter | hangs | — |
| surveys.com (GfK) | cookie wall | — |
