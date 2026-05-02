"""Model Router — task-basierte LLM-Auswahl (NVIDIA NIM + Mistral API).

Einzige API: `router.call(task, prompt, images?) -> str`
Tasks: vision | captcha | persona | logic

Provider (aus config/models.yaml):
  - nvidia  → NVIDIA NIM (Vision + Text)
  - mistral → Mistral API direkt (Text only, $MISTRAL_API_KEY)
"""
from __future__ import annotations
import base64, json, os, re
from enum import Enum
from pathlib import Path
from typing import Any

import httpx
import yaml

# ── Lade .env falls vorhanden (damit MISTRAL_API_KEY aus .env funktioniert) ──
def _load_dotenv(path: str = ".env"):
    p = Path(path)
    if not p.exists():
        return
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        key = key.strip()
        val = val.strip().strip("\"'")
        if key and not os.environ.get(key):
            os.environ[key] = val

_load_dotenv()

NVIDIA_KEY = os.environ.get("NVIDIA_API_KEY", "")
NVIDIA_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
MISTRAL_KEY = os.environ.get("MISTRAL_API_KEY", "")
MISTRAL_URL = "https://api.mistral.ai/v1/chat/completions"


class Task(str, Enum):
    VISION = "vision"
    CAPTCHA = "captcha"
    PERSONA = "persona"
    LOGIC = "logic"


class Provider(str, Enum):
    NVIDIA = "nvidia"
    MISTRAL = "mistral"


class ModelRouter:
    """Leitet Aufgaben an NVIDIA NIM oder Mistral API je nach config/models.yaml.

    Config definiert pro Task:
      - provider: "nvidia" | "mistral"
      - model, fallback[], max_tokens, timeout
    """

    def __init__(self, config_path: str = "config/models.yaml"):
        self._cfg: dict[str, Any] = {"models": {}}
        path = Path(config_path)
        if path.exists():
            raw = yaml.safe_load(path.read_text()) or {}
            self._cfg = raw
        old = Path("config/vision_models.yaml")
        if old.exists() and Task.VISION not in self._cfg.get("models", {}):
            old_raw = yaml.safe_load(old.read_text()) or {}
            self._cfg.setdefault("models", {})[Task.VISION] = {
                "provider": Provider.NVIDIA,
                "model": old_raw.get("current_model", "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning"),
                "fallback": old_raw.get("fallback_models", []),
                "max_tokens": old_raw.get("max_tokens", 300),
                "timeout": old_raw.get("timeout", 60),
            }

    def _task_cfg(self, task: Task) -> dict:
        models = self._cfg.get("models", {})
        defaults = {
            "provider": Provider.NVIDIA, "max_tokens": 300, "timeout": 60,
            "model": "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning", "fallback": [],
        }
        return {**defaults, **models.get(task, models.get(Task.VISION, defaults))}

    def call(self, task: Task, prompt: str, images: list[str] | None = None) -> str:
        cfg = self._task_cfg(task)
        model = cfg["model"]
        provider = cfg.get("provider", Provider.NVIDIA)
        max_tokens = cfg["max_tokens"]
        timeout = cfg["timeout"]
        fallbacks: list[str] = cfg.get("fallback", [])

        text = self._provider_chat(provider, model, prompt, images, max_tokens, timeout)
        if text:
            return text
        for fb_model in fallbacks:
            text = self._provider_chat(provider, fb_model, prompt, images, max_tokens, timeout)
            if text:
                return text
        raise RuntimeError(f"Alle Modelle für {task.value} fehlgeschlagen")

    def _provider_chat(self, provider: str, model: str, prompt: str,
                       images: list[str] | None, max_tokens: int, timeout: int) -> str:
        if provider == Provider.MISTRAL:
            return self._mistral_chat(model, prompt, max_tokens, timeout)
        return self._nim_chat(model, prompt, images, max_tokens, timeout)

    # ── NVIDIA NIM ──────────────────────────────────────────────────────

    def _nim_chat(self, model: str, prompt: str, images: list[str] | None,
                  max_tokens: int, timeout: int) -> str:
        if not NVIDIA_KEY:
            return ""
        content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
        if images:
            for img_path in images:
                try:
                    with open(img_path, "rb") as f:
                        b64 = base64.b64encode(f.read()).decode()
                    content.append({
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{b64}"},
                    })
                except Exception:
                    continue
        try:
            r = httpx.post(
                NVIDIA_URL,
                headers={"Authorization": f"Bearer {NVIDIA_KEY}"},
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": content}],
                    "max_tokens": max_tokens,
                    "temperature": 0.0,
                },
                timeout=timeout,
            )
            if r.status_code != 200:
                return ""
            msg = r.json()["choices"][0]["message"]
            return (msg.get("content") or msg.get("reasoning") or "").strip()
        except Exception:
            return ""

    # ── Mistral API direkt ──────────────────────────────────────────────

    def _mistral_chat(self, model: str, prompt: str,
                      max_tokens: int, timeout: int) -> str:
        if not MISTRAL_KEY:
            return ""
        messages = [{"role": "user", "content": prompt}]
        try:
            r = httpx.post(
                MISTRAL_URL,
                headers={
                    "Authorization": f"Bearer {MISTRAL_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "messages": messages,
                    "max_tokens": max_tokens,
                    "temperature": 0.0,
                },
                timeout=timeout,
            )
            if r.status_code != 200:
                return ""
            return r.json()["choices"][0]["message"]["content"].strip()
        except Exception:
            return ""

    @staticmethod
    def extract_json(text: str) -> dict[str, Any]:
        text = text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("\n", 1)[0].strip()
        text = re.sub(r"//.*?(\n|$)", "", text)  # Entferne //-Kommentare (Mistral)
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            m = re.search(r"\{.*\}", text, re.DOTALL)
            if m:
                try:
                    return json.loads(m.group())
                except json.JSONDecodeError:
                    pass
        return {}


_router: ModelRouter | None = None


def get_router() -> ModelRouter:
    global _router
    if _router is None:
        _router = ModelRouter()
    return _router
