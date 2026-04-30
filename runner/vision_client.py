"""VisionClient – Robustes Vision-API-Gateway mit Dual-Fallback."""
from __future__ import annotations
import base64, json, os, re
from typing import Any
import httpx
from .prompt_kit import SYSTEM_PROMPT

CF_ACCOUNT = os.environ.get("CF_ACCT")
CF_TOKEN = os.environ.get("CF_TOKEN")
NVIDIA_KEY = os.environ.get("NVIDIA_API_KEY")
CF_URL = f"https://api.cloudflare.com/client/v4/accounts/{CF_ACCOUNT}/ai/run/@cf/meta/llama-4-scout-17b-16e-instruct" if CF_ACCOUNT else ""
NVIDIA_URL = "https://integrate.api.nvidia.com/v1/chat/completions"

class VisionClient:
    def __init__(self) -> None:
        if not CF_TOKEN and not NVIDIA_KEY:
            raise EnvironmentError("CF_TOKEN or NVIDIA_API_KEY must be set")

    def get_action(self, image_path: str, user_prompt: str) -> dict[str, Any]:
        with open(image_path, "rb") as f:
            img_b64 = base64.b64encode(f.read()).decode()
        prompt = f"{SYSTEM_PROMPT}\n\n{user_prompt}"
        text = self._call_llm(img_b64, prompt)
        return self._parse_json(text)

    def _call_llm(self, img_b64: str, prompt: str) -> str:
        if CF_TOKEN and CF_URL:
            try:
                with httpx.Client(timeout=45) as client:
                    resp = client.post(CF_URL, headers={"Authorization": f"Bearer {CF_TOKEN}", "Content-Type": "application/json"}, json={
                        "messages": [{"role": "user", "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_b64}"}}
                        ]}], "max_tokens": 200})
                    data = resp.json()
                    result = data.get("result", {}).get("response", "")
                    if result: return result
            except Exception: pass
        if NVIDIA_KEY:
            try:
                with httpx.Client(timeout=60) as client:
                    resp = client.post(NVIDIA_URL, headers={"Authorization": f"Bearer {NVIDIA_KEY}", "Content-Type": "application/json"}, json={
                        "model": "mistralai/mistral-large-3-675b-instruct-2512",
                        "messages": [{"role": "user", "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_b64}"}}
                        ]}], "max_tokens": 200})
                    return resp.json()["choices"][0]["message"]["content"]
            except Exception: pass
        return ""

    @staticmethod
    def _parse_json(text: str) -> dict[str, Any]:
        text = text.strip()
        if text.startswith("```"): text = text.split("\n", 1)[1].rsplit("\n", 1)[0].strip()
        if text.startswith("json"): text = text[4:].strip()
        try: return json.loads(text)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", text, re.DOTALL)
            if match:
                try: return json.loads(match.group(0))
                except json.JSONDecodeError: pass
        return {"action": "click", "element_id": 0, "reasoning": "parse_failed"}
