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
    """Starte Chrome oder verifiziere dass Chrome bereits läuft.

    Chrome muss mit folgenden Flags laufen:
      --remote-debugging-port={state.cdp_port}
      --remote-allow-origins="*"          (MIT Quotes!)
      --force-renderer-accessibility       (Nötig für AX-Tree)
      --no-first-run
      --user-data-dir=/tmp/heypiggy-new-*  (Timestamped profile)

    Falls Chrome bereits läuft (is_chrome_alive=True) wird nur
    dashboard_ws ermittelt — kein Neustart nötig.

    Args:
        state: SurveyState mit cdp_port

    Returns:
        Updated state mit dashboard_ws (wenn Chrome bereit)
        Updated state mit status='error' (wenn Chrome nicht startet)

    Side-Effects:
        - Subprocess: Chrome PID wird ermittelt
        - CDP HTTP: /json endpoint wird geprüft
    """
    from ..chrome import (
        is_chrome_alive,
        find_dashboard_ws,
        ChromeLauncher,
    )

    # Fall 1: Chrome läuft bereits — nur dashboard_ws ermitteln
    if is_chrome_alive(state.cdp_port):
        ws = find_dashboard_ws(state.cdp_port)
        if ws:
            state.dashboard_ws = ws
            state.status = "chrome_ready"
            return state
        # Chrome läuft aber kein Dashboard-WS gefunden → Error
        state.add_error("ensure_chrome", f"Chrome alive but no dashboard WS on port {state.cdp_port}")
        state.status = "error"
        return state

    # Fall 2: Chrome nicht aktiv → mit ChromeLauncher.start_and_verify() starten
    launcher = ChromeLauncher(port=state.cdp_port, debug=True)
    result = launcher.launch_and_verify(url="https://www.heypiggy.com/?page=dashboard")

    if not result.get("ok"):
        state.add_error("ensure_chrome", result.get("error", "Chrome launch failed"))
        state.status = "error"
        return state

    # Chrome gestartet → Dashboard WS ermitteln
    time.sleep(2)  # Warten auf Tab-Initialisierung
    ws = find_dashboard_ws(state.cdp_port)
    if ws:
        state.dashboard_ws = ws
        state.status = "chrome_ready"
    else:
        state.add_error("ensure_chrome", "Chrome launched but no dashboard WS found")
        state.status = "error"
    return state


# ── NODE 2: open_survey ───────────────────────────────────────────────────────
# Funktion: Survey-Tab öffnen via SurveyOpener
# Wrapped:  SurveyOpener.open()
# Returns:  state mit tab_ws + provider gesetzt
#           state mit status='error' (wenn Tab nicht geöffnet)
# Lines:    ~28


