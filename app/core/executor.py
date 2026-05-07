#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""================================================================================
FCTES EXECUTOR — Flow-Execution via importlib
================================================================================

WAS IST DAS?
  Fuehrt gefrorene Flows aus, die als Python-Module kompiliert wurden.
  Nutzt importlib (nicht __import__) fuer saubere, isolierte Execution.

WARUM EXISTIERT DAS?
  Gefrorene Flows sind Python-Dateien (compiled/). Executor laedt sie
  dynamisch und ruft execute(payload) auf.
  
  Architecture:
    ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
    │  dispatcher  │────▶│   executor   │────▶│  Flow-Modul  │
    │  .dispatch() │     │   .run()     │     │  .execute()  │
    └──────────────┘     └──────────────┘     └──────────────┘

SICHERHEIT:
  - importlib.util.spec_from_file_location: Kein sys.path Manipulation
  - Modul wird als "flow_mod" registriert (fixed Name, kein Konflikt)
  - Kein exec() oder eval() — nur importlib
  
  WARUM KEIN exec()?
    exec() ist unsicher (Code-Injection). importlib ist der saubere
    Weg, Python-Dateien dynamisch zu laden.
    
  WARUM "flow_mod" als Modul-Name?
    Fester Name verhindert, dass Module im Cache konfligieren.
    Bei jedem run() wird fresh geladen (neuer sys.modules Eintrag).
    
  WARNUNG: sys.modules["flow_mod"] wird UEBERSCHRIEBEN bei jedem run()!
    Das ist beabsichtigt. Gefrorene Flows sind stateless.
    Bei Bedarf: Eindeutiger Name pro Flow (f"flow_{flow_name}_{version}")

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

import importlib.util   # Sicheres dynamisches Laden von Python-Modulen
import sys              # Für sys.modules (Modul-Cache)
from pathlib import Path # Type-safe Pfad


def run(path, payload):
    """Fuehrt gefrorenen Flow aus.
    
    ARGS:
        path (str): Absoluter Pfad zur kompilierten Flow-Python-Datei
        payload (dict): Parameter fuer den Flow
        
    RETURNS:
        Any: Ergebnis von flow_mod.execute(payload)
        
    RAISES:
        FileNotFoundError: Wenn Flow-Datei nicht existiert
        AttributeError: Wenn Flow kein execute() definiert
        Exception: Alles was der Flow selbst wirft
        
    ALGORITHMUS:
      1. Path(path) erstellen (type-safe)
      2. spec_from_file_location("flow_mod", p) → Modul-Spec
      3. module_from_spec(spec) → Leeres Modul
      4. sys.modules["flow_mod"] = mod → Cache-Eintrag
      5. spec.loader.exec_module(mod) → Code ausfuehren
      6. mod.execute(payload) → Flow-Logik aufrufen
      
    WARUM spec_from_file_location?
      Sicherer als direktes open() + compile() + exec().
      importlib.util handhabt korrekt:
      - __file__, __name__ im Modul
      - Relative Imports im Flow
      - Import-Hooks (z.B. fuer encrypted flows)
      
    WARUM sys.modules["flow_mod"] = mod?
      Damit Modul sich selbst importieren kann (z.B. fuer Sub-Module).
      ABER: Name ist fix ("flow_mod"), nicht eindeutig.
      → Risk: Wenn zwei Flows parallel laufen, kollidieren sie.
      → FIXME: Eindeutiger Name verwenden (flow_{name}_{version}_{timestamp}).
      
    WARUM return mod.execute(payload)?
      Konvention: Jeder gefrorene Flow MUSS execute(payload) definieren.
      Das ist das Entry-Point-Contract.
    """
    p = Path(path)
    spec = importlib.util.spec_from_file_location("flow_mod", p)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["flow_mod"] = mod
    spec.loader.exec_module(mod)
    return mod.execute(payload)
