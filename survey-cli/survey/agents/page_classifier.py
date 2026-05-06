"""
survey/agents/page_classifier.py — Page Classifier Agent (2026-05-06)

FUNKTION: Classified page type in ~80ms using mistral-small.
Identifies: consent, question, completed, login, captcha, audio, video, matrix, unknown.

 Thread: 3 von 5 im ParallelOrchestrator
 Model:  mistral-small (80ms, MICRO) — fast enough for real-time classification
 Input:  page text + element counts + framework hint
 Output: {page_type, confidence, hints, ms}

PAGE TYPES (12 types from stealth-dynamic/classifier.py):
    consent, audio_question, video_question, image_question, math_question,
    matrix_question, text_question, radio_question, checkbox_question,
    login, completed, unknown
"""

from __future__ import annotations
import time
from typing import Dict, Any, Optional


# ── Page Type Detection Heuristics (instant, no LLM needed) ────────────────────
# These run FIRST before any LLM call — 95% of pages can be classified instantly

PAGE_TYPE_PATTERNS = {
    "consent": [
        r"zustimmen|akzeptieren|agree|accept.*cookies|daten.*schutz",
        r"einverstanden|genehmigung|consent",
    ],
    "completed": [
        r"danke.*teilnahme|vielen dank|abgeschlossen|completed|fertig",
        r"thank you|survey complete|ausgefüllt",
        r"gutgeschrieben|belohnung|reward.*earned",
    ],
    "login": [
        r"google.*sign|sign in.*google|oauth|clerk",
        r"passwort vergessen|password forgot",
    ],
    "captcha": [
        r"captcha|code.*eingeben|robot|ich bin kein robot",
        r"bitte.*code|enter.*letters|recaptcha",
    ],
    "audio_question": [
        r"hören sie|audio|hörprobe|tiergeräusch|sound",
        r"was hören sie|listen.*audio",
    ],
    "video_question": [
        r"video.*ansehen|watch.*video|clip.*ansehen",
        r"was sehen sie|sehen sie.*video",
    ],
    "image_question": [
        r"bewerten sie.*bild|rate.*image|foto.*bewertung",
        r"welches bild|which.*image|picture.*rating",
    ],
    "math_question": [
        r"was ist \d+\+\d+|calculate|summieren|rechnen",
        r"2\+2|mathe|mathematics|zahlen",
    ],
    "matrix_question": [
        r"skala von.*bis| Likert| matrix| tabelle",
        r"bitte bewerten|how much.*agree",
    ],
    "text_question": [
        r"beschreiben sie|erzählen sie|textarea|freitext",
        r"warum|原因|explain|理由",
    ],
    "radio_question": [
        r"wählen sie|auswählen|select one|bitte.*antwort",
        r"welche.*bevorzugen|sind sie.*einverstanden",
    ],
}


def classify_page_instant(page_text: str, element_map: Dict) -> Optional[str]:
    """Instant classification using regex patterns. No LLM needed for 95% of cases."""
    text_lower = page_text.lower()

    for ptype, patterns in PAGE_TYPE_PATTERNS.items():
        for pattern in patterns:
            import re
            if re.search(pattern, text_lower, re.IGNORECASE):
                return ptype

    # Check element counts as secondary signal
    counts = element_map.get("counts", {})
    if counts.get("radios", 0) > 0:
        return "radio_question"
    if counts.get("checkboxes", 0) > 0:
        return "checkbox_question"
    if counts.get("textareas", 0) > 0:
        return "text_question"
    if counts.get("role_buttons", 0) > 0:
        return "radio_question"  # CloudResearch pattern

    return None  # Need LLM for uncertain cases


class PageClassifier:
    """Classifies survey page type using instant heuristics + LLM fallback.

    STRATEGY:
    1. Instant regex patterns (0ms) → handles 95% of cases
    2. Element count analysis (0ms) → secondary signal
    3. LLM fallback (80ms, mistral-small) → only for uncertain cases
    """

    def __init__(self, router=None):
        self.router = router

    def classify(self, page_text: str, element_map: Dict,
                 body_text: str = "") -> Dict[str, Any]:
        """Classify page type. Returns {page_type, confidence, method}."""
        start = time.monotonic()
        text = page_text or body_text or ""

        # Step 1: Instant classification (no LLM)
        instant_type = classify_page_instant(text, element_map)
        if instant_type:
            elapsed_ms = round((time.monotonic() - start) * 1000)
            return {
                "agent": "page_classifier",
                "page_type": instant_type,
                "confidence": 0.95,  # High confidence for pattern match
                "method": "instant_heuristic",
                "elapsed_ms": elapsed_ms,
                "framework": element_map.get("framework", "unknown"),
                "elements_hint": element_map.get("counts", {}),
            }

        # Step 2: LLM fallback for uncertain cases
        if self.router:
            from .task_router import call_model, MODELS
            model = MODELS["mistral-small"]  # Always use mistral-small for classification
            prompt = (
                f"Classify this survey page. Page text (first 300 chars):\n"
                f"{text[:300]}\n\n"
                f"Element counts: radios={element_map.get('counts',{}).get('radios',0)}, "
                f"buttons={element_map.get('counts',{}).get('buttons',0)}, "
                f"textareas={element_map.get('counts',{}).get('textareas',0)}, "
                f"role_buttons={element_map.get('counts',{}).get('role_buttons',0)}\n\n"
                f"Page types: consent, radio_question, checkbox_question, text_question, "
                f"matrix_question, math_question, captcha, audio_question, video_question, "
                f"completed, login, unknown\n\n"
                f"Return ONLY the page type word, nothing else."
            )
            result = call_model(model.name, prompt, max_tokens=15, cache=self.router.cache)
            page_type = result.get("content", "unknown").strip().lower()
            if page_type not in ["consent", "radio_question", "checkbox_question",
                                  "text_question", "matrix_question", "math_question",
                                  "captcha", "audio_question", "video_question",
                                  "completed", "login", "unknown"]:
                page_type = "unknown"

            elapsed_ms = round((time.monotonic() - start) * 1000)
            return {
                "agent": "page_classifier",
                "page_type": page_type,
                "confidence": 0.7,
                "method": "llm_fallback",
                "elapsed_ms": elapsed_ms,
                "framework": element_map.get("framework", "unknown"),
                "llm_content": result.get("content", "")[:50],
            }

        # Fallback
        elapsed_ms = round((time.monotonic() - start) * 1000)
        return {
            "agent": "page_classifier",
            "page_type": "unknown",
            "confidence": 0.3,
            "method": "default",
            "elapsed_ms": elapsed_ms,
        }