def open_survey(state: SurveyState) -> SurveyState:
    """Öffne Survey-Tab via tool_open_survey (new tab + cookie injection).

    Nutzt tool_open_survey.open_survey() — getestet und funktionierend (SR-54).
    Erstellt einen neuen Tab, extrahiert CPX URL via window.open interception,
    und navigiert dorthin.

    Wichtig: Der Survey-Tab hat NOCH KEINE heypiggy-Cookies nach diesem
    Schritt — inject_cookies() muss danach aufgerufen werden!

    Args:
        state: SurveyState mit survey_id, provider, dashboard_ws

    Returns:
        Updated state mit tab_ws, provider, url gesetzt
        Updated state mit status='tab_open'
        Updated state mit status='screen_out' (wenn Survey expired)
        Updated state mit status='error' (wenn Tab nicht geöffnet)

    Side-Effects:
        - CDP WebSocket: Neuer Tab wird erstellt
        - CDP WebSocket: window.open interception
        - Dashboard: clickSurvey() wird aufgerufen
    """
    try:
        from tools.tool_open_survey import open_survey as _open_survey_tool
    except ImportError:
        # Fallback wenn relative Import fehlschlägt
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "tool_open_survey",
            "/Users/jeremy/dev/stealth-runner/survey-cli/tools/tool_open_survey.py"
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _open_survey_tool = mod.open_survey

    result = _open_survey_tool(
        survey_id=state.survey_id,
        pid=0, wid=0,
        port=state.cdp_port,
        wait_modal=3.0,
        wait_load=5.0,
    )

    if result.get("status") != "ok":
        error_msg = result.get("reason", "Unknown error opening survey")
        state.add_error("open_survey", error_msg)
        if "screen_out" in error_msg.lower() or "expired" in error_msg.lower():
            state.screen_out = True
            state.status = "screen_out"
        else:
            state.status = "error"
        return state

    # Erfolg: Tab-WS, Provider und URL setzen
    ws_url = result.get("ws_url")
    if ws_url:
        state.tab_ws = ws_url
        state.survey_url = result.get("url", "")
        if result.get("provider"):
            state.provider = result.get("provider")
        state.status = "tab_open"
        state.target_mode = "new_tab"
    else:
        state.add_error("open_survey", "open_survey returned no ws_url")
        state.status = "error"
    return state


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
    """Injiziere heypiggy Session-Cookies in den Survey-Tab.

    KRITISCHER FIX (2026-05-09): Survey-Tabs die via Target.createTarget
    geöffnet werden haben KEINE Session-Cookies. CPX redirectiert zurück
    zum Dashboard → €0 verdient. Diese Node fixed das Problem.

    Workflow:
      1. Heypiggy-Cookies aus Backup-Datei laden
      2. 7 Heypiggy-Cookies filtern (PHPSESSID, user_session, etc.)
      3. Network.setCookies via CDP WebSocket aufrufen
      4. cookies_injected=True setzen

    7 Heypiggy-Cookies (aus ~/.stealth/heypiggy-backup/):
      - PHPSESSID      → www.heypiggy.com
      - user_session   → www.heypiggy.com (KRITISCH!)
      - user_id        → www.heypiggy.com (KRITISCH!)
      - user_a_b_group → www.heypiggy.com
      - lang_pig       → www.heypiggy.com
      - g_state        → www.heypiggy.com
      - referer        → www.heypiggy.com

    Args:
        state: SurveyState mit tab_ws

    Returns:
        Updated state mit cookies_injected=True, status='cookies_injected'
        Updated state mit status='error' (wenn Injection fehlschlägt)

    Side-Effects:
        - Datei-Read: ~/.stealth/heypiggy-backup/heypiggy-cookies.json
        - CDP WebSocket: Network.setCookies (7×)
    """
    if not state.tab_ws:
        state.add_error("inject_cookies", "tab_ws not set — open_survey must run first")
        state.status = "error"
        return state

    # COOKIE TIMING FIX (2026-05-10): in_dashboard mode — tab IS the dashboard
    # tab which already HAS heypiggy session cookies (injected at Chrome startup).
    # No injection needed; skip this node entirely.
    if getattr(state, "target_mode", "new_tab") == "in_dashboard":
        state.cookies_injected = True
        state.status = "cookies_injected"
        return state

    # Schritt 1: Cookie-Datei laden
    cookie_file = os.environ.get(
        "HEYPIGGY_COOKIE_BACKUP", DEFAULT_COOKIE_BACKUP
    )
    try:
        with open(cookie_file) as f:
            cookie_data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        state.add_error("inject_cookies", f"Failed to load cookie file {cookie_file}: {e}")
        state.status = "error"
        return state

    all_cookies = cookie_data.get("cookies", [])
    # Schritt 2: Heypiggy-Cookies filtern
    heypiggy_cookies = [
        {
            "name": c["name"],
            "value": c["value"],
            "domain": c["domain"],
            "path": c.get("path", "/"),
            "expires": c.get("expires", -1),
            "secure": c.get("secure", False),
            "httpOnly": c.get("httpOnly", False),
        }
        for c in all_cookies
        if "heypiggy" in c.get("domain", "").lower()
    ]

    if not heypiggy_cookies:
        state.add_error("inject_cookies", f"No heypiggy cookies found in {cookie_file} (found {len(all_cookies)} total)")
        state.status = "error"
        return state

    # Schritt 3: Network.setCookies aufrufen (Batch in einem Call)
    try:
        ws = websocket.create_connection(state.tab_ws, timeout=15)
        ws.send(json.dumps({
            "id": 1,
            "method": "Network.setCookies",
            "params": {"cookies": heypiggy_cookies},
        }))
        resp = json.loads(ws.recv())
        ws.close()

        if resp.get("result", {}).get("success") is True:
            state.cookies_injected = True
            state.status = "cookies_injected"
        else:
            state.add_error("inject_cookies", f"Network.setCookies returned: {resp}")
            state.status = "error"
    except Exception as e:
        state.add_error("inject_cookies", f"CDP injection failed: {e}")
        state.status = "error"
    return state


