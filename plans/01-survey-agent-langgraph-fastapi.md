# Plan 01: Survey-Agent — LangGraph + FastAPI Primary (2026-05-10)

> **Status**: NEW — Architektur definiert, Implementierung begonnen
> **Parent**: AGENTS.md §12 (LangGraph Survey Agent)
> **Priority**: P0 — Mission-Critical für Survey-Einnahmen
> **Risk**: Niedrig — parallel zu bestehendem Code, keine Breaking Changes

---

## Ziel

**Ein echter Survey-Agent** — nicht ein "dumb daemon" der Scripts abspult, sondern ein System das:
- **beobachtet** (Compact Snapshot via CDP)
- **entscheidet** (NIM Nemotron Decision)
- **lernt** (stealth-memory, learn.md/anti-learn.md)
- **sich erholt** (Auto-Retry, Circuit Breaker, opencode CLI Delegation)
- **koordiniert** (FastAPI endpoints, n8n integration, CLI wrapper)

---

## Architektur: Zwei-Layer-System

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    SURVEY AGENT — TWO-LAYER SYSTEM                      │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  LAYER 1: FastAPI Server (PRIMARY) — Intelligence + Persistence         │
│  ────────────────────────────────────────────────────────────            │
│                                                                          │
│  FastAPI Server (port 8889)                                             │
│  ├── POST /survey/run-graph       → LangGraph invoken (1 Survey)       │
│  ├── GET  /survey/status          → Real-time SurveyState              │
│  ├── GET  /survey/history         → learn.md / anti-learn.md           │
│  ├── POST /survey/scan            → Dashboard scannen                  │
│  └── Background: Watch-Loop       → 24/7 Survey-Check (leicht)         │
│                                                                          │
│       ▲                                                                  │
│       │                                                                  │
│       │ LangGraph (graph.py)                                            │
│       │ ├── SurveyState (state.py) — ALLES in einer dataclass          │
│       │ ├── 8 Nodes (nodes.py) — jede ≤30 Zeilen                       │
│       │ │   ├── ensure_chrome     → ChromeLauncher                    │
│       │ │   ├── open_survey       → SurveyOpener                       │
│       │ │   ├── inject_cookies    → Network.setCookies (KRITISCH!)    │
│       │ │   ├── snapshot_node     → CDP Runtime.evaluate               │
│       │ │   ├── decide_node       → NIM Nemotron Decision              │
│       │ │   ├── execute_node      → BatchExecutor.execute()           │
│       │ │   ├── detect_completion → CompletionDetector                │
│       │ │   └── human_delegate    → opencode CLI                       │
│       │ └── route()              → Conditional Edge Routing            │
│                                                                          │
│  LAYER 2: CLI Wrapper (SECONDARY) — Robustness                          │
│  ────────────────────────────────────────────────────────                │
│                                                                          │
│  ./survey.py run --graph <survey_id>  → Graph invoken, dann exit       │
│  ./survey.py scan                     → Dashboard scannen, dann exit   │
│  ./survey.py status                   → FastAPI GET /status            │
│  Systemd Timer                        → Cron-Backup wenn FastAPI down  │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Warum Zwei-Layer?

| Layer | Stärke | Schwäche | Nutzung |
|-------|--------|----------|---------|
| **FastAPI** | Persistent, intelligent, observability | Server-Crash möglich | Primary für Bot, Monitoring |
| **CLI** | Kein Server, stateless, robust | Kein Gedächtnis | Cron-Backup, Debugging |

**PRIORITY**: FastAPI ist PRIMARY. CLI ist SECONDARY.

---

## CRITISCHER FIX: Cookie-Injection (2026-05-09)

**Root Cause**: Survey-Tabs via `Target.createTarget` haben KEINE Session-Cookies → CPX redirectiert zurück zum Dashboard → €0 verdient.

**Lösung**: Nach Tab-Erstellung → `Network.setCookies` mit 7 Heypiggy-Cookies aus `~/.stealth/heypiggy-backup/heypiggy-cookies.json`

```
7 Heypiggy-Cookies:
  - PHPSESSID      → www.heypiggy.com (KRITISCH!)
  - user_session   → www.heypiggy.com (KRITISCH!)
  - user_id        → www.heypiggy.com (KRITISCH!)
  - user_a_b_group → www.heypiggy.com
  - lang_pig       → www.heypiggy.com
  - g_state        → www.heypiggy.com
  - referer        → www.heypiggy.com
```

---

## Implementierungs-Phasen

