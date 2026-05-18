#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""================================================================================
================================================================================
SURVEY-CLI — Standalone Survey Automation CLI (NEMO v2.0 + Legacy Support)
================================================================================
================================================================================

WAS IST DIESE DATEI?
  Diese Datei ist der HAUPT-EINSTIEGSPUNKT für die Survey-Automation.
  Sie ist ein Standalone CLI-Tool (keine Abhängigkeit von opencode).
  Unterstützt mehrere Modi: login, scan, run, loop, watch, balance, status,
  doctor, kill, summary, opencode, profile.

  Warum ist diese Datei so wichtig?
    - Sie ist der EINSTIEG für menschliche Operatoren (und Agents).
    - Sie koordiniert ALLE Survey-Aktivitäten.
    - Sie enthält den WATCH DAEMON — der 24/7 Survey-Loop.
    - WENN diese Datei fehlschlägt → Keine Einnahmen.

ARCHITEKTUR:
  ┌─────────────────────────────────────────────────────────────────────────────┐
  │                         survey-cli/survey.py                                  │
  │                           (DU BIST HIER)                                    │
  └─────────────────────────────────────────────────────────────────────────────┘
           │
     ┌─────┴──────┬────────┬────────┬────────┬────────┬────────┐
     ▼            ▼        ▼        ▼        ▼        ▼        ▼
  cmd_login   cmd_scan cmd_run cmd_loop cmd_watch cmd_*  (weitere)
     │            │        │        │        │
     ▼            ▼        ▼        ▼        ▼
  auto_google  scanner  runner   runner   runner
  _login.py    (chrome) (NEMO)   (NEMO)   (NEMO loop)
     │                                        │
     ▼                                        ▼
  cua-driver                            WATCH DAEMON
  (6-Step OAuth)                        (24/7 Poller)

  WARUM argparse statt Click/Typer?
    - Einfachheit: Keine externe Dependency nötig.
    - Standardlib: argparse ist immer verfügbar.
    - Dies ist ein Standalone-Script, kein komplexes Framework.

DEPENDENZEN (Was braucht diese Datei?):
  - survey.runner: SurveyRunner, RunnerConfig (NEMO Engine)
  - survey.scanner: scan_dashboard, read_balance (Dashboard-Analyse)
  - survey.chrome: is_chrome_alive, find_bot_tabs, find_dashboard_ws
  - survey.autodoc: log_session, generate_summary (Logging/Doku)
  - survey.accessibility: ensure_accessibility, start_cua_daemon
  - cli.modules.auto_google_login: execute() (Google OAuth)
  - survey.nim: get_nim() (NVIDIA NIM Client)
  - survey.snapshot: generate_snapshot() (Compact Snapshot)
  - survey.opencode_bridge: delegate_task() (OpenCode Integration)
  - Standardlib: sys, os, json, time, argparse, pathlib
  - Third-party: websocket-client (für CDP WebSocket)

ABHÄNGIGE DATEIEN (Was bricht wenn diese Datei fehlt?):
  - KEINE direkten Abhängigkeiten (diese Datei ist der Entry Point).
  - Aber: Alle Survey-Flows starten hier → WENN diese Datei fehlt,
    können keine Surveys ausgeführt werden.

BANNED METHODS — NIEMALS VERWENDEN (siehe /banned.md):
  ❌ playstealth launch — setzt NICHT --force-renderer-accessibility
  ❌ webauto-nodriver — ABSOLUT BANNED
  ❌ cua-driver click (raw element_index) — instabil, nutze tool_click.py
  ❌ --remote-allow-origins=* (ohne Quotes) — zsh glob expansion
  ❌ /tmp/heypiggy-bot (fixed profile) — korruptiert nach Neustart
  ❌ Hardcoded PIDs — dynamisch, niemals hardcodieren
  ❌ pkill -f "Google Chrome" — tötet USER Chrome
  ❌ killall Google Chrome — tötet ALLE Chrome
  ❌ skylight-cli click --element-index — Index instabil

HISTORY / CHANGELOG:
  2026-05-08: MASSIVE DOKUMENTATION hinzugefügt (alle Funktionen, alle Konstanten)
    → WARUM? IndentationError zeigte: Code war nicht ausreichend dokumentiert.
    → IndentationError: survey.py:199, 8 spaces statt 4 (behoben in a8ceca7)
    → VERIFIZIERUNG: python3 -m py_compile survey.py

  2026-05-07: IndentationError behoben (survey.py:199)
    → WARUM: SyntaxError blockierte survey.py komplett.
    → WAS: 8 spaces → 4 spaces (6 Zeilen nach import Statement).
    → DATEI: survey-cli/survey.py:199
    → VERIFIZIERUNG: python3 -m py_compile survey.py

  2026-05-06: 211 Unit Tests für 15 tools/modules hinzugefügt
    → WARUM: Keine Tests = keine Verifikation von Änderungen.
    → WAS: pytest Suite mit 211 Tests.
    → VERIFIZIERUNG: pytest (alle 211 Tests passen)

  2026-05-05: Watch Daemon mit Crash Recovery
    → WARUM: Survey-Loop crashte bei Chrome-Absturz.
    → WAS: Signal Handler (SIGINT/SIGTERM), Exponential Backoff,
           Graceful Shutdown, JSONL Logging.

  2026-05-04: Initialer NEMO Support (Compact Snapshot + NIM)
    → WARUM: cua-driver Loop war zu langsam und instabil.
    → WAS: SurveyRunner mit NEMO Engine integriert.

USAGE:
  # Login
  ./survey.py login

  # Scan Dashboard
  ./survey.py scan

  # Einzelne Survey per ID
  ./survey.py run --id 66846193

  # Einzelne Survey per URL
  ./survey.py run --url https://...

  # Auto-Loop (max 10 Surveys)
  ./survey.py loop --max 10

  # 24/7 Watch Daemon
  ./survey.py watch --interval 60 --max 3

  # Status checken
  ./survey.py status

  # Full Diagnostic
  ./survey.py doctor

  # Bot Chrome sicher beenden
  ./survey.py kill

ENVIRONMENT VARIABLES:
  NVIDIA_API_KEY      Required für Nemotron 3 Omni (NEMO Mode)
  NVIDIA_MODEL        Model Name (default: nvidia/nemotron-3-nano-omni-30b-a3b-reasoning)
  SURVEY_PORT         CDP Port (default: 9999)
  SURVEY_DEBUG        Debug Mode (truthy = verbose output)
  SURVEY_WAIT         Wait zwischen Actions in Sekunden (default: 3.0)

