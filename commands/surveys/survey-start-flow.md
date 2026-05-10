# Survey Start Flow — window.open interception + Cookie Timing Fix

## Status (2026-05-10)
✅ VERIFIED 2026-05-09 — Window.open interception opens survey tab (NOT Input.dispatchMouseEvent!)
❌ BANNED: `Input.dispatchMouseEvent` + fixed coords (600, 670) → FAIL, Chrome blocks window.open()
🔴 WARNING: `Target.createTarget()` opens NEW tab WITHOUT session cookies → Balance = €0

## Primary Method (PREFERRED): Survey in Dashboard Tab

**Why:** Dashboard Tab already has 7 HeyPiggy cookies injected. New tab via Target.createTarget() has NO cookies.

```python
# 1. Capture survey URL via window.open interception
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

# 2. Navigate in SAME dashboard tab (HAS COOKIES!)
ws.send(json.dumps({'id': 0, 'method': 'Page.navigate',
    'params': {'url': captured_survey_url}}))
```

**Problem:** Page.navigate in dashboard tab ALSO didn't fix the cookie timing issue.
E2E Test (2026-05-10): Survey 67078106 completed, balance unchanged €2.70 → €2.70.

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

## ⚠️ COOKIE TIMING WARNING (2026-05-10) — CRITICAL

**window.open interception + Target.createTarget öffnet Survey OHNE Session-Cookies.**

| Metric | Value |
|--------|-------|
| Survey completed | YES (Cint showed "Vielen Dank") |
| Balance before | €2.70 |
| Balance after | €2.70 |
| **Delta** | **€0.00** |

**Root Cause**: `Target.createTarget()` creates new tab → navigates to CPX URL immediately → cookies not yet injected. The entire redirect chain `CPX → Samplicio → Cint → Potloc` runs WITHOUT heypiggy session cookies. Completion tracking cannot associate the event with the correct user session → balance stays €0.

**Affected Code**: `survey-cli/survey/opener.py` → `_open_in_page_modal()` (line 141) calls `_find_new_tab_after_click()` which uses `Target.createTarget()`. Cookies are only injected into the DASHBOARD tab first, then new tab is created WITHOUT cookies.

**Fix Needed**:
1. **PREFERRED**: Open survey in SAME dashboard tab (which already has cookies) — use `Page.navigate()` instead of new tab
2. **ALTERNATIVE**: Inject cookies INTO new tab BEFORE `Page.navigate()` (requires CDP injection into new tab WS first)
3. See `issues.md` → SR-50 for full analysis

**Test Evidence** (2026-05-10, survey 67078106):
- window.open interception captured: `https://click.cpx-research.com/?k=...` ✅
- `Target.createTarget()` created new tab with CPX URL ✅
- Survey flow: 15 pages (Samplicio → Cint) → Completion "Vielen Dank" ✅
- Balance unchanged: €2.70 → €2.70 ❌

## History
- 2026-05-06: Created (Input.dispatchMouseEvent method)
- 2026-05-09: REWRITTEN — window.open interception discovered, Input.dispatchMouseEvent = BANNED
- 2026-05-10: ADDED WARNING — Target.createTarget opens survey WITHOUT session cookies, balance = €0
- 2026-05-10: Page.navigate in dashboard tab ATTEMPTED — FAILED, balance still €0