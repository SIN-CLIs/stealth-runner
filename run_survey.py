#!/usr/bin/env python3
"""
Single Entry Point — EIN Call, fertig.
Agent macht NUR das hier:
  python run_survey.py

NICHT:
  - Schritte selbst überlegen
  - CUA-Befehle raten
  - CDP verwenden
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.orchestrator import run as orch_run
from app.flows.learning import survey_heypiggy

FLOW = "survey_heypiggy"
PAYLOAD = {
    "radio_hints": ["Berlin", "männlich", "Angestellter", "Meister", "Deutsch"],
    "checkbox_hints": ["Keine"],
    "textarea_value": "Ja"
}

if __name__ == "__main__":
    print(f"[FLOW] Starting: {FLOW}")
    result = orch_run(FLOW, survey_heypiggy.execute, PAYLOAD)
    print(f"[FLOW] Result: {result}")