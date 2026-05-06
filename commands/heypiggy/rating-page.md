# HeyPiggy Survey Rating Page (2026-05-06)

## ⚠️ CRITICAL: ALWAYS RATE AFTER SURVEY

**Every heypiggy/CPX survey ends with a rating page. WITHOUT rating, you lose the +0.01€ bonus.**

## Status
**VERIFIED** — +0.01€ bonus earned on TolunaStart survey

## How It Works
After survey completion, heypiggy redirects to:
```
offers.cpx-research.com/rating.php?app_id=11644&subid_1=...
```

This appears as a NEW TAB in Chrome (separate from survey tab).

## Page Structure
```
+0.09 EUR      ← survey reward credited
+0.01 EUR?     ← rating bonus (you earn this!)

Diese Umfrage bewerten

[★ ★ ★ ★ ☆]   ← 4 stars pre-selected
[Submit btn]   ← click to submit
```

## Detection
```python
# Find rating tab
for p in pages:
    if 'offers.cpx-research.com' in p.get('url','') or 'rating.php' in p.get('url',''):
        ws_url = p.get('webSocketDebuggerUrl')
        break

# Or check page content
ws.send(json.dumps({'id': 0, 'method': 'Runtime.evaluate', 'params': {'expression': 'document.body.innerText'}}))
# → Contains "Diese Umfrage bewerten" and "+0.XX EUR"
```

## Element Positions (TolunaStart survey)
| Element | X | Y | Note |
|---------|---|---|------|
| Rating button | 1019 | 181 | "Diese Umfrage bewerten" |
| Star 4 (selected) | 648 | 556 | pre-selected |
| Submit | 600 | 723 | btn-blue |

## Verified Command
```python
# Rating page → click the rating/submit button
ws.send(json.dumps({'id': 0, 'method': 'Input.dispatchMouseEvent', 'params': {'type':'mousePressed','x':1019,'y':181,'button':'left','clickCount':1}}))
json.loads(ws.recv())
ws.send(json.dumps({'id': 1, 'method': 'Input.dispatchMouseEvent', 'params': {'type':'mouseReleased','x':1019,'y':181,'button':'left'}}))
json.loads(ws.recv())

# Or JS click on button
ws.send(json.dumps({'id': 0, 'method': 'Runtime.evaluate', 'params': {'expression': 'document.querySelector("button").click()'}}))
```

## Result
After clicking submit:
```
Zurück zur Website   ← page shows this after successful rating
```

## Balance Impact
| Action | Amount |
|--------|--------|
| Survey completion | +0.09€ |
| Rating bonus | +0.01€ |
| **Total** | **+0.10€** |

## Survey Completion Flow
```
1. Survey tab → completes → redirects to rating.php
2. Rating tab opens (check window.TABS)
3. Click rating button → +0.01€ bonus
4. "Zurück zur Website" appears
5. Close rating tab → back to heypiggy dashboard
6. Verify balance increased
```

## Scripted Version
```python
def rate_survey(pages, ws_url):
    """Find and rate a completed survey"""
    import websocket, json

    # Find rating tab
    rating_url = None
    for p in pages:
        if 'rating.php' in p.get('url',''):
            rating_url = p.get('webSocketDebuggerUrl')
            break

    if not rating_url:
        return {'status': 'no_rating_page'}

    ws = websocket.create_connection(rating_url, timeout=10)

    # Check page content
    ws.send(json.dumps({'id': 0, 'method': 'Runtime.evaluate', 'params': {'expression': 'document.body.innerText'}}))
    r = json.loads(ws.recv())
    text = r.get('result',{}).get('result',{}).get('value','')

    if 'Diese Umfrage bewerten' not in text:
        ws.close()
        return {'status': 'not_rating_page', 'text': text[:200]}

    # Click the rating button (first button on page)
    ws.send(json.dumps({'id': 0, 'method': 'Runtime.evaluate', 'params': {'expression': '(function(){var btn=document.querySelector("button");if(btn)btn.click();})()'}}))
    json.loads(ws.recv())
    ws.close()

    return {'status': 'rated'}

def complete_survey_flow(pages):
    """Complete survey + rating + return to dashboard"""
    # 1. Complete survey in its tab
    # 2. Find rating tab
    rating_result = rate_survey(pages, ws_url)

    # 3. Close rating tab
    # ws.send(json.dumps({'id': 0, 'method': 'Target.closeTarget', 'params': {'targetId': rating_tab_id}}))

    # 4. Return to dashboard
    # ws.send(json.dumps({'id': 0, 'method': 'Target.createTarget', 'params': {'url': 'https://www.heypiggy.com/?page=dashboard'}}))

    return rating_result
```