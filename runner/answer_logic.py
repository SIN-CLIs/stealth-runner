"""answer_logic.py – Frage-Klassifizierung + Persona-gestützte Antwort-Generierung.

Portiert von A2A-SIN-Worker answer_router.py. Fokussiert auf die 3 häufigsten Fragetypen:
1. DEMOGRAPHIC: Alter, Geschlecht, PLZ, Einkommen → Persona-Fact
2. FREE_TEXT: Offene Textfragen (Reiseerfahrung etc.) → Heuristik + Mistral-LLM
3. SINGLE_CHOICE/MULTI: Radio/Checkbox → Persona-Match + LLM-Fallback

NEU: Mistral-LLM Fallback (config/models.yaml → task=persona).
Wenn Keyword-Matching nichts findet, fragt ein dediziertes Mistral-Modell
(mistral/mistral-small-latest) die Persona-Daten intelligent ab.
"""
from __future__ import annotations
import json, os, re, subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from runner.model_router import ModelRouter, Task, get_router

# ── Demografie-Mapping aus Persona-Profil ──
PROFILE = Path(os.path.expanduser("~")) / "dev" / "stealth-runner" / "profiles" / "jeremy.yaml"

def _load_profile():
    """Lade Persona-Daten aus YAML (oder fallback auf hard-coded Werte)."""
    try:
        import yaml
        with open(PROFILE) as f:
            return yaml.safe_load(f)
    except Exception:
        return {
            "age": 32, "gender": "male", "country_name": "Deutschland",
            "city": "Berlin", "postal_code": "10115", "income_monthly_net_eur": 3750,
            "income_yearly_gross_eur": 66000, "employment_status": "employed",
            "occupation": "Softwareentwickler", "education_level": "bachelor",
            "marital_status": "single", "household_size": 1, "children_count": 0,
            "hobbies": ["programmieren", "gaming", "fitness"],
            "interests": ["technologie", "ki", "gaming", "finanzen"],
        }

PERSONA = _load_profile()

# ── Frage → Antwort-Mapping (Demografie) ──
DEMO_MAP = {
    "alter": lambda: str(PERSONA.get("age", 35)),
    "wie alt": lambda: str(PERSONA.get("age", 35)),
    "jahre": lambda: str(PERSONA.get("age", 35)),  
    "geburtsjahr": lambda: "1993",
    "geburtsdatum": lambda: "13.11.1993",
    "geschlecht": lambda: "männlich" if PERSONA.get("gender") == "male" else "weiblich",
    "postleitzahl": lambda: str(PERSONA.get("postal_code", "10115")),
    "plz": lambda: str(PERSONA.get("postal_code", "10115")),
    "wohnort": lambda: PERSONA.get("city", "Berlin"),
    "stadt": lambda: PERSONA.get("city", "Berlin"),
    "bundesland": lambda: "Berlin",
    "land": lambda: PERSONA.get("country_name", "Deutschland"),
    "einkommen": lambda: str(PERSONA.get("income_monthly_net_eur", 3750)),
    "jahreseinkommen": lambda: str(PERSONA.get("income_yearly_gross_eur", 66000)),
    "haushaltseinkommen": lambda: str(PERSONA.get("income_monthly_net_eur", 3750)),
    "beruf": lambda: PERSONA.get("occupation", "Softwareentwickler"),
    "tätigkeit": lambda: PERSONA.get("occupation", "Softwareentwickler"),
    "beschäftigung": lambda: PERSONA.get("employment_status", "angestellt"),
    "bildung": lambda: PERSONA.get("education_level", "Bachelor"),
    "familienstand": lambda: "ledig" if PERSONA.get("marital_status") == "single" else PERSONA.get("marital_status", "ledig"),
    "haushaltsgröße": lambda: str(PERSONA.get("household_size", 1)),
    "kinder": lambda: str(PERSONA.get("children_count", 0)),
}

