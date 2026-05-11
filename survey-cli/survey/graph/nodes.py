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
    """Kanonischer Scan via cdp_universal.scan() — ersetzt handgerolltes JS.

    Setzt state.universal_elements (flach, mit stable_id) und
    state.captcha_frames. snapshot_refs bleibt aus Backward-Compat-Gruenden
    minimal befuellt (fuer alte Tools), wird aber NICHT mehr fuer decide/execute
    genutzt. Pflicht-Kontext: AGENTS.md "KANONISCHE ARCHITEKTUR (2026-05-11)".
    """
    if not state.tab_ws:
        state.add_error("snapshot_node", "tab_ws not set")
        state.status = "error"
        return state

    from ..cdp_universal import scan as _scan_universal
    from ..cdp_client import CDPConnection

    try:
        with CDPConnection(state.tab_ws, timeout=20) as cdp:
            result = _scan_universal(cdp)
    except Exception as e:
        state.add_error("snapshot_node", f"cdp_universal.scan failed: {e}"[:300])
        state.status = "error"
        return state

    elements = []
    for el in result.elements:
        elements.append({
            "stable_id": el.stable_id,
            "frame_id": el.frame_id,
            "role": el.role,
            "name": el.name,
            "value": el.value,
            "tag": el.tag,
            "text": el.text,
            "state": el.state,
            "bbox": el.bbox,
            "attrs": el.attrs,
            "frame_url": el.frame_url,
        })
    state.universal_elements = elements
    state.captcha_frames = result.captcha_frames

    # Backward-Compat-Spiegel: minimaler @eN-Index fuer alte Tools.
    # NEUER Code MUSS universal_elements + stable_id verwenden.
    state.snapshot_refs = {
        f"@e{i}": {"role": el["role"], "text": el["name"],
                   "stable_id": el["stable_id"]}
        for i, el in enumerate(elements)
    }
    state.status = "running"
    print(f"[scan] {len(elements)} elements, {result.frame_count} frames, "
          f"{len(result.captcha_frames)} captcha-iframes")
    return state


# ── NODE 4b: captcha_node (NEU 2026-05-11) ────────────────────────────────────
# Funktion: Captcha-Detection + Solver-Routing via captcha_router
# Wrapped:  CaptchaRouter.detect_and_solve()
# Returns:  state mit captcha_solved_this_iteration = True/False
#
# WANN AUFGERUFEN: Direkt nach snapshot_node, VOR decide_node.
# - Wenn captcha_frames leer UND no_dom_change_count < 2 → NO-OP.
# - Sonst → versucht Detection + Solve via CaptchaRouter.
# Solver leben in stealth-captcha/. Fehlende Solver -> reason='no_solver_for_type'.


def captcha_node(state: SurveyState) -> SurveyState:
    """Erkennt + loest Captchas auf dem aktuellen Tab.

    Pflicht-Kontext: survey-cli/survey/captcha_router.py.
    NIEMALS Captcha-Sniffing in andere Nodes einbauen.
    """
    if not state.captcha_frames and state.no_dom_change_count < 2:
        state.captcha_solved_this_iteration = False
        return state

    if not state.tab_ws:
        state.add_error("captcha_node", "tab_ws not set")
        return state

    from ..cdp_client import CDPConnection
    from ..cdp_universal import scan as _scan
    from ..captcha_router import CaptchaRouter

    try:
        with CDPConnection(state.tab_ws, timeout=20) as cdp:
            scan_res = _scan(cdp)
            router_obj = CaptchaRouter(cdp)
            result = router_obj.detect_and_solve(scan_res)
    except Exception as e:
        state.add_error("captcha_node", str(e)[:300])
        state.captcha_solved_this_iteration = False
        return state

    if result is None:
        state.captcha_solved_this_iteration = False
        return state

    state.captcha_solved_this_iteration = bool(result.solved)
    if result.solved:
        print(f"[captcha] solved type={result.captcha_type} "
              f"elapsed={result.elapsed_ms:.0f}ms")
        state.no_dom_change_count = 0
    else:
        print(f"[captcha] NOT solved type={result.captcha_type} "
              f"reason={result.reason}")
        state.add_error("captcha_node",
                        f"{result.captcha_type}: {result.reason}")
    return state



