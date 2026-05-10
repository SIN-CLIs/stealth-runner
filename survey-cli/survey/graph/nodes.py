"""================================================================================
SURVEY GRAPH NODES — 8 LangGraph Nodes für Survey-Automation
================================================================================

WAS IST DAS?
  8 atomare Graph-Nodes die Survey-Automation in diskrete Schritte zerlegen.
  Jede Node ist <=30 Zeilen und wrapped eine existierende Funktion.
  Keine business logic in Nodes — NUR delegate + state update.

ARCHITEKTUR:
  Jede Node folgt dem gleichen Pattern:
    1. Hole relevante Daten aus state
    2. Rufe existierende Funktion auf
    3. Update state mit Ergebnis
    4. Return updated state

  ┌─────────────────────────────────────────────────────────────────────────┐
  │                           NODE EXECUTION ORDER                          │
  ├─────────────────────────────────────────────────────────────────────────┤
  │                                                                          │
  │  ensure_chrome ──→ open_survey ──→ inject_cookies                       │
  │       │                  │                 │                            │
  │       ▼                  ▼                 ▼                            │
  │  (if chrome dead)   (if tab fails)    (if cookies fail)                 │
  │       │                  │                 │                            │
  │       └──────────────────┴─────────────────┘                            │
  │                        │                                                │
  │                        ▼                                                │
  │              ┌──────────────┐                                           │
  │              │  snapshot    │ ← Compact DOM Snapshot via CDP           │
  │              └──────┬───────┘                                           │
  │                     │                                                   │
  │                     ▼                                                   │
  │              ┌──────────────┐                                           │
  │              │    decide    │ ← NIM Nemotron Decision                   │
  │              └──────┬───────┘                                           │
  │                     │                                                   │
  │                     ▼                                                   │
  │              ┌──────────────┐                                           │
  │              │   execute    │ ← Batch Execute via CDP                   │
  │              └──────┬───────┘                                           │
  │                     │                                                   │
  │                     ▼                                                   │
  │         ┌───────────┼───────────┐                                      │
  │         ▼           ▼           ▼                                      │
  │   detect_completion  │         │                                       │
  │    (completed?)      │         │                                       │
  │         │            │         │                                       │
  │    [yes] ── END      │         │                                       │
  │    [no] ─────────────┘         │                                       │
  │                       ┌────────┘                                        │
  │                       │                                                 │
  │                       ▼                                                 │
  │              ┌──────────────┐                                           │
  │              │ should       │                                           │
  │              │ delegate?    │                                           │
  │              └──────┬───────┘                                           │
  │                     │                                                   │
  │           ┌─────────┴─────────┐                                        │
  │           ▼                   ▼                                        │
  │      [yes]                  [no]                                       │
  │      human_delegate         snapshot (next iteration)                   │
  │           │                                                         │
  │           ▼                                                         │
  │         END                                                         │
  │                                                                          │
  └─────────────────────────────────────────────────────────────────────────┘

NODE LIST (8 nodes, jede ≤30 Zeilen):

  1. ensure_chrome(state)           Chrome starten/verifizieren
  2. open_survey(state)             Survey-Tab öffnen via SurveyOpener
  3. inject_cookies(state)          Heypiggy-Cookies in Survey-Tab injizieren
  4. snapshot_node(state)           Compact DOM-Snapshot via CDP
  5. decide_node(state)             NIM Nemotron Decision (oder placeholder)
  6. execute_node(state)            Batch-Execution via BatchExecutor
  7. detect_completion(state)       Survey-Completion/Screen-Out detectieren
  8. human_delegate(state)          An opencode CLI delegieren

KONZEPT: SINGLE RESPONSIBILITY
  Jede Node hat GENAU eine Aufgabe. Keine Node kombiniert zwei Operationen.
  → Wenn eine Node fehlschlägt, wissen wir exakt was passiert ist.
  → Keine "schauen wir mal ob es geklappt hat" Logik in Nodes.
  → Jede Node ist standalone testbar.

ROOT CAUSE inject_cookies (2026-05-09):
  Survey-Tabs die via `Target.createTarget` geöffnet werden haben KEINE
  heypiggy-Cookies → CPX redirectiert zurück zum Dashboard → €0 verdient.
  Lösung: 7 Heypiggy-Cookies (PHPSESSID, user_session, user_id, etc.)
  aus ~/.stealth/heypiggy-backup/heypiggy-cookies.json laden und per
  Network.setCookies in den Survey-Tab injizieren.

  HEYPIGGY-Cookies (7 Stück):
    - PHPSESSID       → www.heypiggy.com
    - user_session    → www.heypiggy.com (KRITISCH für Login!)
    - user_id         → www.heypiggy.com (KRITISCH!)
    - user_a_b_group  → www.heypiggy.com
    - lang_pig        → www.heypiggy.com
    - g_state         → www.heypiggy.com
    - referer         → www.heypiggy.com

BANNED METHODS — NIEMALS VERWENDEN:
  ❌ playstealth launch — setzt NICHT --force-renderer-accessibility
  ❌ webauto-nodriver — ABSOLUT BANNED
  ❌ cua-driver click (raw index) — instabil, nutze tool_click.py
  ❌ Hardcoded PIDs — dynamisch, niemals hardcodieren
  ❌ pkill -f "Google Chrome" — tötet USER Chrome
  ❌ killall Google Chrome — tötet ALLE Chrome
  ❌ skylight-cli click --element-index — Index instabil

DEPENDENCIES:
  - .state.SurveyState — State-Objekt
  - ..chrome — ChromeLauncher.launch_and_verify(), find_dashboard_ws()
  - ..opener — SurveyOpener.open() → OpenResult
  - ..execute — BatchExecutor.execute() → BatchResult
  - ..completion_detector — CompletionDetector.detect_ws()
  - ..cdp_client — CDPConnection (für cookie injection)
  - .opencode_tool — delegate_task() → opencode CLI

================================================================================"""

