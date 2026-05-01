"""dom_prescan – Vision-free Fast Path via unmask-cli DOM-Scan."""
from __future__ import annotations
import re
from typing import Any


CONFIDENCE_THRESHOLD = 0.60

QUESTION_PATTERNS = re.compile(
    r"(what|which|how|when|where|who|why|do you|are you|have you|"
    r"did you|would you|could you|please select|choose|pick|"
    r"was|wie|welch|wann|wo|wer|warum|bitte w[aä]hle)",
    re.IGNORECASE,
)

BUTTON_ROLES = {"AXButton", "AXLink", "AXCheckBox", "AXRadioButton", "button", "link"}
TEXT_ROLES = {"AXTextField", "AXTextArea", "AXComboBox", "AXSearchField", "textarea", "input"}
IMAGE_SELECTORS = re.compile(r"img|image|picture|figure|SVG|canvas", re.IGNORECASE)


def _has_images(elements: list[dict[str, Any]]) -> bool:
    for el in elements:
        sel = el.get("selector", "")
        role = el.get("role", "")
        if IMAGE_SELECTORS.search(sel) or IMAGE_SELECTORS.search(role):
            return True
    return False


def classify_element(el: dict[str, Any]) -> str:
    role = el.get("role", "")
    label = el.get("label", el.get("text", ""))
    if QUESTION_PATTERNS.search(label):
        return "question_text"
    if role in BUTTON_ROLES:
        return "clickable"
    if role in TEXT_ROLES:
        return "text_input"
    if role == "div" and len(label) > 2 and len(label) < 100:
        return "clickable"
    if el.get("reasons") and "clickable" in el.get("reasons", []):
        return "clickable"
    return "unknown"


def prescan_dom(dom_data: list[dict[str, Any]]) -> dict[str, Any]:
    if isinstance(dom_data, list):
        elements = dom_data
    elif isinstance(dom_data, dict):
        elements = dom_data.get("elements", [])
    else:
        return {"confidence": 0.0, "action": None, "reason": "invalid input", "path": "needs_vision"}

    if not elements:
        return {"confidence": 0.0, "action": None, "reason": "no elements found", "path": "needs_vision"}

    if _has_images(elements):
        return {"confidence": 0.0, "action": None, "reason": "page contains images — Vision required", "path": "needs_vision"}

    classified = []
    for i, el in enumerate(elements):
        el_type = classify_element(el)
        score = 0.5
        if el_type == "clickable":
            score = 0.6
            if len(el.get("text", el.get("label", ""))) > 5:
                score = 0.70
        elif el_type == "question_text":
            score = 0.75
        elif el_type == "text_input":
            score = 0.65
        classified.append({"index": i, "type": el_type, "element": el, "score": score})

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
                "reasoning": f"DOM prescan: question detected, clicking '{best_c['element'].get('text', best_c['element'].get('label', 'button'))[:50]}'",
                "path": "vision_free",
            }

    if clickables:
        best_c = max(clickables, key=lambda x: x["score"])
        if best_c["score"] >= CONFIDENCE_THRESHOLD:
            return {
                "confidence": best_c["score"],
                "action": "click",
                "element_id": best_c["index"],
                "reasoning": f"DOM prescan: best clickable '{best_c['element'].get('text', best_c['element'].get('label', ''))[:50]}'",
                "path": "vision_free",
            }

    if text_inputs:
        best_t = max(text_inputs, key=lambda x: x["score"])
        if best_t["score"] >= CONFIDENCE_THRESHOLD:
            return {
                "confidence": best_t["score"],
                "action": "type",
                "element_id": best_t["index"],
                "reasoning": f"DOM prescan: text input at '{best_t['element'].get('text', best_t['element'].get('label', 'field'))[:50]}'",
                "path": "vision_free",
            }

    return {"confidence": 0.0, "action": None, "reason": "DOM prescan: low confidence or image content — fallback to Vision", "path": "needs_vision"}
