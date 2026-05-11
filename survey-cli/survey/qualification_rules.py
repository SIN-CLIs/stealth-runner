#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
qualification_rules.py — Survey Qualification Maximizer
========================================================

ZIEL: 100% Qualification Rate — NIEMALS disqualifiziert werden!

REGELN (2026-05-11):
1. NIEMALS "möchte nicht angeben" / "prefer not to say" / "keine Angabe"
2. IMMER positive/inklusive Antworten:
   - Kinder: "Ja, habe Kinder" oder "Erwarte Kinder"
   - Haustiere: "Ja, habe Haustiere"
   - Einkommen: Mittleres bis hohes Einkommen (nicht "unter X")
   - Alter: Innerhalb der Zielgruppe (25-54 typisch)
3. Bei Multi-Select: MEHR auswählen, nicht weniger
4. Bei Marken/Produkte: Bekannte Marken auswählen
5. Bei Kaufabsicht: "Ja, in den nächsten 3-6 Monaten"

IMPLEMENTATION:
- Hooks in decide_node für Antwort-Auswahl
- Pattern-basierte Erkennung von Disqualifikations-Fragen
- Override-Werte für kritische Felder
"""

from __future__ import annotations
import re
from typing import Optional


# ═══════════════════════════════════════════════════════════════════════════════
# DISQUALIFICATION PATTERNS — Diese Antworten NIEMALS auswählen!
# ═══════════════════════════════════════════════════════════════════════════════

NEVER_SELECT_PATTERNS = [
    # Deutsch
    r"möchte.*nicht.*angeben",
    r"keine\s*angabe",
    r"weiß\s*nicht",
    r"nicht\s*sicher",
    r"keines\s*davon",
    r"nichts\s*davon",
    r"trifft\s*nicht\s*zu",
    r"keine\s*kinder",
    r"habe\s*keine\s*kinder",
    r"keine\s*haustiere",
    r"habe\s*keine\s*haustiere",
    r"kein\s*interesse",
    r"nie(mals)?",
    r"unter\s*\d+.*€",  # "unter 1000€" = niedriges Einkommen
    r"weniger\s*als",
    r"arbeitslos",
    r"nicht\s*berufstätig",
    
    # Englisch
    r"prefer\s*not\s*(to\s*)?(say|answer|disclose)",
    r"rather\s*not\s*say",
    r"don'?t\s*know",
    r"not\s*sure",
    r"none\s*of\s*(the\s*)?(above|these)",
    r"no\s*children",
    r"don'?t\s*have\s*(any\s*)?children",
    r"no\s*pets",
    r"don'?t\s*have\s*(any\s*)?pets",
    r"not\s*interested",
    r"never",
    r"under\s*\$?\d+",
    r"less\s*than",
    r"unemployed",
    r"not\s*employed",
]

NEVER_SELECT_COMPILED = [re.compile(p, re.IGNORECASE) for p in NEVER_SELECT_PATTERNS]


# ═══════════════════════════════════════════════════════════════════════════════
# ALWAYS PREFER PATTERNS — Diese Antworten BEVORZUGEN!
# ═══════════════════════════════════════════════════════════════════════════════

ALWAYS_PREFER_PATTERNS = [
    # Kinder
    (r"kinder|children|kids", [
        r"ja.*kinder",
        r"yes.*children",
        r"have\s*children",
        r"habe.*kind",
        r"1-2\s*kinder",
        r"1-2\s*children",
        r"erwart.*kind",  # erwartet Kind
        r"expect.*child",
    ]),
    
    # Haustiere
    (r"haustier|pet|animal", [
        r"ja.*haustier",
        r"yes.*pet",
        r"have\s*pet",
        r"habe.*haustier",
        r"hund|dog",
        r"katze|cat",
    ]),
    
    # Kaufabsicht
    (r"kaufen|purchase|buy|interest", [
        r"ja.*interesse",
        r"yes.*interest",
        r"definitiv",
        r"definitely",
        r"in\s*den\s*nächsten",
        r"in\s*the\s*next",
        r"wahrscheinlich",
        r"likely",
        r"sehr\s*wahrscheinlich",
        r"very\s*likely",
    ]),
    
    # Einkommen (mittleres bis hohes)
    (r"einkommen|income|salary|gehalt", [
        r"40\.?000.*60\.?000",
        r"60\.?000.*80\.?000",
        r"80\.?000.*100\.?000",
        r"\$?50[,.]?000",
        r"\$?75[,.]?000",
        r"3\.?000.*4\.?000.*€",
        r"4\.?000.*5\.?000.*€",
    ]),
    
    # Beschäftigung
    (r"beruf|employ|job|work|occupation", [
        r"vollzeit",
        r"full.?time",
        r"angestellt",
        r"employed",
        r"selbständig",
        r"self.?employed",
    ]),
]


def is_disqualifying_answer(answer_text: str) -> bool:
    """Prüft ob eine Antwort zur Disqualifikation führen würde.
    
    Args:
        answer_text: Der Text der Antwortoption
        
    Returns:
        True wenn diese Antwort NICHT gewählt werden sollte
    """
    answer_lower = answer_text.lower().strip()
    
    for pattern in NEVER_SELECT_COMPILED:
        if pattern.search(answer_lower):
            return True
    
    return False


def get_preferred_answer(question_text: str, answers: list[str]) -> Optional[int]:
    """Findet die beste Antwort für eine Qualification-Frage.
    
    Args:
        question_text: Der Fragetext
        answers: Liste der Antwortoptionen
        
    Returns:
        Index der bevorzugten Antwort, oder None wenn keine Präferenz
    """
    question_lower = question_text.lower()
    
    # 1. Finde relevante Präferenz-Patterns
    for question_pattern, answer_patterns in ALWAYS_PREFER_PATTERNS:
        if re.search(question_pattern, question_lower, re.IGNORECASE):
            # Frage matched — suche beste Antwort
            for i, answer in enumerate(answers):
                answer_lower = answer.lower()
                for pref_pattern in answer_patterns:
                    if re.search(pref_pattern, answer_lower, re.IGNORECASE):
                        return i
    
    return None


def filter_safe_answers(answers: list[str]) -> list[int]:
    """Filtert Antworten die NICHT disqualifizierend sind.
    
    Args:
        answers: Liste der Antwortoptionen
        
    Returns:
        Liste der Indizes von sicheren Antworten
    """
    safe_indices = []
    
    for i, answer in enumerate(answers):
        if not is_disqualifying_answer(answer):
            safe_indices.append(i)
    
    return safe_indices


def rank_answers_for_qualification(question_text: str, answers: list[str]) -> list[int]:
    """Rankt Antworten nach Qualification-Wahrscheinlichkeit.
    
    Returns:
        Sortierte Liste der Indizes (beste zuerst)
    """
    # 1. Preferred answer (wenn vorhanden)
    preferred = get_preferred_answer(question_text, answers)
    
    # 2. Safe answers (nicht disqualifizierend)
    safe = filter_safe_answers(answers)
    
    # 3. Ranking aufbauen
    ranked = []
    
    if preferred is not None and preferred in safe:
        ranked.append(preferred)
    
    for idx in safe:
        if idx not in ranked:
            ranked.append(idx)
    
    # 4. Unsafe answers am Ende (nur als Fallback)
    for i in range(len(answers)):
        if i not in ranked:
            ranked.append(i)
    
    return ranked


# ═══════════════════════════════════════════════════════════════════════════════
# SPEED OPTIMIZATION — Schnelle Antwort-Strategien
# ═══════════════════════════════════════════════════════════════════════════════

def get_fast_answer_strategy(question_type: str) -> dict:
    """Gibt schnelle Antwort-Strategie für Fragetyp zurück.
    
    Args:
        question_type: "single_choice", "multiple_choice", "rating", etc.
        
    Returns:
        Strategy dict mit Anweisungen
    """
    strategies = {
        "single_choice": {
            "action": "select_first_safe",
            "fallback": "select_middle",
            "timeout_ms": 500,
        },
        "multiple_choice": {
            "action": "select_top_3_safe",
            "fallback": "select_all_safe",
            "timeout_ms": 800,
        },
        "rating": {
            "action": "select_positive",  # 4-5 von 5, 7-10 von 10
            "fallback": "select_middle_high",
            "timeout_ms": 300,
        },
        "matrix": {
            "action": "select_consistent_positive",
            "fallback": "select_middle",
            "timeout_ms": 1000,
        },
        "open_text": {
            "action": "skip_or_minimal",
            "fallback": "generic_positive",
            "timeout_ms": 2000,
        },
    }
    
    return strategies.get(question_type, strategies["single_choice"])


# ═══════════════════════════════════════════════════════════════════════════════
# NVIDIA NIM INTEGRATION — Schnelle Modelle für Survey-Entscheidungen
# ═══════════════════════════════════════════════════════════════════════════════

NVIDIA_MODELS = {
    "vision": "nvidia/nvidia/nemotron-3-nano-omni-30b-a3b-reasoning",
    "tool_use": "nvidia/openai/gpt-oss-120b",
}


def get_nvidia_model_for_task(task: str) -> str:
    """Wählt das beste Nvidia-Modell für eine Aufgabe.
    
    Args:
        task: "screenshot_analysis", "answer_selection", "captcha", etc.
        
    Returns:
        Modell-Name für Nvidia NIM API
    """
    vision_tasks = ["screenshot_analysis", "captcha", "image_selection", "drag_drop"]
    tool_tasks = ["answer_selection", "form_filling", "navigation"]
    
    if task in vision_tasks:
        return NVIDIA_MODELS["vision"]
    else:
        return NVIDIA_MODELS["tool_use"]


# ═══════════════════════════════════════════════════════════════════════════════
# EXPORTS
# ═══════════════════════════════════════════════════════════════════════════════

__all__ = [
    "is_disqualifying_answer",
    "get_preferred_answer",
    "filter_safe_answers",
    "rank_answers_for_qualification",
    "get_fast_answer_strategy",
    "get_nvidia_model_for_task",
    "NVIDIA_MODELS",
]
