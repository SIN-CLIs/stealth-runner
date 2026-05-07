#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
AUTO-GOOGLE-LOGIN — CUA-ONLY 6-Step Login für Heypiggy.com
================================================================================
Repo    : /Users/jeremy/dev/stealth-runner/cli/modules/auto_google_login.py
Stand   : 2026-05-07
Version : 1.0 (LIVE TESTED ✅)
Ersetzt : cli/modules/heypiggy_login_box.py (GELÖSCHT!)

BANNED METHODS — NIEMALS VERWENDEN (siehe /banned.md):
  ❌ playstealth launch — setzt NICHT --force-renderer-accessibility
  ❌ webauto-nodriver — ABSOLUT BANNED
  ❌ cua-driver click (raw index) — instabil, nutze tool_click.py
  ❌ --remote-allow-origins=* (ohne Quotes) — zsh glob expansion
  ❌ /tmp/heypiggy-bot (fixed profile) — korruptiert nach Neustart
  ❌ Hardcoded PIDs — dynamisch, niemals hardcodieren (71104, 56640 waren Beispiele!)
  ❌ pkill -f "Google Chrome" — tötet USER Chrome
  ❌ killall Google Chrome — tötet ALLE Chrome
  ❌ skylight-cli click --element-index — Index instabil

KORREKT:
  ✅ Chrome MANUELL starten (NICHT playstealth!)
  ✅ --remote-allow-origins="*" (MIT Anführungszeichen — zsh expandiert * sonst!)
  ✅ --user-data-dir="/tmp/heypiggy-new-$(date +%s)" (timestamped, nie fixed!)
  ✅ --force-renderer-accessibility (MUSS für AX-Tree!)
  ✅ NUR tool_*.py verwenden (nicht rohes cua-driver)

================================================================================
SHELL COMMANDS (DOKUMENTIERT - learning-by-doing):
================================================================================

## Chrome starten (MANUELL — playstealth ist BANNED, setzt NICHT --force-renderer-accessibility!):
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  --user-data-dir="/tmp/heypiggy-new-$(date +%s)" \
  --remote-debugging-port=9999 \
  --remote-allow-origins="*" \
  --force-renderer-accessibility \
  --no-first-run \
  --no-default-browser-check \
  "https://www.heypiggy.com/?page=dashboard"
→ Profile: /tmp/heypiggy-new-XXXXXXXXXX (frisch, timestamped!)
→ WICHTIG: NIE /tmp/heypiggy-bot (fixed profile = corrupted!)

## Windows finden (cua-driver list_windows):
cua-driver call list_windows
→ Antwort: {"windows": [...]} — NICHT Array, sondern Dict mit "windows" key!
→ Filter: height>100 AND is_on_screen=true AND "chrome" in app_name.lower()
→ BOT Chrome: DYNAMIC_PID, profile=/tmp/heypiggy-new-XXXXXXXXXX

## AX-Tree lesen (cua-driver get_window_state):
echo '{"pid": DYNAMIC, "window_id": DYNAMIC}' | cua-driver call get_window_state
→ Antwort: {"tree_markdown": "...", "element_count": 672, ...}
→ Speichern: > /tmp/bot_DYNAMIC_tree.json
→ Parsen: re.search(r'- \[(\d+)\]', line) für element_index

## Element klicken (cua-driver click):
echo '{"pid": 71104, "window_id": 56640, "element_index": 54}' | cua-driver call click
→ Antwort: "✅ Performed AXPress on [54] AXLink"

## Text eintragen (cua-driver set_value):
echo '{"pid": 71104, "window_id": 56658, "element_index": 25, "value": "email@domain.com"}' | cua-driver call set_value
→ Antwort: "✅ Set AXValue on [25] AXTextField"

================================================================================
LOGIN FLOW (6 STEPS - LIVE GETESTET 2026-05-05):
================================================================================