================================================================================
================================================================================
"""

# ============================================================================
# IMPORTS
# ============================================================================
# WARUM sys? Für sys.path Manipulation (Imports aus Parent-Verzeichnis).
# WARUM sys.path.insert? Ermöglicht relative Imports aus Parent-Dir.
# WARUM os? Für Umgebungsvariablen (NVIDIA_API_KEY, SURVEY_PORT), Pfade.
# WARUM json? Für CDP WebSocket Nachrichten (JSON-RPC über WebSocket).
# WARUM time? Für Delays, Timestamps, Backoff-Berechnung.
# WARUM argparse? CLI-Argument-Parsing. Standardlib, keine externe Dependency.
# WARUM Path? Für plattform-unabhängige Pfad-Manipulation.
import sys
import os
import json
import time
import argparse
from pathlib import Path

# ============================================================================
# IMPORT-PATH KONFIGURATION
# ============================================================================
# WARUM diese Manipulation?
#   survey.py kann aus verschiedenen Verzeichnissen aufgerufen werden:
#   - Aus survey-cli/ (direkt)
#   - Aus stealth-runner/ (als Modul)
#   - Aus irgendwo anders
#   → Wir müssen sicherstellen dass cli.modules und survey.* importierbar sind.
#
# WARUM insert(0, ...)?
#   Unser Parent-Dir sollte VOR anderen Pfaden durchsucht werden.
#   → Vermeidet Konflikte mit system-weiten Paketen.
#
# WARUM _stealth_root?
#   Der Workspace-Root ist 2 Ebenen über survey.py:
#   /workspace/stealth-runner/survey-cli/survey.py
#   → _stealth_root = /workspace/stealth-runner/
#   → Dort liegen cli/modules/ und src/

# Aktuelles Verzeichnis von survey.py
_survey_cli_dir = os.path.dirname(os.path.abspath(__file__))

# Parent-Verzeichnis (stealth-runner/)
_stealth_root = os.path.dirname(_survey_cli_dir)

# survey-cli/ zu sys.path hinzufügen (für survey.* Imports)
if _survey_cli_dir not in sys.path:
    sys.path.insert(0, _survey_cli_dir)

# stealth-runner/ zu sys.path hinzufügen (für cli.modules, src Imports)
if _stealth_root not in sys.path:
    sys.path.insert(0, _stealth_root)


# ============================================================================
# KONSTANTEN
# ============================================================================
# WARUM DEFAULT_PORT = 9999?
#   CDP (Chrome DevTools Protocol) lauscht auf einem Port.
#   9999 ist unser Konvention — nicht reserviert, leicht zu merken.
#   WARUM nicht 9222? 9222 ist Chrome's Default-CDP-Port, aber wir wollen
#   einen festen Port für unsere Bot-Instanz.
#   WARUM nicht 8080? 8080 wird oft von Webservern genutzt.
DEFAULT_PORT = 9999

# WARUM DEFAULT_INTERVAL = 30?
#   Poll-Interval für Watch Daemon.
#   Nicht zu kurz (verbraucht CPU, überlastet Dashboard)
#   Nicht zu lang (verpasst Surveys die schnell weg sind)
#   Erfahrungswert: 30s = guter Kompromiss.
DEFAULT_INTERVAL = 30

# WARUM DEFAULT_MAX_SURVEYS = 5?
#   Max Surveys pro Loop/Watch-Cycle.
#   Nicht zu viele (Qualität leidet, Captcha-Rate steigt)
#   Nicht zu wenige (verschwendet Chancen)
#   Erfahrungswert: 5 = 3-5 min pro Cycle bei ~1min pro Survey.
DEFAULT_MAX_SURVEYS = 5

# WARUM DEFAULT_BALANCE_TARGET = 5.0?
#   Watch Daemon stoppt wenn dieses Guthaben erreicht ist.
#   5.00€ = Auszahlungsschwelle bei HeyPiggy (typisch).
#   WARUM float? HeyPiggy zeigt Cent-Beträge (z.B. 3.47€).
DEFAULT_BALANCE_TARGET = 5.0

# WARUM MAX_CONSECUTIVE_ERRORS = 20?
#   Ursprünglich 5, aber Surveys scheitern OFT an Captchas.
#   Bei 5: Watch Daemon stoppt nach 5 Captcha-Fehlern.
#   Bei 20: Toleranter — gibt genug Chancen für erfolgreiche Surveys.
#   WARUM nicht 50? Zu tolerant — echte Probleme werden nicht erkannt.
MAX_CONSECUTIVE_ERRORS = 20


# ============================================================================
# KOMMANDO-FUNKTIONEN — Jede Funktion EXTREM dokumentiert
# ============================================================================

def cmd_login(args):
    """
    ================================================================================
    KOMMANDO: login — Heypiggy Google OAuth Login via cua-driver
    ================================================================================

    WAS macht diese Funktion?
      Delegiert an cli.modules.auto_google_login.execute().
      Dies ist ein Thin-Wrapper — die eigentliche Logik ist in auto_google_login.py.

    Args:
      args (Namespace): argparse Namespace. Enthält args.port (für Logging).
                        WARUM wird port nicht genutzt? auto_google_login findet
                        Chrome dynamisch (nicht nur über Port).

    Returns:
      dict: Login-Ergebnis.
            {"status": "ok", "pid": int, "wid": int} — Erfolg
            {"status": "error", "reason": str} — Fehler

    Side Effects:
      - Ruft auto_google_login.execute() auf.
      - Kann Chrome starten (wenn nicht läuft).
      - Schreibt in ~/.stealth/sessions.json (via SessionManager).
      - Interagiert mit Google OAuth (Netzwerk).

    BANNED in dieser Funktion:
      ❌ Kein playstealth launch (auch nicht indirekt!)
    ================================================================================
    """
    # Import der Login-Funktion
    # WARUM lazy import? Vermeidet zirkuläre Imports beim Modul-Load.
    # WARUM from cli.modules? cli.modules liegt im Parent-Verzeichnis (stealth-runner/).
    from cli.modules.auto_google_login import execute as google_login

    # Login ausführen
    # WARUM execute()? Das ist die Hauptfunktion in auto_google_login.py.
    # WARUM kein pid übergeben? auto_google_login findet Chrome selbst (oder startet es).
    result = google_login()

    # Status extrahieren
    status = result.get("status")

    # Ergebnis ausgeben
    if status == "ok":
        # Erfolg: PID und WID anzeigen
        # WARUM? Menschlicher Operator (oder Agent) braucht diese für Debugging.
        print(f"✅ Login successful — PID={result.get('pid')}, WID={result.get('wid')}")
    else:
        # Fehler: Reason anzeigen
        # WARUM? Ermöglicht schnelle Diagnose ohne in Logs zu suchen.
        print(f"❌ Login failed: {result.get('reason', 'unknown')}")

    return result


def cmd_scan(args):
    """
    ================================================================================
    KOMMANDO: scan — Dashboard nach verfügbaren Surveys scannen
    ================================================================================

    WAS macht diese Funktion?
      Scannt das HeyPiggy Dashboard nach verfügbaren Survey-IDs.
      Filtert Provider (purespectrum, surveyrouter werden übersprungen).
      Zeigt Survey-Details (ID, Provider, Status, URL-Vorschau).

    Args:
      args (Namespace):
        - args.port: CDP Port (default: 9999)
        - args.all: Wenn True, zeigt ALLE Provider (inkl. blocked).
                    WARUM? Manchmal will man blocked Provider sehen (Debugging).

    Returns:
      list: Liste von viable Survey-IDs (strings).
            Leere Liste wenn keine Surveys verfügbar.

    Side Effects:
      - Ruft CDP WebSocket auf (Dashboard-Tab).
      - Führt JavaScript aus (document.querySelectorAll).
      - Macht HTTP-Requests (CPX API für Details).

    BANNED in dieser Funktion:
      ❌ Kein hardcoded Survey-Filtering (Provider-Liste kommt aus Config).
    ================================================================================
    """
    # Lazy Import
    # WARUM lazy? survey.scanner importiert survey.chrome etc. — teuer.
    from survey.scanner import scan_dashboard

    # Provider-Filter
    # WARUM purespectrum/surveyrouter? Erfahrung: Diese Provider haben niedrige
    # Conversion-Rates oder blockieren oft. Siehe RunnerConfig.skip_providers.
    skip = None if args.all else ["purespectrum", "surveyrouter"]

    # Dashboard scannen
    # WARUM port=args.port? Chrome CDP könnte auf anderem Port laufen.
    viable = scan_dashboard(port=args.port, skip_providers=skip)

    return viable


def cmd_run(args):
    """
    ================================================================================
    KOMMANDO: run — Einzelne Survey ausführen (LangGraph Survey-Agent)
    ================================================================================

    WAS macht diese Funktion?
      Führt eine EINZELNE Survey aus — entweder per ID oder direkter URL.
      Nutzt den LangGraph Survey-Agent (run_survey_loop) als PRIMARY.
      SurveyRunner ist deprecated und wird nicht mehr verwendet.

    Args:
      args (Namespace):
        - args.port: CDP Port
        - args.id: Survey ID (CPX Research ID)
        - args.url: Direkte Survey URL (überspringt API-Lookup)
        - args.no_nim: Ignoriert (decide_node nutzt immer NIM wenn verfügbar)
        - args.no_rate: Ignoriert (auto-rating kommt später, SR-44)
        - args.debug: Verbose Output

    Returns:
      SurveyState: Ergebnis der Survey-Ausführung.
                   None wenn weder --id noch --url angegeben.

    Side Effects:
      - Startet Chrome (wenn nicht läuft) via ChromeLauncher.
      - Öffnet Survey-Tab in Chrome via SurveyOpener.
      - Injiziert 7 Heypiggy-Cookies in Survey-Tab.
      - Führt NEMO Loop aus: snapshot → NIM decide → batch execute → detect completion.
      - Liest Balance vor/nach der Session.
      - Delegiert an opencode CLI bei 3× failures.

    BANNED in dieser Funktion:
      ❌ Kein hardcoded Survey-ID
      ❌ Keine SurveyRunner mehr (deprecated, durch run_survey_loop ersetzt)
    ================================================================================
    """
    # Survey-ID und Provider ermitteln
    if args.url:
        survey_id = "direct"
        survey_url = args.url
        # Provider aus URL extrahieren (einfache Heuristik)
        provider = _detect_provider_from_url(args.url)
    elif args.id:
        survey_id = args.id
        survey_url = ""
        # Provider wird von SurveyOpener/open_survey aus URL ermittelt
        provider = ""
    else:
        print("❌ Use --id or --url")
        return None

    # SurveyState erstellen
    # WARUM SurveyState? Zentrales State-Objekt für den LangGraph Survey-Agent.
    from survey.graph import SurveyState, run_survey_loop

    state = SurveyState(
        survey_id=survey_id,
        provider=provider,
        survey_url=survey_url,  # Für --url: direkte URL statt CPX Lookup
        cdp_port=args.port,
    )

    # Survey ausführen via run_survey_loop
    # WARUM run_survey_loop statt SurveyRunner?
    #   - LangGraph-Architektur: 8 Nodes, conditional routing
    #   - Balance-Tracking: balance_before/balance_after automatisch
    #   - Cookie-Injection: 7 Heypiggy-Cookies vor Page.navigate
    #   - Delegation: 3× failures → opencode CLI
    final_state = run_survey_loop(state)

    # Ergebnis ausgeben
    _print_result_graph(final_state)
    return final_state


def cmd_loop(args):
    """
    ================================================================================
    KOMMANDO: loop — Automatischer Survey-Loop (scan → filter → run)
    ================================================================================

    WAS macht diese Funktion?
      Führt mehrere Surveys automatisch hintereinander aus.
      1. Scannt Dashboard nach verfügbaren Surveys
      2. Filtert blocked Provider
      3. Führt jede Survey aus (bis max erreicht)
      4. Zeigt Zusammenfassung

    Args:
      args (Namespace):
        - args.port: CDP Port
        - args.max: Max Surveys (default: 5)
        - args.no_nim: NIM deaktivieren
        - args.no_rate: Auto-Rating deaktivieren
        - args.debug: Debug Mode

    Returns:
      list: Liste von SurveyResult Objekten.

    Side Effects:
      - Mehrere Chrome-Tabs öffnen/schließen.
      - Mehrere NIM Calls (wenn NIM aktiviert).
      - Balance kann sich ändern.

    BANNED in dieser Funktion:
      ❌ Kein while True ohne Break (muss max_respect haben)
    ================================================================================
    """
    # Lazy Import

    # RunnerConfig erstellen (siehe cmd_run für Details)
    config = RunnerConfig(
        cdp_port=args.port,
        use_nim=not args.no_nim,
        auto_rate=not args.no_rate,
        max_surveys=args.max,
        debug=args.debug or os.getenv("SURVEY_DEBUG", ""),
        wait_after_action=float(os.getenv("SURVEY_WAIT", "3.0")),
    )

    # SurveyRunner initialisieren
    runner = SurveyRunner(config=config)

    # NIM Status
    nim_available = runner.nim and runner.nim.available
    nim_status = "✅" if nim_available else "⚠️  (auto-pilot)"
    print(f"  NVIDIA NIM: {nim_status}")
    print(f"  Max surveys: {args.max}")
    print()

    # Loop ausführen
    # WARUM run_loop()? Kapselt Scan + Filter + Run in einer Funktion.
    results = runner.run_loop(max_surveys=args.max)

    return results




def _run_survey_via_graph(survey_dict, provider, args):
    """Issue #34: Wrapper to invoke survey via LangGraph instead of SurveyRunner."""
    from survey.graph import create_graph, SurveyState
    from survey.graph.checkpointer import make_run_config
    import time
    
    graph = create_graph()
    state = SurveyState(
        survey_id=survey_dict.get("id"),
        provider=provider,
        cdp_port=args.port,
        no_nim=args.no_nim,
        no_rate=args.no_rate,
    )
    state.session_start_time = time.time()
    
    try:
        # SR-238: pass deterministic thread_id config so SqliteSaver
        # picks up the right thread on resume after crash.
        final_state = graph.invoke(state, config=make_run_config(state))
        return {
            "success": final_state.status == "completed",
            "balance_earned": final_state.balance_after - final_state.balance_before,
            "error": None if final_state.status in ["completed", "screen_out"] else final_state.errors[-1].get("error", "unknown"),
            "status": final_state.status,
            "details": {
                "iterations": final_state.iteration,
                "errors_count": len(final_state.errors),
            }
        }
    except Exception as e:
        return {
            "success": False,
            "balance_earned": 0.0,
            "error": str(e),
            "status": "error",
        }

