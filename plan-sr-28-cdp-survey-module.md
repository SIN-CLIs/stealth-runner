# Plan SR-28: CDP Survey Module

## Overview
Rewrite `survey_heypiggy.py` from `cua-driver` to direct CDP WebSocket. Target: **-90% latency**, no external daemon dependency.

## Architecture

```
cli/modules/
├── survey_cdp.py          ← NEW: Main module
│   ├── SurveyCDP          ← Class with CDP WebSocket management
│   ├── detect_provider()  ← URL → ProviderPattern
│   ├── answer_question()  ← Dispatch to provider pattern
│   └── run_survey()       ← Full flow: create_target → loop → complete
│
├── provider_patterns.py   ← NEW: Pattern definitions
│   ├── ProviderPattern    ← Dataclass
│   ├── QUALTRICS          ← .NextButton, input[type=radio], table.ChoiceStructure
│   ├── TOLUNASTART        ← button, .cf-radio, .cf-checkbox, input[type=number]
│   ├── STRAT7             ← .bsbutton, input[type=radio]
│   ├── BRAND_AMBASSADOR   ← .submit-btn, input[type=radio]
│   ├── INSIGHTS_TODAY     ← select, label click
│   └── register           ← {"qualtrics": QUALTRICS, ...}
│
└── persona.py             ← Already exists in A2A repo → copy/import
```

## CDP WebSocket Flow (replaces cua-driver)

### Before (cua-driver)
```python
def _cua(pid, wid, method, params=None):
    # Shell subprocess → cua-driver CLI → macOS AX API → ~500ms
    r = subprocess.run(["cua-driver", "call", method], input=json.dumps(p))
```

### After (CDP direct)
```python
class SurveyCDP:
    def __init__(self, port=9999):
        self.base_url = f"http://127.0.0.1:{port}/json"
    
    def eval(self, ws_url, js):
        ws = websocket.create_connection(ws_url)
        ws.send(json.dumps({'id': 0, 'method': 'Runtime.evaluate', 
                           'params': {'expression': js}}))
        return json.loads(ws.recv()).get('result',{}).get('result',{}).get('value')
    
    def create_target(self, dashboard_ws, url):
        # Target.createTarget via dashboard WebSocket
        ws = websocket.create_connection(dashboard_ws)
        ws.send(json.dumps({'id': 1, 'method': 'Target.createTarget', 
                           'params': {'url': url}}))
        result = json.loads(ws.recv())
        return result['result']['targetId']
```

## Provider Pattern Detection

```python
PROVIDERS = {
    'qualtrics': ProviderPattern(
        name='qualtrics',
        url_patterns=['eu.qualtrics.com', 'qualtrics.com/jfe/form'],
        click_next='document.querySelector(".NextButton").click()',
        click_radio='document.querySelectorAll("input[type=radio]")[{idx}].click()',
        click_checkbox='document.querySelectorAll("input[type=checkbox]")[{idx}].click()',
        fill_textarea='(function(t){{var el=document.querySelector("textarea:not(.g-recaptcha-response)");el.value="{}";el.dispatchEvent(new Event("input",{{bubbles:true}}));el.dispatchEvent(new Event("change",{{bubbles:true}}));}})()'),
        fill_matrix='(function(r){{var rows=document.querySelectorAll("table.ChoiceStructure tbody tr");for(var i=0;i<rows.length;i++)rows[i].querySelectorAll("input[type=radio]")[r[i]].click();}})()',
        completion_text='Zurück zur Website',
    ),
    'tolunastart': ProviderPattern(
        name='tolunastart',
        url_patterns=['tolunastart.com', 'survey.toluna'],
        click_next='document.querySelector("button").click()',
        click_radio='(function(){{var rs=document.querySelectorAll(".cf-radio");rs[{idx}].click();}})()',
        click_checkbox='(function(){{var cbs=document.querySelectorAll(".cf-checkbox");[{idxs}].forEach(function(i){{cbs[i].click()}});}})()',
        fill_input='(function(){{var i=document.querySelector("input[type=number],input[type=text]");i.value="{}";i.dispatchEvent(new Event("input",{{bubbles:true}}));}})()',
        completion_text='Vielen Dank',
    ),
    # ... strat7, brand_ambassador, insights_today, purespectrum
}

def detect_provider(url):
    for name, pattern in PROVIDERS.items():
        for up in pattern.url_patterns:
            if up in url:
                return name, pattern
    return 'unknown', None
```

## Answer Engine

```python
class AnswerEngine:
    def __init__(self, ws_url, provider_pattern):
        self.ws = ws_url
        self.pp = provider_pattern
    
    def answer_radio(self, index):
        js = self.pp.click_radio.format(idx=index)
        return eval_via_ws(self.ws, js)
    
    def answer_checkbox(self, indices):
        js = self.pp.click_checkbox.format(idxs=','.join(map(str, indices)))
        return eval_via_ws(self.ws, js)
    
    def click_next(self):
        return eval_via_ws(self.ws, self.pp.click_next)
    
    def fill_textarea(self, text):
        js = self.pp.fill_textarea.format(text)
        return eval_via_ws(self.ws, js)
    
    def fill_matrix(self, ratings):
        js = self.pp.fill_matrix.format(str(ratings))
        return eval_via_ws(self.ws, js)
```

## Full Run

```python
def run_survey(survey_id, persona, dashboard_ws_url, port=9999):
    """Complete a survey from API start to completion."""
    s = SurveyCDP(port)
    
    # 1. Get URL from API
    url = get_survey_url(survey_id)
    
    # 2. Create new tab
    tab_id = s.create_target(dashboard_ws_url, url)
    time.sleep(5)  # wait for redirect
    
    # 3. Get tab WebSocket
    tab_ws = s.get_tab_ws(tab_id)
    
    # 4. Detect provider
    current_url = s.get_tab_url(tab_id)
    provider_name, pattern = detect_provider(current_url)
    
    # 5. Answer loop
    engine = AnswerEngine(tab_ws, pattern)
    for i in range(50):  # max 50 questions
        text = s.eval(tab_ws, 'document.body.innerText.substring(0,500)')
        
        # Check completion
        if pattern.completion_text in text:
            break
        
        # Try demographics first
        engine.fill_demographics(persona)
        
        # Try generic answer
        engine.answer_radio(0)  # first option
        engine.click_next()
        time.sleep(2)
    
    # 6. Rate survey
    rate_survey(s, tab_id)
    
    return {"status": "ok", "earned": balance_after - balance_before}
```

## Implementation Steps

| Step | File | Time |
|------|------|------|
| 1 | `survey_cdp.py` — CDP WebSocket Manager | 1h |
| 2 | `provider_patterns.py` — Pattern definitions | 1h |
| 3 | Answer Engine — Radio/Checkbox/Textarea/Matrix | 1.5h |
| 4 | Full flow runner + Completion detection | 1h |
| 5 | Demographics auto-fill | 30min |
| 6 | Integration test (Qualtrics HUK) | 30min |
| 7 | Integration test (TolunaStart) | 30min |

**Total: ~5-6h**
