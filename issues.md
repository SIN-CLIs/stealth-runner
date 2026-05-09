# Issues — Stealth-Runner SOTA (2026-05-10)

> **Master Plan**: `plans/01-survey-agent-langgraph-fastapi.md` — LangGraph + FastAPI Primary
> **Survey Agent**: `survey-cli/survey/graph/` — 5 files, ~2200 lines (✅ IMPLEMENTED)
> **Assignee**: `stealth-orchestrator` | **Repo**: [stealth-runner](https://github.com/SIN-CLIs/stealth-runner)

---

## 🚨 CRITICAL BLOCKER

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
| SR-39-49 | OPEN | LangGraph + FastAPI Integration (neue Issues) |

---

## Summary (All Issues)

| Priority | Count | Issues |
|----------|-------|--------|
| P0 (Critical) | 8 | SR-38, SR-39, SR-40, SR-41, SR-42, SR-43, #1, #16 |
| P1 (High) | 5 | SR-44, SR-45, SR-46, SR-47, #15 |
| P2 (Medium) | 3 | SR-48, SR-49, #8 |
| P3 (Low) | 3 | SR-10, SR-11, #11 |
| Deprecated | 7 | #2, #3, #5, #6, SR-28, SR-30, SR-31 |

---

**Letzte Aktualisierung: 2026-05-10**