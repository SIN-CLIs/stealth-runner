#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""================================================================================
FCTES REGISTRY — Source of Truth für Gefrorene Flows
================================================================================

WAS IST DAS?
  Zentrale Registry aller gefrorenen (production) Flows.
  Speichert: Flow-Name → {version, path, frozen: True}
  
  Dies ist die SOURCE OF TRUTH. Wenn ein Flow hier nicht registriert ist,
  darf er NICHT als Production-Tool ausgeführt werden!

WARUM EXISTIERT DAS?
  Agenten können opencode.json manipulieren (oder es gibt race conditions).
  Registry ist separat, minimalistisch, und dient als Kanonische Wahrheit.
  
  Architecture:
    ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
    │   compiler   │────▶│   registry   │────▶│  dispatcher  │
    │  .compile()  │     │   .save()    │     │   .dispatch()│
    └──────────────┘     └──────────────┘     └──────────────┘
                              │
                              ▼
                    app/state/registry.json

DATEI:
  registry.json (in STATE_DIR)
    → Format: {"flow_name": {"version": 1746691200, "path": "...", "frozen": true}}
    → WARUM "frozen": true?
      Explicit Flag statt implizit. Dispatcher prüft explizit:
      if not meta.get("frozen"): raise Exception
      → Verhindert, dass unfrozen Flows ausgeführt werden.
    → WARUM version als int?
      Unix-Timestamp. Eindeutig, sortierbar, parsierbar.

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

import json      # Für registry.json — Source of Truth
import os        # Für os.path.exists(), os.makedirs()

from app.config import STATE_DIR

# REGISTRY_FILE: Pfad zur Registry-JSON
#   → Ort: app/state/registry.json (versioniert, git-tracked)
#   → Warum nicht ~/.stealth/? Weil Registry Teil der App-Logik ist
#     (nicht User-spezifisch). Mehrere Agents teilen dieselbe Registry.
REGISTRY_FILE = STATE_DIR + "/registry.json"


def save(flow_name, version, path):
    """Registriert gefrorenen Flow in Registry.
    
    ARGS:
        flow_name (str): Eindeutiger Flow-Name
        version (int): Unix-Timestamp (Compile-Zeit)
        path (str): Absoluter Pfad zur kompilierten Flow-Datei
        
    WARUM Überschreiben statt Append?
      Jeder Flow hat NUR EINE aktive Version. Alte Versionen werden
      durch neue ersetzt (dict assignment: data[flow_name] = {...}).
      → Kein Version-Historie (einfacher, weniger Speicher).
      
    WARUM print?
      Audit-Trail. Jede Registry-Änderung wird geloggt.
    """
    data = _load()
    data[flow_name] = {"version": version, "path": str(path), "frozen": True}
    _save(data)
    print(f"[REGISTRY] {flow_name} → v{version}")


def get(flow_name):
    """Gibt Registry-Eintrag für Flow zurück.
    
    ARGS:
        flow_name (str): Name des Flows
        
    RETURNS:
        dict oder None: {"version": int, "path": str, "frozen": bool}
        
    WARUM None statt Exception?
      Dispatcher prüft auf None und wirft eigene Exception mit Kontext.
      → Besserer Fehler-Message für Agent.
    """
    return _load().get(flow_name)


def is_frozen(flow_name):
    """Prüft ob Flow gefroren (production-ready) ist.
    
    ARGS:
        flow_name (str): Name des Flows
        
    RETURNS:
        bool: True wenn registriert UND frozen=True
        
    WARUM nicht nur get()?
      Convenience. Dispatcher nutzt is_frozen() für schnelle Prüfung.
      
    WARUM "entry is not None"?
      Expliziter Check. None → False (nicht gefroren).
    """
    entry = get(flow_name)
    return entry is not None and entry.get("frozen", False)


def _load():
    """Lädt registry.json.
    
    WARUM leeres Dict als Default?
      Erste Ausführung: Datei existiert nicht → leere Registry.
      → Graceful, kein Fehler.
    """
    if not os.path.exists(REGISTRY_FILE):
        return {}
    return json.loads(open(REGISTRY_FILE).read())


def _save(data):
    """Speichert registry.json.
    
    WARUM os.makedirs?
      STATE_DIR muss nicht vorher existieren.
    """
    os.makedirs(STATE_DIR, exist_ok=True)
    open(REGISTRY_FILE, "w").write(json.dumps(data, indent=2))
