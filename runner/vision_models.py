"""Pydantic-Modelle für die strukturierte Validierung von Vision-Antworten."""
from __future__ import annotations
from typing import Literal, Any
from pydantic import BaseModel, Field, ConfigDict

class VisionActionBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

class ClickAction(VisionActionBase):
    action: Literal["click"]
    element_id: int = Field(..., ge=0)
    reasoning: str = ""

class TypeAction(VisionActionBase):
    action: Literal["type"]
    element_id: int = Field(..., ge=0)
    args: dict = Field(default_factory=lambda: {"text": "", "clear_first": False})

class ScrollAction(VisionActionBase):
    action: Literal["scroll"]
    args: dict = Field(default_factory=lambda: {"direction": "down"})

class HoldAction(VisionActionBase):
    action: Literal["hold"]
    element_id: int = Field(..., ge=0)
    args: dict = Field(default_factory=lambda: {"duration_ms": 3000})

class WaitAction(VisionActionBase):
    action: Literal["wait"]

class DoneAction(VisionActionBase):
    action: Literal["done"]

_MODELS = [ClickAction, TypeAction, ScrollAction, HoldAction, WaitAction, DoneAction]

def validate_vision_response(raw: dict[str, Any]) -> dict[str, Any]:
    for model in _MODELS:
        try:
            return model(**raw).model_dump()
        except Exception:
            continue
    return {"action": "wait"}
