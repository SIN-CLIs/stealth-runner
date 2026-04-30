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
    def _build_action_prompt(self, session):
        return (
            'You are a survey automation agent. Analyze the screenshot and decide the NEXT action.\n'
            'Previous steps: {steps}. Current EUR earned: {eur}.\n'
            'The screenshot shows a web page with interactive elements marked as [N] AXRole "text".\n'
            'Reply with JSON: {{"action":"click","element_id":N,"reasoning":"..."}}\n'
            'or {{"action":"type","text":"...","reasoning":"..."}}\n'
            'or {{"action":"scroll","direction":"down","reasoning":"..."}}\n'
        ).format(steps=session.get('steps', 0), eur=session.get('earnings_eur', 0.0))

    def _ask_vision(self, img_b64, prompt):
        if CF_TOKEN:
            try:
                data = json.dumps({
                    'messages': [{'role':'user','content':[
                        {'type':'text','text':prompt},
                        {'type':'image_url','image_url':{'url':f'data:image/jpeg;base64,{img_b64}'}}
                    ]}],'max_tokens':120
                }).encode()
                req = urllib.request.Request(CF_URL, data=data,
                    headers={'Authorization':f'Bearer {CF_TOKEN}','Content-Type':'application/json'})
                r = json.loads(urllib.request.urlopen(req, timeout=35).read())
                return r.get('result',{}).get('response','')
            except: pass
        
        if NVIDIA_KEY:
            try:
                data = json.dumps({
                    'model': 'mistralai/mistral-large-3-675b-instruct-2512',
                    'messages': [{'role':'user','content':[
                        {'type':'text','text':prompt},
                        {'type':'image_url','image_url':{'url':f'data:image/jpeg;base64,{img_b64}'}}
                    ]}],'max_tokens':120
                }).encode()
                req = urllib.request.Request(NVIDIA_URL, data=data,
                    headers={'Authorization':f'Bearer {NVIDIA_KEY}','Content-Type':'application/json'})
                resp = json.loads(urllib.request.urlopen(req, timeout=60).read())
                return resp['choices'][0]['message']['content']
            except: pass
        return ''

    def _parse_action(self, text):
        try:
            return json.loads(text.strip().split('```json')[1].split('```')[0].strip())
        except: pass
        try:
            return json.loads(text.strip())
        except: pass
        m = re.search(r'\{.*\}', text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(0))
            except: pass
        return {"action": "click", "element_id": 0, "reasoning": f"failed_to_parse: {text[:50]}"}

    def analyze(self, screenshot_path, session):
        img = Image.open(screenshot_path).convert('RGB')
        buf = BytesIO()
        img.save(buf, 'JPEG', quality=50)
        img_b64 = base64.b64encode(buf.getvalue()).decode()

        prompt = self._build_action_prompt(session)
        text = self._ask_vision(img_b64, prompt)
        return self._parse_action(text)

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
