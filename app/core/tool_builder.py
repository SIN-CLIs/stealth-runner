#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""================================================================================
FCTES TOOL BUILDER — opencode.json Registration
================================================================================

WAS IST DAS?
  Registriert gefrorene Flows als Tools in opencode.json.
  opencode.json ist das Interface zwischen FCTES und dem Agent/CLI.
  
  Wenn ein Flow kompiliert wird, erzeugt tool_builder einen Eintrag:
  {
    "name": "survey_heypiggy_v1746691200",
    "description": "Frozen deterministic flow: survey_heypiggy",
    "strict": true,
    "input_schema": {"type": "object", "properties": {}, "additionalProperties": true},
    "frozen_at": 1746691200,
    "source": "FCTES-compiler"
  }

WARUM EXISTIERT DAS?
  Agenten und CLI lesen opencode.json um verfuegbare Tools zu finden.
  Ein Tool in opencode.json = Agent darf es aufrufen.
  Kein Tool in opencode.json = Agent weiss nicht, dass es existiert.
  
  Architecture:
    ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
    │   compiler   │────▶│ tool_builder │────▶│ opencode.json│
    │  .compile()  │     │  .register() │     │              │
    └──────────────┘     └──────────────┘     └──────────────┘
                                                   │
                                                   ▼
                                            ┌──────────────┐
                                            │ Agent / CLI  │
                                            │ (reads tools)│
                                            └──────────────┘

DATEI:
  opencode.json (in Repo-Root)
    → Format: {"tools": [...], "flows": [...]}
    → WARUM im Repo-Root?
      opencode.json ist die Schnittstelle zum Agent-System.
      Muss im Root liegen damit der Agent es findet.
    → WARUM nicht gitignored?
      Registrierte Tools muessen versioniert werden (Team-Sync).
    → WARUM indent=2?
      Human-readable fuer Diff/Review.

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

import json      # Für opencode.json
import os        # Für os.path.exists()

from app.config import OPENCODE_JSON


def register(flow_name, version):
    """Registriert kompilierten Flow als Tool in opencode.json.
    
    ARGS:
        flow_name (str): Name des Flows (z.B. "survey_heypiggy")
        version (int): Unix-Timestamp (Compile-Zeit)
        
    WARUM alte Versionen loeschen?
      Jeder Flow hat NUR EINE aktive Version im opencode.json.
      Alte Versionen werden gefiltert:
      [t for t in tools if not t["name"].startswith(flow_name + "_v")]
      → Verhindert, dass Agent verwirrt wird durch 20 alte Versionen.
      
    WARUM strict: true?
      Hard Enforcement: Agent darf nur definierte Felder senden.
      additionalProperties: true erlaubt trotzdem Extra-Felder.
      → Kombination: Schema ist relaxed, aber Tool ist strict.
      (Ja, das ist inkonsistent. FIXME: strict + additionalProperties: false)
      
    WARUM source: "FCTES-compiler"?
      Audit-Trail. Wenn Tool kaputt ist, wissen wir: Compiler erzeugt es.
      → Nicht manuell editiert, nicht von anderem Tool.
      
    WARUM print?
      Audit-Trail in Daemon-Log.
    """
    data = _load()
    tool_name = f"{flow_name}_v{version}"
    tool = {
        "name": tool_name,
        "description": f"Frozen deterministic flow: {flow_name}",
        "strict": True,
        "input_schema": {"type": "object", "properties": {}, "additionalProperties": True},
        "frozen_at": version,
        "source": "FCTES-compiler"
    }
    # Alte Versionen dieses Flows entfernen
    data["tools"] = [t for t in data.get("tools", []) if not t["name"].startswith(flow_name + "_v")]
    data.setdefault("tools", []).append(tool)
    _save(data)
    print(f"[TOOL] Registered: {tool_name}")


def list_tools():
    """Listet alle registrierten Tools auf.
    
    RETURNS:
        list: Liste aller Tool-Dictionaries aus opencode.json
        
    WARUM nicht gefiltert?
      Aufrufer (CLI, Agent) kann selbst filtern.
      → Maximale Flexibilität.
    """
    return _load().get("tools", [])


def is_registered(flow_name):
    """Prueft ob Flow bereits als Tool registriert ist.
    
    ARGS:
        flow_name (str): Name des Flows (OHNE Version!)
        
    RETURNS:
        bool: True wenn irgendeine Version registriert ist
        
    WARUM any() mit startswith?
      Wir pruefen ob EINE Version existiert, nicht eine spezifische.
      "survey_heypiggy_v123" startswith "survey_heypiggy_v" → True
      
    WARUM nicht exakter Match?
      Flow-Name ohne Version = "survey_heypiggy".
      Tool-Name = "survey_heypiggy_v1746691200".
      → Prefix-Match noetig.
    """
    tools = _load().get("tools", [])
    return any(t["name"].startswith(f"{flow_name}_v") for t in tools)


def _load():
    """Lädt opencode.json oder Default-Struktur.
    
    RETURNS:
        dict: {"tools": [...], "flows": [...]}
        
    WARUM Default mit leeren Listen?
      Erste Ausführung: Datei existiert nicht → leere Struktur.
      → Kein KeyError spaeter.
    """
    if not os.path.exists(OPENCODE_JSON):
        return {"tools": [], "flows": []}
    return json.loads(open(OPENCODE_JSON).read())


def _save(data):
    """Speichert opencode.json.
    
    WARUM indent=2?
      Human-readable fuer git diff und Code Review.
    
    WARNUNG: Kein Backup!
      Bei Crash waehrend write() ist opencode.json korrupt.
      → FIXME: Atomic write (temp file + rename).
    """
    open(OPENCODE_JSON, "w").write(json.dumps(data, indent=2))