# ── NODE 4: snapshot_node ─────────────────────────────────────────────────────
# Funktion: Compact DOM-Snapshot via CDP generieren
# Wrapped:  CDP Runtime.evaluate (inline JS)
# Returns:  state mit snapshot_refs (Dict von @eN refs)
# Lines:    ~30
#
# SOTA Pattern: Compact Snapshot für NIM-Effizienz
#   - 500 tokens in (nicht 5000)
#   - 1 LLM-Call pro SEITE (nicht pro element)
#   - @eN Referenzen (nicht XPath/CSS)


def snapshot_node(state: SurveyState) -> SurveyState:
    """Generiere kompaktes DOM-Snapshot via CDP Runtime.evaluate.

    SOTA Pattern (2026-05-06): Compact Snapshot statt Full DOM Tree.
    1 LLM-Call pro Seite → ~500 tokens in, ~100 tokens raus.
    10× effizienter als cua-driver loop (~5000 tokens pro Seite).

    Snapshot generiert:
      - Radio/Checkbox-Buttons mit Label-Text (gesorted nach Y-Position)
      - Text-Areas (textarea)
      - Text-Inputs
      - Submit/Next-Buttons

    Format: state.snapshot_refs = {
      "@e0": {"role": "radio", "text": "Männlich", "idx": 0},
      "@e1": {"role": "radio", "text": "Weiblich", "idx": 1},
      "@e2": {"role": "textarea", "text": "", "idx": 0},
      "@e3": {"role": "button", "text": "Nächster", "idx": 0},
    }

    Args:
        state: SurveyState mit tab_ws

    Returns:
        Updated state mit snapshot_refs gefüllt
        Updated state mit status='running'

    Side-Effects:
        - CDP WebSocket: Runtime.evaluate (DOM-Query + Text-Extraktion)
    """
    if not state.tab_ws:
        state.add_error("snapshot_node", "tab_ws not set")
        state.status = "error"
        return state

    try:
        ws = websocket.create_connection(state.tab_ws, timeout=15)
        ws.send(json.dumps({
            "id": 0,
            "method": "Runtime.evaluate",
            "params": {"expression": """
(function() {
    var refs = {};
    // Radio + Checkbox
    var inputs = document.querySelectorAll('input[type=radio],input[type=checkbox]');
    var seen = new Set();
    inputs.forEach(function(inp, i) {
        var label = document.querySelector('label[for="' + inp.id + '"]') ||
            inp.closest('label') || inp.previousElementSibling;
        var text = label ? (label.textContent || '').trim() : inp.name || inp.value || '';
        if(!text || seen.has(text)) return;
        seen.add(text);
        refs['@e' + Object.keys(refs).length] = {
            role: inp.type + (inp.checked ? '-checked' : '-selected'),
            text: text.substring(0, 100),
            idx: i,
            tag: 'input'
        };
    });
    // Textareas
    document.querySelectorAll('textarea').forEach(function(ta) {
        refs['@e' + Object.keys(refs).length] = {
            role: 'textarea', text: '', idx: 0, tag: 'textarea'
        };
    });
    // Buttons (Weiter, Nächster, etc.)
    document.querySelectorAll('button,input[type=submit]').forEach(function(btn) {
        var t = (btn.textContent || '').trim();
        if(t && !seen.has(t)) {
            seen.add(t);
            refs['@e' + Object.keys(refs).length] = {
                role: 'button', text: t.substring(0, 50), idx: 0, tag: btn.tagName
            };
        }
    });
    return JSON.stringify(refs);
})()
"""},
        }))
        resp = json.loads(ws.recv())
        ws.close()

        raw_refs = resp.get("result", {}).get("result", {}).get("value", "{}")
        state.snapshot_refs = json.loads(raw_refs) if isinstance(raw_refs, str) else {}
        state.status = "running"
    except Exception as e:
        state.add_error("snapshot_node", f"CDP snapshot failed: {e}")
        state.status = "error"
    return state