def cmd_watch(args):
    """
    ================================================================================
    KOMMANDO: watch — 24/7 Watch Daemon (CONTINUOUS POLLER)
    ================================================================================

    WAS macht diese Funktion?
      DER HAUPT-DAEMON für 24/7 Survey-Automation.
      Läuft ENDLOS (bis SIGINT/SIGTERM oder max_consecutive_errors erreicht).

      LOOP:
        1. Prüfe Login-State
           → WENN nicht eingeloggt: Google OAuth Login (auto_google_login.execute())
        2. Health-Check (Chrome läuft? Dashboard erreichbar?)
        3. Balance lesen
        4. Survey-Loop ausführen (max args.max Surveys)
        5. Ergebnisse loggen
        6. Warten (interval, oder sofort bei Erfolg)
        7. Wiederholen

    FEATURES:
      - Graceful Shutdown: SIGINT/SIGTERM → sauberes Beenden + Logging
      - Crash Recovery: Chrome-Crash erkannt → Backoff → Retry
      - Exponential Backoff: Fehler werden langsamer retries
      - Balance Target: Stoppt wenn Zielguthaben erreicht
      - JSONL Logging: Strukturierte Logs für Analyse

    Args:
      args (Namespace):
        - args.port: CDP Port (default: 9999)
        - args.interval: Poll-Interval in Sekunden (default: 30)
        - args.max: Max Surveys pro Cycle (default: 3)
        - args.no_nim: NIM deaktivieren
        - args.no_rate: Auto-Rating deaktivieren

    Returns:
      None (läuft endlos bis Shutdown).

    Side Effects:
      - Läuft ENDLOS (bis interrupted).
      - Startet/verwendet Chrome-Prozess.
      - Schreibt in ~/.stealth/daemon_state.json.
      - Schreibt in survey-cli/logs/*.jsonl.
      - Nutzt cua-driver Daemon.
      - Verändert HeyPiggy-Balance.

    CRITICAL BUGS / BEKANNTE PROBLEME:
      - Issue #1: Login-Loop Failure
        → WENN Login fehlschlägt → Endlosschleife "NEUE TAB! Aber NICHT eingeloggt!"
        → Ursache: auto_google_login.execute() schlägt fehl, wird aber wiederholt
        → Fix: Siehe issues/001-login-loop-failure.md

      - Issue #2: Daemon State Management
        → cua-driver Daemon wird nicht verifiziert
        → "Continuing with CDP-only mode" ist gefährlich (cua-driver fehlt)
        → Fix: Siehe issues/002-daemon-state-management.md

    RACE CONDITIONS:
      - Chrome kann während Login crashen → OAuth hängt
      - Mehrere Watch-Prozesse könnten gleichzeitig laufen
      - Dashboard-Tab kann sich ändern während Scan
      - Survey-Tab kann sich ändern während Ausführung

    BANNED in dieser Funktion:
      ❌ Kein while True ohne Exit-Condition (max_consecutive_errors ist Exit)
      ❌ Kein playstealth launch (auch nicht indirekt via auto_google_login)
      ❌ Kein killall/pkill (Graceful Shutdown nur via SIGTERM)
    ================================================================================
    """
    # ============================================================================
    # LAZY IMPORTS
    # ============================================================================
    # WARUM lazy? Diese Module sind teuer zu laden (Chrome-Check, WebSocket, etc.).
    # WARUM in Funktion statt global? Vermeidet Import-Fehler beim Modul-Load
    # (z.B. wenn survey.chrome nicht existiert während Entwicklung).
    import signal
    from survey.scanner import read_balance
    from survey.chrome import is_chrome_alive, find_bot_tabs, find_dashboard_ws
    from survey.autodoc import log_session

    # ============================================================================
    # KONFIGURATION
    # ============================================================================
    # Poll-Interval aus args
    # WARUM local Variable? Klarere Lesbarkeit, einfacher zu debuggen.
    interval = args.interval

    # RunnerConfig für SurveyRunner
    # WARUM debug=False? Watch Mode = Production — kein Verbose Output.
    config = RunnerConfig(
        cdp_port=args.port,
        use_nim=not args.no_nim,
        auto_rate=not args.no_rate,
        debug=False,
        max_surveys=args.max,
    )

    # ============================================================================
    # ZUSTAND (State Dictionary)
    # ============================================================================
    # WARUM dict statt Klasse? Einfachheit — keine zusätzliche Klasse nötig.
    # WARUM Mutable? State wird im Loop verändert (running, total_earned, etc.).
    # WARUM NICHT global? Global State = Race Conditions bei mehreren Threads.
    # → Lösung: Diese Funktion ist single-threaded (kein threading).
    state = {
        # running: True solange Daemon laufen soll
        # WARUM Bool? Einfachster Mechanismus für Loop-Control.
        # WIRD GESETZT AUF: False bei SIGINT/SIGTERM (shutdown Handler)
        "running": True,

        # total_earned: Kumulierte Einnahmen dieser Session
        # WARUM float? HeyPiggy zeigt Cent-Beträge (z.B. 0.05€).
        # WARUM 0.0? Initialwert — wird inkrementiert.
        "total_earned": 0.0,

        # loop_count: Anzahl durchlaufener Cycles
        # WARUM int? Zählvariable.
        # WARUM 0? Initialwert.
        "loop_count": 0,

        # consecutive_errors: Anzahl aufeinanderfolgender Fehler
        # WARUM int? Wird inkrementiert bei Fehlern, zurückgesetzt bei Erfolg.
        # WARUM wichtig? Exit-Condition — bei zu vielen Fehlern stoppen wir.
        "consecutive_errors": 0,

        # max_consecutive_errors: Schwellwert für Exit
        # WARUM 20? Siehe Konstanten-Dokumentation oben.
        # WARUM in State? Könnte konfigurierbar sein (aus Config-Datei).
        "max_consecutive_errors": MAX_CONSECUTIVE_ERRORS,

        # session_start: Timestamp für Duration-Berechnung
        # WARUM time.time()? Unix Timestamp, einfach zu subtrahieren.
        "session_start": time.time(),
    }

    # ============================================================================
    # SIGNAL HANDLER — Graceful Shutdown
    # ============================================================================
    # WARUM Signal Handler? Watch Daemon läuft endlos.
    # Ohne Handler: Ctrl+C killt Python sofort — kein Cleanup.
    # Mit Handler: Chrome-Tabs schließen, Logs schreiben, State speichern.
    def shutdown(signum, frame):
        """
        Graceful Shutdown bei SIGINT (Ctrl+C) oder SIGTERM.

        WAS macht diese Funktion?
          Setzt state["running"] = False → Loop beendet sich sauber.
          Loggt Session-Zusammenfassung.
          Schließt keine Chrome-Tabs (das übernimmt der Caller).

        Args:
          signum (int): Signal-Nummer (2 für SIGINT, 15 für SIGTERM).
          frame (Frame): Aktueller Stack Frame (nicht genutzt).

        Side Effects:
          - Setzt state["running"] = False.
          - Ruft log_session() auf (schreibt in JSONL).
          - Gibt Shutdown-Nachricht aus.

        WARUM nicht Chrome killen?
          Chrome-Tabs sollten vom Loop geschlossen werden (sauberer).
          Wenn Loop gerade in einem try/except ist, wird es den Break sehen.
        """
        # Signal-Name ermitteln
        # WARUM signal.Signals? Menschenlesbarer Name statt Zahl.
        sig_name = signal.Signals(signum).name

        # Session-Dauer berechnen
        elapsed = time.time() - state["session_start"]

        # Shutdown-Nachricht
        print(f"\n[WATCH] Received {sig_name} — shutting down gracefully...")
        print(f"[WATCH] Session: {state['loop_count']} loops, "
              f"+{state['total_earned']:.2f}€ earned in {elapsed:.0f}s")

        # Loop stoppen
        state["running"] = False

        # Session loggen
        # WARUM log_session? Strukturierte Logs für spätere Analyse.
        log_session("watch_stop", "ok", {
            "reason": sig_name,
            "loops": state["loop_count"],
            "earned": state["total_earned"],
            "elapsed_s": round(elapsed),
        })

    # Signal-Handler registrieren
    # WARUM signal.SIGINT? Ctrl+C im Terminal.
    # WARUM signal.SIGTERM? Kill-Signal von anderen Prozessen (z.B. systemd).
    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    # ============================================================================
    # BANNER — Start-Meldung
    # ============================================================================
    # WARUM Banner? Menschlicher Operator (oder Agent) sieht sofort:
    #   - Was läuft? (Watch Daemon)
    #   - Welche Konfiguration? (interval, max, NIM, target)
    #   - Wie stoppen? (Ctrl+C)
    print(f"\n{'═'*60}")
    print("  🔄 SURVEY-CLI WATCH DAEMON — 24/7 Mode")
    print(f"{'═'*60}")

    # ============================================================================
    # ACCESSIBILITY CHECK (ONCE at start)
    # ============================================================================
    # WARUM nur einmal? Accessibility ändert sich nicht während Runtime.
    # WARUM ensure_accessibility? Prüft ob macOS Accessibility aktiv ist.
    #   → WENN nicht aktiv: cua-driver findet KEINE Elemente → Login schlägt fehl.
    # WARUM start_cua_daemon? Startet cua-driver als Daemon (falls nicht läuft).
    from survey.accessibility import ensure_accessibility
    from survey.daemon_manager import DaemonManager

    cua_mgr = DaemonManager()
    if not cua_mgr.ensure_running():
        print("[WATCH] ❌ CRITICAL: cua-driver daemon failed to start")
        print("[WATCH] → Install cua-driver oder manuell starten: nohup cua-driver serve &")
        log_session("watch_stop", "error", {"reason": "daemon_start_failed"})
        return

    # Accessibility prüfen
    # FIX Issue #1: Hard-Stop bei fehlender Accessibility (nicht "Continuing...").
    # WARUM? Ohne Accessibility ist AX-Tree LEER → Login unmöglich.
    # → "Continuing with CDP-only mode" war ein BUG (CDP kann kein Login).
    if not ensure_accessibility(port=args.port):
        print("[WATCH] ❌ CRITICAL: Chrome Accessibility not available")
        print("[WATCH] → Chrome MUSS mit --force-renderer-accessibility gestartet werden")
        print("[WATCH] → System Settings → Privacy & Security → Accessibility → Google Chrome")
        log_session("watch_stop", "error", {"reason": "accessibility_unavailable"})
        return  # HARD STOP — keine Survey ohne Accessibility möglich

    # Konfiguration anzeigen
    print(f"  Poll interval:  {interval}s")
    print(f"  Max/cycle:      {args.max}")
    print(f"  NVIDIA NIM:     {'✅' if config.use_nim else '⚠️  auto-pilot'}")
    print(f"  Balance target: {config.balance_target}€")
    print("  Logs:           survey-cli/logs/")
    print("  Stop:           Ctrl+C or SIGTERM")
    print(f"{'═'*60}\n")

    # Session-Start loggen
    log_session("watch_start", "ok", {
        "interval": interval,
        "max_per_cycle": args.max,
        "use_nim": config.use_nim,
    })

    # ============================================================================
    # AUTO-LOGIN (wenn nicht eingeloggt)
    # ============================================================================
    # WARUM vor dem Loop? Der Loop braucht eingeloggtes Dashboard.
    # WARUM nicht im Loop? Login ist einmalig — nicht bei jedem Cycle.
    print("[WATCH] Checking login state...")

    # Lazy Import (vermeidet zirkuläre Imports beim Modul-Load)
    from cli.modules.auto_google_login import execute as google_login

    # Quick Login-Check via CDP
    # WARUM CDP statt cua-driver? Schneller — kein AX-Tree nötig.
    # WARUM Runtime.evaluate? Führt JS im Browser aus.
    # WARUM document.title.includes('Umfragen')? Wenn eingeloggt: Title enthält "Umfragen".
    # WARUM document.body.innerText.includes('Abmelden')? Wenn eingeloggt: "Abmelden"-Link sichtbar.
    logged_in = False
    dash_ws = find_dashboard_ws(args.port)

    if dash_ws:
        try:
            # WebSocket-Verbindung aufbauen
            # WARUM websocket.create_connection? Einfacher als websocket-client mit async.
            # WARUM timeout=10? Nicht zu kurz (langsamer Desktop), nicht zu lang (warten nervt).
            ws = websocket.create_connection(dash_ws, timeout=10)

            # CDP Runtime.evaluate senden
            # WARUM {"id":0}? CDP verwendet JSON-RPC mit Request IDs.
            # WARUM "Runtime.evaluate"? Führt JavaScript im Browser-Context aus.
            ws.send(json.dumps({
                "id": 0,
                "method": "Runtime.evaluate",
                "params": {
                    "expression": (
                        "document.title.includes('Umfragen') || "
                        "document.body.innerText.includes('Abmelden')"
                    )
                }
            }))

            # Antwort empfangen
            r = json.loads(ws.recv())

            # WebSocket schließen
            # WARUM sofort? Nicht mehr nötig, spart Ressourcen.
            ws.close()

            # Ergebnis extrahieren
            # WARUM .get("result",{}).get("result",{}).get("value",False)?
            #   CDP Response ist tief verschachtelt:
            #   {"result": {"result": {"value": true}}}
            logged_in = r.get("result", {}).get("result", {}).get("value", False)

        except Exception:
            # WARUM bare except? CDP kann fehlschlagen (Chrome nicht bereit, etc.).
            # → Graceful degradation: logged_in bleibt False.
            # BUG: Sollte spezifischer sein (siehe Error-Handling Best Practices).
            pass

    # WENN nicht eingeloggt → Login durchführen
    if not logged_in:
        print("[WATCH] Not logged in — running cua-driver Google OAuth login...")

        # Google Login ausführen
        # WARUM auto_google_login.execute()? Kapselt den kompletten 6-Step Flow.
        login_result = google_login()

        # Ergebnis prüfen
        if login_result.get("status") != "ok":
            # Login fehlgeschlagen — FIX Issue #1: Kein Endlos-Loop!
            # WARUM max_retries? Verhindert Endlosschleife bei persistentem Fehler.
            # → Bisher: Login failed → retrying later → Login failed → ... (endlos)
            # → Neu: Nach 3 Fehlern → HARD STOP mit Fehlermeldung.
            max_login_retries = 3
            login_retry_count = 0

            while login_retry_count < max_login_retries:
                login_retry_count += 1
                print(f"[WATCH] ❌ Login failed (attempt {login_retry_count}/{max_login_retries}): "
                      f"{login_result.get('reason')}")

                if login_retry_count >= max_login_retries:
                    print(f"[WATCH] ❌ CRITICAL: Login failed after {max_login_retries} attempts")
                    print("[WATCH] → Manual intervention required")
                    log_session("watch_stop", "error", {
                        "reason": "login_max_retries_exceeded",
                        "attempts": login_retry_count,
                        "last_error": login_result.get('reason'),
                    })
                    return  # HARD STOP — verhindert Endlosschleife

                # Exponential Backoff vor Retry
                wait_s = min(60, 2 ** login_retry_count)
                print(f"[WATCH] Waiting {wait_s}s before retry...")
                time.sleep(wait_s)

                # Erneut versuchen
                login_result = google_login()

            # FALLBACK: Wenn alle Retries fehlschlagen
            print("[WATCH] ❌ Login exhausted — stopping watch daemon")
            log_session("watch_stop", "error", {"reason": "login_exhausted"})
            return
        else:
            # Login erfolgreich
            print("[WATCH] ✅ Login successful")
            # WARTEN bis Dashboard bereit
            # WARUM 3s? Weiterleitung nach Login kann dauern.
            time.sleep(3)

    # ============================================================================
    # HAUPT-LOOP (Endlos bis Shutdown oder max_errors)
    # ============================================================================
    while state["running"]:
        # Loop-Counter inkrementieren
        state["loop_count"] += 1

        # Loop-Start-Zeit
        # WARUM time.monotonic()? Monotonic = nicht von Systemzeit-Änderungen beeinflusst.
        time.monotonic()

        try:
            # ── Health Check: Chrome läuft? ──
            # WARUM is_chrome_alive? Prüft ob Chrome-Prozess existiert und CDP erreichbar.
            # WARUM port=args.port? Chrome könnte auf anderem Port lauschen.
            if not is_chrome_alive(args.port):
                print(f"[WATCH] ⚠️  Chrome not responding on port {args.port} — waiting...")

                # Fehler-Counter erhöhen
                state["consecutive_errors"] += 1

                # Max-Fehler erreicht?
                if state["consecutive_errors"] >= state["max_consecutive_errors"]:
                    print("[WATCH] ❌ Too many Chrome failures — stopping")
                    break  # Loop beenden

                # Exponential Backoff
                # WARUM min(60, ...)? Max 60s warten — länger ist sinnlos.
                # WARUM 2 ** consecutive_errors? 1, 2, 4, 8, 16, 32, ... → exponentiell.
                wait_s = min(60, 2 ** state["consecutive_errors"])
                print(f"[WATCH] Waiting {wait_s}s...")
                time.sleep(wait_s)
                continue  # Nächste Loop-Iteration

            # ── Health Check: cua-driver Daemon läuft? ──
            cua_health = cua_mgr.health_check()
            if not cua_health.get("healthy"):
                print(f"[WATCH] ⚠️  cua-driver daemon unhealthy: {cua_health.get('reason')} — recovering...")
                if not cua_mgr.ensure_running():
                    state["consecutive_errors"] += 1
                    if state["consecutive_errors"] >= state["max_consecutive_errors"]:
                        print("[WATCH] ❌ Too many cua-daemon failures — stopping")
                        break
                    time.sleep(10)
                    continue
                state["consecutive_errors"] = 0

            # ── Dashboard prüfen ──
            dashboard_ws = find_dashboard_ws(args.port)
            if not dashboard_ws:
                print("[WATCH] ⚠️  No dashboard tab found")
                state["consecutive_errors"] += 1
                time.sleep(interval)
                continue

            # ── Fehler-Counter zurücksetzen ──
            # WARUM hier? Health-Check und Dashboard-Check erfolgreich.
            state["consecutive_errors"] = 0

            # ── Balance lesen ──
            balance_before = read_balance(args.port)

            # ── Offene Tabs zählen ──
            tabs = len(find_bot_tabs(args.port))

            # ── Status ausgeben ──
            print(f"\n[{state['loop_count']}] Balance: {balance_before}€ | "
                  f"Tabs: {tabs} | "
                  f"Earned: +{state['total_earned']:.2f}€ | "
                  f"{time.strftime('%H:%M:%S')}")

            # ── Balance Target prüfen ──
            # WARUM balance_target? Wenn Ziel erreicht → Aufhören.
            # WARUM 5.00€? Typische Auszahlungsschwelle.
            if balance_before >= config.balance_target:
                print(f"[WATCH] 🎯 Balance target reached: {balance_before}€")
                print(f"[WATCH] Total earned: +{state['total_earned']:.2f}€")
                break  # Loop beenden

            # ── Survey-Cycle ausführen ──
            # WARUM SurveyRunner? Kapselt NEMO-Engine.
            # WARUM jedes Mal neu erstellen? Runner hält State pro Cycle.
            runner = SurveyRunner(config=config)
            results = runner.run_loop(max_surveys=args.max)

            # ── Ergebnisse auswerten ──
            earned = sum(r.earned for r in results if r.earned > 0)
            state["total_earned"] += earned
            completed = sum(1 for r in results if r.status == "completed")
            failed = len(results) - completed

            # Balance nach Cycle
            balance_after = read_balance(args.port)

            # ── Icons für Ergebnisse ──
            # WARUM Icons? Schneller visueller Überblick im Log.
            icons = " ".join(
                "✅" if r.status == "completed" else
                "⛔" if r.status == "blocked" else "❌"
                for r in results
            )
            print(f"  → +{earned:.2f}€ | {completed} done, {failed} fail | "
                  f"Balance: {balance_after}€ | {icons}")

            # ── Smart Backoff ──
            # WARUM Smart? Wartezeit abhängig von Ergebnissen.
            if completed == 0:
                if failed == 0:
                    # Keine Surveys verfügbar → länger warten
                    # WARUM interval? Dashboard hat keine Surveys → braucht Zeit zum Refresh.
                    wait_s = interval
                    print(f"  No surveys found — waiting {wait_s}s...")
                else:
                    # Surveys versucht aber fehlgeschlagen → schneller Retry
                    # WARUM min(interval, 10)? Nicht länger als normal warten.
                    wait_s = min(interval, 10)
                    print(f"  All failed — retrying in {wait_s}s...")
                time.sleep(wait_s)
            else:
                # Surveys erfolgreich → SOFORT weiter (kein Warten)
                # WARUM? Mehr Surveys = mehr Einnahmen. Zeit = Geld.
                pass

        except KeyboardInterrupt:
            # Ctrl+C während Loop → Graceful Shutdown
            shutdown(signal.SIGINT, None)

        except Exception as e:
            # UNERWARTETER FEHLER
            # BUG: Sollte spezifischer sein — welcher Fehler?
            state["consecutive_errors"] += 1
            print(f"[WATCH] ❌ Error in loop {state['loop_count']}: {e}")

            # Exponential Backoff
            if state["consecutive_errors"] >= state["max_consecutive_errors"]:
                print("[WATCH] ❌ Too many consecutive errors — stopping")
                break

            # Wartezeit berechnen
            # WARUM min(300, ...)? Max 5 Minuten warten.
            # WARUM 5 * (2 ** errors)? Stärkerer Backoff als bei Chrome-Fehlern.
            wait_s = min(300, 5 * (2 ** state["consecutive_errors"]))
            print(f"[WATCH] Backing off {wait_s}s (error {state['consecutive_errors']}/{state['max_consecutive_errors']})")
            time.sleep(wait_s)

    # ============================================================================
    # SHUTDOWN — Zusammenfassung
    # ============================================================================
    elapsed = time.time() - state["session_start"]
    print(f"\n{'═'*60}")
    print("  WATCH DAEMON STOPPED")
    print(f"{'═'*60}")
    print(f"  Loops:     {state['loop_count']}")
    print(f"  Earned:    +{state['total_earned']:.2f}€")
    print(f"  Duration:  {elapsed:.0f}s ({elapsed/3600:.1f}h)")
    print(f"{'═'*60}\n")


