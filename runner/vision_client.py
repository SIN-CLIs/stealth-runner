import json, base64, urllib.request, os, re
from io import BytesIO
from PIL import Image
from sin_survey_core import extract_eur_from_text, classify_error

CF_TOKEN = os.environ.get("CF_TOKEN", "")
CF_ACCT = os.environ.get("CF_ACCT", "4621434bea0a1efc1ceff2a3f670e0c9")
NVIDIA_KEY = os.environ.get("NVIDIA_API_KEY", "")
CF_URL = f"https://api.cloudflare.com/client/v4/accounts/{CF_ACCT}/ai/run/@cf/meta/llama-4-scout-17b-16e-instruct"
NVIDIA_URL = "https://integrate.api.nvidia.com/v1/chat/completions"

class VisionClient:
    def analyze(self, screenshot_path, session):
        img = Image.open(screenshot_path).convert('RGB')
        buf = BytesIO()
        img.save(buf, 'JPEG', quality=50)
        img_b64 = base64.b64encode(buf.getvalue()).decode()
        prompt = self._build_action_prompt(session)
        text = self._ask_vision(img_b64, prompt)
        return self._parse_action(text)

    def detect_state(self, window_state):
        return _detect_page_state(window_state)

    def extract_earnings(self, screenshot_path=None, page_text=""):
        data = None
        if screenshot_path:
            img = Image.open(screenshot_path).convert('RGB')
            buf = BytesIO()
            img.save(buf, 'JPEG', quality=50)
            img_b64 = base64.b64encode(buf.getvalue()).decode()
            prompt = 'Find EUR amount earned. Reply ONLY: EUR=1.23 or EUR=0'
            data = self._ask_vision(img_b64, prompt)
        return extract_eur_from_text(data or page_text or "")

def _detect_page_state(window_state):
    markdown = window_state.get('tree_markdown', '')
    url = window_state.get('url', '').lower()
    if 'dashboard' in url or 'deine verfügbaren erhebungen' in markdown.lower():
        return 'dashboard'
    if 'survey_end' in url or 'thank you' in markdown.lower():
        return 'survey_end'
    if 'dq' in url or 'disqualif' in markdown.lower():
        return 'dq'
    return 'question'
