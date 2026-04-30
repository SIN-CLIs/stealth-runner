from __future__ import annotations
import yaml
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from typing import Literal

class StealthConfig(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="", case_sensitive=False, extra="forbid")
    cf_account_id: str = Field(..., min_length=1)
    cf_api_token: str = Field(..., min_length=1)
    vision_model: Literal["gpt-4o", "llama-4-scout"] = "llama-4-scout"
    vision_timeout_sec: float = Field(5.0, gt=0, le=15)
    cli_timeout_sec: float = Field(8.0, gt=0, le=30)
    confidence_threshold: float = Field(0.75, ge=0.0, le=1.0)
    max_retries: int = Field(2, ge=0, le=5)
    dry_run: bool = False

class SurveyConfig(BaseSettings):
    url: str; max_loops: int = 50; recovery_limit: int = 3
    @classmethod
    def from_yaml(cls, path: Path) -> "SurveyConfig":
        data = yaml.safe_load(path.read_text()); return cls(**data)
