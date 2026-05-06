# Survey Start Flow (VERIFIED 2026-05-06)

## Dashboard to Survey Tab

### Step 1: Click survey card
```python
ws.send(json.dumps({'id': 0, 'method': 'Runtime.evaluate', 'params': {'expression': '(function(){var s=document.querySelectorAll(".survey-item");if(s.length>0){var r=s[0].getBoundingClientRect();s[0].click();return "CLICKED:"+Math.round(r.left)+","+Math.round(r.top);}return "NIX";})()'}}))
```

### Step 2: Click "Umfrage starten" button via MouseEvent
```python
ws.send(json.dumps({'id': 0, 'method': 'Input.dispatchMouseEvent', 'params': {'type':'mousePressed','x':600,'y':670,'button':'left','clickCount':1}}))
ws.recv()
ws.send(json.dumps({'id': 1, 'method': 'Input.dispatchMouseEvent', 'params': {'type':'mouseReleased','x':600,'y':670,'button':'left'}}))
ws.recv()
```

### Step 3: Check for new survey tab
```bash
curl -s http://127.0.0.1:9999/json | python3 -c "import sys,json;d=json.load(sys.stdin);[print(p.get('id','')[:20],'|',p.get('url','')[:70]) for p in d]"
```

## Find survey tab
```python
pages = json.loads(urllib.request.urlopen(f'http://127.0.0.1:{PORT}/json').read())
for p in pages:
    if 'heypiggy' not in p.get('url',''):
        survey_ws = p.get('webSocketDebuggerUrl', '')
```

## Status
✅ VERIFIED — Survey opens in new tab after clicking "Umfrage starten" modal button.