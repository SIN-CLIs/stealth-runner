"""Pydantic-Modelle für die strukturierte Validierung von Vision-Antworten."""
from __future__ import annotations
from typing import Literal, Any, Annotated
import pydantic
from pydantic import BaseModel, Field

class ClickAction(BaseModel):
    action: Literal["click"] = "click"
    element_id: int = Field(..., ge=0)
    reasoning: str = ""

class TypeAction(BaseModel):
    action: Literal["type"] = "type"
    element_id: int = Field(..., ge=0)
    args: dict = Field(default_factory=lambda: {"text": "", "clear_first": False})

class ScrollAction(BaseModel):
    action: Literal["scroll"] = "scroll"
    args: dict = Field(default_factory=lambda: {"direction": "down"})

class HoldAction(BaseModel):
    action: Literal["hold"] = "hold"
    element_id: int = Field(..., ge=0)
    args: dict = Field(default_factory=lambda: {"duration_ms": 3000})

class WaitAction(BaseModel):
    action: Literal["wait"] = "wait"

class DoneAction(BaseModel):
    action: Literal["done"] = "done"

VisionAction = ClickAction | TypeAction | ScrollAction | HoldAction | WaitAction | DoneAction

def validate_vision_response(raw: dict[str, Any]) -> VisionAction:
    try:
        return pydantic.TypeAdapter(VisionAction).validate_python(raw)
    except pydantic.ValidationError:
        return WaitAction(action="wait")
