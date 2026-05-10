# Issues — Stealth-Runner SOTA (2026-05-10)

> **Master Plan**: `plans/01-survey-agent-langgraph-fastapi.md` — LangGraph + FastAPI Primary
> **Survey Agent**: `survey-cli/survey/graph/` — 5 files, ~2200 lines (✅ IMPLEMENTED)
> **Assignee**: `stealth-orchestrator` | **Repo**: [stealth-runner](https://github.com/SIN-CLIs/stealth-runner)

---

## 🚨 CRITICAL BLOCKER

### SR-54: Survey Completion Tracking — Cookie + Subid + Balance Fix Bundle (2026-05-10)
**Priority**: P0 | **Labels**: `bug`, `critical`, `tracking`, `e2e-verified` | **Component**: opener.py, chrome.py, tool_open_survey.py, scanner.py
**Status**: ✅ FIXED & VERIFIED (2026-05-10) | **Found**: 2026-05-10 | **Assignee**: stealth-orchestrator
**Blocking**: ALL surveys earn €0 — 3 root causes combined
**E2E Test**: ✅ VERIFIED — Survey 66695822 (Cint→Tivian), Balance €2.70 → €2.75 (+€0.05)

**Three Interdependent Root Causes:**
1. **Cookie Timing** — `Target.createTarget()` opened survey in new tab WITHOUT 7 HeyPiggy session cookies
2. **Subid Missing** — window.open interception captured URL BEFORE `subid_2=<subid_cpx>` was appended  
3. **Balance Reading** — DOM regex read first € value (survey reward) instead of maximum (user balance)

**Files Changed:**
- `survey-cli/survey/opener.py` — cookie injection in `_create_tab()` + `_open_in_page_modal()`
- `survey-cli/survey/chrome.py` — `inject_heypiggy_cookies_to_tab()` helper
- `survey-cli/tools/tool_open_survey.py` — subid preservation in `open_survey()`
- `survey-cli/survey/scanner.py` — balance reading returns MAX € value (not first)
- `survey-cli/survey/graph/nodes.py` + `state.py` — session validation integration
- `stealth-captcha/src/stealth_captcha/solver/drag_drop_angular.py` — multi-approach solver (4 approaches)

**Tests:** 17/18 + 18/18 + 10/10 passed (pre-existing failures only)

---

### SR-51: subid Parameter Missing in Intercepted URL — Balance = €0
**Priority**: P0 | **Labels**: `bug`, `critical`, `tracking` | **Component**: opener.py, tool_open_survey.py
**Status**: ✅ FIXED & VERIFIED (2026-05-10) | **Found**: 2026-05-10 | **Assignee**: stealth-orchestrator
**Blocking**: ALL surveys earn €0 — subid is Heypiggy's tracking key for completion credit
**E2E Test**: ✅ VERIFIED — Survey 66695822 (Cint→Tivian), Balance €2.70 → €2.75 (+€0.05)

**Root Cause** (from /tmp/e2e_test_results.md):
- `openSurvey()` in heypiggy JS sets `subid_2=<subid_cpx>` before calling `window.open()`
- window.open interception captures the URL BEFORE this subid is appended
- Intercepted URL shows `subid_1=&subid_2=website` (default empty values)
- Heypiggy Completion-Tracking requires correct subid to credit the user account
- Without subid: survey completes but balance cannot be credited → €0

**Intercept Flow (BROKEN):**
```
1. window.open override captures URL from openSurvey()
2. URL already has subid_1=&subid_2=website (NOT the real subid!)
3. Target.createTarget({url: captured_url}) → opens survey WITHOUT tracking
4. CPX → Samplicio → PureSpectrum → Potloc → CloudResearch (all without subid)
5. Survey completes → Heypiggy can't match completion to user → €0
```

**Original openSurvey() Flow (WORKING):**
```
1. openSurvey() sets subid_2=<subid_cpx>
2. window.open(url_with_subid) → opens in new tab WITH tracking
3. Heypiggy credits user via subid when survey completes → €€
```

**Proposed Fix:**
- Capture the URL from openSurvey() BEFORE window.open override
- Parse the full URL including `subid_1`, `subid_2`, `subid_cpx` parameters
- OR: Inject heypiggy subid into intercepted URL before Target.createTarget
- OR: Use Page.navigate in dashboard tab (which already has cookies) instead of new tab

**Files to Change:**
- `survey-cli/tools/tool_open_survey.py`: `_handle_modal_with_cdp()` — extract and preserve subid
- `survey-cli/survey/opener.py`: `_open_in_page_modal()` — inject subid into URL

---

### SR-52: Chrome Crash During Survey Completion — Q3 at CloudResearch
**Priority**: P0 | **Labels**: `bug`, `critical`, `crash` | **Component**: cdp_client.py, survey loop
**Status**: OPEN | **Found**: 2026-05-10 | **Assignee**: stealth-orchestrator
**Blocking**: Surveys crash mid-completion, leaving zombie tabs

**Root Cause** (from /tmp/e2e_test_results.md):
- Survey 67078107: redirect chain `CPX → Samplicio → PureSpectrum → Potloc → CloudResearch`
- Chrome crashed at Q3 (cognitive question) during CloudResearch survey
- CDP connection lost — WebSocket error or JS exception
- Survey never reached completion page
- Chrome restart required → session cookies expired → login needed

**Test Evidence (2026-05-10):**
| Step | Result |
|------|--------|
| Survey opened via window.open interception | ✅ URL captured (but subid=empty) |
| Redirect chain: CPX → Samplicio → PureSpectrum → Potloc → CloudResearch | ✅ All redirects worked |
| Reached Q3 (cognitive questions at CloudResearch) | ✅ |
| Chrome crashed | ❌ CDP connection lost |
| Survey completion reached | ❌ NO — crash prevented completion |
| Balance before: €2.70, after: €2.70 | ❌ €0 earned |

**Possible Causes:**
1. Memory leak during complex multi-redirect survey (6+ page loads)
2. CDP WebSocket disconnection (network issue or Chrome internal)
3. JS exception in CloudResearch survey (unhandled error)
4. CDP "No such target id" error after tab switches
5. Angular/React component crash in survey page

**Proposed Fixes:**
1. CDP crash handler: detect WebSocket error, restart Chrome, resume survey
2. Tab re-discovery after every redirect: `_refresh_tab_ws()` after Page.navigate
3. Survey timeout: abort after 5 minutes with retry
4. Zombie tab cleanup: detect crashed tabs, close them, continue

**Files to Change:**
- `survey-cli/survey/cdp_client.py`: crash detection + reconnect
- `survey-cli/survey/runner.py`: timeout + retry logic
- `survey-cli/survey/opener.py`: tab re-discovery after redirects

---

### SR-53: Session Expires After Chrome Restart — Cookie Backup Invalid
**Priority**: P2 | **Labels**: `bug`, `cookies`, `session` | **Component**: cookie_manager.py, opener.py
**Status**: OPEN | **Found**: 2026-05-10 | **Assignee**: stealth-orchestrator
**Blocking**: Must re-login after every Chrome restart, breaks automation continuity

**Root Cause** (from /tmp/e2e_test_results.md):
- Cookie backup `~/.stealth/heypiggy-backup/heypiggy-cookies.json` was taken during active session
- After Chrome restart: backup cookies became invalid (session expiry)
- Session cookies typically expire after 30min-2h
- `Network.setCookies` with expired cookies → Chrome ignores them
- Dashboard shows logged-out state → must re-login

**Test Evidence (2026-05-10):**
- Session verified alive before survey (body.innerText contains "abmelden") ✅
- Survey opened via window.open interception ✅
- Chrome crashed at Q3 ❌
- Chrome restart required (Chrome crashed) ❌
- Session expired during restart ❌
- Backup cookies invalid → dashboard logged out ❌
- Re-login required → subid tracking broken ❌

**Session Recovery Protocol (Proposed):**
```
BEFORE survey operation:
1. Validate session: navigate to heypiggy.com → check body.innerText for "abmelden"
2. If logged out: restore from backup + re-login via Google OAuth
3. If backup cookies fail: extract fresh cookies from running Chrome

AFTER Chrome restart:
1. Detect restart (Chrome PID changed or no WS connection)
2. Restore session via cookie injection OR re-login
3. Verify login before proceeding with survey
```

**Files to Change:**
- `survey-cli/survey/opener.py`: session validation before survey
- `agent-toolbox/core/cookie_manager.py`: session recovery protocol
- `agent-toolbox/core/gmx_service.py`: reference implementation (already has recovery)

---

## Previous Critical Blockers

### SR-50: Cookie Timing — Survey öffnet sich ohne Session-Cookies, balance = €0
**Priority**: P0 | **Labels**: `bug`, `critical`, `cookies` | **Component**: opener.py
**Status**: OPEN | **Found**: 2026-05-10 | **Assignee**: stealth-orchestrator
**Blocking**: ALL surveys earn €0 despite completion — every provider (Cint, Samplicio, PureSpectrum)

**Root Cause** (from /tmp/survey_test_results.md):
- Survey completed (Cint showed "Vielen Dank"), balance unchanged: €2.70 before → €2.70 after
- 7 HeyPiggy-Cookies are injected AFTER `Target.createTarget()` creates the new tab
- The entire redirect chain runs WITHOUT session cookies: `CPX → Samplicio → Cint → Potloc`
- Heypiggy's completion tracking requires cookies to be present when the redirect returns to the platform
- Without cookies, completion event cannot be associated with the correct user session → balance stays €0

**Affected Code**: `survey-cli/survey/opener.py`
- `_open_in_page_modal()` (line 118): calls `_find_new_tab_after_click()` which uses `Target.createTarget()`
- `_create_tab()` (line 247): creates blank tab, injects stealth, THEN navigates — cookies not injected before navigation
- Cookie injection happens on the DASHBOARD tab first, then new survey tab is created WITHOUT cookies

**Test Evidence** (2026-05-10, survey 67078106):
| Step | Result |
|------|--------|
| Survey opened via window.open interception + Target.createTarget | ✅ Tab created |
| Survey flow: Samplicio → Cint (14 pages) | ✅ Completed |
| Cint showed "Vielen Dank" | ✅ Completion detected |
| Balance before: €2.70, after: €2.70 | ❌ NO INCREASE |
| New survey appeared in list (€1.03) | Survey was processed but NO credit |

**Failed Fix Approaches**:
| Approach | Why Failed |
|----------|------------|
| Inject cookies after tab creation | Tab already navigated to CPX URL without cookies |
| Wait longer before checking balance | Completion tracking never happened — timing is the root cause |
| Manual re-test after same flow | Same result: €0 earned despite completion |

**Proposed Fixes** (ordered by priority):
1. **PREFERRED**: Open survey in the SAME dashboard tab (which already has cookies) — navigate to CPX URL instead of creating new tab
2. **ALTERNATIVE**: Inject cookies INTO the new tab BEFORE navigating to the survey URL (requires CDP injection into new tab's WS before Page.navigate)
3. **WORKAROUND**: Find heypiggy completion callback URL and call it directly with cookies after survey completes

**Files to Change**:
- `survey-cli/survey/opener.py`: `_open_in_page_modal()` — use dashboard tab for survey instead of new tab
- `survey-cli/survey/opener.py`: `_create_tab()` — inject cookies before `navigate_tab()`

---

### SR-38: PureSpectrum Drag-Drop Puzzle — 66% stuck, €0 verdient
**Priority**: P0 | **Labels**: `bug`, `providers`, `critical` | **Component**: purespectrum.py
**Status**: OPEN | **Found**: 2026-05-09 | **Assignee**: stealth-orchestrator
**Blocking**: All PureSpectrum surveys (12+ IDs) — €0 verdient

**Root Cause** (from AGENTS.md §11.3):
- Angular CDK (v7+) uses ONLY PointerEvents: `@HostListener('pointerdown')`
- `__ngContext__` is a Production Build Index (number, not Object) — `findInstance(4, '_dropListRef')` = null
- `window.ng` (Dev-Mode API) not available in Production
- `DragDropCaptchaSolver` in stealth-captcha uses `Input.dispatchMouseEvent` → WRONG event type
- Synthetic PointerEvents blocked by Angular on low level

**Failed Approaches** (all tested 2026-05-09):
| Approach | Why Failed |
|----------|------------|
| `__ngContext__` traversal | `__ngContext__` is **number** (4), not Object |
| `window.ng.getComponent()` | Dev-Mode only, not Production |
| JS `dispatchEvent(MouseEvent)` | Angular CDK ignores MouseEvents |
| JS `dispatchEvent(PointerEvent)` | Angular blocks synthetic PointerEvents |
| CDP `Input.dispatchMouseEvent` | Sends MouseEvents, CDK needs PointerEvents |
| CSS clone + mutation | Angular change detection not triggered |

**Solution Architecture** (4 new files):
1. `stealth-captcha/src/stealth_captcha/solver/drag_drop_angular.py` → AngularDragDropSolver
2. `survey-cli/tools/tool_drag_captcha.py` → POST /survey/drag-solve
3. `survey-cli/survey/providers/purespectrum.py:solve_drag_puzzle()` → fix PointerEvent
4. `commands/surveys/purespectrum-drag-puzzle.md` → ✅ VERIFIED after 10×

**Key Insight**: `pointerdown` → `pointermove` (middle) → `pointerup` over drop-zone.
CDP has NO `Input.dispatchPointerEvent` — must use `Runtime.evaluate` with pointer event dispatch.

**Progress**: 0% → 33% (Cookie + ROBOT captcha) → 33% → 66% → BLOCKED

---

## Phase 1: LangGraph Integration (WOCHE 1)

### SR-39: cmd_run in survey.py → run_survey_loop() statt SurveyRunner
**Priority**: P0 | **Labels**: `enhancement`, `langgraph` | **Component**: survey.py
**Status**: OPEN | **Assignee**: stealth-orchestrator

**Problem**: `cmd_run` in `survey-cli/survey.py` nutzt noch `SurveyRunner` (893 Zeilen Monolith) statt `run_survey_loop()` aus dem Graph.
**Fix**: `cmd_run` → `run_survey_loop(state)` statt `SurveyRunner(config).run_survey()`.
**Files**: `survey-cli/survey.py` (~200 Zeilen refactor)
**Verification**: `./survey.py run --graph 67064749` → Graph invoken, SurveyRunner nicht genutzt

---

### SR-40: cmd_watch in survey.py → Graph invoken (Background-Task)
**Priority**: P0 | **Labels**: `enhancement`, `langgraph` | **Component**: survey.py
**Status**: OPEN | **Assignee**: stealth-orchestrator

**Problem**: Watch-Daemon (`cmd_watch`) ist der "dumb daemon" — nutzt SurveyRunner statt LangGraph.
**Fix**: Watch-Loop invoken `create_graph().invoke(state)` pro Survey, Background-Task für 24/7.
**Files**: `survey-cli/survey.py` (~300 Zeilen refactor)
**Blocking**: SR-39 (cmd_run muss zuerst fertig sein)

---

### SR-41: Balance-Tracking in graph.py einbauen
**Priority**: P0 | **Labels**: `enhancement`, `langgraph` | **Component**: graph.py
**Status**: OPEN | **Assignee**: stealth-orchestrator

**Problem**: `run_survey_loop()` hat kein Balance-Tracking. `balance_before`/`balance_after` in SurveyState werden nicht gesetzt.
**Fix**: `balance_tracker.py` → `read_balance()` vor/after Survey, in detect_completion_node.
**Files**: `survey-cli/survey/graph/graph.py` (~50 Zeilen)
**Verification**: `state.balance_earned` zeigt echten Verdienst nach Survey

---

### SR-42: POST /survey/run-graph FastAPI Endpoint
**Priority**: P0 | **Labels**: `enhancement`, `fastapi`, `langgraph` | **Component**: agent-toolbox/api/survey_tools.py
**Status**: OPEN | **Assignee**: stealth-orchestrator

**Problem**: Graph existiert als Python-Code aber nicht als FastAPI Endpoint.
**Fix**: Neuer Endpoint `POST /survey/run-graph` → `create_graph().invoke(state)`.
**Files**: `agent-toolbox/api/survey_tools.py` (~30 Zeilen)
**Verification**: `curl -X POST http://127.0.0.1:8889/survey/run-graph -d '{"survey_id":"67064749"}'`

---

## Phase 2: Intelligence (WOCHE 2)

### SR-43: decide_node → NIM Nemotron Decision integrieren
**Priority**: P0 | **Labels**: `enhancement`, `nim`, `langgraph` | **Component**: graph/nodes.py
**Status**: OPEN | **Assignee**: stealth-orchestrator

**Problem**: `decide_node()` ist ein Placeholder (heuristic: erste Radio auswählen). Kein echter NIM API Call.
**Fix**: `survey-cli/survey/nim.py` → `NIMSurveyClient.decide()` integrieren in `decide_node()`.
**Files**: `survey-cli/survey/graph/nodes.py` (~50 Zeilen)
**Verification**: `decide_node()` macht echten NVIDIA NIM Call (nicht Placeholder)

---

### SR-44: Auto-Rating integrieren in Graph
**Priority**: P1 | **Labels**: `enhancement`, `rating` | **Component**: graph/nodes.py
**Status**: OPEN | **Assignee**: stealth-orchestrator

**Problem**: Nach Survey-Completion wird kein Rating aufgerufen (+0.01€ Bonus verloren).
**Fix**: Nach `detect_completion()` → `survey_rater.py` → Rating-Click auf CPX Rating-Page.
**Files**: `survey-cli/survey/graph/nodes.py` (~30 Zeilen)

---

### SR-45: Auto-Doc + stealth-memory integrieren
**Priority**: P1 | **Labels**: `enhancement`, `memory` | **Component**: graph/nodes.py
**Status**: OPEN | **Assignee**: stealth-orchestrator

**Problem**: Graph logged nicht nach learn.md/anti-learn.md. Kein Echtzeit-Monitoring.
**Fix**: Nach jedem Survey → stealth-memory Update (erfolgreich/failed, provider, error).
**Files**: `survey-cli/survey/graph/` (~40 Zeilen in detect_completion_node)

---

## Phase 3: FastAPI Production (WOCHE 3)

### SR-46: Watch-Loop als FastAPI Background-Task
**Priority**: P0 | **Labels**: `enhancement`, `fastapi` | **Component**: agent-toolbox/api/
**Status**: OPEN | **Assignee**: stealth-orchestrator

**Problem**: Kein FastAPI-Server der 24/7 Survey-Loop managet.
**Fix**: FastAPI Background-Task → Watch-Loop mit `/survey/run-graph` pro Survey.
**Files**: `agent-toolbox/api/` (~100 Zeilen)

---

### SR-47: GET /survey/status + GET /survey/history Endpoints
**Priority**: P1 | **Labels**: `enhancement`, `fastapi`, `monitoring` | **Component**: agent-toolbox/api/
**Status**: OPEN | **Assignee**: stealth-orchestrator

**Problem**: Kein Real-Time Monitoring. Agent sieht nur Post-Mortem-Logs.
**Fix**:
- `GET /survey/status` → aktueller SurveyState (running/completed/error)
- `GET /survey/history` → learn.md / anti-learn.md Inhalte
**Files**: `agent-toolbox/api/` (~40 Zeilen)

---

## Phase 4: LangGraph Promotion (WOCHE 4+)

### SR-48: run_survey_loop() → create_graph().invoke() (echtes LangGraph)
**Priority**: P1 | **Labels**: `enhancement`, `langgraph` | **Component**: graph/graph.py
**Status**: OPEN | **Assignee**: stealth-orchestrator

**Problem**: `run_survey_loop()` ist nur Fallback (ohne LangGraph). Echtes LangGraph nicht genutzt.
**Fix**: Phase 1-3 fertig → `run_survey_loop()` → `create_graph().invoke(state)`.
**Files**: `survey-cli/survey/graph/graph.py`

---

### SR-49: Graph compiled promotion (nach 10× Erfolg)
**Priority**: P2 | **Labels**: `enhancement`, `fctes` | **Component**: graph/
**Status**: OPEN | **Assignee**: stealth-orchestrator

**Problem**: Graph nach 10× Erfolg nicht als frozen/production markiert.
**Fix**: `survey-cli/survey/graph/compiled/` → `survey_graph_v{TIMESTAMP}.py`, chmod 444.
**Files**: `survey-cli/survey/graph/`

---

## Stale Issues (Deprecated — durch neue Architektur gelöst)

| Issue | Status | Grund |
|-------|--------|-------|
| #2 Survey completion not detected | DEPRECATED | `detect_completion_node` im Graph, `completion_detector.py` existiert. Referenz auf `src/stealth_survey/survey_agent.py` (DELETED). |
| #3 Tab switching not automated | DEPRECATED | `open_survey_node` + `inject_cookies_node` im Graph. Referenz auf DELETED Modul. |
| #5 Anti-stuck loop | DEPRECATED | `execute_node` nutzt `verify_state_change()` aus execute.py. Iteration-Limit als Safety-Net. |
| #6 Element leaf-node filter too aggressive | DEPRECATED | Graph nutzt CDP inline JS für Snapshot (nicht `snapshot.py` walker). Referenz auf DELETED `src/stealth_survey/compact_snapshot.py`. |
| #12 Login-Loop Failure | DONE | `DaemonManager` + hard-stops implementiert. |
| #13 Daemon State Management | DONE | `DaemonManager` mit state machine. |
| #14 Chrome Startup Flags | DONE | `ChromeLauncher` mit enforce. |

---

## Offene Issues (unabhängig von LangGraph)

### #10: Graphify Auto-Rebuild auf jedem Commit
**Priority**: P3 | **Labels**: `enhancement`, `ci` | **Component**: hooks
**Status**: OPEN | **Assignee**: stealth-orchestrator

**Problem**: Pre-commit hook rebuildt graphify visualization auf jedem Commit (3s Latenz).
**Fix**: Selective rebuild nur bei `*.py` Änderungen in survey-cli/ oder src/.

### #11: Tab-Switching Test-Coverage
**Priority**: P3 | **Labels**: `testing` | **Component**: tests
**Status**: OPEN | **Assignee**: stealth-orchestrator

**Problem**: Kein Integrationstest für Tab-Switching im neuen Graph.
**Fix**: `survey-cli/tests/test_graph_tab_switching.py`.

### #15: Session File Corruption
**Priority**: P1 | **Labels**: `bug`, `session` | **Component**: opencode sessions
**Status**: OPEN | **Assignee**: stealth-orchestrator

**Problem**: `~/.local/share/opencode/sessions/` enthält 2965 Dateien mit je 2 Bytes. Kein Lern-Daten.
**Fix**: Session-Write-Verify (size > 100 bytes + JSON validation).

### #16: Code-Completeness-Verification Missing
**Priority**: P0 | **Labels**: `enhancement`, `ci` | **Component**: scripts, pre-commit
**Status**: OPEN | **Assignee**: stealth-orchestrator

**Problem**: Keine automatisierte Prüfung auf fehlende Kommentare, hardcoded PIDs, BANNED-Methods.
**Fix**: `scripts/verify_completeness.py` als pre-commit hook.

### #1: Qualtrics Language Page stuck
**Priority**: P0 | **Labels**: `bug`, `providers` | **Component**: execute.py
**Status**: OPEN | **Assignee**: stealth-orchestrator

**Problem**: CDP `Input.dispatchMouseEvent` auf "Deutschland" advance nicht. `>>` Button nicht im Snapshot.
**Fix**: Qualtrics-spezifische Selector in `PROVIDER_COMMANDS` (`.NextButton` + `.LabelWrapper`).

### #8: Qualtrics Provider Commands
**Priority**: P2 | **Labels**: `enhancement`, `providers` | **Component**: execute.py
**Status**: OPEN | **Assignee**: stealth-orchestrator

**Problem**: JS Selectors matchen nicht die echte Qualtrics DOM.
**Fix**: `PROVIDER_COMMANDS["qualtrics"]` updaten mit echten Selektoren.

---

## Historical Reference (Completed)

| Issue | Status | Title |
|-------|--------|-------|
| SR-11 | DONE | CI/CD — GitHub Actions, Pre-Commit, Auto-Release |
| SR-12 | DONE | Test Suite — Unit, Integration, E2E |
| SR-13 | DONE | Survey Provider Adapter — Samplicio.us, Cint, Nfield |
| SR-14 | DONE | Audio Capture Module — BlackHole + ffmpeg + Omni |
| SR-15 | DONE | Captcha Solving — Simple, GeeTest v4, Lemin Puzzle |
| SR-16 | DONE | Error Recovery — Disqualification, Modal Error, Timeout |
| SR-17 | DONE | CUA-ONLY Migration — skylight-cli → cua-driver |
| SR-18 | DONE | stealth-session — Warm Daemon for <50ms Command Execution |
| SR-19 | DONE | stealth-axiom — 3-Tier Hierarchical Model Router |
| SR-20 | DONE | RecursiveMAS — RecursiveLink + Survey MAS Pipeline |
| SR-21 | DONE | stealth-sota — Chaos/Security/Healing/Observability/Determinism |
| SR-22 | DONE | stealth-core + stealth-dynamic — Basis-Klassen + Dynamic Engine |
| SR-23 | DONE | stealth-memory — Eternal Memory |
| SR-24 | DONE | E2E Test: GoCaptcha Slide with Real Browser |
| SR-25 | DONE | README.md + CLI Documentation for @stealth/captcha |
| SR-26 | DONE | Unit Tests: CDP Client + HitTester + Memory |
| SR-27 | DONE | stealth-suite: Incident Resolution + Monitoring |
| SR-28 | DEPRECATED | CDP Survey Module → `src/stealth_survey/` DELETED, Graph implementiert |
| SR-29 | BLOCKED | PureSpectrum CAPTCHA OCR → SR-38 (Drag-Drop) |
| SR-30 | DEPRECATED | Dashboard Poller → SR-40 (Watch-Loop) + Graph |
| SR-31 | DEPRECATED | Flow Compiler FCTES → app/ DELETED |
| SR-32 | MERGED | Provider Auto-Detect → #1 + #8 |
| SR-33 | DONE | Persona System |
| SR-34 | MERGED | Survey Flow Test Suite → #11 |
| SR-35 | MERGED | Chrome Lease Manager → ChromeLauncher |
| SR-36 | DEFERRED | Generated Docs De-Duplication |
| SR-37 | DONE | OpenCode Fix: Zod v4 Crash + GitNexus + Graphify |
| SR-38 | BLOCKED | PureSpectrum Drag-Drop Blocker → KRITISCH! |
| SR-50 | CRITICAL | Cookie Timing — Survey öffnet sich ohne Session-Cookies, balance = €0 |
| SR-51 | CRITICAL | subid Parameter Missing in Intercepted URL → balance = €0 |
| SR-52 | CRITICAL | Chrome Crash During Survey Completion → Q3 CloudResearch |
| SR-53 | OPEN | Session Expires After Chrome Restart → cookie backup invalid |
| SR-55 | DONE | LangGraph Import Fix + FastAPI Background-Task + Deps |
| SR-55a | OPEN | Background-Task E2E Test — API starten, 30min laufen lassen, prüfen |
| SR-56 | CRITICAL | PureSpectrum Web Components blocken CDP Interaction |
| SR-57 | OPEN | NIM Nemotron Integration in decide_node (Placeholder → echter Call) |
| SR-39-49 | DEPRECATED | LangGraph + FastAPI Integration → konkretisiert in SR-55 bis SR-57 |

---

### SR-55: LangGraph Import Fix + FastAPI Background-Task + Dependencies (2026-05-10)
**Priority**: P1 | **Labels**: `infrastructure`, `langgraph`, `fastapi`, `done` | **Component**: graph.py, main.py, pyproject.toml, Makefile
**Status**: ✅ DONE (2026-05-10) | **Found**: 2026-05-10 | **Assignee**: stealth-orchestrator
**Blocking**: LangGraph StateGraph konnte nicht importiert werden → Graph-Engine offline

**Root Causes:**
1. **LangGraph in .venv, System-Python 3.14** — `langgraph==1.1.10` in `.venv/lib/python3.12/site-packages`, aber System-Python 3.14 hat keinen Zugriff
2. **Fehlende Dependencies** — `fastapi`, `uvicorn`, `openai`, `playwright`, `websocket-client` waren nicht im venv installiert
3. **HTTPException Import fehlte** — `survey_tools.py:473` verwendete `HTTPException` ohne Import

**Fixes:**
- `.venv` path injection in `graph.py:112-130` (sys.path.insert vor langgraph Import)
- `uv pip install` für alle fehlenden Packages
- `from fastapi import APIRouter, HTTPException` in survey_tools.py

**Files Changed:**
- `survey-cli/survey/graph/graph.py` — venv path injection + LANGGRAPH_AVAILABLE fix
- `agent-toolbox/api/main.py` — `_survey_loop()` Background-Task, startup/shutdown events
- `agent-toolbox/api/dashboard_routes.py` — `_scan_dashboard_impl()` Refactor für Background + Endpoint
- `agent-toolbox/api/survey_tools.py` — HTTPException Import fix
- `agent-toolbox/start-api.sh` — venv Python Startup-Script
- `Makefile` — `run`, `dev`, `start-bg`, `stop-bg` Targets
- `pyproject.toml` — Dependencies: fastapi, uvicorn, langgraph, websocket-client

**Result**: LangGraph `create_graph().invoke()` funktioniert, FastAPI Background-Task läuft alle 5min

---

### SR-55a: Background-Task E2E Test (2026-05-10)
**Priority**: P1 | **Labels**: `testing`, `e2e`, `fastapi` | **Component**: main.py
**Status**: OPEN | **Found**: 2026-05-10 | **Assignee**: stealth-orchestrator
**Blocking**: Background-Task wurde implementiert aber nie live getestet

**Test Plan:**
1. `./start-api.sh --bg` starten
2. Chrome auf Port 9999 starten (Recipe aus AGENTS.md)
3. 30 Minuten warten
4. Prüfen ob:
   - `api.log` zeigt "[BG-LOOP]" Logs
   - Surveys wurden gescannt ("Found X surveys")
   - Eine Survey wurde ausgewählt und ausgeführt
   - Balance hat sich verändert (oder Screen-Out erkannt)
5. `curl http://localhost:8889/docs` → Swagger UI erreichbar

**Expected:**
- Mindestens 1 Survey-Scan pro 5min
- Mindestens 1 Survey-Execution pro 15min (wenn Surveys verfügbar)
- Keine Crash-Loops (consecutive_failures < 3)

---

### SR-56: PureSpectrum Web Components blocken CDP Interaction (2026-05-10)
**Priority**: P0 (CRITICAL) | **Labels**: `blocker`, `purespectrum`, `shadow-dom`, `web-components` | **Component**: purespectrum.py, drag_drop_angular.py
**Status**: OPEN / BLOCKED | **Found**: 2026-05-10 | **Assignee**: stealth-orchestrator
**Blocking**: PureSpectrum Surveys können nicht über 66% hinaus fortschreiten

**Observed Behavior:**
- Survey 67105461 (PureSpectrum / PulseOpinion) — blockiert bei "Gaming question"
- DOM enthält `<ps-root>`, `<ps-button>`, `<ps-next-button>` (Custom Elements / Web Components)
- Standard CDP `Runtime.evaluate()` + `element.click()` funktioniert NICHT
- Buttons bleiben `disabled=true` nach Click
- Checkboxes werden nicht selektiert

**Root Cause Hypothesis:**
- PureSpectrum verwendet Shadow DOM innerhalb der Custom Elements
- CDP `Runtime.evaluate()` hat keinen Zugriff auf Shadow DOM ohne `pierce` Parameter
- Angular CDK Event-System blockiert synthetic events auf Web Components
- Event-Bubbling funktioniert nicht durch Shadow DOM Barriere

**CDP Methods to Research:**
- `DOM.getDocument(pierce=True)` — durchdringt Shadow DOM
- `DOM.querySelector(nodeId, selector, pierce=True)` — Selektoren in Shadow DOM
- `Runtime.evaluate()` + Shadow DOM piercing via JS (`element.shadowRoot.querySelector()`)
- `Input.dispatchMouseEvent()` — native Browser-Engine Events (synthetisch vs. trusted)

**Potential Solutions:**
1. **Shadow DOM Piercing**: `document.querySelector('ps-next-button').shadowRoot.querySelector('button').click()`
2. **CDP DOM Piercing**: `DOM.querySelector(nodeId, 'button', pierce=True)` → `DOM.getContentQuads()` → `Input.dispatchMouseEvent()`
3. **Playwright Shadow DOM**: `page.locator('ps-next-button >> button').click()` (Playwright kann Shadow DOM nativ)
4. **Custom Element Polyfill**: JS-Script das Custom Elements entfernt und durch Standard-HTML ersetzt

**Files Affected:**
- `survey-cli/survey/providers/purespectrum.py` — `solve_purespectrum_preflight()` + `solve_drag_puzzle()`
- `stealth-captcha/src/stealth_captcha/solver/drag_drop_angular.py` — Drag-Drop Solver
- `agent-toolbox/api/survey_tools.py` — `POST /survey/purespectrum-preflight`

**E2E Test:**
- Survey mit PureSpectrum Provider finden (via Dashboard-Scan)
- Öffnen und bei 66% prüfen ob Buttons klickbar sind
- Wenn nicht: Shadow DOM Methoden testen

---

### SR-57: NIM Nemotron Integration in decide_node (2026-05-10)
**Priority**: P1 | **Labels**: `ai`, `nim`, `nemotron`, `placeholder` | **Component**: nodes.py
**Status**: OPEN | **Found**: 2026-05-10 | **Assignee**: stealth-orchestrator
**Blocking**: Survey-Antworten sind rule-basiert, nicht intelligent — Disqualifikations-Rate hoch

**Current State:**
- `nodes.py:decide_node()` ist ein PLACEHOLDER
- Gibt hardcoded Actions zurück (nicht basierend auf Snapshot-Inhalt)
- Kein echter API Call zu NVIDIA NIM

**Goal:**
- `decide_node()` soll einen echten Nemotron 3 Omni API Call machen
- Input: Compact Snapshot (questions, options, progress, provider)
- Output: Actions Array (radio select, text fill, submit)
- Model: `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning` via `integrate.api.nvidia.com/v1/chat/completions`

**Implementation Plan:**
1. **API Key**: `NVIDIA_API_KEY` aus Environment (Prefix: `nvapi-...`)
2. **Request Format**: OpenAI-compatible Chat Completions API
3. **System Prompt**: Survey-Answering Agent mit Persona (Jeremy, 32, Berlin, männlich)
4. **Tools/Functions**: `select_option`, `fill_text`, `click_submit`, `detect_question_type`
5. **Response Parsing**: JSON-Schema für Actions Array

**Example API Call:**
```python
client = OpenAI(
    base_url="https://integrate.api.nvidia.com/v1",
    api_key=os.getenv("NVIDIA_API_KEY")
)
response = client.chat.completions.create(
    model="nvidia/nemotron-3-nano-omni-30b-a3b-reasoning",
    messages=[...],
    stream=False
)
```

**Files to Change:**
- `survey-cli/survey/graph/nodes.py` — `decide_node()` implementieren
- `survey-cli/survey/graph/nim_client.py` — NEU: NIMSurveyClient Klasse
- `pyproject.toml` — `openai>=1.0` Dependency (bereits installiert)

---

## Summary (All Issues)

| Priority | Count | Issues |
|----------|-------|--------|
| P0 (Critical) | 11 | SR-38, SR-39, SR-40, SR-41, SR-42, SR-43, SR-50, SR-51, SR-52, SR-56, #1 |
| P1 (High) | 8 | SR-44, SR-45, SR-46, SR-47, SR-55a, SR-57, #15, #16 |
| P2 (Medium) | 4 | SR-48, SR-49, SR-53, #8 |
| P3 (Low) | 2 | #10, #11 |
| Done | 2 | SR-54, SR-55 |
| Deprecated | 8 | #2, #3, #5, #6, SR-28, SR-30, SR-31, SR-39-49 |

---

**Letzte Aktualisierung: 2026-05-10**