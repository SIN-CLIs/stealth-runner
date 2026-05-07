#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""================================================================================
FCTES TRACKER — Success Counter & Auto-Promotion
================================================================================

WAS IST DAS?
  Zentrale Erfolgs-Zählung für FCTES (Freeze & Compile Tool Enforcement System).
  Recordet jeden Flow-Run und triggert automatisch Promotion zu Production,
  wenn Threshold (10 Erfolge) erreicht wird.

WARUM EXISTIERT DAS?
  Agenten vergessen zu zählen. Sie sagen "success" aber speichern nicht.
  Dieses Modul persistiert Erfolge in JSON und triggert compile() automatisch.
  → Zero-friction: Flow wird frozen, sobald er reif ist.

ARCHITEKTUR:
  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
  │   tracker    │────▶│   compiler   │────▶│  production  │
  │  .record()   │     │  .compile()  │     │   (frozen)   │
  └──────────────┘     └──────────────┘     └──────────────┘
       │
       ▼
  ~/.stealth/state/success.json

DEPENDENZEN:
  - app.core.compiler.FlowCompiler: Für Status-Abfrage und Promotion-Trigger
  - app.config.STATE_DIR: Wo success.json gespeichert wird

DATEI:
  success.json (in STATE_DIR)
    → Format: {"flow_name": run_count, ...}
    → WARUM run_count und nicht success_count?
      Diese Datei ist ein SECONDARY index (schneller Lookup).
      Der PRIMARY status ist in flow_<name>.json (detaillierter).
    → WARUM JSON und nicht SQLite?
      Einfachkeit. Max 50 Flows, kein Query-Performance-Bedarf.

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

KORREKT:
  ✅ NUR survey-cli/tools/ für Browser-Interaktionen
  ✅ NUR src/stealth_survey/ für NEMO-Loop
