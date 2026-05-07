#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""================================================================================
FCTES GLOBAL CONFIGURATION — Zentrale Konstanten
================================================================================

WAS IST DAS?
  Zentrale Konfigurationsdatei fuer das gesamte FCTES-System.
  ALLE Pfade und Konstanten an EINER Stelle — keine Magic Strings im Code.

WARUM EXISTIERT DAS?
  Magic Strings = Bugs. Wenn sich ein Pfad aendert, muss man 20 Dateien
  editieren. Mit config.py aendert man EINE Zeile.
  
  Architecture:
    ┌──────────────┐
    │   config.py  │◄────── Alle Module importieren von hier
    └──────────────┘
         │
    ┌────┴────┬────────┬────────┬────────┐
    │compiler │registry│tracker │executor│tool_builder│
    └─────────┴────────┴────────┴────────┘

KONSTANTEN:
  THRESHOLD = 10
    → Warum 10? Siehe compiler.py REQUIRED_SUCCESSES.
    → Statistisch signifikant (99%+ Konfidenz).
    → NIE aendern ohne alle Flow-Status zu invalidieren!
    
  ROOT_DIR = "/Users/jeremy/dev/stealth-runner"
    → Absoluter Pfad zum Repo-Root.
    → Warum hardcoded? Weil __file__ relativ ist und bei Symlinks failt.
    → FIXME: Dynamisch via Path(__file__).parent.parent ermitteln.
    
  FLOW_DIR = ROOT_DIR + "/app/flows/learning"
    → Wo YAML-Definitionen der Learning-Flows liegen.
    → Jeder Flow = eigener Unterordner mit flow.yaml.
    
  COMPILED_DIR = ROOT_DIR + "/app/flows/compiled"
    → Wo gefrorene Flows landen.
    → Dateien: <flow_name>_v<TIMESTAMP>.py
    → Diese Dateien sind GENERIERT — nicht manuell editieren!
    
  STATE_DIR = ROOT_DIR + "/app/state"
    → Wo Status-Dateien liegen:
      - flow_<name>.json (FlowStatus)
      - registry.json (Registry)
      - success.json (Tracker)
    → Git-tracked fuer Team-Synchronisation.
    
  OPENCODE_JSON = ROOT_DIR + "/opencode.json"
    → Agent/CLI Interface — Liste aller registrierten Tools.
    → Siehe tool_builder.py fuer Format.
    
  PLAYSTEALTH_PID = None
    → DEPRECATED! Playstealth ist BANNED (siehe banned.md).
    → Bleibt None. NIE verwenden!
    
  CHROME_WID = None
    → Fenster-ID wird dynamisch ermittelt (via cua-driver list_windows).
    → Hardcoded WID = kaputt (UI aendert sich).
    → Bleibt None. NIE verwenden!
    
  CDP_PORT = None
    → CDP-Port wird dynamisch ermittelt (via Chrome-Prozess).
    → Standard: 9999, aber kann abweichen bei Konflikten.
    → Bleibt None. NIE hardcodieren!

BANNED METHODS — NIEMALS VERWENDEN:
  ❌ playstealth launch
  ❌ webauto-nodriver
  ❌ cua-driver click (raw index)
  ❌ --remote-allow-origins=* (ohne Quotes)
  ❌ /tmp/heypiggy-bot (fixed profile)
  ❌ Hardcoded PIDs
  ❌ pkill -f "Google Chrome"
  ❌ killall Google Chrome
  ❌ skylight-cli click --element-index
================================================================================"""

# ═════════════════════════════════════════════════════════════════════════════
# FCTES KONSTANTEN
# ═════════════════════════════════════════════════════════════════════════════

# THRESHOLD: Schwelle fuer Production-Promotion
#   → 10 = statistisch signifikant (99%+ Konfidenz bei p=0.5)
#   → Wenn geaendert: ALLE Flow-Status invalidieren (reset auf learning)!
#   → NICHT aendern ohne Team-Abstimmung und Migration!
THRESHOLD = 10

# ROOT_DIR: Absoluter Pfad zum Repository-Root
#   → Warum hardcoded? __file__ ist relativ und failt bei:
#     - Symlinks (readlink -f)
#     - Verschiedenen CWD (cd /tmp && python /pfad/script.py)
#     - Docker/Paketierung (Mount-Punkte)
#   → FIXME: Ermitteln via subprocess.run(['git', 'rev-parse', '--show-toplevel'])
#     fuer echte Robustheit.
ROOT_DIR = "/Users/jeremy/dev/stealth-runner"

# FLOW_DIR: Learning-Flow YAML-Definitionen
#   → Struktur: FLOW_DIR/<flow_name>/flow.yaml
#   → Beispiel: FLOW_DIR/survey_heypiggy/flow.yaml
#   → Alternative: FLOW_DIR/<flow_name>.yaml (flat, legacy)
FLOW_DIR = ROOT_DIR + "/app/flows/learning"

# COMPILED_DIR: Gefrorene Production-Flows
#   → Dateien: COMPILED_DIR/<flow_name>_v<TIMESTAMP>.py
#   → GENERIERT durch compiler.py — NIE manuell editieren!
#   → Wenn geloescht: Flow muss neu kompiliert werden (10 Erfolge noetig).
COMPILED_DIR = ROOT_DIR + "/app/flows/compiled"

# STATE_DIR: Persistente Status-Dateien
#   → Dateien:
#     - flow_<name>.json: FlowStatus (tier, run_count, etc.)
#     - registry.json: Source of Truth fuer gefrorene Flows
#     - success.json: Globaler Erfolgs-Counter
#   → Git-tracked fuer Team-Synchronisation
#   → NIE loeschen! Status-Verlust = Flows starten von vorne.
STATE_DIR = ROOT_DIR + "/app/state"

# OPENCODE_JSON: Agent/CLI Interface
#   → Format: {"tools": [...], "flows": [...]}
#   → Wird von tool_builder.py geschrieben
#   → Wird von Agent/CLI gelesen
#   → Git-tracked (Synchronisation zwischen Entwicklern)
OPENCODE_JSON = ROOT_DIR + "/opencode.json"

# ═════════════════════════════════════════════════════════════════════════════
# DEPRECATED / BANNED KONSTANTEN (NICHT VERWENDEN!)
# ═════════════════════════════════════════════════════════════════════════════

# PLAYSTEALTH_PID: Wurde fuer playstealth-Integration genutzt.
#   → playstealth ist BANNED (siehe banned.md).
#   → Diese Variable bleibt None und wird entfernt in v2.0.
#   → NIE verwenden! Chrome MANUELL starten (siehe survey-cli/survey/chrome.py).
PLAYSTEALTH_PID = None  # ❌ BANNED — nicht verwenden!

# CHROME_WID: Wurde fuer hardcoded Window-ID genutzt.
#   → Window-IDs aendern sich bei jedem Chrome-Start!
#   → Hardcoded WID = Klick auf falsches Fenster = Chaos.
#   → Dynamisch ermitteln via cua-driver list_windows.
CHROME_WID = None  # ❌ BANNED — nicht verwenden!

# CDP_PORT: Wurde fuer hardcoded CDP-Port genutzt.
#   → Standard ist 9999, aber kann abweichen (Port belegt, mehrere Instanzen).
#   → Dynamisch ermitteln via Chrome-Prozess (--remote-debugging-port).
CDP_PORT = None  # ❌ BANNED — nicht verwenden!