# ============================================================================
# WEITERE KOMMANDO-FUNKTIONEN (kürzer dokumentiert, aber immer noch EXTREM)
# ============================================================================

def cmd_balance(args):
    """
    ================================================================================
    KOMMANDO: balance — Aktuelles Guthaben + Zusammenfassung anzeigen
    ================================================================================
    Args:
      args (Namespace):
        - args.port: CDP Port
        - args.days: Tage der Historie (default: 7)
    Returns:
      float: Aktuelles Guthaben in €
    Side Effects:
      - Liest HeyPiggy Dashboard via CDP.
      - Generiert Zusammenfassung aus Logs.
    ================================================================================
    """
    from survey.scanner import read_balance
    from survey.autodoc import generate_summary, print_summary

    # Balance lesen
    balance = read_balance(port=args.port)
    print(f"\n{'='*50}")
    print(f"  CURRENT BALANCE: {balance}€")
    print(f"{'='*50}")

    # Zusammenfassung generieren
    summary = generate_summary(days=args.days)
    print_summary(summary)

    return balance


def cmd_status(args):
    """
    ================================================================================
    KOMMANDO: status — System-Status prüfen (Chrome, Login, NIM)
    ================================================================================
    Args:
      args (Namespace):
        - args.port: CDP Port
    Returns:
      dict: Status-Dictionary
    Side Effects:
      - Prüft Chrome-Prozess.
      - Prüft CDP-Erreichbarkeit.
      - Prüft NVIDIA NIM Verfügbarkeit.
    ================================================================================
    """
    from survey.chrome import is_chrome_alive, find_bot_pids, find_dashboard_ws
    from survey.snapshot import generate_snapshot
    from survey.nim import get_nim
    from survey.scanner import read_balance

    print(f"\n{'='*50}")
    print("  SURVEY-CLI STATUS")
    print(f"{'='*50}")

    # Chrome Status
    alive = is_chrome_alive(args.port)
    pids = find_bot_pids()
    print("\n  Chrome:")
    print(f"    Running:  {'✅' if alive else '❌'}")
    print(f"    PIDs:     {pids if pids else 'none'}")
    print(f"    Port:     {args.port}")

    if alive:
        # Dashboard
        ws_url = find_dashboard_ws(args.port)
        if ws_url:
            print("    Dashboard: ✅ Connected")
            try:
                generate_snapshot(ws_url)
                balance = read_balance(args.port)
                print(f"    Balance:   {balance}€")
            except Exception:
                print("    Dashboard: connected (read error)")
        else:
            print("    Dashboard: ❌ Not found")

    # NIM Status
    nim = get_nim()
    key = os.getenv("NVIDIA_API_KEY", "")
    print("\n  NVIDIA NIM:")
    print(f"    API Key:  {'✅ set' if key else '❌ NOT SET'}")
    print(f"    Status:   {'✅ ready' if nim and nim.available else '❌ unavailable'}")
    print(f"    Model:    {nim.model if nim and nim.model else 'N/A'}")

    print()
    return {"chrome_alive": alive, "pid_count": len(pids), "nim_ready": bool(nim and nim.available)}