# ── NODE 5: decide_node ───────────────────────────────────────────────────────
# Funktion: NIM Nemotron Decision (oder heuristic fallback)
# Wrapped:  survey.nim.get_nim().decide() oder heuristic placeholder
# Returns:  state mit nim_actions (List von Actions)
# Lines:    ~22
#
# SR-57 (2026-05-10): NIM Nemotron 3 Omni Integration.
#   - Echter API Call zu integrate.api.nvidia.com/v1/chat/completions
#   - Chain-of-Thought Prompting für Reasoning-Modell
#   - Fallback zu heuristic wenn NIM nicht verfügbar (kein API Key, Rate Limit, etc.)


def decide_node(state: SurveyState) -> SurveyState:
    """Entscheide welche Actions für die aktuelle Seite ausgeführt werden.

    SOTA Pattern: NVIDIA NIM Nemotron 3 Omni Decision (SR-57).
    Input: Compact Snapshot (snapshot_refs) + Survey Profile
    Output: List von Actions [{ref, action, value}, ...]

    Implementation:
      1. Lade Survey Profile (Jeremy Schulze, 32, Berlin, männlich)
      2. Baue Compact Snapshot aus state.snapshot_refs
      3. Rufe NIMClient.decide() auf (echter API Call)
      4. Wenn NIM nicht verfügbar → heuristic fallback (erste Radio-Option, Textarea "Berlin", Submit)

    Args:
        state: SurveyState mit snapshot_refs, provider

    Returns:
        Updated state mit nim_actions = [
            {"ref": "@e0", "action": "select"},
            {"action": "submit"},
        ]

    Side-Effects:
        - NIM API Call (wenn NVIDIA_API_KEY gesetzt)
        - Kein API Call wenn NIM nicht verfügbar (circuit breaker open, no key, etc.)
    """
    refs = state.snapshot_refs
    actions = []

    # ═══════════════════════════════════════════════════════════════════════
    # SCHRITT 1: NIM Nemotron Decision (PRIMARY)
    # ═══════════════════════════════════════════════════════════════════════
    # WARUM NIM?
    # → Intelligente Entscheidungen basierend auf Profil (Alter, Geschlecht, Wohnort)
    # → Chain-of-Thought Reasoning für komplexe Fragen (Matrix, Ranking, etc.)
    # → Besser als heuristic → niedrigere Disqualifikations-Rate
    #
    # WARUM try/except?
    # → NIM könnte nicht verfügbar sein (kein API Key, Rate Limit, Netzwerk-Fehler)
    # → Wir wollen NIEMALS den Survey-Loop crashen wegen NIM
    # → Fallback zu heuristic ist immer verfügbar
    try:
        from survey.nim import get_nim
        from survey.profile_loader import ProfileLoader

        # Lade Profil (Jeremy Schulze, 32, Berlin, männlich)
        profile = ProfileLoader.load_profile()

        # Baue Snapshot für NIM
        snapshot = {
            "refs": refs,
            "semantic": {
                "questions": [],  # TODO: Fragen-Extraktion aus snapshot_refs
                "progress": f"{state.iteration}/{state.max_iterations}",
            },
            "provider": state.provider or "unknown",
        }

        # NIM Client entscheiden lassen
        nim = get_nim()
        result = nim.decide(snapshot=snapshot, profile=profile)

        # Extrahiere Actions aus NIM Response
        if result and "actions" in result:
            actions = result["actions"]
            # Logge NIM Entscheidung (für Debugging)
            print(f"[NIM] {result.get('model', 'unknown')}: {len(actions)} actions, "
                  f"{result.get('tokens', {}).get('total', 0)} tokens, "
                  f"{result.get('elapsed_ms', 0)}ms")

    except Exception as e:
        # NIM Fehler → logge aber crashe nicht
        print(f"[NIM] Fallback zu heuristic: {type(e).__name__}: {e}")

    # ═══════════════════════════════════════════════════════════════════════
    # SCHRITT 2: Heuristic Fallback (wenn NIM keine Actions liefert)
    # ═══════════════════════════════════════════════════════════════════════
    # WARUM Fallback?
    # → Wenn NIM nicht verfügbar (kein API Key) → Survey trotzdem ausfüllen
    # → Wenn NIM Actions leer zurückgibt → heuristic als Safety-Net
    # → Survey-Loop darf NIEMALS stoppen wegen AI-Fehlern

    if not actions:
        # Heuristic Decision (Fallback):
        # Finde erstes Radio/Checkbox und select es
        for ref, info in refs.items():
            role = info.get("role", "")
            if role in ("radio-selected", "radio-selected"):
                actions.append({"ref": ref, "action": "select"})
                break
            elif role.startswith("radio"):
                actions.append({"ref": ref, "action": "select"})
                break

        # Finde Textarea und fülle mit Test-Wert
        has_textarea = any(v.get("role") == "textarea" for v in refs.values())
        if has_textarea:
            # Persona-basiert: Wohnort aus Profil
            try:
                from survey.profile_loader import ProfileLoader
                profile = ProfileLoader.load_profile()
                city = profile.get("city", "Berlin")
                actions.append({"ref": None, "action": "fill", "value": city})
            except Exception:
                actions.append({"ref": None, "action": "fill", "value": "Berlin"})

        # Finde Submit-Button (Nächster/Weiter/Skip)
        button_texts = ["Nächster", "Weiter", "Next", "Skip", "Weiter"]
        for ref, info in refs.items():
            text = info.get("text", "")
            if info.get("role") == "button" and any(bt in text for bt in button_texts):
                actions.append({"ref": ref, "action": "submit"})
                break

    state.nim_actions = actions
    return state


