# brain.md — Architektur-Entscheidungen & Systemwissen (2026-05-10)

> **Letztes Update**: 2026-05-10
> **← [sinrules.md](sinrules.md)**: Zentrale Regeln
> **← [AGENTS.md](AGENTS.md)**: Projekt-Wissensbasis
> **← [registry.md](registry.md)**: Command Index

---

## TOOL STACK (AKTUELL, 2026-05-10)

| Tool | Status | Verwendung |
|------|--------|------------|
| **CDP WebSocket** | ✅ PRIMARY | Browser-Interaktionen, Web-Content |
| **survey-cli/survey/graph/** | ✅ PRIMARY | LangGraph Survey-Agent |
| **cua-driver** | ⚠️ DEPRECATED | NUR native Popups/Sheets |
| **skylight-cli** | ⚠️ DEPRECATED | Window Capture (Legacy) |
| **playstealth launch** | ❌ BANNED | Profil 902, Port 9224, keine Cookie-Injection |
| **webauto-nodriver** | ❌ BANNED | ABSOLUT VERBOTEN |
| **decrypt_cookies.py** | ❌ BANNED | Chrome <147 only |

---

## LANGGRAPH SURVEY AGENT (AKTUELL, 2026-05-10)

**Location**: `survey-cli/survey/graph/` (5 Files)

```
survey-cli/survey/graph/
├── __init__.py         ← PUBLIC API (SurveyState, create_graph, run_survey_loop, delegate_task, SurveyGraphError)
├── state.py            ← SurveyState dataclass (~434Z)
├── nodes.py            ← 8 Graph Nodes (~753Z)
├── graph.py            ← StateGraph Builder + run_survey_loop() ~379Z
└── opencode_tool.py    ← CLI Delegation

TOTAL: ~1770Z
```

### run_survey_loop() vs create_graph()

| Funktion | Dependency | Wann nutzen |
|----------|-----------|-------------|
| `run_survey_loop(state)` | **KEIN** LangGraph nötig | ✅ PRIMARY — cmd_run nutzt dies |
| `create_graph()` | LangGraph erforderlich | Future — Phase 4 |

**WICHTIG**: `run_survey_loop()` ist die standalone Implementierung — KEIN LangGraph. `cmd_run` in `survey.py` nutzt `run_survey_loop()`.

### NEMO Loop (in run_survey_loop)

```
Phase 1: Setup
  ensure_chrome → open_survey → inject_cookies

Phase 2: NEMO Loop (jede Iteration inkrementiert!)
  snapshot_node → decide_node → execute_node → detect_completion
  Routing: snapshot (continue) | human_delegate (3× fail) | END

Phase 3: Balance lesen
  balance_after = read_balance()
```

### 8 Graph Nodes

| Node | Funktion | Status |
|------|---------|--------|
| `ensure_chrome` | ChromeLauncher.launch_and_verify() | ✅ Implementiert |
| `open_survey` | SurveyOpener.open() | ✅ Implementiert |
| `inject_cookies` | Network.setCookies (7 Heypiggy-Cookies) | ✅ Implementiert |
| `snapshot_node` | CDP Runtime.evaluate inline JS | ✅ Implementiert |
| `decide_node` | Heuristic fallback (Placeholder) | ⚠️ NIM nicht integriert |
| `execute_node` | BatchExecutor.execute() | ✅ Implementiert |
| `detect_completion` | CompletionDetector | ✅ Implementiert |
| `human_delegate` | opencode CLI Delegation (3× failures) | ✅ Implementiert |

---

## CHROME START (REGELN 1-4)

```bash
cp -R "$HOME/Library/Application Support/Google Chrome/Profile 901 (Jeremy)" /tmp/chrome-jeremy-heypiggy-9999

nohup "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  --remote-debugging-port=9999 \
  --remote-allow-origins="*" \
  --force-renderer-accessibility \
  --no-first-run \
  --user-data-dir="/tmp/chrome-jeremy-heypiggy-9999" \
  "https://www.heypiggy.com/?page=dashboard" &>/dev/null &

sleep 4
# Dann: 7 Heypiggy-Cookies injizieren aus ~/.stealth/heypiggy-backup/heypiggy-cookies.json
```

### 7 Heypiggy-Cookies (KRITISCH!)
- PHPSESSID, user_session, user_id, user_a_b_group, lang_pig, g_state, referer
- Backup: `~/.stealth/heypiggy-backup/heypiggy-cookies.json`
- Injektion: `Network.setCookies` (Batch in einem Call)

---

## cmd_run vs cmd_loop vs cmd_watch (survey.py)

| Command | Engine | Status |
|---------|--------|--------|
| `cmd_run` | `run_survey_loop()` (survey.graph) | ✅ REFRACTORED (2026-05-10) |
| `cmd_loop` | `SurveyRunner.run_loop()` | ⚠️ NOCH SurveyRunner (deprecated) |
| `cmd_watch` | `SurveyRunner.run_loop()` | ⚠️ NOCH SurveyRunner (deprecated) |

### cmd_run (REFRACTORED 2026-05-10)
```python
from survey.graph import SurveyState, run_survey_loop
state = SurveyState(survey_id=args.id, provider=provider, survey_url=survey_url)
final_state = run_survey_loop(state)
_print_result_graph(final_state)
```
- Balance-Tracking: balance_before/balance_after
- Iteration: JEDE Iteration, nicht nur bei Actions
- survey_url field: für --url Argument Support
- NIM decide_node: Placeholder (kein echter API Call)

---

## SURVEY PROVIDER (BEKANNT)

| Provider | URL | Flow | Status |
|----------|-----|------|--------|
| Purespectrum | `purespectrum.com` | Cookie→ROBOT→Textarea→Visual→**Drag-Drop "Zahl X"** | ❌ BLOCKED |
| Samplicio.us | `rx.samplicio.us/consent/` | Consent→My-Take | ✅ |
| TolunaStart | `enter.ipsosinteractive.com` | `cf-radio-answer` class | ✅ |
| Cint | `sw.cint.com/Session/` | Session→Fragen | ✅ |
| Nfield/Kantar | `nfieldeu-interviewing.nfieldmr.com` | Audio/Video (blob) | 🔄 |
| Qualtrics | various | Matrix/Radio/Dropdown | 🔄 |

---

## DRAG-DROP PUZZLE (BLOCKED)

**Problem**: Angular CDK PointerEvents werden blockiert.
**Location**: `purespectrum.py:solve_drag_puzzle()` — BROKEN
**Fix needed**: PointerEvent-Simulation auf DOM-Ebene via `Runtime.evaluate`
**Siehe**: AGENTS.md §11.3

---

## BANNED (NIEMALS VERWENDEN)

- `pkill -f "Google Chrome"` → tötet USER Chrome!
- `killall Google Chrome` → tötet ALLE Chrome!
- `playstealth launch` → keine Cookie-Injection, Profil 902
- `webauto-nodriver` → ABSOLUT VERBOTEN
- `decrypt_cookies.py` → Chrome <147 only
- `launch_parallel.py` → ❌ DELETED (2026-05-09) — verschlüsselte Cookies, Profil 902
- Hardcoded PIDs → dynamisch!

---

## KEY FILES (AKTUELL)

```
CHROME START         → AGENTS.md REGELN 1-4
SURVEY RUN (cmd_run)  → survey-cli/survey.py:cmd_run() → survey_cli.survey.graph.run_survey_loop()
LANGGRAPH AGENT      → survey-cli/survey/graph/ (state.py, nodes.py, graph.py, opencode_tool.py, __init__.py)
SURVEY AGENT API     → survey-cli/survey/graph/__init__.py (PUBLIC API)
FASTAPI ENDPOINTS    → agent-toolbox/api/survey_tools.py
CHROME KILL          → survey/chrome.py:safe_kill_bot()
CAPTCHA SOLVE        → stealth-captcha/src/stealth_captcha/cli.py
NVIDIA VISION        → stealth-captcha/src/stealth_captcha/solver/text.py:PixtralCaptchaBackend
NVIDIA NIM           → survey/nim.py (Placeholder)
```

---

## GITHUB ISSUES (AKTUELL)

- SR-38 bis SR-49 (12 Issues in "Survey-Agent-v1" Milestone)
- SR-39: ✅ cmd_run → run_survey_loop() (DONE 2026-05-10)
- SR-40: ⏳ cmd_watch → Graph invoke (TODO)
- SR-41: ✅ balance_before/balance_after (DONE 2026-05-10)
- SR-42: ⏳ POST /survey/run-graph FastAPI (TODO)

---

## VERALTET / GELÖSCHT (DO NOT USE)

- `src/stealth_survey/` → INTENTIONALLY DELETED 2026-05-08
- `app/` → INTENTIONALLY DELETED 2026-05-08
- `plans/01-canonical-engine.md` → GELÖSCHT
- `plans/01-survey-agent-langgraph-fastapi.md` → MASTER PLAN (GILT NOCH!)
- `survey-cli/survey/runner.py` → deprecated (893Z, noch in use von cmd_loop/cmd_watch)
- `survey-cli/survey/plan.md` → GELÖSCHT

---

*Update 2026-05-10: brain.md komplett umgeschrieben. Alte CUA-ONLY Stack Dokumentation ist obsolet. cmd_run nutzt jetzt run_survey_loop(). Alte Login-Logs (15k+ Zeilen) sind entfernt.*