from __future__ import annotations

import json
import os
import time
import websocket

from .state import SurveyState
from .opencode_tool import delegate_task

# ── PATH CONSTANTS ─────────────────────────────────────────────────────────────

# Backup-Cookie-Pfad: wird von Cookie-Injection genutzt.
# Wird bei Bedarf überschrieben (z.B. für Tests).
DEFAULT_COOKIE_BACKUP = os.path.expanduser("~/.stealth/heypiggy-backup/heypiggy-cookies.json")

# ── NODE 1: ensure_chrome ─────────────────────────────────────────────────────
# Funktion: Chrome starten/verifizieren
# Wrapped:  ChromeLauncher.launch_and_verify()
# Returns:  state mit dashboard_ws gesetzt (wenn chrome gestartet)
#           state mit status='error' (wenn chrome nicht startet)
# Lines:    ~22


def ensure_chrome(state: SurveyState) -> SurveyState:
    from ..chrome import is_chrome_alive, find_dashboard_ws, ChromeLauncher
    if is_chrome_alive(state.cdp_port):
        ws = find_dashboard_ws(state.cdp_port)
        if ws: state.dashboard_ws = ws; state.status = "chrome_ready"; return state
        state.add_error("ensure_chrome", f"Chrome alive no WS port {state.cdp_port}"); state.status = "error"; return state
    result = ChromeLauncher(port=state.cdp_port, debug=True).launch_and_verify(url="https://www.heypiggy.com/?page=dashboard")
    if not result.get("ok"): state.add_error("ensure_chrome", result.get("error","launch failed")); state.status = "error"; return state
    time.sleep(2)
    ws = find_dashboard_ws(state.cdp_port)
    if ws: state.dashboard_ws = ws; state.status = "chrome_ready"
    else: state.add_error("ensure_chrome", "launched no WS"); state.status = "error"
    return state


# ── NODE 2: open_survey ───────────────────────────────────────────────────────
# Funktion: Survey-Tab öffnen via SurveyOpener
# Wrapped:  SurveyOpener.open()
# Returns:  state mit tab_ws + provider gesetzt
#           state mit status='error' (wenn Tab nicht geöffnet)
# Lines:    ~28


def open_survey(state: SurveyState) -> SurveyState:
    try:
        from tools.tool_open_survey import open_survey as _open_survey_tool
    except ImportError:
        import importlib.util
        spec = importlib.util.spec_from_file_location("tool_open_survey", "/Users/jeremy/dev/stealth-runner/survey-cli/tools/tool_open_survey.py")
        mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod); _open_survey_tool = mod.open_survey
    result = _open_survey_tool(survey_id=state.survey_id, pid=0, wid=0, port=state.cdp_port, wait_modal=3.0, wait_load=5.0)
    if result.get("status") != "ok":
        err = result.get("reason", "Unknown")
        state.add_error("open_survey", err)
        if "screen_out" in err.lower() or "expired" in err.lower(): state.screen_out = True; state.status = "screen_out"
        else: state.status = "error"
        return state
    ws_url = result.get("ws_url")
    if not ws_url: state.add_error("open_survey", "no ws_url"); state.status = "error"; return state
    state.tab_ws = ws_url; state.survey_url = result.get("url", "")
    if result.get("provider"): state.provider = result.get("provider")
    state.target_mode = "in_dashboard" if result.get("flow") == "in_page" else "new_tab"
    state.status = "tab_open"; return state


