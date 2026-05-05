#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
RUN_SURVEY — Single Entry Point für Heypiggy Survey Flow
================================================================================
Repo    : /Users/jeremy/dev/stealth-runner/run_survey.py
Stand   : 2026-05-05
Version : 1.0 (aktualisiert für auto_google_login ✅)

================================================================================
SHELL COMMAND ZUM STARTEN:
================================================================================

# Variante 1: Direkt (empfohlen)
python3 run_survey.py

# Variante 2: Mit explizitem Payload
cd /Users/jeremy/dev/stealth-runner
python3 -c "
from app.flows.learning.survey_heypiggy import execute
result = execute()
print(result)
"

# Variante 3: Direkt mit auto_google_login (falls nur Login nötig)
python3 -c "
from cli.modules.auto_google_login import execute as auto_login
result = auto_login()
print(result)
"

================================================================================
FLOW ARCHITEKTUR:
================================================================================

run_survey.py → survey_heypiggy.execute() → auto_google_login.execute()
                                              ↓
                                         Dashboard (pid, wid)
                                              ↓
                                         Survey Loop (50x)
                                              ↓
                                         Balance-Vergleich

================================================================================
PERSONA (HARDCODED):
================================================================================

BERLIN — MÄNNLICH — ANGESTELLTER — MEISTER — DEUTSCH

Address: Kurfürstenstraße 124, 10785 Berlin
Haushalt: 2-Personen
Anstellung: Unbefristet

radio_hints    = ["Berlin", "männlich", "Angestellter", "Meister", "Deutsch"]
checkbox_hints = ["Keine"]
textarea_value = "Ja"

================================================================================
EXPECTED OUTPUT:
================================================================================

Bei erfolgreichem Survey (z.B. 15 Fragen, 0.77€ pro Survey):

{
  "status": "ok",
  "earned": 0.77,
  "start": 0.00,
  "end": 0.77,
  "pid": 71104,
  "wid": 56640
}

Bei Login-Fehler:

{
  "status": "error",
  "reason": "login_failed" | "chrome_launch_failed" | "no_dashboard_window" | ...
}

================================================================================
"""

import sys
import os

# Projekt-Root in sys.path für relative Imports
sys.path.insert(0, os.path.dirname(__file__))


def main():
    """
    Main Entry Point für Survey Flow
    """
    FLOW = "survey_heypiggy"

    print(f"[FLOW] Starting: {FLOW}")
    print(f"[FLOW] Persona: Berlin, männlich, Angestellter, Meister, Deutsch")
    print(f"[FLOW] Import: from app.flows.learning import survey_heypiggy")

    # Direkt survey_heypiggy.execute() aufrufen (ohne orchestrator)
    from app.flows.learning import survey_heypiggy
    result = survey_heypiggy.execute()

    print(f"[FLOW] Result: {result}")
    return result


if __name__ == "__main__":
    main()
