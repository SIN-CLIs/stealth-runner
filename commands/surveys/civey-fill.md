# Civey Survey Fill (VERIFIED 2026-05-06)

## Provider
Civey (int-widget.civey.com) — React SPA

## Welcome Page Fields
- Geschlecht: Männlich/Weiblich (radio buttons)
- Geburtsjahr: input[type=number] at @424,481
- PLZ: input[type=text] at @424,561
- Weiter: button at @424,617

## Fill + Submit Script
```python
import json, websocket, urllib.request, time

PORT = 9999
pages = json.loads(urllib.request.urlopen(f'http://127.0.0.1:{PORT}/json').read())
survey_ws = None
for p in pages:
    if 'civey' in p.get('url','').lower():
        survey_ws = p.get('webSocketDebuggerUrl', '')

# 1. Click "Männlich" label
ws = websocket.create_connection(survey_ws, timeout=8)
ws.send(json.dumps({'id': 0, 'method': 'Runtime.evaluate', 'params': {'expression': '(function(){var all=document.querySelectorAll("label, span, div");for(var i=0;i<all.length;i++){var t=all[i].textContent.trim();if(t==="Männlich"){all[i].click();return "CLICKED:"+t;}}return "NIX";})()'}}))
json.loads(ws.recv())
ws.close()

time.sleep(1)

# 2. Click year input + type 1993
ws2 = websocket.create_connection(survey_ws, timeout=8)
ws2.send(json.dumps({'id': 0, 'method': 'Input.dispatchMouseEvent', 'params': {'type':'mousePressed','x':500,'y':490,'button':'left','clickCount':1}}))
ws2.recv()
ws2.send(json.dumps({'id': 1, 'method': 'Input.dispatchMouseEvent', 'params': {'type':'mouseReleased','x':500,'y':490,'button':'left'}}))
ws2.recv()
ws2.close()
time.sleep(0.5)

ws3 = websocket.create_connection(survey_ws, timeout=8)
ws3.send(json.dumps({'id': 0, 'method': 'Runtime.evaluate', 'params': {'expression': '(function(){var inp=document.activeElement;if(inp&&inp.tagName==="INPUT"){inp.select();inp.value="1993";inp.dispatchEvent(new KeyboardEvent("input",{bubbles:true,cancelable:true,data:"1993"}));inp.dispatchEvent(new KeyboardEvent("change",{bubbles:true,cancelable:true}));return "TYPED:"+inp.value;}return "NIX";})()'}}))
json.loads(ws3.recv())
ws3.close()

time.sleep(0.5)

# 3. Click PLZ input + type 10785
ws4 = websocket.create_connection(survey_ws, timeout=8)
ws4.send(json.dumps({'id': 0, 'method': 'Input.dispatchMouseEvent', 'params': {'type':'mousePressed','x':500,'y':570,'button':'left','clickCount':1}}))
ws4.recv()
ws4.send(json.dumps({'id': 1, 'method': 'Input.dispatchMouseEvent', 'params': {'type':'mouseReleased','x':500,'y':570,'button':'left'}}))
ws4.recv()
ws4.close()
time.sleep(0.5)

ws5 = websocket.create_connection(survey_ws, timeout=8)
ws5.send(json.dumps({'id': 0, 'method': 'Runtime.evaluate', 'params': {'expression': '(function(){var inp=document.activeElement;if(inp&&inp.tagName==="INPUT"){inp.select();inp.value="10785";inp.dispatchEvent(new KeyboardEvent("input",{bubbles:true,cancelable:true,data:"10785"}));inp.dispatchEvent(new KeyboardEvent("change",{bubbles:true,cancelable:true}));return "TYPED:"+inp.value;}return "NIX";})()'}}))
json.loads(ws5.recv())
ws5.close()

time.sleep(1)

# 4. Click Weiter
ws6 = websocket.create_connection(survey_ws, timeout=8)
ws6.send(json.dumps({'id': 0, 'method': 'Input.dispatchMouseEvent', 'params': {'type':'mousePressed','x':500,'y':626,'button':'left','clickCount':1}}))
ws6.recv()
ws6.send(json.dumps({'id': 1, 'method': 'Input.dispatchMouseEvent', 'params': {'type':'mouseReleased','x':500,'y':626,'button':'left'}}))
ws6.recv()
ws6.close()

time.sleep(4)

# 5. Check next page
ws7 = websocket.create_connection(survey_ws, timeout=8)
ws7.send(json.dumps({'id': 0, 'method': 'Runtime.evaluate', 'params': {'expression': 'document.body.innerText.substring(0,500)'}}))
r = json.loads(ws7.recv())
ws7.close()
print(r.get('result',{}).get('result',{}).get('value','NIX')[:400])
```

## Find Input Positions
```python
ws.send(json.dumps({'id': 0, 'method': 'Runtime.evaluate', 'params': {'expression': '(function(){var inputs=document.querySelectorAll("input");for(var i=0;i<inputs.length;i++){var r=inputs[i].getBoundingClientRect();if(r.width>0)return i+":INPUT type:"+inputs[i].type+" @"+Math.round(r.left)+","+Math.round(r.top);}return "NIX";})()'}}))
```

## Status
⚠️ WORKING — Values set but page doesn't advance (React validation issue). Needs investigation.