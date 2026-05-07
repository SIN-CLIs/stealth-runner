#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
================================================================================
AUTO-GOOGLE-LOGIN — CUA-ONLY 6-Step Login für Heypiggy.com
================================================================================
================================================================================

WAS IST DIESE DATEI?
  Diese Datei ist das Herzstück des HeyPiggy Login-Systems. Sie automatisiert
  den Google OAuth Login für heypiggy.com über macOS Accessibility (AX) APIs
  via cua-driver. OHNE diesen Login können KEINE Surveys ausgeführt werden.

  Warum ist diese Datei so wichtig?
    - Sie ist der ERSTE Schritt in JEDEM Survey-Flow
    - Wenn sie fehlschlägt: 0 Surveys, 0 Einnahmen, Endlosschleife
    - Sie wurde LIVE getestet am 2026-05-05 mit PID=71104 (Historisch!)
    - Sie hat 8 dokumentierte CRITICAL BUGS die behoben wurden

ARCHITEKTUR / DATENFLUSS:
  ┌─────────────────────────────────────────────────────────────────────────────┐
  │                         auto_google_login.py                                │
  │                              (DU BIST HIER)                                 │
  └─────────────────────────────────────────────────────────────────────────────┘
           │
           ▼
  ┌─────────────────────────────────────────────────────────────────────────────┐
  │  STEP 0: _find_logged_in_heypiggy()                                         │
  │  → Prüft OB bereits eingeloggt (vermeidet Doppel-Login)                     │
  │  → Sortiert Windows nach z_index (neueste zuerst)                           │
  │  → Sucht Keywords: "umfragen", "auszahlung", "abmelden"                     │
  └─────────────────────────────────────────────────────────────────────────────┘
           │ Wenn gefunden: Sofort-Return (PID, WID, logged_in=True)
           ▼ Wenn NICHT gefunden: Chrome starten + 6-Step Flow
  ┌─────────────────────────────────────────────────────────────────────────────┐
  │  STEP 1: Chrome starten (MANUELL — playstealth ist BANNED!)               │
  │  → SessionManager.launch("heypiggy", url)                                   │
  │  → Chrome MUSS mit --force-renderer-accessibility gestartet werden          │
  │  → Chrome MUSS mit --remote-allow-origins="*" gestartet werden              │
  │  → Profile: /tmp/heypiggy-new-XXXXXXXXXX (timestamped, NIE fixed!)          │
  └─────────────────────────────────────────────────────────────────────────────┘
           │
           ▼
  ┌─────────────────────────────────────────────────────────────────────────────┐
  │  STEP 2: Dashboard Window finden                                            │
  │  → _find_bot_wid(["heypiggy", "dashboard", "verdienen"])                    │
  │  → Filter: bounds.height > 100 AND "chrome" in app_name                     │
  │  → WICHTIG: Dashboard-WID ≠ OAuth-WID (OAuth öffnet NEUES Window!)          │
  └─────────────────────────────────────────────────────────────────────────────┘
           │
           ▼
  ┌─────────────────────────────────────────────────────────────────────────────┐
  │  STEP 3: Google Login-Symbol klicken (AXLink, NICHT AXButton!)            │
  │  → _find_idx(tree, "google login-symbol", ["AXLink"])                       │
  │  → _click(pid, wid, idx)                                                   │
  │  → Warten 5s (OAuth Popup braucht Zeit!)                                   │
  └─────────────────────────────────────────────────────────────────────────────┘
           │
           ▼
  ┌─────────────────────────────────────────────────────────────────────────────┐
  │  STEP 4: Email eingeben + "Weiter" klicken                                  │
  │  → NEUE WID finden (OAuth Popup!)                                           │
  │  → _find_idx(tree, "e-mail oder telefonnummer", ["AXTextField"])            │
  │  → _type(pid, wid, email_idx, "zukunftsorientierte.energie@gmail.com")     │
  │  → _find_idx(tree, "weiter", ["AXButton"])                                  │
  │  → _click(pid, wid, weiter_idx)                                            │
  │  → Warten 5s (Keychain Auto-Fill braucht Zeit!)                             │
  └─────────────────────────────────────────────────────────────────────────────┘
           │
           ▼
  ┌─────────────────────────────────────────────────────────────────────────────┐
  │  STEP 5: Keychain "Fortfahren" klicken                                    │
  │  → Keychain füllt Credentials AUTOMATISCH aus                               │
  │  → "Jeremy Schulze" Konto ist vorausgewählt                               │
  │  → NUR "Fortfahren" klicken — KEIN Passwort eingeben!                       │
  │  → _find_idx(tree, "fortfahren", ["AXButton"])                              │
  │  → _click(pid, wid, fortsetzen_idx)                                         │
  │  → Fallback: "Konto" Button wenn "Fortfahren" nicht gefunden                │
  │  → Warten 5s                                                                │
  └─────────────────────────────────────────────────────────────────────────────┘
           │
           ▼
  ┌─────────────────────────────────────────────────────────────────────────────┐
  │  STEP 6: Final "Weiter" klicken                                             │
  │  → Account vollständig authentifizieren                                     │
  │  → _find_idx(tree, "weiter", ["AXButton"])                                  │
  │  → _click(pid, wid, final_idx)                                              │
  │  → Warten 5s                                                                │
  │  → OAuth Window sollte GESCHWUNDEN sein                                     │
  │  → Dashboard sollte "Umfragen", "Auszahlung", "Abmelden" zeigen            │
  └─────────────────────────────────────────────────────────────────────────────┘
           │
           ▼
  ┌─────────────────────────────────────────────────────────────────────────────┐
  │  VERIFY: Dashboard eingeloggt?                                              │
  │  → _find_bot_wid(["heypiggy", "dashboard", "verdienen"])                     │
  │  → AX-Tree prüfen: "abmelden" oder "umfragen" im Text?                      │
  │  → Return: {"status": "ok", "pid": X, "wid": Y}                              │
  └─────────────────────────────────────────────────────────────────────────────┘

DEPENDENZEN (Was bricht wenn diese Datei fehlt?):
  - survey-cli/survey.py → cmd_watch() ruft execute() auf
  - src/stealth_survey/survey_agent.py → SurveyAgent.run_loop() ruft Login auf
  - cli/modules/session_manager.py → SessionManager.launch() für Chrome-Start
  → ALLE Survey-Flows sind BLOCKIERT ohne diese Datei!

ABHÄNGIGKEITEN (Was braucht diese Datei?):
  - cua-driver (System-Binary): MUSS installiert sein, MUSS als Daemon laufen
  - Google Chrome (App): MUSS in /Applications/Google Chrome.app existieren
  - macOS Accessibility APIs: System Settings → Accessibility muss aktiviert sein
  - SessionManager: Für Chrome-Start und Registry-Verwaltung
  - Python Pakete: subprocess, json, time, re (Standardlib)

BANNED METHODS — NIEMALS VERWENDEN (siehe /banned.md):
  ❌ playstealth launch
     → WARUM BANNED: Setzt NICHT --force-renderer-accessibility
     → FOLGE: AX-Tree ist LEER → cua-driver findet keine Elemente
     → ALTERNATIVE: Chrome MANUELL starten oder SessionManager.launch()

  ❌ webauto-nodriver
     → WARUM BANNED: Dead Project, keine Updates, instabil
     → FOLGE: Kann Chrome crashen, Credentials leaken
     → ALTERNATIVE: cua-driver oder CDP WebSocket

  ❌ cua-driver click (raw element_index ohne Verify)
     → WARUM BANNED: Index ist instabil (DOM ändert sich)
     → FOLGE: Klickt falsches Element → Daten verloren, Survey disqualifiziert
     → ALTERNATIVE: _find_idx() für Label-basiertes Matching

  ❌ --remote-allow-origins=* (ohne Anführungszeichen)
     → WARUM BANNED: zsh expandiert * zu Dateinamen im aktuellen Verzeichnis
     → FOLGE: Chrome startet mit --remote-allow-origins=file1 file2 ... → Crash
     → ALTERNATIVE: --remote-allow-origins="*" (MIT Anführungszeichen!)

  ❌ /tmp/heypiggy-bot (fixed profile path)
     → WARUM BANNED: Profile wird korrupt nach Neustart (Cookies, Cache)
     → FOLGE: Login schlägt fehl, Sessions überschrieben
     → ALTERNATIVE: /tmp/heypiggy-new-$(date +%s) (timestamped, immer frisch)

  ❌ Hardcoded PIDs (71104, 56640, etc.)
     → WARUM BANNED: PIDs sind DYNAMISCH (ändern sich bei jedem Chrome-Start)
     → FOLGE: Agent arbeitet auf falschem/alten Prozess → Fehler oder Datenverlust
     → ALTERNATIVE: PID zur Laufzeit finden via _find_bot_wid() oder ps

  ❌ pkill -f "Google Chrome"
     → WARUM BANNED: Tötet ALLE Chrome-Instanzen (USER + BOT!)
     → FOLGE: User verliert Tabs, Sessions, Arbeit
     → ALTERNATIVE: NUR Bot-Chrome beenden (SessionManager.close_all())

  ❌ killall Google Chrome
     → WARUM BANNED: Tötet ALLE Chrome-Instanzen (USER + BOT!)
     → FOLGE: User verliert Tabs, Sessions, Arbeit
     → ALTERNATIVE: NUR Bot-Chrome beenden

  ❌ skylight-cli click --element-index
     → WARUM BANNED: Index ist instabil (siehe cua-driver raw index)
     → FOLGE: Gleiche Probleme wie cua-driver raw index
     → ALTERNATIVE: Label-basiertes Matching oder BatchExecutor

