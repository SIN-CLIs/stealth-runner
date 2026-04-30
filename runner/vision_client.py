"""VisionClient – Cloudflare/NVIDIA mit diskcache-Semantic-Cache."""
from __future__ import annotations
import base64, json, os, re, hashlib
import httpx
from diskcache import Cache
from .prompt_kit import SYSTEM_PROMPT

CF_ACCOUNT = os.environ.get("CF_ACCT")
CF_TOKEN = os.environ.get("CF_TOKEN")
NVIDIA_KEY = os.environ.get("NVIDIA_API_KEY")
CF_URL = f"https://api.cloudflare.com/client/v4/accounts/{CF_ACCOUNT}/ai/run/@cf/meta/llama-4-scout-17b-16e-instruct" if CF_ACCOUNT else ""
NVIDIA_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
_cache = Cache("/tmp/stealth_vision_cache")

class VisionClient:
    def get_action(self, image_path: str, prompt: str) -> dict:
        with open(image_path, "rb") as f: raw = f.read()
        img_hash = hashlib.sha256(raw).hexdigest()
        if cached := _cache.get(img_hash): return cached
        b64 = base64.b64encode(raw).decode()
        text = self._call_llm(b64, f"{SYSTEM_PROMPT}\n\n{prompt}")
        action = self._parse_json(text)
        _cache.set(img_hash, action, expire=3600)
        return action

    def _call_llm(self, img_b64: str, prompt: str) -> str:
        if CF_TOKEN and CF_URL:
            try:
                r = httpx.post(CF_URL, headers={"Authorization": f"Bearer {CF_TOKEN}"}, json={"messages":[{"role":"user","content":[{"type":"text","text":prompt},{"type":"image_url","image_url":{"url":f"data:image/png;base64,{img_b64}"}}]}],"max_tokens":200}, timeout=45)
                d = r.json().get("result",{}).get("response","")
                if d: return d
            except: pass
        if NVIDIA_KEY:
            try:
                r = httpx.post(NVIDIA_URL, headers={"Authorization": f"Bearer {NVIDIA_KEY}"}, json={"model":"mistralai/mistral-large-3-675b-instruct-2512","messages":[{"role":"user","content":[{"type":"text","text":prompt},{"type":"image_url","image_url":{"url":f"data:image/png;base64,{img_b64}"}}]}],"max_tokens":200}, timeout=60)
                return r.json()["choices"][0]["message"]["content"]
            except: pass
        return ""

    @staticmethod
    def _parse_json(text: str) -> dict:
        text = text.strip()
        if text.startswith("```"): text = text.split("\n",1)[1].rsplit("\n",1)[0]
        try: return json.loads(text)
        except:
            m = re.search(r"\{.*\}", text, re.DOTALL)
            if m:
                try: return json.loads(m.group())
                except: pass
        return {"action":"wait"}
