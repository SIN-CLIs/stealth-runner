"""
survey/agents/persona_checker.py — Persona Checker Agent (2026-05-06)

WARUM: Falsche Antworten (z.B. Alter 16-25 statt 26-39 für einen 32-Jährigen)
führen sofort zur Disqualifikation. Dieser Agent matched jede Option
gegen das Persona-Profil (Alter aus date_of_birth, Geschlecht, Ort, etc.)
und gibt ranked preferred_answers zurück.

ARCHITEKTUR: Thread 2/5 im ParallelOrchestrator.
Model: nemotron-nano (500ms, MID) — braucht reasoning für komplexes Mapping.
Input: page_text, element_map, profile-Dict.
Output: {preferred_answers: [{idx, text, score, reason}], persona_match_score, ms}.
Kein State außerhalb des Function-Calls.

BANNED METHODS — NIEMALS VERWENDEN:
❌ playstealth launch
❌ webauto-nodriver — ABSOLUT BANNED
❌ cua-driver click (raw index)
❌ --remote-allow-origins=* (ohne Quotes)
❌ /tmp/heypiggy-bot (fixed profile)
❌ Hardcoded PIDs
❌ pkill -f "Google Chrome"
❌ killall Google Chrome
❌ skylight-cli click --element-index
"""

from __future__ import annotations
import time
import re
from typing import Dict, List, Any


class PersonaChecker:
    """Validates answer options against persona profile.

    STRATEGY: Keyword-Matching + Fallback zu NIM für unbekannte Fragen.
    Persona: Jeremy Schulze, 32, Berlin, männlich, Angestellter, Master, 2-Personen-HH
    """

    PERSONA_HINTS = {
        "male": ["männlich", "mann", "male", "herr", "man"],
        "female": ["weiblich", "frau", "female", "woman"],
        "employed": ["angestellt", "beschäftigt", "employed", "arbeitnehmer", "vollzeit"],
        "berlin": ["berlin", "10785", "kurfürstenstraße"],
        "age_brackets": [
            ("16-25", lambda a: 16 <= a <= 25),
            ("26-39", lambda a: 26 <= a <= 39),
            ("40-55", lambda a: 40 <= a <= 55),
            ("55+", lambda a: a >= 55),
        ],
        "education": ["abitur", "master", "hochschule", "universität"],
        "income": ["3000-4000", "mittel", "mittleres einkommen"],
    }

    # Questions that ALWAYS disqualify if answered wrong
    DISQUALIFICATION_TRAPS = {
        "amazonas": ["nein", "definitiv nicht"],  # Wer würde den Amazonas schwimmen?
        "swim amazon": ["nein", "definitiv nicht"],
    }

    def __init__(self, router=None):
        self.router = router

    def check(self, page_text: str, element_map: Dict,
              profile: Dict) -> Dict[str, Any]:
        """Check all answer options against persona. Returns scored answers."""
        start = time.monotonic()
        answers = self._extract_answers(page_text, element_map)
        profile = profile or {}

        scored = []
        for i, (idx, text) in enumerate(answers):
            score, reason = self._score_answer(text, profile, page_text)
            scored.append({
                "idx": i,
                "element_idx": idx,
                "text": text[:80],
                "score": score,
                "reason": reason,
                "safe": score > 0.5,  # Low score = might be trap question
            })

        # Sort by score descending
        scored.sort(key=lambda x: x["score"], reverse=True)

        # Check for disqualification traps
        trap_detected = self._check_trap(page_text, scored)

        elapsed_ms = round((time.monotonic() - start) * 1000)
        return {
            "agent": "persona_checker",
            "elapsed_ms": elapsed_ms,
            "answers_count": len(scored),
            "preferred_answers": scored[:3],  # Top 3
            "best_answer": scored[0] if scored else None,
            "trap_detected": trap_detected,
            "profile_used": {
                "gender": profile.get("gender", "?"),
                "age": profile.get("age", "?"),
                "city": profile.get("city", "?"),
            },
            "persona_match_score": scored[0].get("score", 0) if scored else 0,
        }

    def _extract_answers(self, page_text: str, element_map: Dict) -> List:
        """Extract all answer options from page."""
        answers = []

        # From element map (radios and role-buttons)
        for e in element_map.get("elements", {}).get("radios", []):
            text = e.get("text", "").strip()
            if text and len(text) > 1:
                answers.append((e.get("idx", 0), text))

        for e in element_map.get("elements", {}).get("role_buttons", []):
            text = e.get("text", "").strip()
            if text and len(text) > 1:
                answers.append((e.get("idx", 0), text))

        # Parse from page text (radio options often appear as text)
        text_lower = page_text.lower()
        lines = page_text.split("\n")
        for line in lines:
            line = line.strip()
            if len(line) > 3 and len(line) < 100:
                # Heuristic: lines that look like answer options
                if not line.startswith("Frage") and not line.startswith("Bitte"):
                    if not any(kw in line.lower() for kw in ["button", "submit", "weiter"]):
                        # Check if it's near radio indicators
                        if line[0].isupper() or line[0].isdigit():
                            answers.append((len(answers), line))

        return answers[:10]  # Cap at 10

    def _score_answer(self, text: str, profile: Dict, page_text: str) -> tuple:
        """Score an answer option: 0.0-1.0 + reason string."""
        text_lower = text.lower()
        score = 0.5  # Default neutral
        reasons = []

        # Gender
        gender = profile.get("gender", "male")
        if gender == "male":
            if any(w in text_lower for w in self.PERSONA_HINTS["male"]):
                score += 0.3; reasons.append("gender:male match")
            if any(w in text_lower for w in self.PERSONA_HINTS["female"]):
                score -= 0.4; reasons.append("gender:female (wrong)")

        # Age brackets
        age = profile.get("age", 32)
        for bracket, cond in self.PERSONA_HINTS["age_brackets"]:
            if bracket in text_lower and cond(age):
                score += 0.2; reasons.append(f"age:{bracket} match")
            if bracket in text_lower and not cond(age):
                score -= 0.1

        # City (Berlin)
        city = profile.get("city", "Berlin")
        if city.lower() in text_lower:
            score += 0.3; reasons.append(f"city:{city} match")

        # Employment
        if profile.get("employment") in ("employed_fulltime", "employed"):
            if any(w in text_lower for w in self.PERSONA_HINTS["employed"]):
                score += 0.2; reasons.append("employed match")

        # Education
        if "master" in profile.get("education", "").lower() or "abitur" in profile.get("education", "").lower():
            if "hochschule" in text_lower or "universität" in text_lower:
                score += 0.1; reasons.append("education match")

        # Penalize "cannot answer" / "don't know" options
        if any(kw in text_lower for kw in ["nicht beantworten", "keine angabe", "weiß nicht",
                                            "cannot answer", "prefer not"]):
            score -= 0.3; reasons.append("fallback option (penalized)")

        # Normalize to 0-1
        score = max(0, min(1, score))

        return score, "; ".join(reasons[:3]) if reasons else "default"

    def _check_trap(self, page_text: str, scored: List) -> bool:
        """Detect disqualification trap questions."""
        text_lower = page_text.lower()
        for trap_kw, bad_answers in self.DISQUALIFICATION_TRAPS.items():
            if trap_kw in text_lower:
                # Check if best answer is one of the bad answers
                if scored and scored[0].get("text", "").lower() in bad_answers:
                    return True
        return False