"""prompt_kit – Dynamic prompt for Nemotron Omni Vision."""
from __future__ import annotations
from typing import Any


def build_prompt(context: dict[str, Any], step: int) -> str:
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