# ── NODE 5: decide_node ───────────────────────────────────────────────────────
# Funktion: NIM Nemotron Decision — Universal Survey Decision Engine
# Wrapped:  NIMClient.decide() + heuristic fallback
# Returns:  state mit nim_actions
# Lines:    ~27

def decide_node(state: SurveyState) -> SurveyState:
    """Waehlt EINE Aktion basierend auf state.universal_elements.

    Strategie (Reihenfolge):
      0) Wenn letzter Klick no_dom_change → schliesse vorheriges stable_id
         aus. Schutz gegen Issue #24 (anti-stuck loop).
      1) NIM/LLM-Decide (falls verfuegbar): LLM bekommt flache Liste mit
         stable_id + role + name + state, liefert genau eine Decision.
      2) Heuristik-Fallback:
         a) Erstes ungeklicktes Radio → click
         b) Erste leere textbox → fill
         c) Button mit Name in {Weiter,Next,Submit,Continue,Senden,…} → click
         d) Sonst: action="wait"
    Setzt state.decision = {action, stable_id?, value?, key?, reason}.
    nim_actions wird Backward-Compat parallel gefuellt.
    """
    from ..profile_loader import ProfileLoader
    try:
        from ..nim import get_nim
    except Exception:
        get_nim = None

    profile = ProfileLoader.load_profile()
    elements = state.universal_elements or []

    last = state.last_action_result or {}
    avoid_id = ""
    if last.get("success") is False and last.get("reason") == "no_dom_change":
        avoid_id = last.get("stable_id", "")

    decision: Dict[str, Any] = {}

    # 1) LLM-Decide (optional)
    if get_nim and elements:
        try:
            llm_in = {
                "elements": [
                    {"stable_id": e["stable_id"], "role": e["role"],
                     "name": e["name"], "value": e["value"],
                     "checked": e.get("state", {}).get("checked", False)}
                    for e in elements
                    if not e.get("state", {}).get("disabled")
                ],
                "avoid_stable_id": avoid_id,
                "no_dom_change_count": state.no_dom_change_count,
                "iteration": state.iteration,
                "provider": state.provider or "unknown",
            }
            llm_out = get_nim().decide(snapshot=llm_in, profile=profile) or {}
            actions = llm_out.get("actions") or []
            if actions:
                a0 = actions[0]
                sid = a0.get("stable_id") or ""
                act = a0.get("action") or ""
                if sid and act and sid != avoid_id:
                    decision = {"action": act, "stable_id": sid,
                                "value": a0.get("value", ""),
                                "reason": "llm"}
                state.nim_actions = actions
        except Exception as e:
            state.add_error("decide_node", f"nim failed: {e}"[:200])

    # 2) Heuristik
    if not decision:
        # 2a Radio/Checkbox
        for e in elements:
            if e["stable_id"] == avoid_id:
                continue
            if e.get("state", {}).get("disabled"):
                continue
            if e["role"] in ("radio", "checkbox", "switch"):
                if not e.get("state", {}).get("checked"):
                    decision = {"action": "click", "stable_id": e["stable_id"],
                                "reason": f"heuristic_radio:{e['name'][:30]}"}
                    break

        # 2b leere textbox
        if not decision:
            for e in elements:
                if e["stable_id"] == avoid_id:
                    continue
                if e["role"] in ("textbox", "searchbox", "spinbutton"):
                    if not e.get("value"):
                        val = str(profile.get("city", "Berlin"))
                        decision = {"action": "fill",
                                    "stable_id": e["stable_id"],
                                    "value": val,
                                    "reason": "heuristic_fill"}
                        break

        # 2c continue button
        if not decision:
            cont = ("weiter", "next", "submit", "continue",
                    "senden", "fortfahren", "ok")
            for e in elements:
                if e["stable_id"] == avoid_id:
                    continue
                if e["role"] == "button":
                    name_low = (e.get("name") or "").lower()
                    if any(w in name_low for w in cont):
                        decision = {"action": "click",
                                    "stable_id": e["stable_id"],
                                    "reason": f"heuristic_button:{name_low[:30]}"}
                        break

        # 2d wait
        if not decision:
            decision = {"action": "wait", "reason": "no_candidate_found"}

    state.decision = decision
    print(f"[decide] action={decision.get('action')} "
          f"stable_id={decision.get('stable_id','')[:10]} "
          f"reason={decision.get('reason','')[:40]}")
    return state


