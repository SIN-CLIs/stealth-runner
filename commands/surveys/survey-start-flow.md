# Survey Start Flow — window.open interception + Target.createTarget

## Status
✅ VERIFIED 2026-05-09 — Window.open interception opens survey tab (NOT Input.dispatchMouseEvent!)
❌ BANNED: `Input.dispatchMouseEvent` + fixed coords (600, 670) → FAIL, Chrome blocks window.open()

## Dashboard to Survey Tab (KORREKT)

### Step 1: Click survey card
```python
# clickSurvey('ID') opens modal on dashboard
ws.send(json.dumps({'id': 0, 'method': 'Runtime.evaluate',
    'params': {'expression': "clickSurvey('67064749')"}}))
```

### Step 2: window.open interception → Target.createTarget
```python
# "Umfrage starten" button hat onclick="openSurvey()"
# openSurvey() nutzt window.open(url) → Chrome Popup Blocker!
# Lösung: window.open abfangen + Target.createTarget

# window.open abfangen → URL capture
ws.send(json.dumps({'id': 0, 'method': 'Runtime.evaluate',
    'params': {'expression': '''
(function() {
  var surveyURL = null;
  var origOpen = window.open.bind(window);
  window.open = function(url) { surveyURL = url; return null; }
  try { openSurvey(); } catch(e) {}
  window.open = origOpen;
  return surveyURL;
})()
'''}}))

# Target.createTarget öffnet URL (KEIN Popup Blocker!)
ws.send(json.dumps({'id': 0, 'method': 'Target.createTarget',
    'params': {'url': captured_survey_url}}))
```

### Step 3: Find survey tab
```bash
curl -s http://127.0.0.1:9999/json | python3 -c "
import sys,json
d=json.load(sys.stdin)
for p in d:
    url = p.get('url','')
    if 'heypiggy' not in url and url.startswith('http'):
        print(p.get('id')[:20], '|', url[:70])
"
```

## Warum Input.dispatchMouseEvent nicht funktioniert

- `Input.dispatchMouseEvent({x:600, y:670})` klickt an Koordinaten (Maus-Simulation)
- Button ist sichtbar, Klick registered
- ABER: onclick="openSurvey()" wird NICHT ausgelöst (Chrome Popup Blocker)
- `window.open()` ist das Problem, nicht der Klick selbst
- Target.createTarget ist Browser-Intern → kein Blocker

## Tool (survey-cli/tools/tool_open_survey.py)
```python
from tools.tool_open_survey import open_survey
result = open_survey("66929608", pid=0, wid=0, port=9999)
# → {"status": "ok", "tab_id": "...", "ws_url": "...", "provider": "cint", "flow": "modal_window_open_intercept"}
```

## Test Results (2026-05-09)
- Survey 67064749 → purespectrum tab opened ✅
- Survey 66929608 → cint tab opened (fallback, no modal) ✅
- Survey 66995119 → cint tab opened (fallback, no modal) ✅

## History
- 2026-05-06: Created (Input.dispatchMouseEvent method)
- 2026-05-09: REWRITTEN — window.open interception discovered, Input.dispatchMouseEvent = BANNED