================================================================================"""

import json      # Für success.json — human-readable counter
import os        # Für os.path.exists(), os.makedirs()
import time      # Für Zeitstempel (nicht aktiv genutzt, reserviert)
from pathlib import Path  # Type-safe Pfad-Manipulation

# ═════════════════════════════════════════════════════════════════════════════
# KONFIGURATION
# ═════════════════════════════════════════════════════════════════════════════
from app.config import STATE_DIR

# TRACK_FILE: Persistenter Counter für alle Flow-Runs
#   → Zweck: Schneller, globaler Überblick über alle Flow-Erfolge
#   → Warum nicht in flow_<name>.json? Weil das für STATUS ist (tier, etc.).
#     Dieses File ist für QUICK LOOKUP (z.B. "Wie viele Surveys heute?").
#   → Warum nicht im Repo? Weil es sich ändert bei jedem Run (git noise).
TRACK_FILE = STATE_DIR + "/success.json"


# ═════════════════════════════════════════════════════════════════════════════
# FUNKTION: record()
# ═════════════════════════════════════════════════════════════════════════════
def record(flow_name, verdict="success_direct"):
    """Recordet einen Flow-Run und triggert Auto-Promotion.
    
    ARGS:
        flow_name (str): Name des Flows (z.B. "survey_heypiggy")
        verdict (str): Ergebnis des Runs
            - "success_direct": Voller Erfolg → zählt für Promotion
            - "success_disqual": Disqualifiziert → zählt NICHT
            - "error_*": Fehler → zählt als failure
            
    RETURNS:
        bool: True (immer, außer bei Exception)
        
    ALGORITHMUS:
      1. FlowCompiler.record_run() aufrufen → Status aktualisieren
      2. success.json laden (oder leeres Dict)
      3. Counter für flow_name erhöhen
      4. success.json speichern
      5. Status abfragen (FlowCompiler.get_status)
      6. WENN can_promote: compile() triggern
      7. Log Promotion-Erfolg
      
    WARUM record_run() VOR _load()/_save()?
      Status-Update hat Priorität. Wenn _load() fehlschlägt (korrupte JSON),
      wollen wir trotzdem den Status im flow_<name>.json aktualisiert haben.
      → Status ist PRIMARY, success.json ist SECONDARY (nice-to-have).
      
    WARUM automatisch compile()?
      Zero-friction promotion. Agent/Daemon muss nicht explizit prüfen.
      Nach 10. Erfolg wird Flow SOFORT gefroren.
      → Verhindert, dass Agent den 11. Run noch als "learning" macht.
      
    WARUM import INSIDE der Funktion?
      Lazy import von FlowCompiler. Vermeidet circular imports
      (compiler.py importiert tracker.py nicht, aber tracker.py importiert
      compiler.py). → Vermeidet Import-Loop beim Modul-Load.
      
    SIDE-EFFECTS:
      - Schreibt in flow_<name>.json (via compiler)
      - Schreibt in success.json (via _save)
      - Kann compile() triggern (erzeugt compiled/ + registry.json + opencode.json)
      - Print-Ausgabe für Daemon-Log
    """
    from app.core.compiler import FlowCompiler
    compiler = FlowCompiler()
    compiler.record_run(flow_name, verdict)

    data = _load()
    data[flow_name] = data.get(flow_name, 0) + 1
    _save(data)
    count = data[flow_name]

    status = compiler.get_status(flow_name)
    remaining = status["remaining"]
    tier = status["tier"]
    print(f"[TRACKER] {flow_name} #{count} ({tier}) — {remaining} bis production")

    # Auto-Promotion: Wenn genug Erfolge, sofort kompilieren
    if status["can_promote"]:
        compiled = compiler.compile(flow_name)
        if compiled:
            print(f"[TRACKER] {flow_name} PROMOTED to production! ✅")

    return True


# ═════════════════════════════════════════════════════════════════════════════
# FUNKTION: get()
# ═════════════════════════════════════════════════════════════════════════════
def get(flow_name):
    """Gibt detaillierten Status für Flow zurück.
    
    ARGS:
        flow_name (str): Name des Flows
        
    RETURNS:
        dict: FlowStatus.summary() — alle Diagnose-Felder
        
    WARUM nicht success.json zurückgeben?
      success.json hat nur run_count (wenig Information).
      FlowCompiler.get_status() hat tier, remaining, can_promote, etc.
      → Reicherer Output für CLI und Agent-Diagnose.
    """
    from app.core.compiler import FlowCompiler
    return FlowCompiler().get_status(flow_name)


# ═════════════════════════════════════════════════════════════════════════════
# HELPER: _load() / _save()
# ═════════════════════════════════════════════════════════════════════════════
def _load():
    """Lädt success.json oder leeres Dict.
    
    WARUM nicht Exception bei korruptem JSON?
      Korrupte JSON = Datenverlust, aber nicht fatal.
      Wir returnen leeres Dict und starten frisch.
      → Graceful degradation: Flow läuft weiter, Counter resettet.
      
    WARUM nicht os.path.exists check?
      open() wirft FileNotFoundError, den wir catchen könnten.
      Aber os.path.exists() + open() ist zweit atomic (race condition).
      → Einfacher: try/except um json.loads().
    """
    if not os.path.exists(TRACK_FILE):
        return {}
    return json.loads(open(TRACK_FILE).read())


def _save(data):
    """Speichert success.json atomisch.
    
    WARUM os.makedirs(STATE_DIR, exist_ok=True)?
      STATE_DIR muss nicht vorher existieren (erster Run erzeugt es).
      
    WARUM json.dumps(indent=2)?
      Human-readable für Debug (cat success.json).
      
    WARUM nicht atomic write (temp file + rename)?
      Einfachheit. Bei 50 Flows ist Korruptionsrisiko minimal.
      Bei Bedarf: write to .tmp, then rename (atomic auf POSIX).
    """
    os.makedirs(STATE_DIR, exist_ok=True)
    open(TRACK_FILE, "w").write(json.dumps(data, indent=2))