# ── NODE 6: execute_node ──────────────────────────────────────────────────────
# Funktion: Batch-Execution via SurveyFlowExecutor (Pre-Flight + Safe Sequences)
# Wrapped:  SurveyFlowExecutor.execute_actions()
# Returns:  state mit batch_result, consecutive_failures incrementiert/resetet
# Lines:    ~25

def execute_node(state: SurveyState) -> SurveyState:
    """Fuehrt state.decision aus via cdp_actuator (echter Klick + Verify).

    Pflicht-Verify: success=False mit reason='no_dom_change' wird HIER als
    Misserfolg behandelt — NICHT als success. Damit ist die alte Halluzination
    "Performed ohne Wirkung" strukturell unmoeglich.

    State-Updates:
      state.last_action_result  {success, reason, before_hash, after_hash,
                                  new_url, elapsed_ms, stable_id, action_type}
      state.no_dom_change_count inkrementiert bei no_dom_change, sonst 0
      state.consecutive_failures inkrementiert bei jedem failure
    """
    if not state.tab_ws:
        state.add_error("execute_node", "tab_ws not set")
        state.status = "error"
        return state

    decision = state.decision or {}
    action = decision.get("action") or ""
    sid = decision.get("stable_id") or ""

    # wait/done: keine CDP-Aktion
    if action in ("wait", "done", ""):
        state.last_action_result = {"success": True, "reason": action or "noop",
                                    "stable_id": "", "action_type": action}
        state.reset_failures()
        state.no_dom_change_count = 0
        state.batch_result = {"success": True, "results": [],
                              "total_success": 0, "total_fail": 0,
                              "elapsed_ms": 0}
        time.sleep(1.0)
        return state

    from ..cdp_client import CDPConnection
    from ..cdp_actuator import Actuator

    try:
        with CDPConnection(state.tab_ws, timeout=20) as cdp:
            actuator = Actuator(cdp)
            actuator.refresh_scan()

            if action == "click" or action == "submit":
                result = actuator.click(sid)
            elif action == "fill":
                result = actuator.fill(sid, decision.get("value", ""))
            elif action == "press_key":
                result = actuator.press_key(decision.get("key", "Enter"))
            else:
                state.add_error("execute_node", f"unknown action: {action!r}")
                state.status = "error"
                return state
    except Exception as e:
        state.add_error("execute_node", str(e)[:300])
        state.increment_failures()
        return state

    state.last_action_result = {
        "success": result.success,
        "reason": result.reason,
        "before_hash": result.before_hash,
        "after_hash": result.after_hash,
        "new_url": result.new_url,
        "elapsed_ms": result.elapsed_ms,
        "stable_id": sid,
        "action_type": action,
    }
    state.batch_result = {
        "success": result.success,
        "results": [state.last_action_result],
        "total_success": 1 if result.success else 0,
        "total_fail": 0 if result.success else 1,
        "elapsed_ms": result.elapsed_ms,
    }

    print(f"[act] {action} {sid[:10]} success={result.success} "
          f"reason={result.reason} elapsed={result.elapsed_ms:.0f}ms")

    if not result.success:
        state.increment_failures()
        if result.reason == "no_dom_change":
            state.no_dom_change_count += 1
    else:
        state.reset_failures()
        state.no_dom_change_count = 0
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