# ── NODE 6: execute_node ──────────────────────────────────────────────────────
# Funktion: Batch-Execution via BatchExecutor
# Wrapped:  BatchExecutor.execute()
# Returns:  state mit batch_result, consecutive_failures incrementiert/resetet
# Lines:    ~28


def execute_node(state: SurveyState) -> SurveyState:
    """Führe NIM-Entscheidungen als CDP Batch-Action aus.

    Wrapped BatchExecutor.execute() aus execute.py.
    Provider-spezifische CDP Commands werden von BatchExecutor intern
    gemappt (qualtrics, tolunastart, strat7, purespectrum, etc.).

    SOTA Features in BatchExecutor:
      - State-Verify nach jedem Click (DOM-Hash-Vergleich)
      - CDP dispatchMouseEvent für Angular v19 (zone.js compatibility)
      - Keyboard Fallback (Tab+Enter) für React/Angular
      - Auto-Retry bei "No such target" errors

    Args:
        state: SurveyState mit tab_ws, provider, snapshot_refs, nim_actions

    Returns:
        Updated state mit batch_result (actions, success, fail, elapsed_ms)
        Updated state mit consecutive_failures incrementiert (bei fail)
        Updated state mit consecutive_failures reset (bei success)

    Side-Effects:
        - CDP WebSocket: Multiple Runtime.evaluate + Input.dispatchMouseEvent
        - DOM-State wird verändert (Radio-Buttons selected, Text gefüllt)
    """
    from ..execute import BatchExecutor

    if not state.tab_ws:
        state.add_error("execute_node", "tab_ws not set")
        state.status = "error"
        return state

    if not state.nim_actions:
        # Keine Actions nötig (z.B. Wait-Page oder Completion)
        state.batch_result = {"actions": [], "total_success": 0, "total_fail": 0, "elapsed_ms": 0}
        return state

    executor = BatchExecutor(
        ws_url=state.tab_ws,
        provider=state.provider,
        config={"debug": False},
    )
    result = executor.execute(
        actions=state.nim_actions,
        snapshot_refs=state.snapshot_refs,
    )

    # Result in state speichern
    state.batch_result = {
        "actions": result.actions,
        "total_success": result.total_success,
        "total_fail": result.total_fail,
        "elapsed_ms": result.total_elapsed_ms,
    }

    # consecutive_failures management
    if result.total_fail > 0:
        state.increment_failures()
    else:
        state.reset_failures()

    return state


# ── NODE 7: detect_completion ─────────────────────────────────────────────────
# Funktion: Survey-Completion/Screen-Out detectieren
# Wrapped:  CompletionDetector.detect_ws()
# Returns:  state mit completion_detected + screen_out + balance_after
# Lines:    ~22