### Phase 1: MVP — LangGraph als Engine (WOCHE 1)

**Ziel**: `cmd_run` und `cmd_watch` in `survey.py` nutzen `run_survey_loop()` statt `SurveyRunner`

| # | Task | Datei | Zeilen | Status |
|---|------|-------|--------|--------|
| 1.1 | **`cmd_run` → `run_survey_loop()`** statt SurveyRunner | `survey-cli/survey.py` | ~200 | ❌ ZU TUN |
| 1.2 | **`cmd_watch` → Graph invoken** (Background-Task) | `survey-cli/survey.py` | ~300 | ❌ ZU TUN |
| 1.3 | **Balance-Tracking einbauen** in graph.py | `survey-cli/survey/graph/graph.py` | ~50 | ❌ ZU TUN |
| 1.4 | **`POST /survey/run-graph`** FastAPI Endpoint | `agent-toolbox/api/survey_tools.py` | ~30 | ❌ ZU TUN |
| 1.5 | **Syntax verifizieren** + alle 5 Files testen | `survey-cli/survey/graph/` | — | ✅ FERTIG |

**Result Phase 1**: LangGraph ist die Engine. SurveyRunner ist deprecated (nicht gelöscht).

### Phase 2: Intelligence — NIM Integration (WOCHE 2)

**Ziel**: `decide_node` ist kein Placeholder mehr — echter NIM Nemotron Call

| # | Task | Datei | Zeilen | Status |
|---|------|-------|--------|--------|
| 2.1 | **NIM Client lesen** (survey-cli/survey/nim.py) | `survey-cli/survey/nim.py` | — | ❌ ZU TUN |
| 2.2 | **`decide_node` → NIM integrieren** | `survey-cli/survey/graph/nodes.py` | ~50 | ❌ ZU TUN |
| 2.3 | **Auto-Rating integrieren** (survey_rater.py) | `survey-cli/survey/graph/nodes.py` | ~30 | ❌ ZU TUN |
| 2.4 | **Auto-Doc** (JSONL logging in nodes) | `survey-cli/survey/graph/` | ~30 | ❌ ZU TUN |
| 2.5 | **stealth-memory integration** | `survey-cli/survey/graph/` | ~40 | ❌ ZU TUN |

**Result Phase 2**: Survey-Agent ist intelligent — beobachtet, entscheidet, lernt.

### Phase 3: Production — FastAPI als Primary (WOCHE 3)

**Ziel**: FastAPI Server läuft 24/7, CLI ist nur Fallback

| # | Task | Datei | Zeilen | Status |
|---|------|-------|--------|--------|
| 3.1 | **Watch-Loop als FastAPI Background-Task** | `agent-toolbox/api/` | ~100 | ❌ ZU TUN |
| 3.2 | **`GET /survey/status`** (real-time SurveyState) | `agent-toolbox/api/` | ~20 | ❌ ZU TUN |
| 3.3 | **`GET /survey/history`** (learn.md/anti-learn.md) | `agent-toolbox/api/` | ~20 | ❌ ZU TUN |
| 3.4 | **n8n trigger** (POST bei completion) | `agent-toolbox/api/` | ~30 | ❌ ZU TUN |
| 3.5 | **Systemd Timer** als CLI-Backup | `~/.config/systemd/` | ~30 | ❌ ZU TUN |

**Result Phase 3**: FastAPI ist Production. CLI ist Robustness-Fallback.

### Phase 4: Promotion — 10× Erfolg (WOCHE 4+)

**Ziel**: Nach 10× erfolgreichem Survey → Graph ist VERIFIED = frozen

| # | Task | Datei | Status |
|---|------|-------|--------|
| 4.1 | **`run_survey_loop()` → `create_graph().invoke()`** (echtes LangGraph) | `survey-cli/survey/graph/graph.py` | ❌ ZU TUN |
| 4.2 | **Graph compiled promotion** (`survey-cli/survey/graph/compiled/`) | `survey-cli/survey/graph/` | ❌ ZU TUN |
| 4.3 | **`runner.py` als deprecated markieren** (chmod 444) | `survey-cli/survey/runner.py` | ❌ ZU TUN |
| 4.4 | **AGENTS.md: "LangGraph = PRODUCTION"** dokumentieren | `AGENTS.md` | ❌ ZU TUN |

---

## Lösch-Liste (Plans die der neuen Architektur widersprechen)