# ── Heuristische Antworten für häufige Free-Text-Fragen ──
FREE_TEXT_ANSWERS = {
    "reiseerfahrung|unvergessliche reise": 
        "Letzten Sommer war ich in Barcelona. Die Sagrada Familia hat mich mit ihrer Architektur tief beeindruckt, und die Tapas in den kleinen Gassen der Altstadt waren ein kulinarisches Erlebnis, das ich nie vergessen werde.",
    "hobby|freizeit": 
        "In meiner Freizeit programmiere ich gerne an eigenen Projekten und spiele Videospiele. Ausserdem gehe ich zwei Mal pro Woche ins Fitnessstudio, um einen Ausgleich zum Büroalltag zu haben.",
    "beruf|arbeit|tätigkeit": 
        "Ich arbeite als Softwareentwickler in der IT-Branche. Mein Fokus liegt auf Backend-Systemen und Cloud-Infrastruktur.",
    "wohnen|wohnung|haus": 
        "Ich wohne in einer gemieteten 3-Zimmer-Wohnung in Berlin. Die Lage ist zentral, was den Arbeitsweg kurz hält.",
    "einkaufen|shopping": 
        "Ich kaufe hauptsächlich online ein, besonders Elektronik und Lebensmittel. Für Kleidung gehe ich gelegentlich in die Geschäfte in der Berliner Innenstadt.",
    "auto|fahrzeug|mobilität": 
        "Ich besitze kein eigenes Auto. In Berlin nutze ich hauptsächlich die öffentlichen Verkehrsmittel und das Fahrrad.",
    "medien|nachrichten|news": 
        "Ich lese täglich Nachrichten auf Spiegel Online und Heise. Für internationale Themen nutze ich Reddit.",
    "streaming|netflix|spotify": 
        "Ich nutze Netflix und Spotify regelmässig. YouTube schaue ich vor allem für Tech-Tutorials und Gaming-Content.",
}

@dataclass
class Answer:
    action: str = "click"  
    element_id: int = 0
    text: str = ""
    reason: str = ""

def classify(question_text: str, element_list: list[dict] | None = None) -> str:
    """Klassifiziere Fragetyp: demographic | free_text | single_choice | multi_choice | attention."""
    q = question_text.lower()
    
    # Attention-Check
    if re.search(r"wähle.*option|bitte klicken sie|als bestätigung|attention", q):
        return "attention"
    
    # Demografie-Keywords
    for key in DEMO_MAP:
        if key in q:
            return "demographic"
    if re.search(r"(wie alt|alter|geboren|geschlecht|wohn|plz|einkommen|beruf|bildung)", q):
        return "demographic"
    
    # Free text keywords (question text indicates text answer regardless of elements)
    if re.search(r"(beschreibe|erzähle|erkläre|berichte|schildere|in \w+ sätzen|in \w+ worten)", q):
        return "free_text"
    
    # Check if free text (no options, has textarea)
    if element_list:
        has_textarea = any(e.get("role") == "AXTextArea" for e in element_list)
        has_options = any(e.get("role") in ("AXRadioButton", "AXCheckBox") for e in element_list)
        if has_textarea and not has_options:
            return "free_text"
    
    return "single_choice"