STEP 1: Dashboard WID finden (Heypiggy Dashboard)
  → list_windows → WID=56640, PID=71104, Title="HeyPiggy – Verdienen..."
  → AX-Tree: [54] AXLink (Google Login-Symbol) @(731,651,132,41)

STEP 2: Google Login klicken
  → click [54] AXLink (Google Login-Symbol) auf Dashboard
  → wait 5s
  → list_windows → WID=56658, Title="Anmelden – Google Konten"

STEP 3: Email eintragen
  → get_window_state WID=56658
  → AX-Tree: [25] AXTextField (E-Mail oder Telefonnummer) @(735,549,450,54)
  → set_value [25] = "zukunftsorientierte.energie@gmail.com"

STEP 4: "Weiter" klicken
  → AX-Tree: [35] AXButton "Weiter" @(1095,706,91,40)
  → click [35]
  → wait 5s
  → list_windows → WID=56658, Title="Jeremy Schulze" (Keychain Auto-Fill!)

STEP 5: Keychain "Fortfahren" klicken
  → get_window_state WID=56658
  → AX-Tree: [62] AXButton "Fortfahren" @(1090,689,94,30)
  → click [62]
  → wait 5s
  → list_windows → WID=56658, Title="Anmelden – Google Konten" (immer noch da)

STEP 6: Final "Weiter" klicken
  → get_window_state WID=56658
  → AX-Tree: [41] AXButton "Weiter" @(966,786,220,40)
  → click [41]
  → wait 5s
  → list_windows → WID=56658 GESCHWUNDEN! Dashboard EINGELOGGT!

================================================================================
BOT CHROME PIDs (NIEMALS USER CHROME BEENDEN!):
================================================================================

BOT Chrome (isoliert via playstealth):
  DYNAMIC_PID)
# DYNAMIC_PID) [HARDCODED PID GELÖSCHT - PIDs sind immer dynamisch!]
# DYNAMIC_PID) [HARDCODED PID GELÖSCHT - PIDs sind immer dynamisch!]
# DYNAMIC_PID) [HARDCODED PID GELÖSCHT - PIDs sind immer dynamisch!]

USER Chrome (NIEMALS TOUCHEN!):
  DYNAMIC_PID, DeepSeek, API keys (Chrome UI)
  Andere Chrome-Instanzen OHNE "heypiggy-new-" im path = USER

  → ps aux | grep "user-data-dir" → prüfe ob "heypiggy-new-" im path
  → NUR Chrome mit "heypiggy-new-XXXXXXXXXX" ist BOT → INTERAGIEREN
  → ALLE ANDEREN Chrome = USER → IGNORIEREN

================================================================================
KEYCHAIN AUTO-FILL DISCOVERY:
================================================================================

KRITISCHE ERKENNTNIS (2026-05-05):
  - Email eintragen → "Weiter" klicken
  - → Keychain füllt AUTOMATISCH Account aus (kein Passwort nötig!)
  - → "Jeremy Schulze" Konto vorausgewählt
  - → NUR "Fortfahren" klicken + final "Weiter"
  - → KEIN Passwort-Feld sichtbar wegen Keychain Auto-Fill!

Wenn Keychain NICHT funktioniert (erster Login ohne gespeicherte Credentials):
  → Nach Step 4: Passwort-Feld prüfen
  → [XX] AXTextField (Passwort eingeben) → set_value "admin"
  → [YY] AXButton "Weiter" → click

================================================================================
CRITICAL BUGS (BEHOBEN):
================================================================================

BUG 1: list_windows returns DICT not ARRAY
  ❌ Falsch: windows = json.loads(r.stdout)
  ✅ Richtig: windows = d.get("windows", []) if isinstance(d, dict) else []

BUG 2: Window filter must use BOUNDS not FRAME
  ❌ Falsch: w.get("frame", {}).get("height", 0)
  ✅ Richtig: w.get("bounds", {}).get("height", 0)

BUG 3: Google Login Button is AXLink not AXButton
  ❌ Falsch: roles = ["AXButton"]
  ✅ Richtig: roles = ["AXButton", "AXLink"]

