"""
Vision-Client Konfiguration (YAML-basiert).
"""
import yaml
from pathlib import Path
from typing import Dict, Any

class VisionConfig:
    def __init__(self, config_path: str = "config/vision_models.yaml"):
        self.config_path = Path(config_path)
        self.config = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        with open(self.config_path) as f:
            return yaml.safe_load(f)

    @property
    def current_model(self) -> str:
        return self.config["current_model"]

    @property
    def fallback_models(self) -> list:
        return self.config.get("fallback_models", [])

    @property
    def max_tokens(self) -> int:
        return self.config.get("max_tokens", 200)

    @property
    def timeout(self) -> int:
        return self.config.get("timeout", 60)