```
Zu löschen:
  plan.md (root)                        → veraltete Status-Datei
  survey-cli/plan.md                    → veraltete Status-Datei
  plans/01-canonical-engine.md          → SurveyRunner statt LangGraph
  plan-sr-30-dashboard-poller.md        → DashboardPoller + SurveyRunner statt Graph
  plan-sr-31-fctes-promotion.md         → app.core.* Referenzen (app/ gelöscht)
  plan-sr-28-cdp-survey-module.md       → src/stealth_survey/ (gelöscht)

Zu behalten (kompatibel mit neuer Architektur):
  plan-sr-29-ps-captcha-ocr.md          → Captcha-OCR (Blocker, auch mit Graph)
  plan-sr-32-provider-detect.md         → Provider-Detection (kompatibel)
  plan-sr-33-persona-system.md          → Persona-System (kompatibel)
  plan-sr-34-test-suite.md              → Tests (kompatibel)
  plan-sr-35-chrome-safety.md           → Chrome-Safety (kompatibel)
  plan-sr-36-docs-cleanup.md            → Docs-Cleanup (kompatibel)
  plan-sr-37-skylight-compact.md        → Compact Snapshot (kompatibel)

plans/00-brutal-assessment.md           → BEHALTEN (Historie)
plans/02-secure-credentials.md          → BEHALTEN (Security)
plans/03-enforce-rules.md               → BEHALTEN (BANNED Methods)
plans/04-runtime-lifecycle.md           → BEHALTEN (Chrome Lifecycle)
plans/05-provider-reliability.md        → BEHALTEN (Provider Docs)
plans/06-test-coverage.md               → BEHALTEN (Tests)
plans/07-auto-login-hardening.md        → BEHALTEN (Login Flow)
plans/08-observability-and-sessions.md  → BEHALTEN (Sessions)
plans/09-live-payout-verification.md    → BEHALTEN (Balance Tracking)
```

---

## Verification

```bash
# Phase 1: Graph als Engine — SurveyRunner wird nicht mehr genutzt
cd /Users/jeremy/dev/stealth-runner/survey-cli
python3 -c "
from survey.graph import SurveyState, run_survey_loop, create_graph
state = SurveyState(survey_id='67064749', provider='purespectrum', cdp_port=9999)
# Test ohne Chrome: state.status sollte 'initialized' sein
print(f'State: {state}')
print(f'Graph module OK: {create_graph is not None}')
"

# Phase 2: NIM Decision
cd /Users/jeremy/dev/stealth-runner/survey-cli
python3 -c "
from survey.graph.nodes import decide_node
from survey.graph.state import SurveyState
s = SurveyState()
s.snapshot_refs = {'@e0': {'role': 'radio', 'text': 'Männlich', 'idx': 0}}
s = decide_node(s)
print(f'NIM Actions: {s.nim_actions}')
"

# Phase 3: FastAPI Endpoint
curl -X POST http://127.0.0.1:8889/survey/run-graph \
  -H "Content-Type: application/json" \
  -d '{"survey_id": "67064749", "provider": "purespectrum"}'

# Phase 4: Balance nach Survey
python3 -c "
from survey.graph.state import SurveyState
s = SurveyState(balance_before=2.60, balance_after=3.10)
print(f'Earned: €{s.balance_earned}')  # → €0.50
"
```

---

## Exit-Kriterien

| Kriterium | Prüfung |
|-----------|---------|
| LangGraph als Engine | `cmd_run` und `cmd_watch` nutzen `run_survey_loop()`, nicht `SurveyRunner` |
| NIM Decision | `decide_node()` macht echten NIM API Call (kein Placeholder) |
| Cookie-Injection | Survey-Tabs haben heypiggy-Cookies → kein CPX redirect |
| Balance-Tracking | `balance_earned` zeigt echten Verdienst nach Survey |
| FastAPI Primary | Server läuft 24/7 mit real-time monitoring |
| CLI Fallback | `./survey.py run --graph <id>` funktioniert wenn FastAPI down |
| Graph frozen | 10× erfolgreich → `survey-cli/survey/graph/compiled/` |

---

## Referenzen

- **AGENTS.md §12**: LangGraph Survey Agent (komplette Doku)
- **AGENTS.md §11.3**: Complete Drag-Drop Puzzle Problem (KRITISCHER Blocker)
- **AGENTS.md §DAEMON WAY**: Learn-by-Doing System
- **survey-cli/survey/graph/**: 5 Files, ~2200 Zeilen (schon fertig ✅)
- **AGENTS.md §11.4**: Tool-Status-Tabelle

---

**Letzte Aktualisierung: 2026-05-10**