def cmd_doctor(args):
    """
    ================================================================================
    KOMMANDO: doctor — Vollständige Selbstdiagnose
    ================================================================================
    Prüft:
      - Python Version
      - Abhängigkeiten (websocket, openai)
      - Chrome Status
      - Profil-Verfügbarkeit
      - Log-Dateien
      - Offene Tabs
    ================================================================================
    """
    from survey.chrome import is_chrome_alive, find_bot_tabs

    print(f"\n{'='*50}")
    print("  🔬 SURVEY-CLI DOCTOR")
    print(f"{'='*50}")

    # Python Version
    print(f"\n  Python: {sys.version.split()[0]}")

    # Abhängigkeiten
    deps = ["websocket", "openai"]
    for dep in deps:
        try:
            __import__(dep)
            print(f"  {dep}:       ✅")
        except ImportError:
            print(f"  {dep}:       ❌ not installed")

    # Chrome Status (wiederverwendet cmd_status)
    cmd_status(args)

    # Profil
    profile_path = Path(__file__).parent / "survey" / "profiles" / "sin_agent_heypiggy.json"
    print(f"  Profile:    {'✅' if profile_path.exists() else '⚠️  using fallback'}")

    # Logs
    logs_dir = Path(__file__).parent / "logs"
    if logs_dir.exists():
        log_files = list(logs_dir.glob("*.jsonl"))
        print(f"  Log files:  {len(log_files)}")
    else:
        print("  Log files:  0")

    # Tabs
    if is_chrome_alive(args.port):
        pages = find_bot_tabs(args.port)
        print(f"  Tabs open:  {len(pages)}")
        for p in pages[:5]:
            url = p.get("url", "")[:70]
            print(f"    {p.get('id','?')[:12]} | {url}")

    print(f"\n  {'='*50}")
    print("  Doctor complete")
    print(f"  {'='*50}\n")


