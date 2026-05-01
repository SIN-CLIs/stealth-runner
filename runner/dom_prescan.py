"""dom_prescan – Vision-free Fast Path via unmask-cli DOM-Scan."""
from __future__ import annotations
import re
from typing import Any


CONFIDENCE_THRESHOLD = 0.85

QUESTION_PATTERNS = re.compile(
    r"(what|which|how|when|where|who|why|do you|are you|have you|"
    r"did you|would you|could you|please select|choose|pick|"
    r"was|wie|welch|wann|wo|wer|warum|bitte waehle)",
    re.IGNORECASE,
)

BUTTON_ROLES = {"AXButton", "AXLink", "AXCheckBox", "AXRadioButton"}
TEXT_ROLES = {"AXTextField", "AXTextArea", "AXComboBox", "AXSearchField"}


def classify_element(el: dict[str, Any]) -> str:
    role = el.get("role", "")
    label = el.get("label", el.get("text", ""))
    if role in BUTTON_ROLES:
        return "clickable"
    if role in TEXT_ROLES:
        return "text_input"
    if QUESTION_PATTERNS.search(label):
        return "question_text"
    if el.get("confidence", 0) > 0.9 and label:
        return "clickable"
    return "unknown"


def prescan_dom(dom_data: dict[str, Any]) -> dict[str, Any]:
    elements = dom_data.get("elements", [])
    if not elements:
        return {"confidence": 0.0, "action": None, "reason": "no elements found"}

    classified = []
    for i, el in enumerate(elements):
        el_type = classify_element(el)
        classified.append({"index": i, "type": el_type, "element": el, "score": el.get("confidence", 0.5)})

    clickables = [c for c in classified if c["type"] == "clickable"]
    text_inputs = [c for c in classified if c["type"] == "text_input"]
    questions = [c for c in classified if c["type"] == "question_text"]

    if questions and clickables:
        best_q = max(questions, key=lambda x: x["score"])
        best_c = max(clickables, key=lambda x: x["score"])
        confidence = min(best_q["score"], best_c["score"])
        if confidence >= CONFIDENCE_THRESHOLD:
            return {
                "confidence": confidence,
                "action": "click",
                "element_id": best_c["index"],
                "reasoning": f"DOM prescan: question detected, clicking {best_c['element'].get('label', 'button')}",
                "path": "vision_free",
            }

    if clickables:
        best_c = max(clickables, key=lambda x: x["score"])
        if best_c["score"] >= CONFIDENCE_THRESHOLD:
            return {
                "confidence": best_c["score"],
                "action": "click",
                "element_id": best_c["index"],
                "reasoning": f"DOM prescan: best clickable '{best_c['element'].get('label', '')}'",
                "path": "vision_free",
            }

    if text_inputs:
        best_t = max(text_inputs, key=lambda x: x["score"])
        if best_t["score"] >= CONFIDENCE_THRESHOLD:
            return {
                "confidence": best_t["score"],
                "action": "type",
                "element_id": best_t["index"],
                "reasoning": f"DOM prescan: text input detected at {best_t['element'].get('label', 'field')}",
                "path": "vision_free",
            }

    return {"confidence": 0.0, "action": None, "reason": "DOM prescan: low confidence, fallback to Vision", "path": "needs_vision"}
