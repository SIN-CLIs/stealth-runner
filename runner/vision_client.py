import base64, json, os, re, urllib.request
from io import BytesIO
from PIL import Image

CF_ACCOUNT = os.environ.get("CF_ACCT", "4621434bea0a1efc1ceff2a3f670e0c9")
CF_TOKEN = os.environ.get("CF_TOKEN", "")
NVIDIA_KEY = os.environ.get("NVIDIA_API_KEY", "")
CF_URL = f"https://api.cloudflare.com/client/v4/accounts/{CF_ACCOUNT}/ai/run/@cf/meta/llama-4-scout-17b-16e-instruct"
NVIDIA_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
from .prompt_kit import SYSTEM_PROMPT, build_prompt

class VisionClient:
    def get_action(self, image_path, user_prompt):
        with open(image_path, "rb") as f:
            img_b64 = base64.b64encode(f.read()).decode()

        prompt = f"{SYSTEM_PROMPT}\n\n{user_prompt}"
        text = self._call_llm(img_b64, prompt)
        return self._parse_json(text)

    def _call_llm(self, img_b64, prompt):
        if CF_TOKEN:
            data = json.dumps({
                'messages': [{'role':'user','content': [
                    {'type':'text','text': prompt},
                    {'type':'image_url','image_url':{'url': f'data:image/png;base64,{img_b64}'}}
                ]}], 'max_tokens': 200
            }).encode()
            req = urllib.request.Request(CF_URL, data=data,
                headers={'Authorization': f'Bearer {CF_TOKEN}', 'Content-Type': 'application/json'})
            try:
                r = json.loads(urllib.request.urlopen(req, timeout=45).read())
                return r.get('result', {}).get('response', '')
            except: pass

        if NVIDIA_KEY:
            data = json.dumps({
                'model': 'mistralai/mistral-large-3-675b-instruct-2512',
                'messages': [{'role':'user','content': [
                    {'type':'text','text': prompt},
                    {'type':'image_url','image_url':{'url': f'data:image/png;base64,{img_b64}'}}
                ]}], 'max_tokens': 200
            }).encode()
            req = urllib.request.Request(NVIDIA_URL, data=data,
                headers={'Authorization': f'Bearer {NVIDIA_KEY}', 'Content-Type': 'application/json'})
            try:
                resp = json.loads(urllib.request.urlopen(req, timeout=60).read())
                return resp['choices'][0]['message']['content']
            except: pass
        return ''

    def _parse_json(self, text):
        text = text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("\n", 1)[0].strip()
            if text.startswith("json"):
                text = text[4:].strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            m = re.search(r'\{.*\}', text, re.DOTALL)
            if m:
                try: return json.loads(m.group(0))
                except: pass
        return {"action": "click", "element_id": 0, "reasoning": "parse_failed"}
