"""Vision-Client Core mit Retry-Logik, Circuit Breaker und Omni-Fallback."""
from __future__ import annotations
import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Any

import yaml
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from requests.exceptions import Timeout, RequestException
from diskcache import Cache

CIRCUIT_BROKEN = False
FAILURE_COUNT = 0
LAST_FAILURE_TIME = 0
_cache = Cache("/tmp/stealth_vision_cache")


class VisionClient:
    def __init__(self, config_path: str = "config/vision_models.yaml"):
        self.logger = logging.getLogger("vision_client")
        self.max_retries = 3
        self.circuit_breaker_threshold = 5
        self.circuit_breaker_timeout = 300
        self._load_config(config_path)

    def _load_config(self, config_path: str):
        config = yaml.safe_load(Path(config_path).read_text())
        self.current_model = config["current_model"]
        self.fallback_models = config.get("fallback_models", [])
        self.max_tokens = config.get("max_tokens", 300)
        self.api_timeout = config.get("timeout", 60)

    def _parse_json(self, text: str) -> dict[str, Any]:
        match = re.search(r"```(?:json)?\s*([^`]+)```", text, re.DOTALL)
        if match:
            text = match.group(1).strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {"action": "wait", "reason": "invalid_json"}

    def get_action(self, image_path: str, prompt: str) -> dict:
        with open(image_path, "rb") as f:
            raw = f.read()
        import hashlib
        img_hash = hashlib.sha256(raw).hexdigest()
        cached = _cache.get(img_hash)
        if cached:
            return cached
        import base64
        b64 = base64.b64encode(raw).decode()
        full_prompt = f"System: {prompt}\nOutput ONLY valid JSON."

        text = self._call_model(self.current_model, b64, full_prompt)
        if not text:
            for fallback in self.fallback_models:
                text = self._call_model(fallback, b64, full_prompt)
                if text:
                    break
        action = self._parse_json(text)
        _cache.set(img_hash, action, expire=3600)
        return action

    def _call_model(self, model: str, img_b64: str, prompt: str) -> str:
        api_key = os.environ.get("NVIDIA_API_KEY", "")
        if not api_key:
            return ""
        try:
            import httpx
            r = httpx.post(
                "https://integrate.api.nvidia.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": model,
                    "messages": [{
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_b64}"}},
                        ],
                    }],
                    "max_tokens": self.max_tokens,
                },
                timeout=self.api_timeout,
            )
            return r.json()["choices"][0]["message"]["content"]
        except Exception:
            return ""

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10),
           retry=retry_if_exception_type((Timeout, RequestException)))
    def analyze_screenshot(self, image_path: str, step: int) -> dict[str, Any]:
        global CIRCUIT_BROKEN, FAILURE_COUNT, LAST_FAILURE_TIME

        if CIRCUIT_BROKEN:
            elapsed = time.time() - LAST_FAILURE_TIME
            if elapsed < self.circuit_breaker_timeout:
                self.logger.error(f"Circuit Breaker! {self.circuit_breaker_timeout - elapsed:.0f}s")
                raise Exception("Circuit Breaker aktiv")
            else:
                CIRCUIT_BROKEN = False
                FAILURE_COUNT = 0
                self.logger.warning("Circuit Breaker reset")

        try:
            prompt = self._build_prompt(step)
            result = self._nvidia_vision_call(prompt, image_path)
            FAILURE_COUNT = 0
            return result
        except Exception as e:
            FAILURE_COUNT += 1
            LAST_FAILURE_TIME = time.time()
            if FAILURE_COUNT >= self.circuit_breaker_threshold:
                CIRCUIT_BROKEN = True
                self.logger.critical("Circuit Breaker triggered")
            raise

    def _build_prompt(self, step: int) -> str:
        return (
            f"You are a browser automation agent. Step {step}. "
            "Analyze the screenshot and return ONLY JSON with:"
            '{"action": "click|type|scroll|done|wait", "element_id": int, "args": {...}}'
            "No explanations, no markdown, just valid JSON."
        )

    def _nvidia_vision_call(self, prompt: str, image_path: str) -> dict:
        import base64
        import requests
        image_data = base64.b64encode(Path(image_path).read_bytes()).decode()
        api_key = os.environ.get("NVIDIA_API_KEY", "")
        headers = {"Authorization": f"Bearer {api_key}"}
        payload = {
            "model": self.current_model,
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_data}"}},
                ],
            }],
            "max_tokens": self.max_tokens,
        }
        response = requests.post(
            "https://integrate.api.nvidia.com/v1/chat/completions",
            headers=headers, json=payload, timeout=self.api_timeout,
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            self.logger.error(f"Invalid JSON: {content}")
            raise Exception("Invalid JSON from Vision-LLM")

    def handle_vision_error(self, error: Exception, state: dict[str, Any]) -> dict[str, Any]:
        error_type = type(error).__name__
        timestamp = time.strftime("%Y-%m-%d_%H-%M-%S")
        with open(f"/tmp/vision_errors_{timestamp}.log", "a") as f:
            f.write(f"{time.time()}|{error_type}|{str(error)}\n")
        return {"action": "wait", "duration_seconds": 3600,
                "reason": f"Vision-LLM failed: {error_type}", "eur": state.get("eur", 0.0)}