# ── NODE 3: inject_cookies ────────────────────────────────────────────────────
# Funktion: Heypiggy-Cookies in Survey-Tab injizieren
# Wrapped:  CDP Network.setCookies
# Returns:  state mit cookies_injected=True
#           state mit status='cookies_injected' (wenn injiziert)
#           state mit status='error' (wenn injection fehlschlägt)
# Lines:    ~45
#
# ROOT CAUSE (2026-05-09):
#   Survey-Tabs via Target.createTarget haben KEINE Session-Cookies.
#   → CPX redirectiert zurück zum Dashboard → €0 verdient.
#   FIX: 7 Heypiggy-Cookies nach Tab-Erstellung injizieren.
#
# Cookie-Dateistruktur:
#   ~/.stealth/heypiggy-backup/heypiggy-cookies.json
#   Format: {"metadata": {...}, "cookies": [40 total, 7 Heypiggy]}


def inject_cookies(state: SurveyState) -> SurveyState:
    if getattr(state, "target_mode", "new_tab") == "in_dashboard":
        state.cookies_injected = True; state.status = "cookies_injected"; return state
    if not state.tab_ws:
        state.add_error("inject_cookies", "tab_ws not set"); state.status = "error"; return state
    cookie_file = os.environ.get("HEYPIGGY_COOKIE_BACKUP", DEFAULT_COOKIE_BACKUP)
    try:
        with open(cookie_file) as f: cookie_data = json.load(f)
    except Exception as e:
        state.add_error("inject_cookies", f"Load failed {cookie_file}: {e}"); state.status = "error"; return state
    heypiggy = [{"name":c["name"],"value":c["value"],"domain":c["domain"],"path":c.get("path","/"),"expires":c.get("expires",-1),"secure":c.get("secure",False),"httpOnly":c.get("httpOnly",False)} for c in cookie_data.get("cookies",[]) if "heypiggy" in c.get("domain","").lower()]
    if not heypiggy:
        state.add_error("inject_cookies", "No heypiggy cookies"); state.status = "error"; return state
    try:
        ws = websocket.create_connection(state.tab_ws, timeout=15)
        ws.send(json.dumps({"id": 1, "method": "Network.setCookies", "params": {"cookies": heypiggy}}))
        resp = json.loads(ws.recv()); ws.close()
        if resp.get("result", {}).get("success") is True:
            state.cookies_injected = True; state.status = "cookies_injected"
        else:
            state.add_error("inject_cookies", str(resp)); state.status = "error"
    except Exception as e:
        state.add_error("inject_cookies", str(e)[:200]); state.status = "error"
    return state


# ── NODE 4: snapshot_node ─────────────────────────────────────────────────────
# Funktion: Compact DOM-Snapshot via CDP (1 LLM-Call pro Seite, ~500 tokens)
# Wrapped:  CDP Runtime.evaluate (inline JS)
# Returns:  state mit snapshot_refs, status='running'
# Lines:    ~28

def snapshot_node(state: SurveyState) -> SurveyState:
    if not state.tab_ws:
        state.add_error("snapshot_node", "tab_ws not set"); state.status = "error"; return state
    try:
        ws = websocket.create_connection(state.tab_ws, timeout=15)
        ws.send(json.dumps({"id": 0, "method": "Runtime.evaluate", "params": {"expression": """
(function(){var r={},s=new Set(),c=0,n=function(role,text,idx,tag){if(!text||s.has(text))return;s.add(text);r['@e'+c++]={role:role,text:text.substring(0,100),idx:idx,tag:tag}};
document.querySelectorAll('input[type=radio],input[type=checkbox],[role=radio],[role=checkbox]').forEach(function(e,i){var t=e.id&&document.querySelector('label[for='+e.id+']')?(document.querySelector('label[for='+e.id+']').textContent||'').trim():'';if(!t)t=(e.getAttribute('aria-label')||'').trim();if(!t){var p=e.parentElement;if(p)t=(p.textContent||'').trim().substring(0,100);}if(!t)t=(e.textContent||e.name||e.value||'').trim();n((e.type||e.getAttribute('role')||'radio')+'-selected',t,i,e.tagName);});
document.querySelectorAll('textarea,input[type=text],input[type=number]').forEach(function(e){n('textarea',(e.placeholder||e.getAttribute('aria-label')||'').trim().substring(0,50),0,e.tagName);});
document.querySelectorAll('button,input[type=submit],[role=button]').forEach(function(e,i){var t=(e.textContent||e.value||e.getAttribute('aria-label')||'').trim();if(t&&!s.has(t)){s.add(t);r['@e'+c++]={role:'button',text:t.substring(0,50),idx:i,tag:e.tagName};}});
return JSON.stringify(r);})()"""}}))
        resp = json.loads(ws.recv()); ws.close()
        state.snapshot_refs = json.loads(resp.get("result",{}).get("result",{}).get("value","{}")) if isinstance(resp.get("result",{}).get("result",{}).get("value"), str) else {}
        state.status = "running"
    except Exception as e:
        state.add_error("snapshot_node", str(e)[:200]); state.status = "error"
    return state