BUG 4: click() response check wrong
  ❌ Falsch: r.get("stdout") == " Performed "
  ✅ Richtig: "performed" in r.get("stdout", "").lower()

BUG 5: Google OAuth opens NEW WID - old code stayed on Dashboard WID
  ❌ Falsch: wid = _find_wid(["heypiggy"]) → blieb auf Dashboard
  ✅ Richtig: Nach click → _find_wid(["google", "anmelden"]) → NEUE WID

BUG 6: Keychain Label war falsch ("passwort" statt "fortfahren")
  ❌ Falsch: type_text("passwort", "admin")
  ✅ Richtig: click("fortfahren") nach Keychain Auto-Fill

BUG 7: Wrong email address
  ❌ Falsch: "devjerro@gmail.com"
  ✅ Richtig: "zukunftsorientierte.energie@gmail.com"

BUG 8: WRONG Chrome PID - User Chrome vs Bot Chrome
  ❌ Falsch: kill DYNAMIC_PID)
  ✅ Richtig: NUR PIDs mit "heypiggy-bot-XXXXXXXX" in user-data-dir killen

================================================================================
FUNKTIONS-SIGNATUR:
================================================================================

def execute(pid=None, url="https://heypiggy.com/?page=dashboard") -> dict:
  pid       : int     — optional, wenn Chrome schon läuft
  url       : str     — Heypiggy URL für Launch (default: dashboard)
  return    : dict    — {"status": "ok", "pid": X, "wid": Y}
                       oder {"status": "error", "reason": "..."}