def cmd_kill(args):
    """
    ================================================================================
    KOMMANDO: kill — Bot Chrome SICHER beenden
    ================================================================================
    WARUM "safely"? NUR Bot-Chrome wird beendet — NIEMALS User-Chrome!
    WARUM wichtig? Bot-Chrome kann im Hintergrund laufen und Ressourcen verbrauchen.
    ================================================================================
    """
    from survey.chrome import safe_kill_bot
    killed = safe_kill_bot()
    if killed:
        print("✅ Bot Chrome killed safely")
    else:
        print("ℹ️  No bot Chrome to kill")


def cmd_summary(args):
    """
    ================================================================================
    KOMMANDO: summary — Earnings-Zusammenfassung
    ================================================================================
    """
    from survey.autodoc import generate_summary, print_summary
    summary = generate_summary(days=args.days or 30)
    print_summary(summary)
    return summary


def cmd_opencode(args):
    """
    ================================================================================
    KOMMANDO: opencode — Coding-Aufgabe an opencode CLI delegieren
    ================================================================================
    WARUM? Ermöglicht es dem Watch Daemon, Coding-Aufgaben auszulagern
    (z.B. "Fix Bug X", "Implementiere Feature Y").
    ================================================================================
    """
    from survey.opencode_bridge import delegate_task

    task = " ".join(args.task) if args.task else sys.stdin.read()
    if not task.strip():
        print("❌ No task provided. Usage: survey.py opencode 'task description'")
        return

    result = delegate_task(task, repo_path=args.repo, timeout=args.timeout)
    print(f"\nOpenCode Result: {result['status']}")
    if result.get("stdout"):
        print(result["stdout"])
    if result.get("stderr"):
        print(f"  stderr: {result['stderr']}")
    return result


