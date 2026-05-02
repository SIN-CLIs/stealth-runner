"""prompt_kit – Dynamic prompts for different model roles.

- build_vision_prompt()  → für Omni (screenshot/video analysis)
- build_logic_prompt()   → für Mistral Medium (decision logic, text-only)
- build_persona_prompt() → für Mistral Small (persona matching, text-only)
"""
from __future__ import annotations
from typing import Any


def build_vision_prompt(context: dict[str, Any], step: int) -> str:
    page = context.get("page", "unknown")
    eur = context.get("eur", 0.0)
    return (
        "You are a survey automation agent. "
        f"This is page: {page}. EUR earned so far: {eur:.2f}. "
        "If you see a SURVEY QUESTION: answer it by clicking the best choice. "
        "If you see a LOADING SPINNER or blank page: output {\"action\":\"wait\"}. "
        "If the survey is COMPLETE (thank you message): output {\"action\":\"done\"}. "
        "If you see a Heypiggy dashboard with NO active survey: look for survey links to click. "
        "Output ONLY valid JSON with action and element_id."
    )


def build_logic_prompt(context: dict[str, Any], step: int) -> str:
    """Dedizierter Logik-Prompt für Mistral Medium (text-only, reasoning).

    Ruft das logic-Modell (mistral-medium-2604) für Survey-Entscheidungen
    und Trap-Erkennung auf — entlastet das Vision-Modell.
    """
    page = context.get("page", "unknown")
    eur = context.get("eur", 0.0)
    persona = context.get("persona", {})
    profile_str = _fmt_profile(persona)
    return (
        f"Du bist ein Survey-Logik-Assistent. Seite: {page}. EUR: {eur:.2f}.\n\n"
        f"BENUTZERPROFIL:\n{profile_str}\n\n"
        "AUFGABE:\n"
        "1. Analysiere die aktuelle Survey-Situation\n"
        "2. Erkenne Fallen: Attention-Checks, Konsistenz-Traps, Screening-Fragen\n"
        "3. Wähle die Persona-konsistente Antwort\n"
        "4. Entscheide ob weitermachen oder abbrechen (Disqualifikation)\n\n"
        "Antworte NUR mit JSON:\n"
        '{"action":"click|type|wait|done|abort","element_id":<int>,'
        '"text":"...","reasoning":"...","confidence":0.0-1.0}'
    )


def build_persona_prompt(context: dict[str, Any], question: str, options: list[str]) -> str:
    """Dedizierter Persona-Prompt für Mistral Small (text-only, schnell).

    Leichtes Modell für schnelles Persona-Matching bei Survey-Fragen.
    """
    persona = context.get("persona", {})
    profile_str = _fmt_profile(persona)
    return (
        "Du bist ein Persona-Matching-Assistent für Umfragen.\n\n"
        f"PERSONA:\n{profile_str}\n\n"
        f"FRAGE: {question}\n\n"
        f"OPTIONEN:\n" + "\n".join(f"- {o}" for o in options) + "\n\n"
        "Wähle die Option, die am besten zur Persona passt.\n"
        "Antworte NUR mit dem genauen Text der Option — kein JSON, keine Erklärung."
    )


def _fmt_profile(persona: dict) -> str:
    if not persona:
        return "(kein Profil geladen)"
    return "\n".join(f"- {k}: {v}" for k, v in persona.items() if v)


# ── Alias für Abwärtskompatibilität ──
build_prompt = build_vision_prompt