def generate_answer(question_text: str, element_list: list[dict] | None = None) -> Answer:
    """Generiere Persona-konsistente Antwort."""
    qtype = classify(question_text, element_list)
    q = question_text.lower()
    
    # ── Demografie: Direkter Persona-Lookup ──
    if qtype == "demographic":
        for key, fn in DEMO_MAP.items():
            if key in q:
                val = fn()
                return Answer(action="type" if element_list and any(e["role"]=="AXTextArea" for e in element_list) else "click",
                              text=val, reason=f"Persona: {key}={val}")
    
    # ── Free Text: Heuristik-Match ──
    if qtype == "free_text":
        for pattern, answer_text in FREE_TEXT_ANSWERS.items():
            if re.search(pattern, q):
                return Answer(action="type", text=answer_text, reason=f"Heuristik: {pattern}")
        # Fallback: generische Berliner IT-Antwort
        return Answer(action="type", 
                      text="Als Softwareentwickler in Berlin verbringe ich meine Freizeit gerne mit Programmieren, Gaming und Fitness. Die Stadt bietet viele kulturelle Möglichkeiten, die ich gerne nutze.",
                      reason="Fallback free_text")
    
    # ── Single/Multi Choice: Element-Matching ──
    if element_list:
        # Suche nach Persona-Werten in den Labels
        for key, fn in DEMO_MAP.items():
            val = fn().lower()
            if any(val == e.get("label", "").lower() for e in element_list 
                   if e["role"] in ("AXRadioButton", "AXCheckBox", "AXButton", "AXLink")):
                for e in element_list:
                    if val == e.get("label", "").lower():
                        return Answer(action="click", element_id=e["index"], 
                                      text=val, reason=f"Exact match: {key}={val}")
        
        # Partial match (z.B. "männlich" in "Ich bin männlich")
        for key, fn in DEMO_MAP.items():
            val = fn().lower()
            for e in element_list:
                if e["role"] in ("AXRadioButton", "AXCheckBox") and val in e.get("label", "").lower():
                    return Answer(action="click", element_id=e["index"],
                                  text=val, reason=f"Partial match: {key}={val} in '{e['label']}'")
    
    # ── LLM-Fallback: Persona via Mistral (text-only, schnell) ──
    llm_result = _ask_persona_llm(question_text, element_list)
    if llm_result:
        return llm_result

    return Answer(action="ask_omni", reason="No match — use Omni Vision")


def _ask_persona_llm(question_text: str, element_list: list[dict] | None = None) -> Answer | None:
    """Nutzt Mistral (task=persona) für intelligentes Persona-Matching.

    Wenn Keyword-Mapping keine Antwort findet, fragen wir ein dediziertes
    Text-LLM (mistral-small-latest) mit dem kompletten Persona-Profil.
    """
    try:
        router = get_router()
        profile_str = json.dumps(PERSONA, indent=2, ensure_ascii=False)
        elements_str = ""
        if element_list:
            elements_str = json.dumps([{
                "index": e.get("index"),
                "role": e.get("role"),
                "label": e.get("label", ""),
                "value": e.get("value", ""),
            } for e in element_list if e.get("role") in (
                "AXRadioButton", "AXCheckBox", "AXButton", "AXLink", "AXTextArea",
            )], indent=2, ensure_ascii=False)

        prompt = (
            f"Du bist ein Persona-basierter Survey-Antwort-Assistent.\n\n"
            f"BENUTZERPROFIL:\n{profile_str}\n\n"
            f"FRAGE: {question_text}\n\n"
            f"SICHTBARE OPTIONEN (AX-Elemente):\n{elements_str or '(keine)'}\n\n"
            f"AUFGABE:\n"
            f"1. Bestimme ob die Frage nach einem Profil-Feld fragt (Alter, Geschlecht, Wohnort, Beruf, etc.)\n"
            f"2. Wenn ja: Wähle die passende Option aus den sichtbaren Elementen oder gib den korrekten Textwert\n"
            f"3. Wenn nein: Antworte mit 'keine_persona_frage'\n\n"
            f"Antworte NUR mit JSON:\n"
            '{{"has_persona_match": true/false, "action": "click|type|ask_omni", '
            '"element_id": <index oder 0>, "text": "<wert>", '
            '"reason": "<begründung>"}}'
        )
        resp = router.call(Task.PERSONA, prompt)
        result = ModelRouter.extract_json(resp)
        if result.get("has_persona_match") and result.get("action") in ("click", "type"):
            return Answer(
                action=result["action"],
                element_id=result.get("element_id", 0),
                text=result.get("text", ""),
                reason=f"Persona-LLM: {result.get('reason', '')}",
            )
    except Exception:
        pass
    return None
