# Chrome CDP Start (VERIFIED 2026-05-06)

## Command
```bash
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  --user-data-dir="/tmp/heypiggy-new-$(date +%s)" \
  --remote-debugging-port=9999 \
  --remote-allow-origins="*" \
  --force-renderer-accessibility \
  "https://www.heypiggy.com/?page=dashboard"
```

## What it does
Starts Chrome with CDP debug port. KEY: `--remote-allow-origins="*"` (quotes matter!)

## Get Browser ID
```bash
curl -s http://127.0.0.1:9999/json | python3 -c "import sys,json;d=json.load(sys.stdin);print(d[0].get('id',''))"
```

## Connect Python
```python
import json, websocket, urllib.request
pages = json.loads(urllib.request.urlopen(f'http://127.0.0.1:{PORT}/json').read())
ws_url = pages[0]['webSocketDebuggerUrl']  # use this directly!
ws = websocket.create_connection(ws_url, timeout=8)
ws.send(json.dumps({'id': 0, 'method': 'Runtime.evaluate', 'params': {'expression': js}}))
r = json.loads(ws.recv())
ws.close()
print(r.get('result',{}).get('result',{}).get('value','NIX'))
```

## Status
✅ VERIFIED — Works after reboot. CDP WS connects fine.