def cmd_profile(args):
    """
    ================================================================================
    KOMMANDO: profile — Aktuelles Persona-Profil anzeigen + Telemetrie-Dump
    ================================================================================

    Subaktionen (``profile_action`` aus argparse):

      ``show``      (default) — zeigt das geladene Profil tabellarisch an.
      ``dump``               — gibt Matcher-Telemetrie als JSON nach stdout
                                und (falls ``--out`` gesetzt) zusaetzlich
                                nach Datei aus. Format: ein Persona-Block
                                pro Zeile JSONL-kompatibel + Stdout-Summary.

    Die Telemetrie wird IN PROCESS aggregiert. ``profile dump`` zeigt also
    NUR Daten, die seit dem letzten Prozess-Start gesammelt wurden — fuer
    persistente Statistiken nutze ``logs/matcher-telemetry-{run_id}.jsonl``,
    das von ``cmd_run`` am Survey-Ende geschrieben wird.
    """
    action = getattr(args, "profile_action", None) or "show"
    profile_name = getattr(args, "name", None) or "jeremy_schulze"

    from survey.profile_loader import ProfileLoader

    if action == "show":
        profile = ProfileLoader.load_profile(profile_name=profile_name)
        missing = ProfileLoader._missing_required(profile)
        print(f"\n{'='*60}")
        print(f"  PERSONA: {profile_name}")
        if missing:
            print(f"  WARNING: missing required keys: {sorted(missing)}")
        print(f"{'='*60}")
        for k, v in profile.items():
            if k.startswith("_"):
                continue
            print(f"  {k:25s}: {v}")
        print()
        return

    if action == "dump":
        telem = ProfileLoader.telemetry()
        out_path = getattr(args, "out", None)

        # Stdout-Summary
        print(f"\n{'='*60}")
        print("  MATCHER TELEMETRY (in-process)")
        print(f"{'='*60}")
        if not telem:
            print("  <empty — kein match_field()/load_profile() bisher>")
        for persona, bucket in telem.items():
            hits = bucket.get("match_hits", 0)
            miss = bucket.get("match_misses", 0)
            total = hits + miss
            rate = (hits / total * 100.0) if total else 0.0
            print(f"  [{persona}]")
            print(f"    loads:           {bucket.get('loads', 0)}")
            print(f"    loaded_from:     {bucket.get('loaded_from', '<n/a>')}")
            print(f"    missing_required:{bucket.get('missing_required_count', 0)}")
            print(f"    match_hits:      {hits}")
            print(f"    match_misses:    {miss}  (hit-rate {rate:.1f}%)")
            per_key = bucket.get("per_key_hits", {})
            if per_key:
                top = sorted(per_key.items(), key=lambda kv: -kv[1])[:10]
                print(f"    top hits:        {top}")
            # SR-59 #58: optional miss_labels table on --miss-labels flag.
            if getattr(args, "miss_labels", False):
                mls = bucket.get("miss_labels", [])
                print(f"    miss_labels:     {len(mls)} record(s)")
                if mls:
                    print("      "
                          + f"{'role':<10} {'label':<40} "
                          + f"{'hash':<8} candidates")
                    print("      " + "-" * 78)
                    for ml in mls[-20:]:  # show last 20
                        role = str(ml.get("role", ""))[:10]
                        lbl = str(ml.get("question_text")
                                  or ml.get("label") or "")[:40]
                        h = str(ml.get("snapshot_hash", ""))[:8]
                        cands = ",".join(ml.get("candidate_keys", [])) or "-"
                        print(f"      {role:<10} {lbl:<40} {h:<8} {cands}")
        print()

        # JSON Out
        import json
        payload = json.dumps(telem, ensure_ascii=False, indent=2)
        print(payload)
        if out_path:
            try:
                with open(out_path, "w") as f:
                    for persona, bucket in telem.items():
                        line = json.dumps(
                            {"persona": persona, **bucket}, ensure_ascii=False,
                        )
                        f.write(line + "\n")
                print(f"\n[profile dump] wrote JSONL to {out_path}")
            except Exception as exc:
                print(f"[profile dump] write failed: {exc}")
        return

    print(f"unknown profile_action: {action!r}")


# ============================================================================
# HILFSFUNKTIONEN
# ============================================================================

def _print_result(result):
    """
    ================================================================================
    Pretty-Print eines Survey-Ergebnisses.
    ================================================================================
    Args:
      result (SurveyResult): Ergebnis der Survey-Ausführung.
    Returns:
      None
    ================================================================================
    """
    if result is None:
        return
    print(f"\n{'='*50}")
    print(f"  Survey:     {result.survey_id}")
    print(f"  Status:     {result.status}")
    print(f"  Provider:   {result.provider}")
    print(f"  Earned:     +{result.earned}€")
    print(f"  Steps:      {result.iterations}")
    print(f"  Duration:   {result.elapsed_s}s")
    print(f"  NIM calls:  {result.nim_calls}")
    if result.error:
        print(f"  Error:      {result.error}")
    print(f"{'='*50}\n")


def _print_result_graph(state):
    """
    ================================================================================
    Pretty-Print eines SurveyState-Ergebnisses (LangGraph Survey-Agent).
    ================================================================================
    Args:
      state (SurveyState): Ergebnis von run_survey_loop().
    Returns:
      None
    ================================================================================
    """
    if state is None:
        return

    # Status-Mapping
    status_icon = {
        "completed": "✅",
        "screen_out": "⚠️",
        "error": "❌",
        "delegated": "🤖",
    }.get(state.status, "?")

    # Verdienst berechnen
    earned = state.balance_earned
    provider = state.provider or "unknown"

    print(f"\n{'='*50}")
    print(f"  Survey:     {state.survey_id}")
    print(f"  Status:     {status_icon} {state.status}")
    print(f"  Provider:   {provider}")
    print(f"  Earned:     +{earned:.2f}€")
    print(f"  Iterations: {state.iteration}")
    print(f"  Failures:   {state.consecutive_failures}")
    if state.errors:
        last = state.errors[-1]
        print(f"  Last error: {last.get('node', '?')}: {last.get('error', '?')[:60]}")
    print(f"{'='*50}\n")

    # SR-54: Matcher-Telemetrie pro Run als JSONL persistieren.
    _persist_matcher_telemetry(state.survey_id or "unknown")


def _persist_matcher_telemetry(run_id: str) -> None:
    """Schreibt ProfileLoader.telemetry() nach logs/matcher-telemetry-{run_id}.jsonl.

    Nicht-fataler Logger-Schritt: Fehler werden nur via print gemeldet, der
    Survey-Run ist bereits fertig. Eine Zeile pro Persona → JSONL.
    """
    import json
    try:
        from survey.profile_loader import ProfileLoader
        telem = ProfileLoader.telemetry()
        if not telem:
            return
        log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
        os.makedirs(log_dir, exist_ok=True)
        path = os.path.join(log_dir, f"matcher-telemetry-{run_id}.jsonl")
        with open(path, "w") as f:
            for persona, bucket in telem.items():
                f.write(json.dumps(
                    {"persona": persona, **bucket}, ensure_ascii=False,
                ) + "\n")
        # Kleines Stdout-Summary: Top-5 Miss-Familien fehlt — wir haben
        # nur Miss-Counter, nicht per-key Miss. Fuer SR-51 erweitern.
        total_hits = sum(b.get("match_hits", 0) for b in telem.values())
        total_miss = sum(b.get("match_misses", 0) for b in telem.values())
        total = total_hits + total_miss
        rate = (total_hits / total * 100.0) if total else 0.0
        print(f"[matcher-telemetry] {total_hits} hits / {total_miss} miss "
              f"({rate:.1f}% hit-rate) -> {path}")
    except Exception as exc:
        print(f"[matcher-telemetry] write failed: {exc}")


def _detect_provider_from_url(url):
    """
    ================================================================================
    Provider aus Survey-URL extrahieren (einfache Heuristik).
    ================================================================================
    Args:
      url (str): Survey-URL
    Returns:
      str: Provider-Name (purespectrum, qualtrics, tolunastart, etc.) oder ""
    ================================================================================
    """
    if not url:
        return ""
    url_lower = url.lower()
    # Provider-Erkennung via URL-Pattern
    if "purespectrum" in url_lower:
        return "purespectrum"
    if "qualtrics" in url_lower:
        return "qualtrics"
    if "ipsosinteractive" in url_lower or "toluna" in url_lower:
        return "tolunastart"
    if "samplicio" in url_lower:
        return "samplicio"
    if "cint" in url_lower:
        return "cint"
    if "nfield" in url_lower:
        return "nfield"
    if "surveyrouter" in url_lower or "heypiggy" in url_lower:
        return "surveyrouter"
    return ""


# ============================================================================
# MAIN — CLI ENTRY POINT
# ============================================================================