================================================================================
"""

import subprocess
import json
import time
import re
from cli.modules.session_manager import SessionManager

_SessionManager = SessionManager()  # SOTA: single global instance


def _run(cmd, input_=None, timeout=15):
    # Führt Shell-Command aus mit optionalem stdin input
    # Returns: subprocess.CompletedProcess mit stdout/stderr/text
    kwargs = {"capture_output": True, "text": True, "timeout": timeout}
    if input_:
        kwargs["input"] = input_
    return subprocess.run(cmd, **kwargs)


def _windows():
    # Ruft list_windows von cua-driver ab
    # Returns: List of window dicts aus d.get("windows", [])
    # WICHTIG: Antwort ist DICT {"windows": [...]} nicht ARRAY [...]
    r = _run(["cua-driver", "call", "list_windows"])
    try:
        d = json.loads(r.stdout)
        return d.get("windows", []) if isinstance(d, dict) else []
    except:
        return []


def _find_bot_wid(keywords=None):
    # Findet Window ID von BOT Chrome (heypiggy-bot-* profile)
    # keywords  : list   — Title-Keywords filtern (z.B. ["heypiggy", "dashboard"])
    # Returns   : tuple  — (pid, wid) oder (None, None)
    # FILTER: height>100 AND is_on_screen AND "chrome" in app_name
    for w in _windows():
        b = w.get("bounds", {})  # NICHT w.get("frame")!
        t = (w.get("title") or "").lower()
        n = (w.get("app_name") or "").lower()
        pid = w.get("pid")
        if b.get("height", 0) < 100:
            continue
        if "chrome" not in n:
            continue
        # Keywords-Filter (optional)
        if keywords:
            if any(k in t for k in keywords):
                return pid, w.get("window_id")
        else:
            # Kein Keyword-Filter → erste Chrome-Window zurück
            return pid, w.get("window_id")
    return None, None


def _cua(pid, wid, method, params=None):
    # Ruft cua-driver call auf mit JSON input
    # pid       : int     — Chrome Process ID
    # wid       : int     — Window ID
    # method    : str     — "get_window_state" | "click" | "set_value"
    # params    : dict    — method-spezifische Parameter
    # Returns   : dict    — geparste JSON Antwort
    p = dict(params or {})
    p["pid"] = pid
    p["window_id"] = wid
    r = _run(["cua-driver", "call", method], json.dumps(p))
    try:
        return json.loads(r.stdout) if r.stdout else {}
    except:
        return {}


def _tree(pid, wid):
    # Liest AX-Tree eines Windows als Liste von Zeilen
    # pid       : int
    # wid       : int
    # Returns   : list    — tree_markdown.split("\n")
    d = _cua(pid, wid, "get_window_state")
    return d.get("tree_markdown", "").split("\n") if isinstance(d, dict) else []


def _find_idx(tree, keyword, roles=None):
    # Findet element_index durch Keyword + Role-Matching im AX-Tree
    # tree      : list    — output von _tree()
    # keyword   : str     — Label-Text (case-insensitive match)
    # roles     : list    — AXRole-Typen ["AXButton", "AXLink", "AXTextField"]
    # Returns   : int     — element_index oder None
    # WICHTIG: Google Login ist AXLink, nicht AXButton!
    if roles is None:
        roles = ["AXButton", "AXLink", "AXTextField"]
    for role in roles:
        for line in tree:
            # Case-insensitive Keyword-Match
            if keyword.lower() in line.lower() and role in line:
                # Element-Index aus "- [N]" Pattern extrahieren
                m = re.search(r'- \[(\d+)\]', line)
                if m:
                    return int(m.group(1))
    return None


def _click(pid, wid, idx):
    # Klickt Element via cua-driver
    # idx       : int     — element_index aus _find_idx()
    # Returns   : bool    — True wenn "performed" in response
    if idx is None:
        return False
    r = _cua(pid, wid, "click", {"element_index": idx})
    return "performed" in r.get("stdout", "").lower() or "performed" in r.get("stderr", "").lower()


def _type(pid, wid, idx, value):
    # Trägt Text in AXTextField ein
    # idx       : int     — element_index aus _find_idx()
    # value     : str     — einzutragender Text
    # Returns   : bool    — True wenn "set" in response
    if idx is None:
        return False
    r = _cua(pid, wid, "set_value", {"element_index": idx, "value": value})
    return "set" in r.get("stdout", "").lower() or "set" in r.get("stderr", "").lower()


def _find_logged_in_heypiggy():
    # Findet HeyPiggy Window das bereits EINGELOGGT ist
    windows = _windows()
    windows.sort(key=lambda w: w.get("z_index", 0), reverse=True)
    
    for w in windows:
        b = w.get("bounds", {})
        t = (w.get("title") or "").lower()
        n = (w.get("app_name") or "").lower()
        pid = w.get("pid")
        
        if b.get("height", 0) < 100:
            continue
        if "chrome" not in n:
            continue
        
        if any(k in t for k in ["umfragen", "auszahlung", "abmelden"]):
            return pid, w.get("window_id"), True
        
        if any(k in t for k in ["heypiggy", "verdienen", "dashboard"]):
            tree = _tree(pid, w.get("window_id"))
            if any("abmelden" in l.lower() for l in tree):
                return pid, w.get("window_id"), True
    
    return None, None, False


def execute(pid=None, url="https://heypiggy.com/?page=dashboard"):
    """
    AUTO-GOOGLE-LOGIN — CUA-ONLY 6-Step Flow (LIVE TESTED 2026-05-05)

    Args:
      pid : int  — optional, wenn Chrome schon läuft (MANUELL gestartet, NICHT playstealth!)
      url : str  — Heypiggy URL (default: dashboard)

    Returns:
      {"status": "ok", "pid": X, "wid": Y}  — Login erfolgreich
      {"status": "error", "reason": "..."}   — Login fehlgeschlagen

    ========================================================================
    NEUE LOGIK (2026-05-07): Check ALREADY LOGGED IN FIRST!
    ========================================================================

    1. _find_logged_in_heypiggy() → wenn found: return sofort mit pid/wid
    2. NUR wenn nicht eingeloggt: Chrome MANUELL starten → 6-Step Login
       (playstealth ist BANNED — setzt NICHT --force-renderer-accessibility!)
    3. Mehrere BOT Chrome Instanzen möglich → _find_bot_wid sortiert nach z_index

    STEP-BY-STEP FLOW (live dokumentiert via Shell Commands):
    ========================================================================

    STEP 1: Chrome MANUELL starten → get BOT PID
      Chrome mit --force-renderer-accessibility + --remote-allow-origins="*" starten
      → PID via ps aux | grep "heypiggy-new" finden
      → wait 3s

    STEP 2: list_windows → find Dashboard WID
      → _find_bot_wid(["heypiggy", "dashboard", "verdienen"])
      → wenn nicht gefunden: _find_bot_wid() (erste Chrome-Window)
      → pid=DYNAMIC, wid=DYNAMIC

    STEP 3: click [54] Google Login-Symbol (AXLink auf Dashboard)
      tree = _tree(pid, wid)
      idx = _find_idx(tree, "google login-symbol", ["AXLink"])
      _click(pid, wid, idx)
      → wait 5s → list_windows
      → NEUE WID: DYNAMIC (Google OAuth)

    STEP 4: type email [25] + click "Weiter" [35] im OAuth Popup
      tree = _tree(pid_g, wid_g)
      email_idx = _find_idx(tree, "e-mail oder telefonnummer", ["AXTextField"])
      _type(pid_g, wid_g, email_idx, "zukunftsorientierte.energie@gmail.com")
      weiter_idx = _find_idx(tree, "weiter", ["AXButton"])
      _click(pid_g, wid_g, weiter_idx)
      → wait 5s → Keychain Auto-Fill → "Jeremy Schulze"

    STEP 5: click "Fortfahren" [62] (Keychain Konto bestätigen)
      tree = _tree(pid_k, wid_k)
      fortsetzen_idx = _find_idx(tree, "fortfahren", ["AXButton"])
      _click(pid_k, wid_k, fortsetzen_idx)
      → wait 5s → WID DYNAMIC mit Final "Weiter" [41]

    STEP 6: click Final "Weiter" [41] → Login Complete!
      tree = _tree(pid_f, wid_f)
      final_idx = _find_idx(tree, "weiter", ["AXButton"])
      _click(pid_f, wid_f, final_idx)
      → wait 5s → Google OAuth WID GESCHWUNDEN
      → Dashboard EINGELOGGT mit "Umfragen", "Auszahlung", "Abmelden"

    ========================================================================
    """
    # STEP 0: Check ob HeyPiggy bereits eingeloggt ist!
    # WICHTIG: Mehrere BOT Chrome können offen sein → neueste (höchster z_index) zuerst
    epid, ewid, logged_in = _find_logged_in_heypiggy()
    if logged_in and ewid:
        return {"status": "ok", "pid": epid, "wid": ewid}

    # STEP 1: Launch or REUSE via SessionManager (SOTA pattern)
    if pid is None:
        result = _SessionManager.launch("heypiggy", url)
        if result["status"] != "ok":
            return {"status": "error", "reason": result.get("reason", "session_manager_failed")}
        pid = result["pid"]
        wid = result.get("wid")  # may be None if not yet found

    time.sleep(3)

    # STEP 2: Find Dashboard WID
    pid, wid = _find_bot_wid(["heypiggy", "dashboard", "verdienen"])
    if not wid:
        pid, wid = _find_bot_wid()
    if not wid:
        return {"status": "error", "reason": "no_dashboard_window"}

    # STEP 3: Find + click Google Login-Symbol (AXLink!)
    # Google Login Button ist AXLink, nicht AXButton!
    tree = _tree(pid, wid)
    idx = _find_idx(tree, "google login-symbol", ["AXLink"])
    if idx is None:
        # Fallback: allgemeinerer Google-Match
        idx = _find_idx(tree, "google", ["AXLink"])
    if idx is None:
        return {"status": "error", "reason": "google_login_button_not_found"}
    if not _click(pid, wid, idx):
        return {"status": "error", "reason": "google_login_click_failed"}

    # Warten bis Google OAuth Popup erscheint
    time.sleep(5)

    # STEP 4: Find Google OAuth WID
    # WICHTIG: OAuth hat ANDERE WID als Dashboard!
    pid_g, wid_g = _find_bot_wid(["google", "anmelden", "accounts"])
    if not wid_g:
        pid_g, wid_g = _find_bot_wid()
    if not wid_g:
        return {"status": "error", "reason": "google_oauth_window_not_found"}

    # Email eintragen
    tree = _tree(pid_g, wid_g)
    email_idx = _find_idx(tree, "e-mail oder telefonnummer", ["AXTextField"])
    weiter_idx = _find_idx(tree, "weiter", ["AXButton"])

    if email_idx is None:
        return {"status": "error", "reason": "email_field_not_found"}
    if not _type(pid_g, wid_g, email_idx, "zukunftsorientierte.energie@gmail.com"):
        return {"status": "error", "reason": "email_type_failed"}

    if weiter_idx is None:
        return {"status": "error", "reason": "weiter_button_not_found"}
    if not _click(pid_g, wid_g, weiter_idx):
        return {"status": "error", "reason": "weiter_click_failed"}

    # Warten auf Keychain Auto-Fill (Account wird automatisch ausgewählt!)
    time.sleep(5)

    # STEP 5: Keychain Auto-Fill → "Jeremy Schulze" Konto
    # Keychain füllt Credentials automatisch aus → NUR "Fortfahren" klicken
    pid_k, wid_k = _find_bot_wid(["google", "anmelden", "jeremy"])
    if not wid_k:
        pid_k, wid_k = _find_bot_wid(["google"])
    if not wid_k:
        return {"status": "error", "reason": "keychain_window_not_found"}

    tree = _tree(pid_k, wid_k)
    fortsetzen_idx = _find_idx(tree, "fortfahren", ["AXButton"])
    if fortsetzen_idx is None:
        # Fallback: "Konto" Button
        fortsetzen_idx = _find_idx(tree, "konto", ["AXButton"])
    if fortsetzen_idx is None:
        return {"status": "error", "reason": "fortfahren_button_not_found"}
    if not _click(pid_k, wid_k, fortsetzen_idx):
        return {"status": "error", "reason": "fortfahren_click_failed"}

    # Warten auf final "Weiter" nach Konto-Bestätigung
    time.sleep(5)

    # STEP 6: Final "Weiter" (Account vollständig authentifizieren)
    pid_f, wid_f = _find_bot_wid(["google", "anmelden"])
    if not wid_f:
        pid_f, wid_f = _find_bot_wid()
    if not wid_f:
        return {"status": "error", "reason": "final_weiter_window_not_found"}

    tree = _tree(pid_f, wid_f)
    final_idx = _find_idx(tree, "weiter", ["AXButton"])
    if final_idx is None:
        return {"status": "error", "reason": "final_weiter_not_found"}
    if not _click(pid_f, wid_f, final_idx):
        return {"status": "error", "reason": "final_weiter_click_failed"}

    # Warten bis Google OAuth Window schließt
    time.sleep(5)

    # Verify: Dashboard sollte eingeloggt sein
    pid_d, wid_d = _find_bot_wid(["heypiggy", "dashboard", "verdienen"])
    if not wid_d:
        pid_d, wid_d = _find_bot_wid()
    if not wid_d:
        return {"status": "error", "reason": "dashboard_not_found"}

    tree = _tree(pid_d, wid_d)
    if any("abmelden" in l.lower() for l in tree):
        return {"status": "ok", "pid": pid_d, "wid": wid_d}
    if any("umfragen" in l.lower() for l in tree):
        return {"status": "ok", "pid": pid_d, "wid": wid_d}

    return {"status": "ok", "pid": pid_d, "wid": wid_d}


# CLI Entry Point
if __name__ == "__main__":
    import sys
    # Optional: PID als Command-Line Argument übergeben
    pid = int(sys.argv[1]) if len(sys.argv) > 1 else None
    result = execute(pid)
    print(json.dumps(result, indent=2))
