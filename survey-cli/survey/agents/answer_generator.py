"""
survey/agents/answer_generator.py — Answer Generator Agent (2026-05-06)

WARUM: Der NIM-Client gibt Actions als @eN refs zurück. Dieser Agent
übersetzt die abstrakten Actions in konkrete CDP/JS Commands.
Falsche Method-Selection (z.B. JS .click() auf Angular) führt zu
Nicht-Funktion — der Survey-Flow bleibt stehen.

ARCHITEKTUR: Agent 4/5 im ParallelOrchestrator. Model: nemotron-nano (500ms, MID).
Input: element_map, page_classifier, persona_checker, page_text.
Output: Actions-Liste mit {action, ref, value, x, y, selector, method}.
Method-Selection: Angular v19 → CDP dispatchMouseEvent ONLY (JS .click()
wird von Zone.js ignoriert). React → CDP für [role=button].
Standard HTML → JS .click() OK. Unknown → CDP Fallback (universell sicher).

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
import json
from typing import Dict, List, Any, Optional


class AnswerGenerator:
    """Generates optimal action sequence for survey page.

    DECISION TREE:
    1. Radio/Checkbox → select first preferred by PersonaChecker
    2. Textarea → fill with persona-appropriate text
    3. Submit button → CDP-click by text match
    4. Multi-select → first non-cannot-answer per group

    CDP CLICK STRATEGY:
    - ANGULAR: always CDP dispatchMouseEvent (never JS .click())
    - REACT (role=button): always CDP dispatchMouseEvent
    - STANDARD: JS .click() works but CDP is safer
    - UNKNOWN: always CDP dispatchMouseEvent (universal fallback)
    """

    # Button text keywords that trigger submit action
    SUBMIT_KEYWORDS = [
        "weiter", "next", "submit", "nächste", "continue", "fortfahren",
        "send", "absenden", "forward", "forwardbtn", "klicken sie hier",
    ]

    def __init__(self, router=None):
        self.router = router

    def generate(self, page_text: str,
                 element_map: Dict,
                 page_class: Dict,
                 persona_result: Dict,
                 profile: Dict) -> Dict[str, Any]:
        """Generate action sequence for current page."""
        start = time.monotonic()
        framework = element_map.get("framework", "unknown")
        elements = element_map.get("elements", {})
        actions = []

        pt = page_class.get("page_type", "unknown")

        # ── CONSENT PAGE ───────────────────────────────────────────────────────
        if pt == "consent":
            consent_btns = [e for e in elements.get("buttons", [])
                           if any(kw in e.get("text", "").lower()
                                  for kw in ["zustimmen", "accept", "agree", "einverstanden"])]
            if consent_btns:
                b = consent_btns[0]
                actions.append({
                    "action": "click",
                    "method": "cdp",  # Always CDP for consent buttons
                    "x": b.get("x", 0), "y": b.get("y", 0),
                    "selector": b.get("sel", "button"),
                    "text": b.get("text", ""),
                })
            return self._finish(actions, start, pt)

        # ── COMPLETED PAGE ─────────────────────────────────────────────────────
        if pt == "completed":
            return self._finish([{"action": "complete"}], start, pt)

        # ── TEXT QUESTION (textarea) ───────────────────────────────────────────
        if pt == "text_question" and elements.get("textareas"):
            ta = elements["textareas"][0]
            answer = self._generate_text_answer(page_text, profile)
            actions.append({
                "action": "fill",
                "method": "cdp",  # CDP for Angular form binding
                "x": ta.get("x", 0), "y": ta.get("y", 0),
                "selector": "textarea",
                "value": answer,
                "text": ta.get("text", ""),
            })
            # Also click submit
            submit = self._find_submit(elements)
            if submit:
                actions.append(self._make_cdp_click(submit))
            return self._finish(actions, start, pt)

        # ── RADIO QUESTION ─────────────────────────────────────────────────────
        if pt in ("radio_question", "checkbox_question") or elements.get("radios"):
            # Use persona_checker top answer
            best = persona_result.get("best_answer")
            if best and best.get("safe", True):
                # Find element by index
                target_idx = best.get("idx", 0)
                target = self._find_by_idx(elements, target_idx)
                if target:
                    method = "cdp" if framework in ("angular", "react", "unknown") else "js"
                    actions.append(self._make_action(target, "click", method))
                    # Also click submit
                    submit = self._find_submit(elements)
                    if submit:
                        actions.append(self._make_cdp_click(submit))
                else:
                    # Fallback: select first radio
                    radios = elements.get("radios", [])
                    if radios:
                        actions.append(self._make_action(radios[0], "click", "cdp"))
                        submit = self._find_submit(elements)
                        if submit:
                            actions.append(self._make_cdp_click(submit))
            else:
                # Trap detected — select first non-"cannot answer"
                safe = [a for a in persona_result.get("preferred_answers", [])
                        if a.get("safe", True)]
                if safe:
                    target = self._find_by_idx(elements, safe[0].get("idx", 0))
                    if target:
                        actions.append(self._make_action(target, "click", "cdp"))
                submit = self._find_submit(elements)
                if submit:
                    actions.append(self._make_cdp_click(submit))

        # ── ROLE-BUTTON PATTERN (CloudResearch, React) ─────────────────────────
        elif elements.get("role_buttons"):
            # Select first role-button matching persona preference
            role_btns = elements.get("role_buttons", [])
            preferred = [b for b in role_btns
                        if any(kw in b.get("text", "").lower()
                               for kw in ["berlin", "männlich", "angestellt"])]
            if preferred:
                actions.append(self._make_action(preferred[0], "click", "cdp"))
            elif role_btns:
                actions.append(self._make_action(role_btns[0], "click", "cdp"))
            submit = self._find_submit(elements)
            if submit:
                actions.append(self._make_cdp_click(submit))

        # ── UNKNOWN / FALLBACK ─────────────────────────────────────────────────
        if not actions:
            # Universal fallback: click first available submit + first radio
            if elements.get("radios"):
                actions.append(self._make_action(elements["radios"][0], "click", "cdp"))
            submit = self._find_submit(elements)
            if submit:
                actions.append(self._make_cdp_click(submit))
            else:
                # Last resort: click first button
                btns = elements.get("buttons", [])
                if btns:
                    actions.append(self._make_action(btns[0], "click", "cdp"))

        return self._finish(actions, start, pt)

    def _generate_text_answer(self, page_text: str, profile: Dict) -> str:
        """Generate appropriate text answer based on question context."""
        text_lower = page_text.lower()
        name = profile.get("name", "Jeremy")
        city = profile.get("city", "Berlin")

        if "gemüse" in text_lower or "vegetable" in text_lower:
            return "Karotten werden von vielen Menschen gegessen, weil sie gesund und vielseitig sind."
        if "hobby" in text_lower or "freizeit" in text_lower:
            return "Ich lese gerne Bücher und unternehme Spaziergänge in der Natur."
        if "beschreib" in text_lower:
            return "Ich finde das Thema interessant und nehme gerne an Umfragen teil."
        if "warum" in text_lower:
            return f"Ich lebe in {city} und interessiere mich für verschiedene Themen."
        if "meinung" in text_lower or "opinion" in text_lower:
            return f"Meine Meinung basiert auf meinen persönlichen Erfahrungen in {city}."
        # Default
        return "Ja, ich stimme dem zu und finde das Thema relevant."

    def _find_submit(self, elements: Dict) -> Optional[Dict]:
        """Find the submit/next button."""
        submit_btns = elements.get("submit_btns", [])
        if submit_btns:
            return submit_btns[0]
        # Fallback: any reasonable-sized button
        for b in elements.get("buttons", []):
            if b.get("w", 0) > 50 and b.get("h", 0) > 20:
                return b
        return None

    def _find_by_idx(self, elements: Dict, idx: int) -> Optional[Dict]:
        """Find element by its index in the combined list."""
        for cat in ["radios", "checkboxes", "text_inputs", "textareas",
                    "buttons", "role_buttons"]:
            for e in elements.get(cat, []):
                if e.get("idx") == idx:
                    return e
        return None

    def _make_action(self, element: Dict, action: str, method: str) -> Dict:
        """Convert element to action dict."""
        return {
            "action": action,
            "method": method,
            "x": element.get("x", 0),
            "y": element.get("y", 0),
            "selector": element.get("sel", ""),
            "text": element.get("text", "")[:40],
            "tag": element.get("tag", ""),
            "type": element.get("type", ""),
        }

    def _make_cdp_click(self, element: Dict) -> Dict:
        """Make a CDP click action (universal, works on all frameworks)."""
        return {
            "action": "click",
            "method": "cdp",
            "x": element.get("x", 0),
            "y": element.get("y", 0),
            "selector": element.get("sel", "button"),
            "text": element.get("text", "")[:40],
        }

    def _finish(self, actions: List, start, page_type: str) -> Dict:
        elapsed_ms = round((time.monotonic() - start) * 1000)
        return {
            "agent": "answer_generator",
            "elapsed_ms": elapsed_ms,
            "actions": actions,
            "action_count": len(actions),
            "confidence": 0.85 if actions else 0.3,
            "page_type": page_type,
            "has_submit": any(a.get("action") == "click" and
                              a.get("selector") in ["button", "submit", "input[type=submit]"]
                              for a in actions),
        }