"""Nemotron 3 Nano Omni – Unified Video+Audio+Image+Text Client.

Ersetzt separate Vision+Sprache-Stacks durch EIN Modell:
- 30B-A3B Mixture-of-Experts, native 1920×1080, 256K Kontext
- Conv3D temporale Videokompression, 9× höherer Durchsatz
- Gleicher NVIDIA NIM Endpoint, gleicher API-Key
"""
from __future__ import annotations
import base64
import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any

import httpx
from diskcache import Cache

NVIDIA_KEY = os.environ.get("NVIDIA_API_KEY")
NVIDIA_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
OMNI_MODEL = "nvidia/nvidia/nemotron-3-nano-omni-30b-a3b-reasoning"
FALLBACK_MODEL = "meta/llama-3.2-90b-vision-instruct"
_cache = Cache("/tmp/stealth_omni_cache")


class OmniError(Exception):
    pass


class OmniClient:
    """Single multimodal client for video, audio, image, text."""

    def __init__(self, model: str = OMNI_MODEL):
        self.model = model
        if not NVIDIA_KEY:
            raise OmniError("NVIDIA_API_KEY not set")

    def analyze_image(self, image_path: str, prompt: str,
                      temperature: float = 0.0, max_tokens: int = 300) -> dict[str, Any]:
        with open(image_path, "rb") as f:
            raw = f.read()
        img_hash = hashlib.sha256(raw).hexdigest()
        cached = _cache.get(img_hash)
        if cached:
            return cached
        b64 = base64.b64encode(raw).decode()
        response = self._call_api(messages=[{
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
                {"type": "text", "text": prompt},
            ],
        }], temperature=temperature, max_tokens=max_tokens)
        action = self._parse_json(response)
        _cache.set(img_hash, action, expire=3600)
        return action

    def analyze_video(self, video_path: str,
                      prompt: str = "Analyze this screen recording. What happened?",
                      max_tokens: int = 500) -> dict[str, Any]:
        with open(video_path, "rb") as f:
            video_b64 = base64.b64encode(f.read()).decode()
        v_hash = hashlib.sha256(video_b64.encode()).hexdigest()[:16]
        cached = _cache.get(v_hash)
        if cached:
            return cached
        response = self._call_api(messages=[{
            "role": "user",
            "content": [
                {"type": "video_url", "video_url": {"url": f"data:video/mp4;base64,{video_b64}"}},
                {"type": "text", "text": prompt},
            ],
        }], max_tokens=max_tokens)
        result = self._parse_json(response)
        _cache.set(v_hash, result, expire=86400)
        return result

    def analyze_frame_sequence(self, image_paths: list[str], prompt: str,
                                max_tokens: int = 500) -> dict[str, Any]:
        seq_hash = hashlib.sha256("|".join(image_paths).encode()).hexdigest()[:16]
        cached = _cache.get(seq_hash)
        if cached:
            return cached
        content: list[dict] = []
        for i, path in enumerate(image_paths):
            with open(path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode()
            content.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}})
            content.append({"type": "text", "text": f"[Frame {i+1}/{len(image_paths)}]"})
        content.append({"type": "text", "text": prompt})
        response = self._call_api(messages=[{"role": "user", "content": content}], max_tokens=max_tokens)
        result = self._parse_json(response)
        _cache.set(seq_hash, result, expire=3600)
        return result

    def _call_api(self, messages: list[dict], temperature: float = 0.0,
                  max_tokens: int = 300) -> str:
        try:
            r = httpx.post(NVIDIA_URL, headers={"Authorization": f"Bearer {NVIDIA_KEY}"},
                           json={"model": self.model, "messages": messages,
                                 "max_tokens": max_tokens, "temperature": temperature},
                           timeout=90)
            return r.json()["choices"][0]["message"]["content"]
        except Exception:
            if self.model != FALLBACK_MODEL:
                try:
                    r = httpx.post(NVIDIA_URL, headers={"Authorization": f"Bearer {NVIDIA_KEY}"},
                                   json={"model": FALLBACK_MODEL, "messages": messages,
                                         "max_tokens": max_tokens, "temperature": temperature},
                                   timeout=60)
                    return r.json()["choices"][0]["message"]["content"]
                except Exception as e:
                    raise OmniError(f"API call failed: {e}") from e
            raise

    @staticmethod
    def _parse_json(text: str) -> dict:
        text = text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("\n", 1)[0].strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            m = re.search(r"\{.*\}", text, re.DOTALL)
            if m:
                try:
                    return json.loads(m.group())
                except json.JSONDecodeError:
                    pass
        return {"action": "wait", "reasoning": "parse_failed"}


_omni_instance: OmniClient | None = None


def get_omni() -> OmniClient:
    global _omni_instance
    if _omni_instance is None:
        _omni_instance = OmniClient()
    return _omni_instance
