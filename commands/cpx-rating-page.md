# CPX-RESEARCH Rating Page (2026-05-06)

## STATUS
- **VERIFIED** — +0.01€ bonus earned

## URL Pattern
```
offers.cpx-research.com/rating.php?app_id=11644&...
→ After survey completion, redirected to rating page
```

## Page Structure
```
+0.17 EUR guteschrieben
+0.01 EUR?     ← this is what you earn for rating!
Diese Umfrage bewerten

[★ ★ ★ ★ ☆]  ← star rating (4 stars pre-selected)
[Submit btn]  ← btn-blue input at center-bottom
```

## Elements Found
| Element | Class | Position | Action |
|---------|-------|----------|--------|
| Star 1 | star hover selected | 504,556 | already selected |
| Star 2 | star hover selected | 552,556 | already selected |
| Star 3 | star hover selected | 600,556 | already selected |
| Star 4 | star hover selected | 648,556 | already selected |
| Star 5 | star hover | 696,556 | not selected |
| Submit | btn-blue input | 600,723 | CLICK |

## ✅ VERIFIED COMMAND
```python
# Rating page → click submit button (4 stars already selected!)
ws_url = "webSocketDebuggerUrl from JSON"  # for tab with cpx-research

ws.send(json.dumps({'id': 0, 'method': 'Input.dispatchMouseEvent', 'params': {'type':'mousePressed','x':600,'y':723,'button':'left','clickCount':1}}))
ws.recv()
ws.send(json.dumps({'id': 1, 'method': 'Input.dispatchMouseEvent', 'params': {'type':'mouseReleased','x':600,'y':723,'button':'left'}}))
ws.recv()
```

## Detection
```python
# Find rating tab
for p in pages:
    if 'cpx-research' in p.get('url','').lower() or 'rating' in p.get('url','').lower():
        ws_url = p.get('webSocketDebuggerUrl', '')
        break

# Check for rating content
ws.send(json.dumps({'id': 0, 'method': 'Runtime.evaluate', 'params': {'expression': 'document.body.innerText'}}))
# → Contains "+0.17 EUR", "+0.01 EUR?", "Diese Umfrage bewerten"
```

## Result After Submit
```
Zurück zur Website  ← page title after successful rating
```

## Balance Impact
- Survey completion: +0.17€ credited
- Rating bonus: +0.01€ bonus
- Total earned today: ~1.27€