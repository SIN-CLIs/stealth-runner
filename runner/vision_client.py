"""VisionClient – NVIDIA NIM Vision (llama-3.2-90b)."""
from __future__ import annotations
import base64, json, os, re, hashlib
import httpx
from diskcache import Cache
from .prompt_kit import SYSTEM_PROMPT

NVIDIA_KEY = os.environ.get("NVIDIA_API_KEY")
NVIDIA_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
VISION_MODEL = "meta/llama-3.2-90b-vision-instruct"
_cache = Cache("/tmp/stealth_vision_cache")


class VisionClient:
    def get_action(self, image_path: str, prompt: str) -> dict:
        with open(image_path, "rb") as f:
            raw = f.read()
        img_hash = hashlib.sha256(raw).hexdigest()
        if cached := _cache.get(img_hash):
            return cached
        b64 = base64.b64encode(raw).decode()
        text = self._call_llm(b64, f"{SYSTEM_PROMPT}\n\n{prompt}")
        action = self._parse_json(text)
        _cache.set(img_hash, action, expire=3600)
        return action

    def _call_llm(self, img_b64: str, prompt: str) -> str:
        if not NVIDIA_KEY:
            return ""
        try:
            r = httpx.post(
                NVIDIA_URL,
                headers={"Authorization": f"Bearer {NVIDIA_KEY}"},
                json={
                    "model": VISION_MODEL,
                    "messages": [{
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_b64}"}},
                        ],
                    }],
                    "max_tokens": 200,
                },
                timeout=60,
            )
            return r.json()["choices"][0]["message"]["content"]
        except Exception:
            return ""

    @staticmethod
    def _parse_json(text: str) -> dict:
        text = text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("\n", 1)[0]
        try:
            return json.loads(text)
        except Exception:
            m = re.search(r"\{.*\}", text, re.DOTALL)
            if m:
                try:
                    return json.loads(m.group())
                except Exception:
                    pass
        return {"action": "wait"}

