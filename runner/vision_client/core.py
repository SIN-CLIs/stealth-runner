"""
Vision-Client Core mit Retry-Logik, Circuit Breaker und Fallback-Action.
"""
import time
import json
import logging
from typing import Dict, Any, Optional
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from requests.exceptions import Timeout, RequestException

# Circuit Breaker Zustand (global für Singleton)
CIRCUIT_BROKEN = False
FAILURE_COUNT = 0
LAST_FAILURE_TIME = 0

class VisionClient:
    def __init__(self, config_path: str = "config/vision_models.yaml"):
        self.logger = logging.getLogger("vision_client")
        self.max_retries = 3
        self.circuit_breaker_threshold = 5
        self.circuit_breaker_timeout = 300  # 5 Minuten in Sekunden

    def _parse_json(self, text: str) -> Dict[str, Any]:
        """Extrahiert JSON aus Text (auch aus Codeblocks)."""
        import re
        
        # JSON-Codeblock extrahieren
        match = re.search(r"```(?:json)?\s*([^`]+)```", text, re.DOTALL)
        if match:
            text = match.group(1).strip()
        
        # JSON parsen
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {"action": "wait", "reason": "invalid_json"}
        self.circuit_breaker_timeout = 300  # 5 Minuten
        self._load_config(config_path)

    def _load_config(self, config_path: str):
        import yaml
        from pathlib import Path
        config = yaml.safe_load(Path(config_path).read_text())
        self.current_model = config["current_model"]
        self.fallback_models = config.get("fallback_models", [])

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((Timeout, RequestException)),
    )
    def analyze_screenshot(self, image_path: str, step: int) -> Dict[str, Any]:
        """
        Analysiert Screenshot mit Vision-LLM.
        Gibt JSON-Action zurück: {"action": "click|type|scroll|done|wait", ...}
        """
        global CIRCUIT_BROKEN, FAILURE_COUNT, LAST_FAILURE_TIME

        if CIRCUIT_BROKEN:
            elapsed = time.time() - LAST_FAILURE_TIME
            if elapsed < self.circuit_breaker_timeout:
                self.logger.error(f"Circuit Breaker aktiv! Warte {self.circuit_breaker_timeout - elapsed:.0f}s")
                raise Exception("Circuit Breaker aktiv")
            else:
                CIRCUIT_BROKEN = False
                FAILURE_COUNT = 0  # Reset auch hier
                self.logger.warning("Circuit Breaker zurückgesetzt!")

        try:
            prompt = self._build_prompt(step)
            result = self._nvidia_vision_call(prompt, image_path)
            FAILURE_COUNT = 0  # Reset bei Erfolg
            return result
        except Exception as e:
            FAILURE_COUNT += 1
            LAST_FAILURE_TIME = time.time()
            if FAILURE_COUNT >= self.circuit_breaker_threshold:
                CIRCUIT_BROKEN = True
                self.logger.critical("Circuit Breaker ausgelöst! Keine weiteren Vision-Calls für 5 Minuten.")
            raise

    def _build_prompt(self, step: int) -> str:
        """Baut Prompt für Vision-LLM."""
        return (
            f"You are a browser automation agent. Step {step}. "
            "Analyze the screenshot and return ONLY JSON with:"
            '{"action": "click|type|scroll|done|wait", "element_id": int, "args": {...}}'
            "No explanations, no markdown, just valid JSON."
        )

    def _nvidia_vision_call(self, prompt: str, image_path: str) -> Dict[str, Any]:
        """NVIDIA Vision API Call."""
        import base64
        import requests
        from pathlib import Path

        image_data = base64.b64encode(Path(image_path).read_bytes()).decode("utf-8")
        api_key = "NVIDIA_API_KEY"  # Wird aus .env geladen

        headers = {"Authorization": f"Bearer {api_key}"}
        payload = {
            "model": self.current_model,
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_data}"}}
                ]
            }],
            "max_tokens": 200
        }

        response = requests.post(
            "https://integrate.api.nvidia.com/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=60
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]

        # JSON parsen
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            self.logger.error(f"Vision-LLM gab kein gültiges JSON zurück: {content}")
            raise Exception("Invalid JSON from Vision-LLM")

    def handle_vision_error(self, error: Exception, state: Dict[str, Any]) -> Dict[str, Any]:
        """Fallback-Action bei Vision-Fehler."""
        error_type = type(error).__name__
        timestamp = time.strftime("%Y-%m-%d_%H-%M-%S")

        # Log in dedicated file
        with open(f"/tmp/vision_errors_{timestamp}.log", "a") as f:
            f.write(f"{time.time()}|{error_type}|{str(error)}\n")

        # Fallback: Warte 1 Stunde + EUR nicht erhöhen
        return {
            "action": "wait",
            "duration_seconds": 3600,
            "reason": f"Vision-LLM failed: {error_type}",
            "eur": state.get("eur", 0.0)
        }