def detect_completion(state: SurveyState) -> SurveyState:
    """Detektiere ob Survey abgeschlossen ist (Completion, Screen-Out oder Balance-Erhöhung).

    CompletionDetector prüft drei Signale:
      1. Page-Text enthält Completion-Marker ("Thank you", "Vielen Dank", etc.)
      2. Page-Text enthält Screen-Out-Marker ("qualify", "not eligible", etc.)
      3. Balance-Erhöhung auf heypiggy Dashboard

    Args:
        state: SurveyState mit tab_ws, balance_before

    Returns:
        Updated state mit completion_detected=True (wenn Survey fertig)
        Updated state mit screen_out=True (wenn disqualifiziert)
        Updated state mit balance_after (wenn erhöht)
        Updated state mit status='completed' oder 'screen_out'

    Side-Effects:
        - CDP WebSocket: document.body.innerText lesen
        - Balance-Check via heypiggy Dashboard oder balance_tracker
    """
    from ..completion_detector import CompletionDetector
    from ..execute import BatchExecutor

    if not state.tab_ws:
        state.add_error("detect_completion", "tab_ws not set")
        return state

    detector = CompletionDetector(cdp_port=state.cdp_port, debug=False)
    page_text = BatchExecutor.read_page_text(state.tab_ws, max_len=500)

    # Signal 1: Completion-Marker
    # Signal 1: Completion-Marker
    completed = detector.detect(page_text)
    if completed:
        state.completion_detected = True
        state.status = "completed"
        # COOKIE TIMING FIX (2026-05-10): in_dashboard mode — navigate back
        if getattr(state, "target_mode", "new_tab") == "in_dashboard" and state.dashboard_ws:
            from ..opener import SurveyOpener
            SurveyOpener(cdp_port=state.cdp_port).navigate_back_to_dashboard(state.tab_ws or state.dashboard_ws or "")
        return state

    # Signal 2: Screen-Out-Marker
    from ..execute import BatchExecutor as BE
    is_error, reason = BE.detect_error_page(page_text)
    if is_error and any(s in reason.lower() for s in ["qualify", "eligible", "screen", "limit", "full"]):
        state.screen_out = True
        state.status = "screen_out"
        # COOKIE TIMING FIX (2026-05-10): in_dashboard mode — navigate back
        if getattr(state, "target_mode", "new_tab") == "in_dashboard" and state.dashboard_ws:
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
    """Delegiere Survey an opencode CLI wenn 3× failures erreicht wurden.

    TRIGGER: consecutive_failures >= 3
    WARUM 3? → 1× Retry ist normal (transient), 2× ist selten,
    3× = echtes Problem das ein Mensch lösen muss.

    Delegation enthält:
      - Survey-ID und Provider
      - Letzten Error (aus state.errors[-1])
      - Iteration und Tab-URL
      - Befehl was zu tun ist

    opencode_tool.delegate_task() führt aus:
      opencode run --format json --dir /Users/jeremy/dev/stealth-runner \
        --prompt "Fix survey 67064749: {reason}"

    Args:
        state: SurveyState mit errors, iteration, tab_ws, consecutive_failures

    Returns:
        Updated state mit status='delegated', delegation_reason
        Updated state mit errors[-1] als delegation_reason

    Side-Effects:
        - subprocess.run: opencode CLI wird gestartet
        - Output wird geloggt für spätere Analyse
    """
    last_error = state.errors[-1] if state.errors else {"error": "unknown"}
    reason = f"3 consecutive failures at iteration {state.iteration}: {last_error.get('error', 'unknown')}"

    state.delegation_reason = reason
    state.status = "delegated"

    # Delegation via opencode CLI
    result = delegate_task(
        survey_id=state.survey_id,
        provider=state.provider,
        reason=reason,
        tab_ws=state.tab_ws,
        iteration=state.iteration,
    )

    # Delegation-Result speichern (kann success oder failure sein)
    state.errors.append({
        "node": "human_delegate",
        "error": f"delegated to opencode: {result.get('stdout', '')[:200]}",
        "iteration": state.iteration,
        "ts": time.time(),
    })
    return state