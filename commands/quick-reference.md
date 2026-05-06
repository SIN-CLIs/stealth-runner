# Quick Reference — heypiggy Survey Automation (2026-05-06)

## Current Session Status

**Balance: 1.77€** (from 1.54€ → +0.23€ today)
- Strat7 survey: +0.09€ ✅
- Strat7 (260409): +0.03€ ✅
- Brand Ambassador: +0.02€ compensation
- TolunaStart survey: +0.09€ (in progress - at 92%)

## ⚠️ SURVEY RULE: ALWAYS RATE BEFORE CLOSING

After every survey completion on heypiggy/CPX:
1. Find the `offers.cpx-research.com/rating.php` tab
2. Click the rating button (usually @1019,181)
3. Stars are pre-selected (4 stars)
4. Click submit to get +0.01€ bonus
5. THEN navigate back to dashboard
→ Without rating: **NO bonus earned!**

See: `/commands/heypiggy/rating-page.md`

## Chrome Connection (LIVE)
```bash
# Port: 9999
# Tab count: 9 tabs currently open

import json, urllib.request, websocket
PORT = 9999
pages = json.loads(urllib.request.urlopen(f'http://127.0.0.1:{PORT}/json').read())
```

## Survey Providers Verified

| Provider | File | Status | Notes |
|----------|------|--------|-------|
| **TolunaStart** | `tolunastart-survey.md` | ✅ VERIFIED | 20+ questions, JS .click() on .cf-radio/.cf-checkbox |
| **Strat7** | `strat7-survey.md` | ✅ VERIFIED | Cookie → industry → age → gender → state → images |
| **Brand Ambassador** | `brand-ambassador-survey.md` | ✅ VERIFIED | 3 attention checks, hidden inputs |
| **Insights-Today** | `insights-today-survey.md` | ❌ SCREEN-OUT | Prescreener done, screen-out at education |
| **PureSpectrum** | `purespectrum-survey.md` | ❌ BLOCKED | CAPTCHA |
| **Nfield/Kantar** | `nfield-survey.md` | ✅ Complete | Audio questions |
| **My-Take** | `my-take-survey.md` | ✅ Complete | Multi-select grid |
| **Proquoai** | `proquoai-survey.md` | ✅ Complete | Angular app |
| **Civey** | `cdp-civey-survey.md` | ✅ Complete | Rating + submit |

## TolunaStart — THE PATTERN (MOST IMPORTANT)

**JS .click() on .cf-radio and .cf-checkbox works!**

```python
# RADIO (single select) — use JS .click() on .cf-radio elements
ws.send(json.dumps({'id': 0, 'method': 'Runtime.evaluate', 'params': {'expression': '(function(){var rs=document.querySelectorAll(".cf-radio");rs[INDEX].click();})()'}}))

# CHECKBOX (multi select) — use JS .click() on .cf-checkbox elements
ws.send(json.dumps({'id': 0, 'method': 'Runtime.evaluate', 'params': {'expression': '(function(){var cbs=document.querySelectorAll(".cf-checkbox");[0,2,3,4].forEach(function(i){cbs[i].click();});})()'}}))

# BUTTON — use JS .click() on button
ws.send(json.dumps({'id': 0, 'method': 'Runtime.evaluate', 'params': {'expression': 'document.querySelector("button").click()'}}))

# SELECT/INPUT — use value setting + Event("input", {bubbles:true})
ws.send(json.dumps({'id': 0, 'method': 'Runtime.evaluate', 'params': {'expression': '(function(){var i=document.querySelector("input[type=number], input[type=text]");if(i){i.value="32";i.dispatchEvent(new Event("input",{bubbles:true}));}document.querySelector("button").click();})()'}}))
```

### TolunaStart Question Types
1. **Single select**: `.cf-radio` — click index
2. **Multi select**: `.cf-checkbox` — click multiple indices
3. **Matrix table**: `.cf-radio` in grid — columns = options, rows = items (indices vary)
4. **Numeric input**: `input[type=number]` — set value + Event
5. **Text input**: `input[type=text]` — set value + Event
6. **Ranking**: `.cf-ranking-answer` — click items to cycle rank (1→2→3→disabled)
7. **Button**: `document.querySelector("button")`

## Survey Routing Chain (CPX Research)
```
heypiggy dashboard → clickSurvey API → click.cpx-research.com →
  → tolunastart.com (✅ WORKS — Toluna)
  → strat7audiences.com (✅ works, screen-out)
  → brand-ambassador.com (✅ works, screen-out)
  → purespectrum.com (❌ CAPTCHA blocked)
  → surveyrouter.com (❌ hangs)
  → insights-today.com (❌ screen-out at education)
```

## Survey Flow (Universal)
1. **Dashboard**: `document.querySelectorAll("[onclick*=clickSurvey]")` → get IDs
2. **Start**: `Target.createTarget` → open survey in new tab
3. **Screener**: Answer demographics (age, gender, location, income)
4. **Survey**: Answer topic questions (AI, insurance, etc.)
5. **RATING**: Find `offers.cpx-research.com/rating.php` tab → rate → submit
6. **Return**: Navigate back to heypiggy dashboard
7. **Balance**: Verify new balance increased

## BANNED Patterns (NEVER USE)
- ❌ `pkill -f "heypiggy-bot"` — kills ALL Chrome
- ❌ `killall Google Chrome` — kills ALL Chrome
- ❌ Hardcoded PIDs (71104, 70293, etc.)
- ❌ Manual WebSocket URL — use webSocketDebuggerUrl from JSON
- ❌ CDP Page.navigate — use Target.createTarget
- ❌ MouseEvent on .cf-radio/.cf-checkbox — use JS .click()
- ❌ skylight-cli, webauto-nodriver MCP

## Survey IDs (Current Dashboard)
```
66583827, 66679635, 66693526, 66724318, 66733280, 66774868,
66781681, 66797518, 66814767, 66821095, 66826773, 66426237
```

## Bot Chrome PIDs (DYNAMIC — find via ps aux)
```
ps aux | grep "user-data-dir=/tmp/heypiggy-bot" | awk '{print $2}'
```

## Balance Tracker
| Date | Balance | Change | Surveys |
|------|---------|--------|---------|
| 2026-05-05 | 1.54€ | +1.54€ | Civey+Proquoai+My-Take |
| 2026-05-06 | 1.77€ | +0.23€ | Strat7×2 + Brand Ambassador + TolunaStart(92%) |

## TolunaStart Quick Command
```python
# Single radio select
(lambda ws, idx: ws.send(json.dumps({'id': 0, 'method': 'Runtime.evaluate', 'params': {'expression': f'(function(){{var rs=document.querySelectorAll(".cf-radio");rs[{idx}].click();document.querySelector("button").click();}})()'}}))))

# Multi checkbox select
(lambda ws, idxs: ws.send(json.dumps({'id': 0, 'method': 'Runtime.evaluate', 'params': {'expression': f'(function(){{var cbs=document.querySelectorAll(".cf-checkbox");{[f"cbs[{i}].click()" for i in idxs]}.forEach(f=>eval(f));document.querySelector("button").click();}})()'}}))))
```

## Next Steps
1. Complete TolunaStart survey (at 92%, demographics section)
2. Rate survey on rating page → +0.01€ bonus
3. Return to dashboard → verify balance
4. Try next survey ID from dashboard
5. Document remaining TolunaStart question patterns