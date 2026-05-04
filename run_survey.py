import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from app.core.orchestrator import run
from app.flows.learning import survey_heypiggy

FLOW = "survey_heypiggy"
PAYLOAD = {
    "radio_hints": ["Berlin", "männlich", "Angestellter", "Meister", "Deutsch"],
    "checkbox_hints": ["Keine"],
    "textarea_value": "Ja"
}

if __name__ == "__main__":
    print(f"[FLOW] Starting: {FLOW}")
    result = run(FLOW, survey_heypiggy.execute, PAYLOAD)
    print(f"[FLOW] Result: {result}")
