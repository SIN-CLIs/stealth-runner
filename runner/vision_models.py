"""Pydantic V2-Modelle für strukturierte Vision-API-Antworten."""
from __future__ import annotations
from typing import Literal, Any
from pydantic import BaseModel, Field, ConfigDict

class ClickAction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal["click"]
    element_id: int = Field(..., ge=0); reasoning: str = ""

class TypeAction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal["type"]; element_id: int = Field(..., ge=0)
    args: dict = Field(default_factory=lambda: {"text": "", "clear_first": False})

class ScrollAction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal["scroll"]; args: dict = Field(default_factory=lambda: {"direction": "down"})

class HoldAction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal["hold"]; element_id: int = Field(..., ge=0)
    args: dict = Field(default_factory=lambda: {"duration_ms": 3000})

class WaitAction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal["wait"]

class DoneAction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal["done"]

_MODELS = [ClickAction, TypeAction, ScrollAction, HoldAction, WaitAction, DoneAction]

def validate_vision_response(raw: dict[str, Any]) -> dict[str, Any]:
    for model in _MODELS:
        try: return model(**raw).model_dump()
        except Exception: continue
    return {"action": "wait"}
