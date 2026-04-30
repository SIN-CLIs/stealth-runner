"""Pydantic V2-Modelle für strukturierte Vision-API-Antworten (10 Aktionstypen)."""
from __future__ import annotations
from enum import StrEnum
from typing import Annotated, Literal, Any
from pydantic import BaseModel, Field, Discriminator, Tag, TypeAdapter, ValidationError

class ActionType(StrEnum):
    CLICK = "click"; TYPE = "type"; KEYPRESS = "keypress"; SCROLL = "scroll"
    DRAG = "drag"; HOLD = "hold"; SELECT_OPTION = "select-option"; TRACK = "track"
    WAIT = "wait"; DONE = "done"

class ClickAction(BaseModel): action: Literal[ActionType.CLICK] = ActionType.CLICK; element_id: int = Field(..., ge=0); reasoning: str = ""
class TypeAction(BaseModel): action: Literal[ActionType.TYPE] = ActionType.TYPE; element_id: int = Field(..., ge=0); args: dict[str, Any] = Field(default_factory=lambda: {"text": "", "clear_first": False})
class ScrollAction(BaseModel): action: Literal[ActionType.SCROLL] = ActionType.SCROLL; args: dict[str, int] = Field(default_factory=lambda: {"delta_y": 300})
class HoldAction(BaseModel): action: Literal[ActionType.HOLD] = ActionType.HOLD; element_id: int = Field(..., ge=0); args: dict[str, int] = Field(default_factory=lambda: {"duration_ms": 3000})
class WaitAction(BaseModel): action: Literal[ActionType.WAIT] = ActionType.WAIT; reasoning: str = ""
class DoneAction(BaseModel): action: Literal[ActionType.DONE] = ActionType.DONE; reasoning: str = ""

VisionAction = ClickAction | TypeAction | ScrollAction | HoldAction | WaitAction | DoneAction

def validate_vision_response(raw: dict[str, Any]) -> VisionAction:
    try: return TypeAdapter(VisionAction).validate_python(raw)
    except ValidationError: return WaitAction(action=ActionType.WAIT, reasoning="validation_failed")
