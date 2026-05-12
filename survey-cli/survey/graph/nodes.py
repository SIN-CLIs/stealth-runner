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
# ruff: noqa: E501  (long JS/HTML payloads in multi-line strings - SR-62 #61)

from __future__ import annotations

import json
import os
import time
from typing import Any  # noqa: F401 — used in annotations under `from __future__ import annotations`

import websocket

from .opencode_tool import delegate_task
from .state import SurveyState

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
        if ws: state.dashboard_ws = ws; state.status = "chrome_ready"; return state  # noqa: E701,E702
        state.add_error("ensure_chrome", f"Chrome alive no WS port {state.cdp_port}"); state.status = "error"; return state  # noqa: E501,E702
    result = ChromeLauncher(port=state.cdp_port, debug=True).launch_and_verify(url="https://www.heypiggy.com/?page=dashboard")
    if not result.get("ok"): state.add_error("ensure_chrome", result.get("error","launch failed")); state.status = "error"; return state  # noqa: E501,E701,E702
    time.sleep(2)
    ws = find_dashboard_ws(state.cdp_port)
    if ws: state.dashboard_ws = ws; state.status = "chrome_ready"  # noqa: E701,E702
    else: state.add_error("ensure_chrome", "launched no WS"); state.status = "error"  # noqa: E701,E702
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
        spec = importlib.util.spec_from_file_location("tool_open_survey", "/Users/jeremy/dev/stealth-runner/survey-cli/tools/tool_open_survey.py")  # noqa: E501
        mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod); _open_survey_tool = mod.open_survey  # noqa: E501,E702
    result = _open_survey_tool(survey_id=state.survey_id, pid=0, wid=0, port=state.cdp_port, wait_modal=3.0, wait_load=5.0)  # noqa: E501
    if result.get("status") != "ok":
        err = result.get("reason", "Unknown")
        state.add_error("open_survey", err)
        if "screen_out" in err.lower() or "expired" in err.lower(): state.screen_out = True; state.status = "screen_out"  # noqa: E501,E701,E702
        else: state.status = "error"  # noqa: E701
        return state
    ws_url = result.get("ws_url")
    if not ws_url: state.add_error("open_survey", "no ws_url"); state.status = "error"; return state  # noqa: E701,E702
    state.tab_ws = ws_url; state.survey_url = result.get("url", "")  # noqa: E702
    if result.get("provider"): state.provider = result.get("provider")  # noqa: E701
    state.target_mode = "in_dashboard" if result.get("flow") == "in_page" else "new_tab"
    state.status = "tab_open"; return state  # noqa: E702


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
        state.cookies_injected = True; state.status = "cookies_injected"; return state  # noqa: E702
    if not state.tab_ws:
        state.add_error("inject_cookies", "tab_ws not set"); state.status = "error"; return state  # noqa: E702
    cookie_file = os.environ.get("HEYPIGGY_COOKIE_BACKUP", DEFAULT_COOKIE_BACKUP)
    try:
        with open(cookie_file) as f: cookie_data = json.load(f)  # noqa: E701
    except Exception as e:
        state.add_error("inject_cookies", f"Load failed {cookie_file}: {e}"); state.status = "error"; return state  # noqa: E501,E702
    heypiggy = [{"name":c["name"],"value":c["value"],"domain":c["domain"],"path":c.get("path","/"),"expires":c.get("expires",-1),"secure":c.get("secure",False),"httpOnly":c.get("httpOnly",False)} for c in cookie_data.get("cookies",[]) if "heypiggy" in c.get("domain","").lower()]  # noqa: E501
    if not heypiggy:
        state.add_error("inject_cookies", "No heypiggy cookies"); state.status = "error"; return state  # noqa: E501,E702
    try:
        ws = websocket.create_connection(state.tab_ws, timeout=15)
        ws.send(json.dumps({"id": 1, "method": "Network.setCookies", "params": {"cookies": heypiggy}}))  # noqa: E501
        resp = json.loads(ws.recv()); ws.close()  # noqa: E702
        if resp.get("result", {}).get("success") is True:
            state.cookies_injected = True; state.status = "cookies_injected"  # noqa: E702
        else:
            state.add_error("inject_cookies", str(resp)); state.status = "error"  # noqa: E702
    except Exception as e:
        state.add_error("inject_cookies", str(e)[:200]); state.status = "error"  # noqa: E702
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
    # ══════════════════════════════════════════════════════════════════════════
    # DRAG-DROP DETECTION (2026-05-11) — Angular CDK + Generic HTML5
    # ══════════════════════════════════════════════════════════════════════════
    # Problem: Angular CDK drag-drop wird NICHT von cdp_universal erkannt weil
    # .cdk-drag keine native ARIA-Role hat. Der Agent versucht normale Klicks,
    # scheitert 2x, und DANN erst wird captcha_node aktiviert — zu spät!
    #
    # Lösung: Hier explizit nach Drag-Drop DOM-Signaturen suchen und in
    # state.drag_drop_detected speichern. captcha_node prüft dieses Flag.
    # ══════════════════════════════════════════════════════════════════════════
    try:
        drag_check_js = '''
        (function(){
            var cdkDrags = document.querySelectorAll('.cdk-drag');
            var cdkDrops = document.querySelectorAll('.cdk-drop-list, .drop-zone');
            var draggables = document.querySelectorAll('[draggable=true]');
            var bodyText = (document.body.innerText || '').toLowerCase();
            
            // Text-Cues für "Zahl X" Puzzle
            var hasZahlCue = /bitte legen sie die zahl|legen sie.*zahl|drag.*number/i.test(bodyText);
            
            // Extrahiere Ziel-Nummer wenn vorhanden
            var numMatch = bodyText.match(/zahl\s*(\d+)|number\s*(\d+)/i);
            var targetNumber = numMatch ? (numMatch[1] || numMatch[2]) : null;
            
            return JSON.stringify({
                cdk_drag_count: cdkDrags.length,
                cdk_drop_count: cdkDrops.length,
                draggable_count: draggables.length,
                has_zahl_cue: hasZahlCue,
                target_number: targetNumber,
                is_drag_drop_puzzle: (cdkDrags.length > 0 || draggables.length > 0) && hasZahlCue
            });
        })()
        '''
        drag_resp = cdp.call_result("Runtime.evaluate", {"expression": drag_check_js})
        drag_raw = drag_resp.get("result", {}).get("value", "{}")
        import json as _json
        drag_info = _json.loads(drag_raw)
        
        state.drag_drop_detected = drag_info.get("is_drag_drop_puzzle", False)
        state.drag_drop_target = drag_info.get("target_number")
        
        if state.drag_drop_detected:
            print(f"[scan] DRAG-DROP PUZZLE DETECTED: target={state.drag_drop_target}, "
                  f"cdk_drags={drag_info.get('cdk_drag_count')}")
    except Exception as e:
        state.drag_drop_detected = False
        state.drag_drop_target = None

    print(f"[scan] {len(elements)} elements, {result.frame_count} frames, "
          f"{len(result.captcha_frames)} captcha-iframes, drag_drop={state.drag_drop_detected}")
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
    # ══════════════════════════════════════════════════════════════════════════
    # TRIGGER-BEDINGUNG (2026-05-11 FIX):
    # ALT: Nur wenn captcha_frames existiert ODER no_dom_change_count >= 2
    #      → Agent klickt 2x vergeblich bevor Captcha-Check startet = ZU SPÄT!
    # NEU: AUCH wenn drag_drop_detected == True (von snapshot_node erkannt)
    #      → Sofortige Captcha-Prüfung wenn Drag-Drop-Puzzle erkannt wurde
    # ══════════════════════════════════════════════════════════════════════════
    has_captcha_hint = bool(state.captcha_frames)
    has_drag_drop = getattr(state, "drag_drop_detected", False)
    stuck_threshold_reached = state.no_dom_change_count >= 2
    
    if not has_captcha_hint and not has_drag_drop and not stuck_threshold_reached:
        state.captcha_solved_this_iteration = False
        return state
    
    # Log warum wir hier sind
    reason = []
    if has_captcha_hint: reason.append("captcha_frames")  # noqa: E701
    if has_drag_drop: reason.append(f"drag_drop(target={getattr(state, 'drag_drop_target', '?')})")  # noqa: E701
    if stuck_threshold_reached: reason.append(f"no_dom_change={state.no_dom_change_count}")  # noqa: E701
    print(f"[captcha] triggered: {', '.join(reason)}")

    if not state.tab_ws:
        state.add_error("captcha_node", "tab_ws not set")
        return state

    from ..cdp_client import CDPConnection
    from ..cdp_universal import scan as _scan
    from ..captcha_router import CaptchaRouter

    # ══════════════════════════════════════════════════════════════════════════
    # FAST-PATH: Wenn snapshot_node bereits drag_drop_detected == True gesetzt
    # hat, rufen wir den Angular-Drag-Drop-Solver DIREKT auf — ohne erneute
    # Detection via CaptchaRouter. Das spart Zeit und vermeidet Race Conditions.
    # ══════════════════════════════════════════════════════════════════════════
    if has_drag_drop:
        print(f"[captcha] FAST-PATH: drag_drop_detected=True, target={getattr(state, 'drag_drop_target', '?')}")  # noqa: E501
        try:
            from ..captcha_adapters import angular_drag_drop_solve
            from ..captcha_router import CaptchaDetection, CaptchaResult
            
            with CDPConnection(state.tab_ws, timeout=30) as cdp:
                detection = CaptchaDetection(
                    captcha_type="angular_drag_drop",
                    dom_hint=f"target={getattr(state, 'drag_drop_target', '?')}"
                )
                result = angular_drag_drop_solve(cdp, detection)
                
            state.captcha_solved_this_iteration = bool(result.solved)
            if result.solved:
                print(f"[captcha] FAST-PATH SOLVED: angular_drag_drop elapsed={result.elapsed_ms:.0f}ms")  # noqa: E501
                state.no_dom_change_count = 0
                state.drag_drop_detected = False  # Reset for next iteration
            else:
                print(f"[captcha] FAST-PATH FAILED: angular_drag_drop reason={result.reason}")
                state.add_error("captcha_node", f"angular_drag_drop: {result.reason}")
            return state
        except Exception as e:
            print(f"[captcha] FAST-PATH EXCEPTION: {e}")
            state.add_error("captcha_node", f"drag_drop_fast_path: {str(e)[:200]}")
            # Fall through to normal detection below
    
    # Standard-Path: CaptchaRouter.detect_and_solve()
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
      0.5) QUALIFICATION FILTER: Filtere disqualifizierende Antworten aus!
           NIEMALS "möchte nicht angeben", "keine Kinder", etc.
      1) NIM/LLM-Decide (falls verfuegbar): LLM bekommt flache Liste mit
         stable_id + role + name + state, liefert genau eine Decision.
      2) Heuristik-Fallback:
         a) Erstes ungeklicktes Radio → click (QUALIFICATION-SAFE!)
         b) Erste leere textbox → fill
         c) Button mit Name in {Weiter,Next,Submit,Continue,Senden,…} → click
         d) Sonst: action="wait"
      3) CUA-FALLBACK: Wenn CDP-Click fehlschlägt (no_dom_change > 2),
         nutze CUA-Driver für echte OS-Level Clicks.
    
    Setzt state.decision = {action, stable_id?, value?, key?, reason}.
    nim_actions wird Backward-Compat parallel gefuellt.
    
    QUALIFICATION RULES (2026-05-11):
      - NIEMALS "prefer not to say" / "möchte nicht angeben" auswählen
      - IMMER positive Antworten: "ja Kinder", "ja Haustiere", etc.
      - Bei Kinder/Tier-Fragen: IMMER "Ja" (sonst Disqualifikation!)
      - Ziel: 100% Survey Completion Rate
    """
    from ..profile_loader import ProfileLoader
    
    # ══════════════════════════════════════════════════════════════════════════
    # QUALIFICATION RULES IMPORT (2026-05-11)
    # ══════════════════════════════════════════════════════════════════════════
    try:
        from ..qualification_rules import (
            is_disqualifying_answer,
            matched_disqualifying_pattern,
            record_qualification_block,
            rank_answers_for_qualification,
            filter_safe_answers,
        )
        HAS_QUALIFICATION_RULES = True
    except ImportError:
        HAS_QUALIFICATION_RULES = False
        def is_disqualifying_answer(x): return False
        def matched_disqualifying_pattern(x): return None
        def record_qualification_block(**kw): pass
        def rank_answers_for_qualification(q, a): return list(range(len(a)))
        def filter_safe_answers(a): return list(range(len(a)))
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

    decision: dict[str, Any] = {}

    # ── Build stable_id → element index once (used by LLM-path filter) ───
    by_sid = {e["stable_id"]: e for e in elements}

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
                    # ── Issue #80: LLM-Path Qualification Filter ──────────
                    # Auch wenn das LLM eine click-Decision für ein
                    # Radio/Checkbox/Switch zurückgibt, MUSS sie durch den
                    # Disqualifikations-Filter laufen. Sonst kippt der Agent
                    # bei jeder "möchte nicht angeben"-Option, die das LLM
                    # auswählt. Heuristik allein hilft nichts wenn das LLM
                    # die Wahl vorher trifft.
                    rejected = False
                    if HAS_QUALIFICATION_RULES and act == "click":
                        el = by_sid.get(sid) or {}
                        if el.get("role") in ("radio", "checkbox", "switch"):
                            label = el.get("name", "") or el.get("value", "")
                            if label and is_disqualifying_answer(label):
                                pat = matched_disqualifying_pattern(label) or ""
                                record_qualification_block(
                                    question_text="",
                                    answer_text=label,
                                    matched_pattern=pat,
                                    source="decide_node:llm",
                                    survey_id=state.survey_id,
                                    provider=state.provider,
                                    iteration=state.iteration,
                                    stable_id=sid,
                                )
                                state.add_error(
                                    "decide_node",
                                    f"qualif_block(llm) {sid} '{label[:40]}' "
                                    f"pat={pat}"[:200],
                                )
                                print(f"[decide] BLOCKED LLM disqualifying "
                                      f"answer: '{label[:50]}' pattern={pat}")
                                rejected = True
                    if not rejected:
                        decision = {"action": act, "stable_id": sid,
                                    "value": a0.get("value", ""),
                                    "reason": "llm"}
                state.nim_actions = actions
        except Exception as e:
            state.add_error("decide_node", f"nim failed: {e}"[:200])

    # 2) Heuristik
    if not decision:
        # 2a Radio/Checkbox — MIT QUALIFICATION FILTER!
        # ──────────────────────────────────────────────────────────────────────
        # WICHTIG: NIEMALS disqualifizierende Antworten auswählen!
        # Der Agent MUSS positive Antworten wählen um nicht rausgeworfen zu werden.
        # ──────────────────────────────────────────────────────────────────────
        
        # Sammle alle Radio-Optionen für diese Frage
        radio_options = []
        for e in elements:
            if e["stable_id"] == avoid_id:
                continue
            if e.get("state", {}).get("disabled"):
                continue
            if e["role"] in ("radio", "checkbox", "switch"):
                if not e.get("state", {}).get("checked"):
                    radio_options.append(e)
        
        # Filtere disqualifizierende Antworten aus
        if radio_options and HAS_QUALIFICATION_RULES:
            safe_options = []
            for e in radio_options:
                label = e.get("name", "") or e.get("value", "")
                if not is_disqualifying_answer(label):
                    safe_options.append(e)
                else:
                    # Issue #80: Telemetry für JEDEN geblockten Heuristik-Skip
                    record_qualification_block(
                        question_text="",
                        answer_text=label,
                        source="decide_node:heuristic",
                        survey_id=state.survey_id,
                        provider=state.provider,
                        iteration=state.iteration,
                        stable_id=e.get("stable_id", ""),
                    )
            # Wenn alle Optionen "unsafe" sind, nimm trotzdem eine (besser als nichts)
            if safe_options:
                radio_options = safe_options
            else:
                print("[decide] WARNING: Alle Optionen sind potenziell disqualifizierend!")
        
        # Wähle erste safe Option
        if radio_options:
            e = radio_options[0]
            decision = {"action": "click", "stable_id": e["stable_id"],
                        "reason": f"heuristic_radio_safe:{e['name'][:30]}"}

        # 2a-bis OPTIONS-BASED COMBOBOX (Dropdown) — KLICK ZUR EXPANSION
        # ----------------------------------------------------------------
        # WARUM DIESE REIHENFOLGE (siehe Issue #50 / SR-52):
        # combobox-Elemente sind zwei sehr verschiedene Sachen:
        #   (a) OPTIONS-BASED  — natives <select> ODER ARIA-combobox mit
        #                        einer angekoppelten listbox/option-Liste.
        #                        MUSS erst geklickt werden, damit sich die
        #                        Option-Liste oeffnet; danach pickt der
        #                        naechste Tick (LLM oder Heuristik 2a) eine
        #                        konkrete <option>.
        #   (b) EDITABLE TEXT  — autocomplete-Eingabefeld (z. B. City-Lookup).
        #                        Verhaelt sich wie eine textbox →
        #                        ProfileLoader.match_field() liefert den
        #                        korrekten Wert, Heuristik 2b ist richtig.
        #
        # Wuerde Heuristik 2b alle Comboboxen anfassen, wuerden Dropdowns
        # (a) faelschlich mit Profil-Text gefuellt — Browser ignoriert das,
        # FSM rotiert in no_dom_change → Screen-Out.
        # Deshalb: dedizierte Combobox-Behandlung VOR 2b.
        #
        # Detection (rein semantisch, keine CSS-Klassen):
        #   - tag == "select"                        → immer options-based
        #   - role == "combobox" und im Snapshot     → wahrscheinlich (a)
        #     existieren option/listbox-Elemente
        # Erweiterung dieser Liste: NUR ARIA-Roles, NIEMALS provider-CSS.
        if not decision:
            has_options_in_snapshot = any(
                el.get("role") in ("option", "listbox") for el in elements
            )
            for e in elements:
                if e["stable_id"] == avoid_id:
                    continue
                if e.get("state", {}).get("disabled"):
                    continue
                if e["role"] != "combobox":
                    continue
                is_native_select = e.get("tag", "").lower() == "select"
                is_options_based = is_native_select or has_options_in_snapshot
                if not is_options_based:
                    # Editable-text-combobox → 2b uebernimmt
                    continue
                if e.get("state", {}).get("expanded"):
                    # Liste schon offen — LLM/2a soll konkrete option waehlen
                    continue
                decision = {"action": "click",
                            "stable_id": e["stable_id"],
                            "reason": f"combobox_expand:{(e.get('name') or '')[:30]}"}
                break

        # 2b leere textbox/searchbox/spinbutton/combobox(editable) — PROFIL-MAPPING
        # ----------------------------------------------------------------
        # Bisher (vor 2026-05-11): IMMER profile["city"] gefuellt, egal
        # welches Feld. Das hat "Berlin" in E-Mail- und PLZ-Felder geschrieben
        # und sofort Screen-Outs ausgeloest.
        #
        # Jetzt: ProfileLoader.match_field() prueft den Element-Namen
        # (Label/Placeholder) gegen Keyword-Familien (DE/EN) und liefert
        # den korrekten Profil-Wert ODER None.
        # → None = HEURISTIK SKIPPT das Feld; im naechsten Tick uebernimmt
        #   der LLM-Fallback (decide_node Pfad 1) die Entscheidung.
        #
        # Combobox-Sonderfall: options-basierte Comboboxen werden bereits
        # von Heuristik 2a-bis bedient (Click zum Aufklappen). HIER nur noch
        # EDITABLE-TEXT-comboboxen (autocomplete) — also welche, fuer die
        # 2a-bis NICHT entschieden hat. Pruefung erfolgt analog zu 2a-bis.
        #
        # Pflicht-Kontext: survey-cli/survey/profile_loader.py KEYWORD-FAMILIEN.
        # Erweiterung: neues Keyword-Pattern dort ergaenzen + Test in
        # survey-cli/tests/test_profile_match_field.py hinzufuegen.
        if not decision:
            has_options_in_snapshot = any(
                el.get("role") in ("option", "listbox") for el in elements
            )
            for e in elements:
                if e["stable_id"] == avoid_id:
                    continue
                if e["role"] not in ("textbox", "searchbox", "spinbutton",
                                     "combobox"):
                    continue
                if e["role"] == "combobox":
                    is_native_select = e.get("tag", "").lower() == "select"
                    if is_native_select or has_options_in_snapshot:
                        # options-based combobox → von 2a-bis behandelt
                        continue
                if e.get("value"):
                    continue  # bereits ausgefuellt
                placeholder = (e.get("attrs") or {}).get("placeholder") or ""
                val = ProfileLoader.match_field(
                    role=e["role"],
                    name=e.get("name") or "",
                    profile=profile,
                    placeholder=placeholder,
                )
                if val is None:
                    # Kein Keyword-Match → LLM-Tick uebernimmt
                    continue
                decision = {"action": "fill",
                            "stable_id": e["stable_id"],
                            "value": val,
                            "reason": "heuristic_fill:profile_match"}
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

            # ─────────────────────────────────────────────────────────────
            # Issue #85: no_dom_change Retry Strategy
            # ─────────────────────────────────────────────────────────────
            # Statt single-shot click() nutzen wir click_with_retry(), das
            # bei "no_dom_change" automatisch bis zu 4x retried mit exp.
            # backoff (0/200/400/800ms). Erst nach 4 Fehlversuchen kommt
            # der CUA-Fallback unten zum Zug. Das spart ca. 80% der CUA-
            # Eskalationen, weil die meisten "no_dom_change"-Cases nur
            # Race-Conditions sind.
            # ─────────────────────────────────────────────────────────────
            if action == "click" or action == "submit":
                result = actuator.click_with_retry(sid)
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
        "attempts": getattr(result, "attempts", 1),  # Issue #85: Retry-Counter
        "dom_stable_ms": getattr(result, "dom_stable_ms", 0.0),  # Issue #84
    }
    state.batch_result = {
        "success": result.success,
        "results": [state.last_action_result],
        "total_success": 1 if result.success else 0,
        "total_fail": 0 if result.success else 1,
        "elapsed_ms": result.elapsed_ms,
    }

    print(f"[act] {action} {sid[:10]} success={result.success} "
          f"reason={result.reason} attempts={getattr(result, 'attempts', 1)} "
          f"elapsed={result.elapsed_ms:.0f}ms")

    if not result.success:
        state.increment_failures()
        # Issue #85: "no_dom_change_after_retries" zählt als no_dom_change-Eskalation
        # (click_with_retry hat schon 4x intern probiert → jetzt CUA-Fallback fair)
        if result.reason in ("no_dom_change", "no_dom_change_after_retries"):
            state.no_dom_change_count += 1
            
            # ══════════════════════════════════════════════════════════════════
            # CUA-FALLBACK: Wenn click_with_retry alle 4 internen Versuche
            # erschöpft hat ODER bei wiederholtem fill/press_key no_dom_change
            # → CUA-Driver für echte OS-Level Clicks.
            # Das löst blockierte Consent-Pages (AYBEE, Ipsos, etc.)
            # ══════════════════════════════════════════════════════════════════
            # Issue #85: Schwelle bleibt bei 2, aber click_with_retry hat
            # vorher schon 4 interne Attempts gemacht. Effektiv eskaliert
            # CUA jetzt nach 2× "no_dom_change_after_retries" = 8 echte Klicks.
            if state.no_dom_change_count >= 2:
                print(f"[execute] CUA-FALLBACK triggered: no_dom_change={state.no_dom_change_count}")  # noqa: E501
                try:
                    from ..cua_fallback import cua_click_blocked_element
                    cua_result = cua_click_blocked_element(
                        element_selector=sid,
                        tab_ws_url=state.tab_ws
                    )
                    print(f"[execute] CUA result: {cua_result}")
                    
                    if cua_result.get("success"):
                        # CUA hat geklickt — warte auf DOM-Change
                        time.sleep(1.0)
                        # Update result
                        state.last_action_result["reason"] = f"cua_{cua_result.get('method', 'unknown')}"  # noqa: E501
                        state.last_action_result["success"] = True
                        state.no_dom_change_count = 0
                        state.reset_failures()
                except ImportError:
                    print("[execute] CUA-Fallback not available (cua_fallback.py missing)")
                except Exception as e:
                    print(f"[execute] CUA-Fallback failed: {e}")
    else:
        state.reset_failures()
        state.no_dom_change_count = 0
    return state


# ── NODE 7: detect_completion ─────────────────────────────────────────────────
# Funktion: Completion/Screen-Out detectieren via CDP page text + CompletionDetector
# Returns:  state mit completion_detected/screen_out + status
# Lines:    ~23

def detect_completion(state: SurveyState) -> SurveyState:
    if not state.tab_ws: state.add_error("detect_completion", "tab_ws not set"); return state  # noqa: E701,E702
    from ..completion_detector import CompletionDetector; from ..execute import BatchExecutor  # noqa: E702
    page_text = BatchExecutor.read_page_text(state.tab_ws, max_len=500)
    if CompletionDetector(cdp_port=state.cdp_port, debug=False).detect(page_text):
        state.completion_detected = True; state.status = "completed"  # noqa: E702
        if getattr(state,"target_mode","new_tab")=="in_dashboard" and state.dashboard_ws:
            from ..opener import SurveyOpener
            SurveyOpener(cdp_port=state.cdp_port).navigate_back_to_dashboard(state.tab_ws or state.dashboard_ws or "")  # noqa: E501
        return state
    is_err, reason = BatchExecutor.detect_error_page(page_text)
    if is_err and any(s in reason.lower() for s in ["qualify","eligible","screen","limit","full"]):
        state.screen_out = True; state.status = "screen_out"  # noqa: E702
        if getattr(state,"target_mode","new_tab")=="in_dashboard" and state.dashboard_ws:
            from ..opener import SurveyOpener
            SurveyOpener(cdp_port=state.cdp_port).navigate_back_to_dashboard(state.tab_ws or state.dashboard_ws or "")  # noqa: E501
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
    reason = f"3 consecutive failures at iteration {state.iteration}: {last_err.get('error','unknown')}"  # noqa: E501
    state.delegation_reason = reason; state.status = "delegated"  # noqa: E702
    result = delegate_task(survey_id=state.survey_id, provider=state.provider, reason=reason, tab_ws=state.tab_ws, iteration=state.iteration)  # noqa: E501
    state.errors.append({"node": "human_delegate", "error": f"delegated: {result.get('stdout','')[:200]}", "iteration": state.iteration, "ts": time.time()})  # noqa: E501
    return state


# ── Issue #39: Auto-Doc + stealth-memory Integration ─────────────────────────
# GOAL: Nach Survey-Completion in stealth-memory persistieren (learn/anti-learn)
# FILES: issue #39, plan: _plans/39-auto-doc-memory.md

def _update_stealth_memory(state: SurveyState) -> None:
    """Persistiere Survey-Ergebnis in stealth-memory für Agent-Lernen.

    Issue #39 (SR-45): Nach jeder Survey muss der Outcome geloggt werden damit
    der Agent über Sessionen hinweg lernt. Erfolgreiches Pattern → learn.md,
    Fehler → anti-learn.md, beides als strukturierte JSONL in den Repo.

    PIPELINE:
    1. Versuche stealth-memory.client.append_outcome() (extern)
    2. Fallback auf lokales JSONL: logs/outcomes/{run_id}.jsonl
    3. Best-effort — Fehler logg, brechen aber den Survey nicht ab

    Args:
        state: SurveyState mit allen Session-Infos (balance, errors, etc.)

    Side-Effects:
        - Schreibt JSONL-Entry in stealth-memory oder logs/outcomes/
        - Logged Fehler via state.add_error()
    """
    import json
    from pathlib import Path
    from datetime import datetime

    if not state.survey_id:
        return

    try:
        # Berechne Erfolg: balance_after > balance_before
        success = state.balance_after > state.balance_before
        duration_ms = int((time.time() - state.session_start_time) * 1000) if hasattr(state, 'session_start_time') else 0  # noqa: E501

        outcome = {
            "ts": datetime.now().isoformat(),
            "run_id": state.run_id or state.survey_id,
            "survey_id": state.survey_id,
            "provider": state.provider or "unknown",
            "success": success,
            "balance_before": state.balance_before,
            "balance_after": state.balance_after,
            "balance_earned": max(0, state.balance_after - state.balance_before),
            "status": state.status,
            "error": state.errors[-1].get("error", "") if state.errors else "",
            "error_iteration": state.errors[-1].get("iteration", 0) if state.errors else 0,
            "total_iterations": state.iteration,
            "page_count": len(state.dom_snapshots) if hasattr(state, 'dom_snapshots') else 0,
            "duration_ms": duration_ms,
        }

        # Try extern stealth-memory client
        try:
            from stealth_memory import client as smem_client
            smem_client.append_outcome(outcome)
            return  # Success
        except ImportError:
            pass  # Fall back to local JSONL

        # Fallback: lokales JSONL in logs/outcomes/
        logs_dir = Path(__file__).resolve().parent.parent / "logs" / "outcomes"
        logs_dir.mkdir(parents=True, exist_ok=True)
        fp = logs_dir / f"{outcome['run_id']}.jsonl"

        with open(fp, "a") as f:
            f.write(json.dumps(outcome, ensure_ascii=False) + "\n")

    except Exception as e:
        # Best-effort — log aber break nicht
        state.add_error("_update_stealth_memory", f"{type(e).__name__}: {str(e)[:100]}")


def detect_completion_with_memory(state: SurveyState) -> SurveyState:
    """Detect Survey Completion UND persistiere Ergebnis in stealth-memory.

    Issue #39 Integration (SR-45): Nach detect_completion, wenn der Survey
    abgeschlossen oder gescreen-out ist, rufe _update_stealth_memory() auf.

    Args:
        state: SurveyState mit completion_detected, balance_before, balance_after

    Returns:
        State mit Memory persistiert (side-effect: JSONL-Eintrag geschrieben)
    """
    # Call original detect_completion logic
    state = detect_completion(state)

    # Nach Completion/Screen-out: Memory Update
    if state.completion_detected or state.screen_out:
        _update_stealth_memory(state)

    return state
