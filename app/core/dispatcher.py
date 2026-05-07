#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""================================================================================
FCTES DISPATCHER — Hard Enforcement: Nur Gefrorene Flows
================================================================================

WAS IST DAS?
  Dispatcher ist das GATEKEEPER-Modul des FCTES-Systems.
  Er laesst NUR versionierte, gefrorene Tools durch.
  
  REGEL: Wenn Tool-Name nicht "_v" enthaelt → REJECTED
  REGEL: Wenn Flow nicht in Registry → REJECTED  
  REGEL: Wenn Flow nicht frozen → REJECTED

WARUM EXISTIERT DAS?
  Agenten sollen NUR frozen Tools aufrufen. Keine Experimente in Production.
  Dispatcher enforced dies hart: Exceptions bei Verletzung.
  
  Architecture:
    ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
    │   Agent/CLI  │────▶│  dispatcher  │────▶│   executor   │
    │  "tool_v123" │     │  .dispatch() │     │   .run()     │
    └──────────────┘     └──────────────┘     └──────────────┘
                              │
                              ▼
                    Prüft: Registry + frozen

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

from app.core import registry, executor


def dispatch(tool_name, payload):
    """Dispatcht Tool-Ausfuehrung mit Hard Enforcement.
    
    ARGS:
        tool_name (str): Vollstaendiger Tool-Name z.B. "survey_heypiggy_v1746691200"
                         MUSS "_v" enthalten (Versions-Tag)
        payload (dict): Parameter-Dict fuer den Flow
        
    RETURNS:
        Any: Ergebnis des Flow-Executions
        
    RAISES:
        ValueError: Wenn Tool-Name nicht versioniert (kein "_v")
        Exception: Wenn Flow nicht in Registry
        Exception: Wenn Flow nicht frozen
        
    ALGORITHMUS:
      1. Prüfen: "_v" in tool_name?
         → NEIN: ValueError("Tool name must be versioned")
      2. Extrahieren: flow_name = tool_name.split("_v")[0]
      3. Registry-Lookup: registry.get(flow_name)
         → None: Exception("Flow not registered")
      4. Prüfen frozen: meta.get("frozen")
         → False: Exception("Flow not frozen")
      5. Executor aufrufen: executor.run(meta["path"], payload)
      
    WARUM ValueError statt Exception fuer unversionierten Namen?
      ValueError = falsche Nutzung (API-Verletzung).
      Exception = Runtime-Fehler (Flow existiert nicht).
      → Unterschiedliche Fehlerklassen fuer unterschiedliche Behebung.
      
    WARUM split("_v")[0]?
      "survey_heypiggy_v1746691200".split("_v") 
      → ["survey_heypiggy", "1746691200"]
      → [0] = "survey_heypiggy" (Flow-Name)
      
    WARUM nicht registry.get(tool_name)?
      Registry speichert Flow-Namen (ohne Version).
      Tool-Name = Flow-Name + Version.
      → Wir muessen den Flow-Name extrahieren.
    """
    if "_v" not in tool_name:
        raise ValueError(f"Tool name must be versioned: {tool_name}")
    flow_name = tool_name.split("_v")[0]
    meta = registry.get(flow_name)
    if not meta:
        raise Exception(f"Flow not registered: {flow_name}")
    if not meta.get("frozen"):
        raise Exception(f"Flow not frozen: {flow_name}")
    return executor.run(meta["path"], payload)