# ── NODE 5: decide_node ───────────────────────────────────────────────────────
# Funktion: NIM Nemotron Decision — Universal Survey Decision Engine
# Wrapped:  NIMClient.decide() + heuristic fallback
# Returns:  state mit nim_actions
# Lines:    ~27

def decide_node(state: SurveyState) -> SurveyState:
    from survey.nim import get_nim; from survey.profile_loader import ProfileLoader
    profile = ProfileLoader.load_profile()
    snapshot = {"refs": state.snapshot_refs, "semantic": {"questions": [], "progress": f"{state.iteration}/{state.max_iterations}"}, "provider": state.provider or "unknown"}
    result = get_nim().decide(snapshot=snapshot, profile=profile)
    actions = result.get("actions", []) if result else []
    if actions:
        print(f"[NIM] {result.get('model','?')}: {len(actions)} actions, {result.get('tokens',{}).get('total',0)} tokens, {result.get('elapsed_ms',0)}ms")
    if not actions:
        for ref, info in state.snapshot_refs.items():
            if info.get("role","").startswith("radio"): actions.append({"ref": ref, "action": "select"}); break
        if any(v.get("role")=="textarea" for v in state.snapshot_refs.values()): actions.append({"ref": None, "action": "fill", "value": profile.get("city","Berlin")})
        for ref, info in state.snapshot_refs.items():
            if info.get("role")=="button" and any(b in info.get("text","") for b in ["Nächster","Weiter","Next","Skip"]): actions.append({"ref": ref, "action": "submit"}); break
    if not actions or not any(a.get("action") in ("submit","click") for a in actions): actions.append({"action": "submit"})
    state.nim_actions = actions; return state


# ── NODE 6: execute_node ──────────────────────────────────────────────────────
# Funktion: Batch-Execution via SurveyFlowExecutor (Pre-Flight + Safe Sequences)
# Wrapped:  SurveyFlowExecutor.execute_actions()
# Returns:  state mit batch_result, consecutive_failures incrementiert/resetet
# Lines:    ~25

def execute_node(state: SurveyState) -> SurveyState:
    if not state.tab_ws:
        state.add_error("execute_node", "tab_ws not set"); state.status = "error"; return state
    if not state.nim_actions:
        state.batch_result = {"success": True, "results": [], "total_success": 0, "total_fail": 0, "elapsed_ms": 0}; return state

    from ..safe_executor import SurveyFlowExecutor
    tab_id = state.tab_ws.split("/devtools/page/")[-1]
    executor = SurveyFlowExecutor(tab_id=tab_id)
    if not executor.connect():
        state.add_error("execute_node", "CDP connection failed"); state.status = "error"; return state

    # nim_actions → execute_actions format
    def to_cmd(action):
        t = action.get("action", ""); ref = action.get("ref", ""); val = action.get("value", "")
        idx = state.snapshot_refs.get(ref, {}).get("idx", 0) or 0
        if t == "select": return {"command": "select_radio", "params": {"radio_id": f"radio_idx_{idx}"}}
        if t == "fill": return {"command": "fill_number", "params": {"input_id": f"input_idx_{idx}", "value": val}}
        if t in ("submit", "click"): return {"command": "click_continue", "params": {"with_sleep": True, "sleep_seconds": 2}}
        return None

    actions = [to_cmd(a) for a in state.nim_actions if to_cmd(a)]
    try:
        result = executor.execute_actions(actions); executor.disconnect()
    except Exception as e:
        state.add_error("execute_node", str(e)[:200]); state.status = "error"; return state

    state.batch_result = result
    state.increment_failures() if result.get("total_fail", 0) > 0 else state.reset_failures()
    return state


# ── NODE 7: detect_completion ─────────────────────────────────────────────────
# Funktion: Completion/Screen-Out detectieren via CDP page text + CompletionDetector
# Returns:  state mit completion_detected/screen_out + status
# Lines:    ~23