def main():
    """
    ================================================================================
    Hauptfunktion — Parst CLI-Argumente und dispatched zu Kommando-Funktionen.
    ================================================================================
    """
    # ArgumentParser erstellen
    # WARUM RawDescriptionHelpFormatter? __doc__ enthält Formatierung (Zeilen, Tabs).
    parser = argparse.ArgumentParser(
        description="survey-cli — Standalone Survey Automation CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__  # Zeigt den Docstring als Hilfe an
    )

    # Globale Optionen
    parser.add_argument("--port", type=int, default=int(os.getenv("SURVEY_PORT", str(DEFAULT_PORT))),
                        help=f"CDP port (default: {DEFAULT_PORT})")
    parser.add_argument("--debug", action="store_true", help="Verbose output")

    # Subcommands
    sub = parser.add_subparsers(dest="command", help="Command")

    # login
    sub.add_parser("login", help="Login to heypiggy")

    # scan
    p = sub.add_parser("scan", help="Scan dashboard for surveys")
    p.add_argument("--all", action="store_true", help="Show all providers (don't skip blocked)")

    # run
    # ============================================================================
    # SUBCOMMAND: run — Einzelne Survey ausführen
    # ============================================================================
    # WARUM eigener Parser? run hat eigene Argumente (--id, --url, --no-nim, --no-rate).
    # WARUM --no-nim? Fallback zu Auto-Pilot wenn NIM nicht verfügbar.
    # WARUM --no-rate? Manche Surveys haben keine Bewertungs-Seite.
    p = sub.add_parser("run", help="Run a survey")
    p.add_argument("--id", type=str, help="Survey ID")
    p.add_argument("--url", type=str, help="Direct survey URL")
    p.add_argument("--no-nim", action="store_true", help="Skip NIM, use auto-pilot")
    p.add_argument("--no-rate", action="store_true", help="Skip survey rating")

    # ============================================================================
    # SUBCOMMAND: loop — Automatischer Survey-Loop
    # ============================================================================
    # WARUM --max? Loop macht mehrere Surveys — max begrenzt die Anzahl.
    # WARUM DEFAULT_MAX_SURVEYS = 5? Erfahrungswert: 3-5min pro Cycle.
    p = sub.add_parser("loop", help="Auto-loop surveys")
    p.add_argument("--max", type=int, default=DEFAULT_MAX_SURVEYS, help=f"Max surveys per loop (default: {DEFAULT_MAX_SURVEYS})")
    p.add_argument("--no-nim", action="store_true", help="Skip NIM")
    p.add_argument("--no-rate", action="store_true", help="Skip rating")

    # ============================================================================
    # SUBCOMMAND: watch — 24/7 Daemon
    # ============================================================================
    # WARUM --interval? Poll-Interval — wie oft das Dashboard gescannt wird.
    # WARUM DEFAULT_INTERVAL = 30? Siehe Konstanten-Dokumentation oben.
    # WARUM --max = 3? Watch macht weniger Surveys pro Cycle als Loop (Dauerbetrieb).
    p = sub.add_parser("watch", help="Continuous poller")
    p.add_argument("--interval", type=int, default=DEFAULT_INTERVAL, help=f"Poll interval in seconds (default: {DEFAULT_INTERVAL})")
    p.add_argument("--max", type=int, default=3, help="Max surveys per poll")
    p.add_argument("--no-nim", action="store_true", help="Skip NIM")
    p.add_argument("--no-rate", action="store_true", help="Skip rating")

    # ============================================================================
    # SUBCOMMAND: balance — Guthaben anzeigen
    # ============================================================================
    # WARUM --days = 7? Standard: Zeige letzte Woche.
    # WARUM int? Ganze Tage, keine Teil-Tage.
    p = sub.add_parser("balance", help="Show balance + summary")
    p.add_argument("--days", type=int, default=7, help="Days of history")

    # ============================================================================
    # SUBCOMMAND: status — System-Status (keine Argumente nötig)
    # ============================================================================
    sub.add_parser("status", help="Check system status")

    # ============================================================================
    # SUBCOMMAND: doctor — Vollständige Diagnose (keine Argumente nötig)
    # ============================================================================
    sub.add_parser("doctor", help="Full self-diagnostic")

    # ============================================================================
    # SUBCOMMAND: kill — Bot Chrome SICHER beenden
    # ============================================================================
    # WARUM kein Argument? safe_kill_bot() findet BOT-PIDs automatisch.
    # WARUM wichtig? Schützt USER Chrome vor unbeabsichtigtem Kill.
    sub.add_parser("kill", help="Kill bot Chrome safely")

    # ============================================================================
    # SUBCOMMAND: summary — Earnings-Zusammenfassung
    # ============================================================================
    # WARUM --days = 30? Monats-Übersicht als Default.
    p = sub.add_parser("summary", help="Earnings summary")
    p.add_argument("--days", type=int, default=30)

    # ============================================================================
    # SUBCOMMAND: opencode — Coding-Aufgabe an opencode CLI delegieren
    # ============================================================================
    # WARUM task als nargs="*"? Erlaubt multi-word Tasks ohne Quotes.
    # WARUM --timeout = 300? 5 Minuten — genug für einfache Tasks.
    p = sub.add_parser("opencode", help="Delegate task to opencode cli")
    p.add_argument("task", nargs="*", help="Task description")
    p.add_argument("--repo", type=str, help="Repo path")
    p.add_argument("--timeout", type=int, default=300, help="Wait timeout in seconds")

    # ============================================================================
    # SUBCOMMAND: profile — Persona anzeigen ODER Matcher-Telemetrie dumpen
    # ============================================================================
    # WARUM nested? "profile" hat zwei Wirkungen: show vs dump. nargs="?" mit
    # Choices erlaubt:
    #   survey profile                 → show (default)
    #   survey profile show --name anna_meyer
    #   survey profile dump --out logs/matcher-{run}.jsonl
    p = sub.add_parser("profile", help="Show persona or dump matcher telemetry")
    p.add_argument(
        "profile_action", nargs="?", default="show",
        choices=("show", "dump"),
        help="show=Profil anzeigen, dump=Matcher-Telemetrie (SR-54) ausgeben",
    )
    p.add_argument("--name", type=str, default="jeremy_schulze",
                   help="Persona-Basename (default: jeremy_schulze)")
    p.add_argument("--out", type=str, default="",
                   help="Pfad fuer JSONL-Output (nur bei dump)")
    # SR-59 #58: show the rich miss_labels table on top of the summary.
    p.add_argument("--miss-labels", dest="miss_labels", action="store_true",
                   help="Bei 'dump': zeige miss_labels-Tabelle (SR-59 #58)")

    # ============================================================================
    # ARGUMENTE PARSEN
    # ============================================================================
    # WARUM parse_args() hier? Alle Sub-Parser sind registriert.
    # parse_args() erstellt Namespace mit command + subcommand-spezifischen Attributen.
    # Beispiel: Namespace(command="run", port=9999, id="66846193", no_nim=False, ...)
    args = parser.parse_args()

    # ============================================================================
    # KEIN KOMMANDO → HILFE ANZEIGEN
    # ============================================================================
    # WARUM nicht Exception? Benutzerfreundlich — Hilfe statt Stacktrace.
    # WARUM print_help()? Zeigt alle verfügbaren Commands und deren Beschreibung.
    if not args.command:
        parser.print_help()
        return

    # ============================================================================
    # KOMMANDO-MAPPING — String → Funktion
    # ============================================================================
    # WARUM dict? O(1) Lookup, einfach zu erweitern, klar lesbar.
    # WARUM nicht if/elif Kette? Unübersichtlich bei 12 Commands.
    # WARUM nicht dynamisch (globals())? Sicherer — nur explizit registrierte Commands.
    cmd_map = {
        "login": cmd_login,
        "scan": cmd_scan,
        "run": cmd_run,
        "loop": cmd_loop,
        "watch": cmd_watch,
        "balance": cmd_balance,
        "status": cmd_status,
        "doctor": cmd_doctor,
        "kill": cmd_kill,
        "summary": cmd_summary,
        "opencode": cmd_opencode,
        "profile": cmd_profile,
    }

    # ============================================================================
    # KOMMANDO AUSFÜHREN
    # ============================================================================
    # WARUM cmd_map.get()? Sichereres Lookup — None wenn Command nicht existiert
    # (obwohl argparse das schon abfängt, defensive programming).
    # WARUM cmd_fn(args)? Jede cmd_* Funktion erwartet args.Namespace.
    cmd_fn = cmd_map.get(args.command)
    if cmd_fn:
        cmd_fn(args)


# ============================================================================
# PROGRAMM-START — Entry Point
# ============================================================================
# WARUM if __name__ == "__main__"?
#   Ermöglicht Import als Modul (from survey-cli.survey import main)
#   ohne dass main() automatisch ausgeführt wird.
# WARUM main()? Kapselt CLI-Logik — testbar.
if __name__ == "__main__":
    main()