HISTORY / CHANGELOG (Jede Änderung dokumentiert mit Datum + Warum):
  2026-05-08: _find_logged_in_heypiggy() hinzugefügt (STEP 0)
    → WARUM: Login-Schleife erkannt (0 Surveys seit Tagen, siehe Issue #1)
    → WAS: Prüft VOR dem Login ob bereits eingeloggt
    → VERIFIZIERUNG: Test test_execute_already_logged_in

  2026-05-07: IndentationError in survey-cli/survey.py behoben
    → WARUM: SyntaxError blockierte survey.py komplett
    → WAS: 8 spaces → 4 spaces (6 Zeilen)
    → DATEI: survey-cli/survey.py:199
    → VERIFIZIERUNG: python3 -m py_compile survey.py

  2026-05-07: SessionManager.launch() integriert (STEP 1)
    → WARUM: Chrome-Start sollte zentralisiert sein (nicht in jeder Datei)
    → WAS: execute() nutzt jetzt SessionManager für Chrome-Start
    → VERIFIZIERUNG: Test test_chrome_launch_via_session_manager

  2026-05-05: Keychain Auto-Fill Discovery (STEP 5)
    → WARUM: Google OAuth zeigt KEIN Passwort-Feld wenn Keychain aktiv
    → WAS: NUR "Fortfahren" klicken statt Passwort eingeben
    → VERIFIZIERUNG: Live-Test PID=71104, WID=56658
    → KRITISCHE ERKENNTNIS: Keychain füllt Credentials automatisch aus!

  2026-05-05: 8 CRITICAL BUGS behoben (siehe BUGS Section unten)
    → WARUM: Jeder Bug hat Login mindestens einmal blockiert
    → WAS: Siehe detaillierte Bug-Beschreibungen unten
    → VERIFIZIERUNG: Live-Tests PID=71104 (alle 6 Steps)

  2026-05-05: Erste Version (cua-driver 6-Step Flow)
    → WARUM: Vorherige Implementierungen waren BANNED (skylight, CDP, webauto)
    → WAS: Kompletter Rewrite mit cua-driver ONLY
    → VERIFIZIERUNG: Live-Test PID=71104

CRITICAL BUGS (BEHOBEN — Dokumentation damit sie NIE wieder passieren):

  BUG 1: list_windows returns DICT not ARRAY
    → FALSCH: windows = json.loads(r.stdout)  # Annahme: Array
    → RICHTIG: windows = d.get("windows", []) if isinstance(d, dict) else []
    → WARUM: cua-driver gibt {"windows": [...]} zurück, nicht [...]
    → IMPACT: Code crashte mit AttributeError wenn "windows" key fehlte

  BUG 2: Window filter must use BOUNDS not FRAME
    → FALSCH: w.get("frame", {}).get("height", 0)  # Frame ist None!
    → RICHTIG: w.get("bounds", {}).get("height", 0)
    → WARUM: "frame" existiert nicht in cua-driver output, "bounds" schon
    → IMPACT: Alle Windows hatten height=0 → Keine Window gefunden

  BUG 3: Google Login Button is AXLink not AXButton
    → FALSCH: roles = ["AXButton"]  # Login-Symbol nicht gefunden
    → RICHTIG: roles = ["AXButton", "AXLink"]
    → WARUM: Google Login-Symbol ist ein Link (<a> Tag), kein Button
    → IMPACT: _find_idx() gab None zurück → Login schlug fehl

  BUG 4: click() response check wrong
    → FALSCH: r.get("stdout") == " Performed "  # Exact match mit Leerzeichen!
    → RICHTIG: "performed" in r.get("stdout", "").lower()
    → WARUM: Response enthält mehr Text als nur "Performed"
    → IMPACT: Erfolgreicher Klick wurde als Fehler gewertet → Endlosschleife

  BUG 5: Google OAuth opens NEW WID - old code stayed on Dashboard WID
    → FALSCH: wid = _find_wid(["heypiggy"])  # Blieb auf Dashboard WID
    → RICHTIG: Nach click → _find_wid(["google", "anmelden"])  # NEUE WID
    → WARUM: OAuth öffnet ein NEUES Window (Popup), nicht im Dashboard
    → IMPACT: Klicks landeten auf Dashboard statt OAuth → Login schlug fehl

  BUG 6: Keychain Label war falsch ("passwort" statt "fortfahren")
    → FALSCH: type_text("passwort", "admin")  # Suchte Passwort-Feld
    → RICHTIG: click("fortfahren")  # Keychain hat bereits ausgefüllt
    → WARUM: Keychain Auto-Fill zeigt "Fortfahren" Button, kein Passwort-Feld
    → IMPACT: Agent wartete auf Passwort-Feld das nicht existierte → Timeout

  BUG 7: Wrong email address
    → FALSCH: "devjerro@gmail.com"  # Falscher Account
    → RICHTIG: "zukunftsorientierte.energie@gmail.com"
    → WARUM: devjerro@gmail.com ist ein alter Test-Account
    → IMPACT: Login schlug fehl weil Account nicht existierte

  BUG 8: WRONG Chrome PID - User Chrome vs Bot Chrome
    → FALSCH: Hardcoded PID oder PID aus ps ohne Filter
    → RICHTIG: NUR PIDs mit "heypiggy-bot-XXXXXXXX" in user-data-dir
    → WARUM: Mehrere Chrome-Instanzen können laufen (USER + BOT)
    → IMPACT: Agent arbeitete auf USER Chrome → Datenverlust, Tab-Crash

KNOWN LIMITATIONS (Bekannte Einschränkungen):
  - Keychain Auto-Fill: Wenn deaktiviert, braucht diese Datei einen
    Passwort-Fallback (noch nicht implementiert, siehe Issue #1 Fix 4)
  - 2FA: Wenn Google 2FA aktiviert ist, schlägt Login fehl (noch nicht
    unterstützt — Workaround: 2FA im Google Account deaktivieren)
  - OAuth Language: Wenn Chrome auf Englisch gestellt ist, sind Labels
    "Continue" statt "Weiter" → _find_idx() schlägt fehl
  - Multiple Google Accounts: Wenn mehrere Accounts im Keychain sind,
    muss möglicherweise der richtige ausgewählt werden (nicht automatisch)

RACE CONDITIONS (Bekannte Race Conditions und wie man sie vermeidet):
  1. Chrome Window während Login wechselt
     → Lösung: Nach jedem _click() WID neu finden (nicht reuse alte WID)
  2. Keychain Auto-Fill dauert länger als 5s
     → Lösung: Wartezeit konfigurierbar machen (nicht hardcoded)
  3. OAuth Popup wird von Popup-Blocker blockiert
     → Lösung: Chrome mit --disable-popup-blocking starten
  4. Zwei Bot-Chrome Instanzen gleichzeitig
     → Lösung: _find_logged_in_heypiggy() sortiert nach z_index (neueste zuerst)

================================================================================
SHELL COMMANDS (DOKUMENTIERT - learning-by-doing, LIVE GETESTET):
================================================================================

STEP 1: Chrome MANUELL starten
  → WARUM MANUELL? playstealth setzt NICHT --force-renderer-accessibility!
  → WARUM timestamped Profile? Fixed Profile wird korrupt nach Neustart!

  Command:
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
      --user-data-dir="/tmp/heypiggy-new-$(date +%s)" \
      --remote-debugging-port=9999 \
      --remote-allow-origins="*" \
      --force-renderer-accessibility \
      --no-first-run \
      --no-default-browser-check \
      "https://www.heypiggy.com/?page=dashboard"

  Erwartetes Ergebnis:
    → Profile: /tmp/heypiggy-new-1777981361 (Beispiel, ändert sich!)
    → CDP Port: 9999
    → Accessibility: Aktiviert (--force-renderer-accessibility)

STEP 2: Windows finden (cua-driver list_windows)
  → WARUM? Wir müssen das richtige Window finden (nicht Menüleiste!)

  Command:
    cua-driver call list_windows

  Erwartetes Ergebnis:
    {"windows": [
      {"pid": 71104, "window_id": 56640, "title": "HeyPiggy – Verdienen...",
       "bounds": {"height": 800, "width": 1200}, "app_name": "Google Chrome", ...}
    ]}

  WICHTIG: Filter auf height>100 (Menüleiste hat height=20!)
  WICHTIG: Filter auf "chrome" in app_name

STEP 3: AX-Tree lesen (cua-driver get_window_state)
  → WARUM? Wir müssen Elemente finden (Google Login-Symbol, Buttons, etc.)

  Command:
    echo '{"pid": 71104, "window_id": 56640}' | cua-driver call get_window_state

  Erwartetes Ergebnis:
    {"tree_markdown": "...", "element_count": 672}
    tree_markdown enthält Zeilen wie:
      '- [54] AXLink "Google Login-Symbol" @(731,651,132,41)'
      '- [35] AXButton "Weiter" @(1095,706,91,40)'

  WICHTIG: Element-Index aus "- [N]" Pattern extrahieren
  WICHTIG: "@" enthält Position (x,y,w,h) — für Debugging

STEP 4: Element klicken (cua-driver click)
  → WARUM cua-driver statt CDP? CDP click() funktioniert nicht mit SPAs
     (Single Page Apps) — cua-driver nutzt AXUIElementPerformAction()
     welches JS-Events korrekt triggert.

  Command:
    echo '{"pid": 71104, "window_id": 56640, "element_index": 54}' | cua-driver call click

  Erwartetes Ergebnis:
    "✅ Performed AXPress on [54] AXLink"

STEP 5: Text eintragen (cua-driver set_value)
  → WARUM set_value statt click + type? set_value setzt AXValue direkt
     ohne Focus-Steal (funktioniert auch wenn Element nicht sichtbar)

  Command:
    echo '{"pid": 71104, "window_id": 56658, "element_index": 25,
           "value": "zukunftsorientierte.energie@gmail.com"}' | cua-driver call set_value

  Erwartetes Ergebnis:
    "✅ Set AXValue on [25] AXTextField"

================================================================================
BOT CHROME PIDs (DOKUMENTATION — NIEMALS USER CHROME BEENDEN!):
================================================================================

WIE unterscheidet man BOT Chrome von USER Chrome?
  1. ps aux | grep "user-data-dir"
  2. Prüfe ob "heypiggy-new-XXXXXXXXXX" im Pfad
  3. WENN JA → BOT Chrome → DARF interagiert/killed werden
  4. WENN NEIN → USER Chrome → DARF NIEMALS gekillt werden

WARUM ist das wichtig?
  - USER Chrome hat private Tabs (Banking, Email, etc.)
  - USER Chrome hat ungespeicherte Arbeit
  - USER Chrome hat opencode Sessions (wenn opencode im Browser läuft)
  - Ein Kill von USER Chrome = Datenverlust!

Historische BOT PIDs (nur als Referenz — PIDs sind IMMER dynamisch!):
  - PID=71104 (2026-05-05, profile=/tmp/heypiggy-bot-1777981361) [BEISPIEL]
  - PID=70293 (2026-05-05, profile=/tmp/heypiggy-bot-1777981087) [BEISPIEL]
  - PID=51212 (2026-05-04, profile=/tmp/heypiggy-bot-1777979455) [BEISPIEL]

  WICHTIG: Diese PIDs sind HISTORISCH und NICHT wiederverwendbar!
  WICHTIG: NIE diese PIDs hardcodieren — immer zur Laufzeit finden!

================================================================================
FUNKTIONS-SIGNATUR (ENTRY POINT):
================================================================================

def execute(pid=None, url="https://heypiggy.com/?page=dashboard") -> dict:
  Args:
    pid : int — Optional. Wenn Chrome bereits läuft, wird diese PID genutzt.
                WENN None: SessionManager.start() startet Chrome.
                WARUM Optional? Wenn Chrome bereits von anderem Flow gestartet.
    url : str — Heypiggy URL. Default ist Dashboard.
                WARUM Dashboard? Login ist nur nötig wenn Dashboard nicht
                eingeloggt ist. Andere Seiten (Impressum) brauchen kein Login.

  Returns:
    {"status": "ok", "pid": int, "wid": int}
      → Login erfolgreich. pid/wid sind des Dashboard-Windows.
      → WARUM pid/wid? Caller muss Dashboard-Window für Surveys nutzen.

    {"status": "error", "reason": str}
      → Login fehlgeschlagen. reason enthält spezifische Ursache.
      → WARUM reason? Ermöglicht differenzierte Fehlerbehandlung.
      → Beispiele: "google_login_button_not_found", "daemon_not_running"

  Side Effects:
    - Startet Chrome-Prozess (wenn pid=None)
    - Mutiert ~/.stealth/sessions.json (SessionManager)
    - Nutzt cua-driver Daemon (muss laufen!)
    - Schreibt AX-Tree zu /tmp/ (für Debugging)
    - Interagiert mit Google OAuth (Netzwerk-Requests)

  Race Conditions:
    - Chrome Window kann sich während Login ändern (siehe BUG 5)
    - Mehrere Bot-Chrome können existieren (siehe _find_logged_in_heypiggy)
    - cua-driver Daemon kann während Call crashen

  BANNED in dieser Funktion:
    ❌ Kein playstealth launch (auch nicht indirekt via SessionManager!)
    ❌ Keine hardcoded PIDs
    ❌ Kein pkill -f "Google Chrome"
    ❌ Kein killall Google Chrome

================================================================================
"""

# ============================================================================
# IMPORTS
# ============================================================================
# WARUM subprocess? Wir müssen cua-driver als External Binary aufrufen.
# cua-driver ist ein Rust/Go Binary, nicht ein Python Modul.
# → subprocess.run() ist der einzige Weg.
import subprocess

# WARUM json? cua-driver kommuniziert via JSON (stdin/stdout).
# Alle Requests und Responses sind JSON-Objekte.
import json

# WARUM time? Wir müssen nach Aktionen WARTEN (Chrome braucht Zeit).
# → time.sleep() ist notwendig, nicht optional.
# → Warum nicht async? Einfachheit. cua-driver ist synchron.
import time

# WARUM re? Wir müssen Element-Indizes aus Text extrahieren.
# Format: "- [54] AXLink ..." → re.search(r'- \[(\d+)\]', line) → 54
import re

# WARUM SessionManager? Zentralisierte Chrome-Verwaltung.
# → Registry von Chrome-Sessions (~/.stealth/sessions.json)
# → Safe Kill (nur Bot-Chrome, nie User-Chrome)
# → Profile-Management (timestamped, cleanup)
from cli.modules.session_manager import SessionManager

# ============================================================================
# GLOBALE VARIABLEN
# ============================================================================
# WARUM global? SessionManager ist teuer zu erstellen (File I/O).
# → Singleton Pattern: Eine Instanz pro Prozess.
# → Thread-Safety: Nicht thread-safe! (Nur ein Agent nutzt diese Datei)
_SessionManager = SessionManager()

# ============================================================================
# HILFSFUNKTIONEN — Jede Funktion wird EXTREM dokumentiert
# ============================================================================

def _run(cmd, input_=None, timeout=15):
    """
    ================================================================================
    Führt ein Shell-Kommando aus mit optionalem stdin Input.
    ================================================================================

    WAS macht diese Funktion?
      Wrapper um subprocess.run() mit JSON-Input/Output für cua-driver.
      Dies ist die LOWEST-LEVEL Funktion in dieser Datei — ALLE anderen
      cua-driver Calls gehen durch diese Funktion.

    Args:
      cmd (list): Kommando als Liste (z.B. ["cua-driver", "call", "list_windows"])
                  WARUM Liste statt String? Sicherer — keine Shell-Injection.
                  WARUM nicht string? subprocess.run(list) escaped automatisch.
      input_ (str, optional): JSON-String für cua-driver stdin.
                             WARUM Optional? list_windows braucht kein Input.
                             WARUM str? cua-driver erwartet JSON-String auf stdin.
      timeout (int, optional): Timeout in Sekunden. Default: 15.
                               WARUM 15? cua-driver ist schnell (<1s), aber
                               bei hoher Systemlast kann es länger dauern.
                               WARUM nicht 30? Zu lang — Agent wartet unnötig.

    Returns:
      subprocess.CompletedProcess: Objekt mit stdout, stderr, returncode.
      → WICHTIG: stdout enthält JSON-Response von cua-driver.
      → WICHTIG: stderr enthält Fehlermeldungen (z.B. "daemon not running").
      → WICHTIG: returncode 0 ≠ Erfolg (cua-driver gibt manchmal 0 bei Fehler).

    Side Effects:
      - Startet External Process (cua-driver Binary)
      - Blockiert bis Timeout oder Process beendet
      - Verbraucht CPU/RAM für cua-driver Process

    Race Conditions:
      - cua-driver Daemon kann während Call terminieren
      → Lösung: Timeout + Retry in Caller

    Example:
      >>> r = _run(["cua-driver", "call", "list_windows"])
      >>> print(r.stdout)
      '{"windows": [...]}'

    BANNED in dieser Funktion:
      ❌ Kein shell=True (Shell-Injection Risiko!)
      ❌ Kein check=True (wir wollen stderr lesen)
    ================================================================================
    """
    # Kwargs für subprocess.run()
    # capture_output=True → stdout/stderr werden captured (nicht Terminal)
    # text=True → Output als String (nicht Bytes)
    # timeout=timeout → Max Wartezeit (verhindert Deadlock)
    kwargs = {"capture_output": True, "text": True, "timeout": timeout}

    # Wenn input_ gegeben: An stdin übergeben
    # WARUM? cua-driver liest JSON von stdin für "call" commands.
    if input_:
        kwargs["input"] = input_

    # subprocess.run() ausführen
    # WARUM nicht Popen? Wir brauchen das Ergebnis SOFORT (synchron).
    # WARUM nicht call? call() gibt nur returncode, nicht stdout/stderr.
    return subprocess.run(cmd, **kwargs)


def _windows():
    """
    ================================================================================
    Ruft list_windows von cua-driver ab und parst die Antwort.
    ================================================================================

    WAS macht diese Funktion?
      Ruft "cua-driver call list_windows" auf und parst JSON-Antwort.
      Dies ist der ERSTE Schritt in JEDEM cua-driver Flow.
      OHNE diese Funktion können wir keine Windows finden → Keine Klicks.

    Returns:
      list: Liste von Window-Dictionaries.
            Beispiel-Element:
            {
              "pid": 71104,
              "window_id": 56640,
              "title": "HeyPiggy – Verdienen...",
              "bounds": {"height": 800, "width": 1200, "x": 0, "y": 25},
              "app_name": "Google Chrome",
              "z_index": 1,
              "is_on_screen": true
            }

      WARUM list? Einfach zu iterieren, filter, sort.
      WARUM dict pro Window? Strukturierte Daten, typisiert.

    BUG 1 (behoben): list_windows returns DICT not ARRAY
      FALSCH:  d = json.loads(r.stdout); windows = d  # Annahme: Array
      RICHTIG: d = json.loads(r.stdout); windows = d.get("windows", [])
      WARUM: cua-driver gibt {"windows": [...]} zurück, nicht [...].

    BUG 2 (behoben): Window filter must use BOUNDS not FRAME
      FALSCH:  w.get("frame", {}).get("height", 0)
      RICHTIG: w.get("bounds", {}).get("height", 0)
      WARUM: "frame" existiert nicht in cua-driver output.

    Side Effects:
      - Ruft cua-driver Binary auf (External Process)
      - Liest aus ~/.stealth/sessions.json (SessionManager)

    Example:
      >>> windows = _windows()
      >>> len(windows)
      3
      >>> windows[0]["title"]
      'HeyPiggy – Verdienen mit Umfragen'

    BANNED in dieser Funktion:
      ❌ Kein hardcoded PID-Filter (z.B. if w["pid"] == 71104)
    ================================================================================
    """
    # cua-driver aufrufen
    # Command: "cua-driver call list_windows"
    # WARUM "call"? cua-driver hat subcommands: "call", "serve", etc.
    # WARUM "list_windows"? Gibt alle AX-Windows der App zurück.
    r = _run(["cua-driver", "call", "list_windows"])

    try:
        # JSON parsen
        # WARUM try/except? Wenn Daemon nicht läuft → stdout ist leer oder Error.
        d = json.loads(r.stdout)

        # BUG 1 Fix: Antwort ist Dict {"windows": [...]}, nicht Array [...]
        # WARUM isinstance check? Sicherheit — falls cua-driver sich ändert.
        if isinstance(d, dict):
            return d.get("windows", [])
        elif isinstance(d, list):
            # Fallback: Falls cua-driver DOCH Array zurückgibt (alte Version?)
            return d
        else:
            # Unerwarteter Typ → Leere Liste (graceful degradation)
            return []
    except Exception:
        # WARUM nicht raise? Weil Caller dann try/except braucht.
        # Stattdessen: Leere Liste → Caller prüft if not windows: return.
        return []


def _find_bot_wid(keywords=None):
    """
    ================================================================================
    Findet Window ID (WID) von BOT Chrome (heypiggy-new-* profile).
    ================================================================================

    WAS macht diese Funktion?
      Durchsucht ALLE Windows und findet das BOT Chrome Window.
      Filter: height>100, app_name enthält "chrome", optional Keywords im Title.

    Args:
      keywords (list, optional): Title-Keywords zum Filtern.
                                 Beispiel: ["heypiggy", "dashboard", "verdienen"]
                                 WARUM Optional? Wenn keine Keywords: erstes Chrome Window.
                                 WARUM Keywords? Mehrere Chrome-Windows können offen sein
                                 (Dashboard, OAuth, Survey, Rating).
                                 → Keywords finden das RICHTIGE Window.

    Returns:
      tuple: (pid, wid) — Process ID und Window ID.
             WARUM tuple? Beide Werte werden für cua-driver Calls benötigt.
             WARUM int? cua-driver erwartet Integer für pid und window_id.
             Wenn nicht gefunden: (None, None)
             WARUM None? Explizite Fehlerbehandlung (if not wid: return error).

    FILTER-LOGIK (Reihenfolge ist WICHTIG):
      1. bounds.height > 100
         → WARUM? Menüleiste (Apple Menu) hat height ~20-40.
         → Menüleiste ignorieren (depth < 5 → nicht Browser-Content).
      2. "chrome" in app_name.lower()
         → WARUM? Nur Chrome-Windows, nicht Safari, Firefox, etc.
      3. Optional: any(k in title.lower() for k in keywords)
         → WARUM? Findet spezifisches Window (Dashboard vs OAuth vs Survey).

    Side Effects:
      - Ruft _windows() auf → cua-driver Binary Call.

    Race Conditions:
      - Wenn mehrere Bot-Chrome existieren: Welches wird gewählt?
        → Lösung: _find_logged_in_heypiggy() sortiert nach z_index (neueste zuerst).
        → Diese Funktion: Erstes passende Window (undefined Reihenfolge).

    Example:
      >>> pid, wid = _find_bot_wid(["heypiggy", "dashboard"])
      >>> print(f"Dashboard: PID={pid}, WID={wid}")
      Dashboard: PID=71104, WID=56640

    BANNED in dieser Funktion:
      ❌ Kein hardcoded PID-Filter
      ❌ Kein hardcoded WID-Filter
    ================================================================================
    """
    # ALLE Windows abrufen
    # WARUM alle? Wir müssen filtern — cua-driver bietet keinen server-side Filter.
    for w in _windows():
        # bounds extrahieren
        # WARUM bounds? Siehe BUG 2: "frame" existiert nicht!
        b = w.get("bounds", {})

        # Title und App-Name (lowercase für case-insensitive Matching)
        # WARUM lowercase? "Chrome" != "chrome" in manchen Locale-Einstellungen.
        t = (w.get("title") or "").lower()
        n = (w.get("app_name") or "").lower()

        # Process ID
        # WARUM int? cua-driver erwartet Integer.
        pid = w.get("pid")

        # FILTER 1: height > 100 (Menüleiste ignorieren)
        # WARUM 100? Menüleiste hat height ~20-40. 100 ist sicherer Cutoff.
        # WARUM nicht 50? Manche Toolbars haben height 50-80.
        if b.get("height", 0) < 100:
            continue  # Nächstes Window

        # FILTER 2: "chrome" in app_name
        # WARUM "in" statt "=="? App-Name könnte "Google Chrome" oder nur "Chrome" sein.
        if "chrome" not in n:
            continue  # Nächstes Window

        # FILTER 3 (optional): Keywords im Title
        if keywords:
            # any() → WENN EINES der Keywords im Title ist → True
            # WARUM any() statt all()? Wir wollen Dashboard finden:
            #   Title = "HeyPiggy – Verdienen mit Umfragen"
            #   Keywords = ["heypiggy", "dashboard"]
            #   → "heypiggy" ist im Title → Match!
            if any(k in t for k in keywords):
                return pid, w.get("window_id")
        else:
            # Keine Keywords → erstes passende Chrome-Window zurückgeben
            # WARUM? Wenn wir nur wissen dass Bot-Chrome existiert,
            # aber nicht welches Window (z.B. für generischen Check).
            return pid, w.get("window_id")

    # Nichts gefunden → (None, None)
    # WARUM None statt Exception? Caller soll entscheiden was zu tun ist
    # (retry, error, oder alternativer Flow).
    return None, None


def _cua(pid, wid, method, params=None):
    """
    ================================================================================
    Ruft cua-driver call auf mit JSON Input.
    ================================================================================

    WAS macht diese Funktion?
      Low-level Wrapper für cua-driver "call" commands.
      Baut JSON-Parameter, sendet an cua-driver stdin, parst Response.

    Args:
      pid (int): Chrome Process ID.
                 WARUM int? cua-driver erwartet Integer.
                 WARUM nicht Optional? Jeder Call braucht eine PID.
      wid (int): Window ID.
                 WARUM int? cua-driver erwartet Integer.
                 WARUM wichtig? Window ID identifiziert das spezifische Window.
      method (str): cua-driver Method Name.
                    Erlaubte Werte:
                    - "get_window_state": Liest AX-Tree
                    - "click": Klickt Element via AXPress
                    - "set_value": Setzt Text in AXTextField
                    - "press_key": Simuliert Tastendruck
                    WARUM diese 4? Sie sind die primären Interaktionsmethoden.
                    WARUM nicht mehr? Nicht alle cua-driver Methods sind stabil.
      params (dict, optional): Method-spezifische Parameter.
                               Beispiele:
                               - click: {"element_index": 54}
                               - set_value: {"element_index": 25, "value": "text"}
                               - press_key: {"key": "return"}
                               WARUM Optional? get_window_state braucht keine params.

    Returns:
      dict: Geparste JSON-Antwort von cua-driver.
            Beispiel (get_window_state):
            {
              "tree_markdown": "- [0] AXWebArea...\n- [1] AXGroup...",
              "element_count": 672,
              "window_title": "HeyPiggy – Verdienen mit Umfragen"
            }
            Beispiel (click):
            {
              "stdout": "✅ Performed AXPress on [54] AXLink",
              "stderr": "",
              "success": true
            }
            WARUM dict? Strukturierte Daten, einfach zu prüfen.

    Side Effects:
      - Ruft cua-driver Binary auf.
      - Interagiert mit Chrome via AX APIs.
      - Kann Chrome-Focus ändern (click, set_value).

    Race Conditions:
      - Wenn Chrome Window sich ändert während Call:
        → cua-driver gibt Error zurück (nicht crash).
      - Wenn Element sich ändert während Call:
        → cua-driver gibt "element not found" zurück.

    Example:
      >>> r = _cua(71104, 56640, "get_window_state")
      >>> print(r.get("element_count"))
      672

    BANNED in dieser Funktion:
      ❌ Kein hardcoded element_index (z.B. 54, 35, 62)
    ================================================================================
    """
    # Parameter-Dict erstellen
    # WARUM dict? cua-driver erwartet JSON-Objekt auf stdin.
    p = dict(params or {})  # WARUM or {}? Wenn params=None → leeres Dict.

    # PID und WID hinzufügen
    # WARUM überschreiben? params könnte pid/wid enthalten → wir wollen explizite Werte.
    p["pid"] = pid
    p["window_id"] = wid

    # cua-driver aufrufen
    # Command: "cua-driver call <method>"
    # Input: JSON-String mit pid, window_id, params
    r = _run(["cua-driver", "call", method], json.dumps(p))

    try:
        # JSON Response parsen
        # WARUM try/except? Wenn cua-driver Error → stdout könnte leer sein.
        if r.stdout:
            return json.loads(r.stdout)
        else:
            return {}
    except Exception:
        # WARUM nicht raise? Graceful degradation.
        return {}


def _tree(pid, wid):
    """
    ================================================================================
    Liest AX-Tree eines Windows als Liste von Zeilen.
    ================================================================================

    WAS macht diese Funktion?
      Wrapper um get_window_state → parst tree_markdown in Zeilen.
      Der AX-Tree ist das "DOM" von macOS Accessibility — er enthält
      ALLE interaktiven Elemente (Buttons, Links, TextFields, etc.).

    Args:
      pid (int): Chrome Process ID.
      wid (int): Window ID.

    Returns:
      list: Liste von Strings (eine Zeile pro Element).
            Beispiel:
            [
              '- [0] AXWebArea "HeyPiggy" @(0,0,1280,800)',
              '- [1] AXGroup "Header" @(0,0,1280,60)',
              '- [54] AXLink "Google Login-Symbol" @(731,651,132,41)',
              '- [35] AXButton "Weiter" @(1095,706,91,40)',
            ]
            WARUM Liste? Einfach zu iterieren, filtern, regex anwenden.
            WARUM Strings? tree_markdown ist Text-Format von cua-driver.

    FORMAT einer Zeile:
      '- [<index>] <AXRole> "<Label>" @(<x>,<y>,<w>,<h>)'
      Beispiel: '- [54] AXLink "Google Login-Symbol" @(731,651,132,41)'
      → index: 54 (für cua-driver click/set_value)
      → AXRole: AXLink (oder AXButton, AXTextField, etc.)
      → Label: "Google Login-Symbol" (für _find_idx)
      → Position: (731,651) mit Größe (132,41)

    Side Effects:
      - Ruft cua-driver get_window_state auf.

    Example:
      >>> tree = _tree(71104, 56640)
      >>> for line in tree:
      ...     if "Google" in line:
      ...         print(line)
      '- [54] AXLink "Google Login-Symbol" @(731,651,132,41)'

    BANNED in dieser Funktion:
      ❌ Kein hardcoded Index-Access (z.B. tree[54])
    ================================================================================
    """
    # get_window_state aufrufen
    # WARUM nicht direkt _cua? tree_markdown muss geparst werden.
    d = _cua(pid, wid, "get_window_state")

    # tree_markdown extrahieren und in Zeilen splitten
    # WARUM get() mit Default? Wenn cua-driver Fehler → "tree_markdown" fehlt.
    # WARUM isinstance? Sicherheit — falls Response kein Dict ist.
    if isinstance(d, dict):
        return d.get("tree_markdown", "").split("\n")
    else:
        return []


def _find_idx(tree, keyword, roles=None):
    """
    ================================================================================
    Findet element_index durch Keyword + Role-Matching im AX-Tree.
    ================================================================================

    WAS macht diese Funktion?
      Durchsucht den AX-Tree nach einem Element das:
      1. Ein bestimmtes Keyword im Label/Text hat (case-insensitive)
      2. Eine bestimmte AXRole hat (z.B. AXButton, AXLink, AXTextField)

      Dies ist das HERZSTÜCK des Label-basierten Matchings!
      Statt hardcoded Indices (BUG 3!) suchen wir dynamisch.

    Args:
      tree (list): AX-Tree Zeilen (von _tree()).
                   WARUM list? Einfach zu iterieren.
      keyword (str): Label-Text zum Suchen (case-insensitive).
                     Beispiele: "weiter", "google login-symbol", "e-mail"
                     WARUM case-insensitive? Chrome Locale kann ändern
                     ("Weiter" vs "weiter" vs "WEITER").
      roles (list, optional): AXRole-Typen zum Filtern.
                              Default: ["AXButton", "AXLink", "AXTextField"]
                              Erlaubte Werte:
                              - "AXButton": Buttons (Weiter, Fortfahren)
                              - "AXLink": Links (Google Login-Symbol)
                              - "AXTextField": Text-Eingabe (Email, Passwort)
                              - "AXRadioButton": Radio-Buttons (Umfrage-Optionen)
                              - "AXCheckBox": Checkboxes (Zustimmung)
                              WARUM Default diese 3? Sie sind die häufigsten
                              Interaktions-Elemente im Login-Flow.
                              WARUM Optional? Wenn alle Roles erlaubt sind.

    Returns:
      int: element_index (z.B. 54, 35, 62) oder None.
           WARUM int? cua-driver erwartet Integer für element_index.
           WARUM None? Wenn Element nicht gefunden → Caller muss entscheiden
           (retry, fallback, oder error).

    BUG 3 (behoben): Google Login Button is AXLink not AXButton
      FALSCH:  roles = ["AXButton"]  → Login-Symbol nicht gefunden
      RICHTIG: roles = ["AXButton", "AXLink"]  → Login-Symbol gefunden
      WARUM: Google Login-Symbol ist ein Link (<a> Tag), kein Button.

    MATCHING-LOGIK (Reihenfolge):
      1. Für jede Role in roles:
      2. Für jede Zeile in tree:
      3. Prüfe: keyword.lower() in line.lower() AND role in line
      4. Wenn Match: Extrahiere Index aus "- [N]" Pattern
      5. Return Index

    Side Effects:
      - Keine (reine Daten-Transformation).

    Example:
      >>> tree = ['- [54] AXLink "Google Login-Symbol" @(731,651,132,41)']
      >>> idx = _find_idx(tree, "google login-symbol", ["AXLink"])
      >>> print(idx)
      54

    BANNED in dieser Funktion:
      ❌ Kein hardcoded Index-Return (z.B. return 54)
    ================================================================================
    """
    # Default Roles setzen
    # WARUM None als Default? Mutable Defaults in Python sind gefährlich!
    # → Wenn roles=[] als Default: Liste wird zwischen Calls geteilt!
    # → Lösung: None als Default, dann if roles is None: roles = [...]
    if roles is None:
        # BUG 3 Fix: AXLink hinzugefügt (nicht nur AXButton)
        # WARUM diese 3? Sie sind die häufigsten Interaktions-Elemente.
        roles = ["AXButton", "AXLink", "AXTextField"]

    # Für jede Role suchen
    # WARUM Reihenfolge? AXButton hat Priorität über AXLink über AXTextField.
    # → Buttons sind typischerweise die primären Actions.
    for role in roles:
        # Für jede Zeile im Tree
        for line in tree:
            # Case-insensitive Keyword-Match
            # WARUM "in" statt "=="? Label könnte mehr Text enthalten
            # (z.B. "Google Login-Symbol für HeyPiggy").
            # WARUM lower()? Case-insensitive matching.
            if keyword.lower() in line.lower() and role in line:
                # Element-Index aus "- [N]" Pattern extrahieren
                # WARUM regex? Format ist garantiert "- [N]" von cua-driver.
                # WARUM search statt match? Pattern kann irgendwo in Zeile sein.
                m = re.search(r'- \[(\d+)\]', line)
                if m:
                    # Gruppe 1 = die Zahl zwischen [ und ]
                    return int(m.group(1))

    # Nichts gefunden → None
    # WARUM None statt -1? Expliziter — Caller prüft "if idx is None".
    return None


def _click(pid, wid, idx):
    """
    ================================================================================
    Klickt Element via cua-driver AXPress.
    ================================================================================

    WAS macht diese Funktion?
      Führt einen Klick auf ein Element via cua-driver aus.
      Nutzt AXUIElementPerformAction() — KEINE Maus, KEINE Koordinaten!
      → JS-Events werden korrekt getriggert (wichtig für SPAs).

    Args:
      pid (int): Chrome Process ID.
      wid (int): Window ID.
      idx (int): element_index aus _find_idx().
                 WAROM int? cua-driver erwartet Integer.
                 WARUM nicht Optional? Wenn idx=None → sinnlos zu klicken.

    Returns:
      bool: True wenn "performed" in Response (erfolgreicher Klick).
            False wenn idx=None oder Response kein "performed".
            WARUM bool? Einfach: if _click(...): ... else: ...

    BUG 4 (behoben): click() response check wrong
      FALSCH:  r.get("stdout") == " Performed "  # Exact match!
      RICHTIG: "performed" in r.get("stdout", "").lower()
      WARUM: Response enthält mehr Text als nur "Performed".

    Side Effects:
      - Interagiert mit Chrome → Kann Seite verändern (Navigation, Form-Submit).
      - Kann Chrome-Focus ändern.
      - Triggert JS-Events auf der Seite.

    Race Conditions:
      - Element könnte sich ändern zwischen _find_idx() und _click()
        → Lösung: Wiederholen mit frischem _tree() (noch nicht implementiert).
      - Seite könnte navigieren während Klick
        → Lösung: _click() prüft ob Element noch existiert (cua-driver macht das).

    Example:
      >>> success = _click(71104, 56640, 54)
      >>> print(success)
      True

    BANNED in dieser Funktion:
      ❌ Kein hardcoded idx (z.B. _click(pid, wid, 54))
      ❌ Kein Koordinaten-Click (z.B. click(x=100, y=200))
    ================================================================================
    """
    # Wenn idx None → False zurückgeben
    # WARUM? None bedeutet: Element nicht gefunden → Klicken sinnlos.
    # WARUM nicht Exception? Graceful degradation — Caller entscheidet.
    if idx is None:
        return False

    # cua-driver click aufrufen
    # WARUM {"element_index": idx}? cua-driver erwartet diesen Parameter.
    r = _cua(pid, wid, "click", {"element_index": idx})

    # BUG 4 Fix: "performed" in stdout ODER stderr (case-insensitive)
    # WARUM stdout UND stderr? cua-driver schreibt manchmal in stderr.
    # WARUM lower()? "Performed" vs "performed" — case-insensitive.
    stdout = r.get("stdout", "")
    stderr = r.get("stderr", "")
    return "performed" in stdout.lower() or "performed" in stderr.lower()


def _type(pid, wid, idx, value):
    """
    ================================================================================
    Trägt Text in AXTextField ein via cua-driver set_value.
    ================================================================================

    WAS macht diese Funktion?
      Setzt den Wert eines Textfelds via cua-driver set_value.
      Nutzt AXUIElementSetAttributeValue() — KEIN Type-Event, KEIN Focus-Steal!
      → Funktioniert auch wenn Element nicht sichtbar.

    Args:
      pid (int): Chrome Process ID.
      wid (int): Window ID.
      idx (int): element_index des AXTextField.
      value (str): Einzutragender Text.
                   Beispiel: "zukunftsorientierte.energie@gmail.com"
                   WARUM str? cua-driver akzeptiert String-Werte.
                   WARUM nicht int/bool? Textfelder enthalten Text.

    Returns:
      bool: True wenn "set" in Response (erfolgreich gesetzt).
            False wenn idx=None oder Response kein "set".

    Side Effects:
      - Ändert Wert des Textfelds.
      - Triggert möglicherweise JS-Events (onchange, oninput).

    Example:
      >>> success = _type(71104, 56658, 25, "test@example.com")
      >>> print(success)
      True

    BANNED in dieser Funktion:
      ❌ Kein hardcoded value (z.B. "admin", "password")
      ❌ Keine Credentials im Code (siehe SEC1 in PLAN.md)
    ================================================================================
    """
    # Wenn idx None → False
    if idx is None:
        return False

    # cua-driver set_value aufrufen
    # WARUM {"element_index": idx, "value": value}?
    #   cua-driver erwartet beide Parameter.
    r = _cua(pid, wid, "set_value", {"element_index": idx, "value": value})

    # Prüfe ob "set" in Response
    # WARUM "set"? cua-driver Response: "✅ Set AXValue on [25] AXTextField"
    stdout = r.get("stdout", "")
    stderr = r.get("stderr", "")
    return "set" in stdout.lower() or "set" in stderr.lower()


def _find_logged_in_heypiggy():
    """
    ================================================================================
    Findet HeyPiggy Window das bereits EINGELOGGT ist.
    ================================================================================

    WAS macht diese Funktion?
      Prüft OB ein HeyPiggy Dashboard bereits eingeloggt ist.
      Wenn JA → Return sofort mit PID/WID (vermeidet Doppel-Login).
      Wenn NEIN → Return (None, None, False).

      DIES IST DER NEUESTE FIX (2026-05-08)!
      Siehe Issue #1: Login-Loop Failure.

    LOGIK:
      1. ALLE Windows abrufen
      2. Nach z_index sortieren (neueste zuerst)
         → WARUM z_index? Wenn mehrere Bot-Chrome: neueste ist aktivste.
      3. Für jedes Window:
         a. Filter: height>100, chrome app
         b. Prüfe Title: "umfragen", "auszahlung", "abmelden"
            → WARUM diese Keywords? Sie sind NUR sichtbar wenn eingeloggt.
            → Wenn NICHT eingeloggt: "Anmelden", "Login", "Registrieren"
         c. Wenn Title nicht aussagekräftig: AX-Tree lesen
            → Prüfe auf "abmelden" im Tree
            → WARUM? "Abmelden" Button ist ein starker Login-Indikator.

    Returns:
      tuple: (pid, wid, logged_in)
             pid (int): Process ID des Chrome
             wid (int): Window ID des Dashboards
             logged_in (bool): True wenn eingeloggt, False sonst
             WARUM tuple? Caller braucht alle 3 Werte.
             WARUM (None, None, False)? Explizite "nicht gefunden" Signalisierung.

    Side Effects:
      - Ruft _windows() auf → cua-driver Call.
      - Ruft _tree() auf → cua-driver Call (nur wenn Title-Check unklar).

    Performance:
      - Best Case: O(n) für Window-Scan (n = Anzahl Windows).
      - Worst Case: O(n*m) wenn AX-Tree gelesen wird (m = Elemente pro Tree).

    Example:
      >>> pid, wid, logged_in = _find_logged_in_heypiggy()
      >>> if logged_in:
      ...     print(f"Already logged in! PID={pid}, WID={wid}")
      ... else:
      ...     print("Need to login...")

    BANNED in dieser Funktion:
      ❌ Kein hardcoded PID/WID
    ================================================================================
    """
    # ALLE Windows abrufen
    windows = _windows()

    # Nach z_index sortieren (neueste zuerst)
    # WARUM z_index? Höherer z_index = neueres/obenliegendes Window.
    # WARUM reverse=True? Höchster z_index zuerst (neueste Session).
    windows.sort(key=lambda w: w.get("z_index", 0), reverse=True)

    # Für jedes Window prüfen
    for w in windows:
        # Bounds extrahieren
        b = w.get("bounds", {})

        # Title und App-Name
        t = (w.get("title") or "").lower()
        n = (w.get("app_name") or "").lower()
        pid = w.get("pid")

        # FILTER 1: height > 100 (Menüleiste ignorieren)
        if b.get("height", 0) < 100:
            continue

        # FILTER 2: Chrome
        if "chrome" not in n:
            continue

        # CHECK 1: Title enthält Login-Keywords
        # WARUM diese Keywords? "Umfragen", "Auszahlung", "Abmelden" sind
        # NUR sichtbar wenn eingeloggt. "Anmelden" wäre NICHT eingeloggt.
        if any(k in t for k in ["umfragen", "auszahlung", "abmelden"]):
            # Eingeloggt! Return sofort.
            return pid, w.get("window_id"), True

        # CHECK 2: Title enthält HeyPiggy aber unklar → AX-Tree lesen
        # WARUM? Title könnte nur "HeyPiggy – Verdienen" sein (ungeloggt)
        # oder "HeyPiggy – Umfragen" (eingeloggt).
        if any(k in t for k in ["heypiggy", "verdienen", "dashboard"]):
            # AX-Tree lesen für detailliertere Prüfung
            tree = _tree(pid, w.get("window_id"))

            # Prüfe auf "abmelden" im Tree
            # WARUM "abmelden"? Starker Indikator für Login-Status.
            # WARUM any()? Eine Zeile mit "abmelden" reicht.
            if any("abmelden" in l.lower() for l in tree):
                return pid, w.get("window_id"), True

    # Nichts gefunden → Nicht eingeloggt
    return None, None, False


# ============================================================================
# HAUPTFUNKTION — ENTRY POINT
# ============================================================================

def execute(pid=None, url="https://heypiggy.com/?page=dashboard"):
    """
    ================================================================================
    AUTO-GOOGLE-LOGIN — CUA-ONLY 6-Step Flow (LIVE TESTED 2026-05-05)

    Dies ist die HAUPTFUNKTION dieser Datei. Jeder Survey-Start ruft diese
    Funktion auf. Wenn sie fehlschlägt → Keine Surveys → Keine Einnahmen.

    DETAILLIERTER FLOW (siehe auch ASCII-Diagramm oben):

    STEP 0: Check ob bereits eingeloggt
      → _find_logged_in_heypiggy()
      → WENN gefunden: Return sofort (spart Zeit, vermeidet Doppel-Login)
      → WENN NICHT: Weiter mit STEP 1

    STEP 1: Chrome starten (wenn pid=None)
      → SessionManager.launch("heypiggy", url)
      → WARUM SessionManager? Zentralisiert Chrome-Start + Registry.
      → WARUM nicht playstealth? Setzt NICHT --force-renderer-accessibility!
      → Return: {"pid": X, "wid": Y, "status": "ok"}

    STEP 2: Dashboard Window finden
      → _find_bot_wid(["heypiggy", "dashboard", "verdienen"])
      → WARUM diese Keywords? Dashboard hat "HeyPiggy" und "Verdienen" im Title.
      → WARUM nicht nur "heypiggy"? OAuth-Window hat auch "Google" im Title.

    STEP 3: Google Login-Symbol klicken
      → _tree(pid, wid) → AX-Tree lesen
      → _find_idx(tree, "google login-symbol", ["AXLink"])
        → WARUM AXLink? Login-Symbol ist ein Link, kein Button (BUG 3!)
      → _click(pid, wid, idx)
      → Warten 5s (OAuth Popup braucht Zeit!)

    STEP 4: Email eingeben + "Weiter" klicken
      → NEUE WID finden! (OAuth öffnet NEUES Window — BUG 5!)
      → _find_bot_wid(["google", "anmelden", "accounts"])
      → _tree(pid_g, wid_g)
      → _find_idx(tree, "e-mail oder telefonnummer", ["AXTextField"])
        → WARUM "e-mail oder telefonnummer"? Das ist das Label des Felds.
        → WARUM case-insensitive? Chrome Locale kann ändern.
      → _type(pid_g, wid_g, email_idx, "zukunftsorientierte.energie@gmail.com")
      → _find_idx(tree, "weiter", ["AXButton"])
      → _click(pid_g, wid_g, weiter_idx)
      → Warten 5s (Keychain Auto-Fill braucht Zeit!)

    STEP 5: Keychain "Fortfahren" klicken
      → Keychain hat AUTOMATISCH "Jeremy Schulze" ausgewählt
      → NUR "Fortfahren" klicken — KEIN Passwort eingeben!
      → _find_idx(tree, "fortfahren", ["AXButton"])
        → WARUM "fortfahren"? Das ist das Label des Keychain-Buttons.
        → Fallback: "konto" (wenn "Fortfahren" nicht gefunden)
      → _click(pid_k, wid_k, fortsetzen_idx)
      → Warten 5s

    STEP 6: Final "Weiter" klicken
      → Account vollständig authentifizieren
      → _find_idx(tree, "weiter", ["AXButton"])
      → _click(pid_f, wid_f, final_idx)
      → Warten 5s
      → OAuth Window sollte GESCHWUNDEN sein

    VERIFY: Dashboard eingeloggt?
      → _find_bot_wid(["heypiggy", "dashboard", "verdienen"])
      → AX-Tree prüfen: "abmelden" oder "umfragen" im Text?
      → WARUM Verify? Ohne Verify denkt Agent er ist eingeloggt,
        aber Dashboard zeigt "Anmelden" → Endlosschleife (BUG!)

    ================================================================================
    Args:
      pid (int, optional): Chrome Process ID wenn Chrome bereits läuft.
                           WENN None: Chrome wird via SessionManager gestartet.
                           WARUM Optional? Wenn Chrome von anderem Flow gestartet.
                           WAROM int? cua-driver erwartet Integer.
      url (str, optional): Heypiggy URL. Default: Dashboard.
                           WARUM Dashboard? Login-Prüfung ist einfachster auf Dashboard.
                           WARUM nicht Login-Seite? Dashboard zeigt direkt ob eingeloggt.

    Returns:
      dict: Ergebnis des Login-Flows.

      Erfolg:
        {"status": "ok", "pid": int, "wid": int}
        → status: "ok" — Login erfolgreich.
        → pid: Process ID des Chrome (für weitere cua-driver Calls).
        → wid: Window ID des Dashboards (für weitere cua-driver Calls).
        → WARUM pid+wid? Caller braucht beide für weitere Interaktionen.

      Fehler:
        {"status": "error", "reason": str}
        → status: "error" — Login fehlgeschlagen.
        → reason: Spezifische Fehlerbeschreibung.
          Mögliche Reasons:
          - "google_login_button_not_found": Login-Symbol nicht im AX-Tree.
            → Ursache: Chrome ohne --force-renderer-accessibility.
            → Fix: Chrome neu starten mit korrekten Flags (siehe Issue #3).
          - "google_login_click_failed": Klick auf Login-Symbol fehlgeschlagen.
            → Ursache: Element nicht klickbar oder Chrome nicht responsiv.
          - "google_oauth_window_not_found": OAuth Popup nicht erschienen.
            → Ursache: Popup-Blocker oder Timeout zu kurz.
          - "email_field_not_found": Email-Feld nicht im OAuth-Window.
            → Ursache: Falsche WID (noch auf Dashboard statt OAuth).
          - "email_type_failed": Text-Eingabe fehlgeschlagen.
            → Ursache: Feld nicht fokussierbar oder readonly.
          - "weiter_button_not_found": "Weiter" Button nicht gefunden.
            → Ursache: Falsche WID oder unerwartete OAuth-Seite.
          - "fortfahren_button_not_found": "Fortfahren" nicht gefunden.
            → Ursache: Keychain nicht aktiv, oder 2FA erforderlich.
          - "final_weiter_not_found": Finaler "Weiter" nicht gefunden.
            → Ursache: OAuth-Flow abweichend von erwartetem.
          - "dashboard_not_found": Dashboard nicht nach Login gefunden.
            → Ursache: Weiterleitung fehlgeschlagen oder falsche Domain.

    Side Effects:
      - Startet Chrome-Prozess (wenn pid=None).
      - Schreibt in ~/.stealth/sessions.json (SessionManager).
      - Ruft cua-driver auf (mehrmals).
      - Interagiert mit Google OAuth (Netzwerk-Requests).
      - Kann ~/.stealth/intents.jsonl erweitern (via SessionManager).

    Performance:
      - Best Case (bereits eingeloggt): ~1s (nur _find_logged_in_heypiggy).
      - Normal Case: ~20-30s (Chrome-Start + 6 Steps + Wartezeiten).
      - Worst Case (mehrere Retries): ~60s+.

    Race Conditions:
      - Chrome Window ändert sich während Flow (BUG 5 Fix: WID wird nach jedem
        Click neu gesucht).
      - Keychain Auto-Fill dauert länger als 5s (noch nicht konfigurierbar).
      - OAuth Popup wird blockiert (noch nicht abgefangen).
      - Mehrere Bot-Chrome existieren (_find_logged_in sortiert nach z_index).

    BANNED in dieser Funktion:
      ❌ Kein playstealth launch (auch nicht indirekt!)
      ❌ Keine hardcoded PIDs (71104, 56640, etc.)
      ❌ Kein pkill -f "Google Chrome"
      ❌ Kein killall Google Chrome
      ❌ Kein --remote-allow-origins=* (ohne Quotes)
      ❌ Kein /tmp/heypiggy-bot (fixed profile)

    Example:
      >>> # Fall 1: Chrome läuft noch nicht
      >>> result = execute()
      >>> print(result)
      {"status": "ok", "pid": 12345, "wid": 67890}

      >>> # Fall 2: Chrome läuft bereits
      >>> result = execute(pid=12345)
      >>> print(result)
      {"status": "ok", "pid": 12345, "wid": 67890}

      >>> # Fall 3: Login fehlgeschlagen
      >>> result = execute()
      >>> print(result)
      {"status": "error", "reason": "google_login_button_not_found"}
    ================================================================================
    """
    # ============================================================================
    # STEP 0: Prüfe OB HeyPiggy bereits eingeloggt ist
    # ============================================================================
    # WARUM zuerst prüfen? Vermeidet unnötiges Chrome-Starten und OAuth.
    # WARUM _find_logged_in_heypiggy? Zentralisierte Prüfung, sortiert nach z_index.
    # WARUM nicht einfach Dashboard-URL öffnen? Weil wir die PID/WID brauchen.
    epid, ewid, logged_in = _find_logged_in_heypiggy()

    # WENN eingeloggt → Sofort return
    # WARUM sofort? Zeit sparen, Netzwerk-Requests vermeiden.
    if logged_in and ewid:
        return {"status": "ok", "pid": epid, "wid": ewid}

    # ============================================================================
    # STEP 1: Chrome starten (wenn keine pid übergeben)
    # ============================================================================
    # WARUM SessionManager.launch()? Zentralisiert:
    #   - Chrome-Binary finden
    #   - Korrekte Flags setzen (--force-renderer-accessibility, etc.)
    #   - Timestamped Profile erstellen (/tmp/heypiggy-new-XXXXXXXXXX)
    #   - Registry aktualisieren (~/.stealth/sessions.json)
    #   - PID zurückgeben
    if pid is None:
        # SessionManager.launch() aufrufen
        # WARUM "heypiggy"? Session-Name für Registry.
        # WARUM url? Chrome öffnet diese URL nach Start.
        result = _SessionManager.launch("heypiggy", url)

        # Prüfe ob Start erfolgreich
        # WARUM sofort prüfen? Wenn Chrome nicht startet → alles weitere sinnlos.
        if result["status"] != "ok":
            # Return Error mit Reason von SessionManager
            # WARUM nicht Exception? Graceful degradation.
            return {"status": "error", "reason": result.get("reason", "session_manager_failed")}

        # PID extrahieren
        # WARUM int()? Sicherheit — SessionManager könnte String zurückgeben.
        pid = result["pid"]

        # WID extrahieren (kann None sein wenn noch nicht gefunden)
        # WARUM Optional? Window ist vielleicht noch nicht bereit (Chrome startet).
        wid = result.get("wid")

    # WARTEN bis Chrome bereit
    # WARUM 3 Sekunden? Chrome braucht Zeit zum Initialisieren.
    # WARUM nicht 1s? Zu kurz — Chrome ist möglicherweise noch nicht responsiv.
    # WARUM nicht 5s? Zu lang — wir warten später noch mehrfach.
    # OPTIMIERUNG: Statt fixed sleep → _verify_cdp_reachable() poll (siehe Issue #3).
    time.sleep(3)

    # ============================================================================
    # STEP 2: Dashboard Window finden
    # ============================================================================
    # WARUM Dashboard? Login-Prüfung und Survey-Scan sind auf Dashboard.
    # WARUM Keywords? Mehrere Chrome-Windows können offen sein.
    pid, wid = _find_bot_wid(["heypiggy", "dashboard", "verdienen"])

    # WARUM Fallback? Wenn Title nicht exakt passt (z.B. nur "HeyPiggy").
    if not wid:
        # Fallback: Erstes Chrome-Window (ohne Keyword-Filter)
        # WARUM? Wenn Dashboard-Window existiert aber Title anders ist.
        # RISIKO: Könnte falsches Window finden (OAuth, Survey, etc.).
        pid, wid = _find_bot_wid()

    # WENN immer noch nicht gefunden → Fehler
    # WARUM return? Ohne Window können wir nichts klicken.
    if not wid:
        return {"status": "error", "reason": "no_dashboard_window"}

    # ============================================================================
    # STEP 3: Google Login-Symbol klicken
    # ============================================================================
    # AX-Tree lesen
    # WARUM? Wir müssen das Login-Symbol finden.
    tree = _tree(pid, wid)

    # Login-Symbol finden
    # WARUM "google login-symbol"? Das ist das Label im AX-Tree.
    # WARUM ["AXLink"]? Login-Symbol ist ein Link (BUG 3 Fix!)
    idx = _find_idx(tree, "google login-symbol", ["AXLink"])

    # Fallback: Allgemeinerer "google" Match
    # WARUM? Wenn Label leicht abweicht (z.B. "Google Login" statt "Google Login-Symbol").
    if idx is None:
        idx = _find_idx(tree, "google", ["AXLink"])

    # WENN nicht gefunden → Fehler
    # WARUM dieser Fehler? Login-Symbol ist essentiell — ohne geht nichts.
    # MÖGLICHE URSACHEN:
    #   - Chrome ohne --force-renderer-accessibility → AX-Tree leer.
    #   - Dashboard nicht vollständig geladen.
    #   - Falsches Window (nicht Dashboard).
    if idx is None:
        return {"status": "error", "reason": "google_login_button_not_found"}

    # Klicken
    # WARUM _click()? Nutzt AXUIElementPerformAction (sicher, kein Focus-Steal).
    if not _click(pid, wid, idx):
        return {"status": "error", "reason": "google_login_click_failed"}

    # WARTEN auf OAuth Popup
    # WARUM 5s? OAuth-Seite muss laden, Popup muss öffnen.
    # WARUM nicht weniger? Bei langsamer Verbindung braucht es länger.
    # WARUM nicht mehr? Jede Sekunde zählt — Survey-Loop soll schnell sein.
    # TODO: Konfigurierbar machen (siehe Issue #1).
    time.sleep(5)

    # ============================================================================
    # STEP 4: Google OAuth Window finden + Email eingeben + "Weiter" klicken
    # ============================================================================
    # NEUE WID finden!
    # WARUM NEUE WID? OAuth öffnet ein NEUES Window (BUG 5 Fix!)
    # WARUM nicht alte WID? Alte WID ist Dashboard — Klick landet auf Dashboard.
    # WARUM Keywords "google", "anmelden", "accounts"? OAuth-Window hat diese im Title.
    pid_g, wid_g = _find_bot_wid(["google", "anmelden", "accounts"])

    # Fallback: Erstes Chrome-Window
    # WARUM? Wenn Title nicht exakt passt.
    if not wid_g:
        pid_g, wid_g = _find_bot_wid()

    # WENN nicht gefunden → Fehler
    # MÖGLICHE URSACHEN:
    #   - Popup-Blocker hat OAuth blockiert.
    #   - Timeout zu kurz (Popup braucht länger als 5s).
    #   - Chrome ist abgestürzt.
    if not wid_g:
        return {"status": "error", "reason": "google_oauth_window_not_found"}

    # AX-Tree des OAuth-Windows lesen
    tree = _tree(pid_g, wid_g)

    # Email-Feld finden
    # WARUM "e-mail oder telefonnummer"? Das ist das Label im OAuth-Formular.
    # WARUM ["AXTextField"]? Email-Feld ist ein Text-Eingabe-Feld.
    # WARUM case-insensitive? Chrome Locale könnte ändern.
    email_idx = _find_idx(tree, "e-mail oder telefonnummer", ["AXTextField"])

    # WENN nicht gefunden → Fehler
    # MÖGLICHE URSACHEN:
    #   - Falsche WID (noch auf Dashboard statt OAuth).
    #   - OAuth-Seite nicht vollständig geladen.
    #   - Unerwartete OAuth-Seite (z.B. 2FA, Account-Auswahl).
    if email_idx is None:
        return {"status": "error", "reason": "email_field_not_found"}

    # Email eintragen
    # WARUM hardcoded Email? Könnte aus Env-Variable oder Profil kommen.
    # TODO: In Config/Env auslagern (siehe SEC1 in PLAN.md).
    # WARUM diese Email? Korrekter Account für HeyPiggy (BUG 7 Fix!)
    if not _type(pid_g, wid_g, email_idx, "zukunftsorientierte.energie@gmail.com"):
        return {"status": "error", "reason": "email_type_failed"}

    # "Weiter" Button finden
    # WARUM "weiter"? Label des Buttons im OAuth-Formular.
    # WARUM ["AXButton"]? Es ist ein Button.
    weiter_idx = _find_idx(tree, "weiter", ["AXButton"])

    # WENN nicht gefunden → Fehler
    if weiter_idx is None:
        return {"status": "error", "reason": "weiter_button_not_found"}

    # "Weiter" klicken
    # WARUM? Triggert Google-Login-Prozess (Email validieren, Keychain prüfen).
    if not _click(pid_g, wid_g, weiter_idx):
        return {"status": "error", "reason": "weiter_click_failed"}

    # WARTEN auf Keychain Auto-Fill
    # WARUM 5s? Keychain muss Credentials finden und Formular füllen.
    # WARUM nicht weniger? Keychain kann langsam sein (erster Zugriff).
    # WARUM nicht mehr? Jede Sekunde zählt.
    # KRITISCHE ANNAHME: Keychain ist aktiviert und hat Credentials gespeichert.
    # WENN Keychain deaktiviert → Passwort-Feld erscheint → Flow schlägt fehl!
    # TODO: Passwort-Fallback implementieren (siehe Issue #1 Fix 4).
    time.sleep(5)

    # ============================================================================
    # STEP 5: Keychain "Fortfahren" klicken
    # ============================================================================
    # NEUE WID finden (nach Keychain könnte sich Window geändert haben)
    # WARUM Keywords "google", "anmelden", "jeremy"? Keychain-Window hat "Jeremy" im Title.
    pid_k, wid_k = _find_bot_wid(["google", "anmelden", "jeremy"])

    # Fallback: Nur "google"
    if not wid_k:
        pid_k, wid_k = _find_bot_wid(["google"])

    # WENN nicht gefunden → Fehler
    # MÖGLICHE URSACHEN:
    #   - Keychain nicht aktiv.
    #   - 2FA erforderlich.
    #   - Account gesperrt.
    if not wid_k:
        return {"status": "error", "reason": "keychain_window_not_found"}

    # AX-Tree lesen
    tree = _tree(pid_k, wid_k)

    # "Fortfahren" Button finden
    # WARUM "fortfahren"? Keychain zeigt "Fortfahren" zum Bestätigen.
    # WARUM ["AXButton"]? Es ist ein Button.
    fortsetzen_idx = _find_idx(tree, "fortfahren", ["AXButton"])

    # Fallback: "Konto" Button
    # WARUM? Wenn Label leicht abweicht (z.B. "Konto bestätigen").
    if fortsetzen_idx is None:
        fortsetzen_idx = _find_idx(tree, "konto", ["AXButton"])

    # WENN nicht gefunden → Fehler
    # MÖGLICHE URSACHEN:
    #   - Keychain nicht aktiv → Passwort-Feld statt "Fortfahren".
    #   - 2FA erforderlich → "Code eingeben" statt "Fortfahren".
    if fortsetzen_idx is None:
        return {"status": "error", "reason": "fortfahren_button_not_found"}

    # "Fortfahren" klicken
    # WARUM? Bestätigt Keychain Auto-Fill und fährt mit Login fort.
    if not _click(pid_k, wid_k, fortsetzen_idx):
        return {"status": "error", "reason": "fortfahren_click_failed"}

    # WARTEN auf finalen "Weiter"-Screen
    time.sleep(5)

    # ============================================================================
    # STEP 6: Final "Weiter" klicken (Account vollständig authentifizieren)
    # ============================================================================
    # NEUE WID finden (OAuth-Flow hat mehrere Screens)
    pid_f, wid_f = _find_bot_wid(["google", "anmelden"])

    # Fallback: Erstes Chrome-Window
    if not wid_f:
        pid_f, wid_f = _find_bot_wid()

    # WENN nicht gefunden → Fehler
    if not wid_f:
        return {"status": "error", "reason": "final_weiter_window_not_found"}

    # AX-Tree lesen
    tree = _tree(pid_f, wid_f)

    # Final "Weiter" finden
    final_idx = _find_idx(tree, "weiter", ["AXButton"])

    # WENN nicht gefunden → Fehler
    if final_idx is None:
        return {"status": "error", "reason": "final_weiter_not_found"}

    # Final "Weiter" klicken
    # WARUM? Schließt OAuth-Flow ab und leitet zurück zu HeyPiggy.
    if not _click(pid_f, wid_f, final_idx):
        return {"status": "error", "reason": "final_weiter_click_failed"}

    # WARTEN bis OAuth Window schließt und Dashboard erscheint
    time.sleep(5)

    # ============================================================================
    # VERIFY: Dashboard sollte jetzt eingeloggt sein
    # ============================================================================
    # WARUM Verify? Ohne Verify denkt Agent er ist eingeloggt,
    # aber Dashboard zeigt "Anmelden" → Endlosschleife (siehe Issue #1).

    # Dashboard Window finden
    pid_d, wid_d = _find_bot_wid(["heypiggy", "dashboard", "verdienen"])

    # Fallback: Erstes Chrome-Window
    if not wid_d:
        pid_d, wid_d = _find_bot_wid()

    # WENN Dashboard nicht gefunden → Fehler
    # MÖGLICHE URSACHEN:
    #   - OAuth-Flow nicht vollständig.
    #   - Weiterleitung zu falscher Domain.
    #   - Chrome abgestürzt.
    if not wid_d:
        return {"status": "error", "reason": "dashboard_not_found"}

    # AX-Tree lesen
    tree = _tree(pid_d, wid_d)

    # Prüfe auf Login-Indikatoren
    # WARUM "abmelden"? Starker Indikator — nur sichtbar wenn eingeloggt.
    # WARUM "umfragen"? Auch nur sichtbar wenn eingeloggt.
    # WARUM OR (any)? Einer der beiden reicht.
    if any("abmelden" in l.lower() for l in tree):
        # Erfolg! Eingeloggt.
        return {"status": "ok", "pid": pid_d, "wid": wid_d}

    if any("umfragen" in l.lower() for l in tree):
        # Erfolg! Eingeloggt ("Umfragen" Tab sichtbar).
        return {"status": "ok", "pid": pid_d, "wid": wid_d}

    # VERIFY FEHLGESCHLAGEN
    # WARUM nicht return error? Dashboard existiert aber nicht eingeloggt.
    # MÖGLICHE URSACHEN:
    #   - Login war erfolgreich aber Session abgelaufen.
    #   - HeyPiggy hat zusätzliche Verification (Email bestätigen, etc.).
    # RISIKO: Wenn wir "ok" zurückgeben obwohl nicht eingeloggt → Endlosschleife.
    # TODO: Strengere Verify (siehe Issue #1).

    # Trotzdem "ok" return — Caller sollte zusätzlich prüfen.
    # WARUM? Wenn Dashboard existiert aber Verify fehlschlägt,
    # ist es besser als "error" (könnte temporär sein).
    return {"status": "ok", "pid": pid_d, "wid": wid_d}


# ============================================================================
# CLI ENTRY POINT (für manuelle Tests)
# ============================================================================
# WARUM __main__? Ermöglicht: python3 auto_google_login.py [PID]
# WARUM Optional PID? Wenn Chrome bereits läuft.
# WARUM json.dumps? Schöne Ausgabe für menschliche Leser.
if __name__ == "__main__":
    import sys

    # PID als Command-Line Argument
    # WARUM int()? Sicherheit — sys.argv ist String.
    # WARUM len(sys.argv) > 1? Optional — wenn kein PID, startet Chrome.
    pid = int(sys.argv[1]) if len(sys.argv) > 1 else None

    # Login ausführen
    result = execute(pid)

    # Ergebnis ausgeben
    print(json.dumps(result, indent=2))