def detect_completion(state: SurveyState) -> SurveyState:
    if not state.tab_ws: state.add_error("detect_completion", "tab_ws not set"); return state
    from ..completion_detector import CompletionDetector; from ..execute import BatchExecutor
    page_text = BatchExecutor.read_page_text(state.tab_ws, max_len=500)
    if CompletionDetector(cdp_port=state.cdp_port, debug=False).detect(page_text):
        state.completion_detected = True; state.status = "completed"
        if getattr(state,"target_mode","new_tab")=="in_dashboard" and state.dashboard_ws:
            from ..opener import SurveyOpener
            SurveyOpener(cdp_port=state.cdp_port).navigate_back_to_dashboard(state.tab_ws or state.dashboard_ws or "")
        return state
    is_err, reason = BatchExecutor.detect_error_page(page_text)
    if is_err and any(s in reason.lower() for s in ["qualify","eligible","screen","limit","full"]):
        state.screen_out = True; state.status = "screen_out"
        if getattr(state,"target_mode","new_tab")=="in_dashboard" and state.dashboard_ws:
            from ..opener import SurveyOpener
            SurveyOpener(cdp_port=state.cdp_port).navigate_back_to_dashboard(state.tab_ws or state.dashboard_ws or "")
        return state
    return state


# ── NODE 8: read_balance_before ───────────────────────────────────────────────
# Funktion: Balance VOR Survey lesen
# Wrapped:  read_balance_with_backoff()
# Returns:  state mit balance_before gesetzt
# Lines:    ~12


def read_balance_before(state: SurveyState) -> SurveyState:
    """Lese heypiggy-Balance VOR der Survey-Session.

    Nutzt read_balance_with_backoff() für robustes Retry.
    Setzt state.balance_before und setzt status='balance_read'.

    Args:
        state: SurveyState mit cdp_port

    Returns:
        Updated state mit balance_before (float) oder 0.0 bei Fehler

    Side-Effects:
        - CDP WebSocket: Dashboard-Tab Text lesen
        - Retry-Loop bis Balance erkannt oder max_retries erreicht
    """
    from ..scanner import read_balance_with_backoff

    try:
        balance = read_balance_with_backoff(port=state.cdp_port, max_retries=3, base_delay=1.0)
        state.balance_before = balance
    except Exception as e:
        state.add_error("read_balance_before", str(e)[:200])
        state.balance_before = 0.0
    return state


# ── NODE 9: read_balance_after ────────────────────────────────────────────────
# Funktion: Balance NACH Survey lesen
# Wrapped:  read_balance_with_backoff()
# Returns:  state mit balance_after + balance_earned gesetzt
# Lines:    ~12


def read_balance_after(state: SurveyState) -> SurveyState:
    """Lese heypiggy-Balance NACH der Survey-Session.

    Nutzt read_balance_with_backoff() für robustes Retry.
    Setzt state.balance_after und berechnet balance_earned.

    Args:
        state: SurveyState mit cdp_port

    Returns:
        Updated state mit balance_after (float) oder balance_before bei Fehler

    Side-Effects:
        - CDP WebSocket: Dashboard-Tab Text lesen
        - Retry-Loop bis Balance erkannt oder max_retries erreicht
    """
    from ..scanner import read_balance_with_backoff

    try:
        balance = read_balance_with_backoff(port=state.cdp_port, max_retries=3, base_delay=1.0)
        state.balance_after = balance
    except Exception as e:
        state.add_error("read_balance_after", str(e)[:200])
        state.balance_after = state.balance_before
    return state


# ── NODE 10: human_delegate ───────────────────────────────────────────────────
# Funktion: An opencode CLI delegieren
# Wrapped:  opencode_tool.delegate_task()
# Returns:  state mit status='delegated', delegation_reason
# Lines:    ~25
#
# TRIGGER: consecutive_failures >= 3
# Grund: Offene Probleme die ein Mensch lösen muss (Captchas, Edge-Cases, etc.)


def human_delegate(state: SurveyState) -> SurveyState:
    last_err = state.errors[-1] if state.errors else {"error": "unknown"}
    reason = f"3 consecutive failures at iteration {state.iteration}: {last_err.get('error','unknown')}"
    state.delegation_reason = reason; state.status = "delegated"
    result = delegate_task(survey_id=state.survey_id, provider=state.provider, reason=reason, tab_ws=state.tab_ws, iteration=state.iteration)
    state.errors.append({"node": "human_delegate", "error": f"delegated: {result.get('stdout','')[:200]}", "iteration": state.iteration, "ts": time.time()})
    return state