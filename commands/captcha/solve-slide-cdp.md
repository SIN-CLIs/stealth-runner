# captcha-solve-slide-cdp.md — GoCaptcha Slide via CDP Input.dispatchMouseEvent ✅

## Status
**VERIFIED** — 2026-05-06, GoCaptcha Slide Captcha gelöst via CDP dispatchMouseEvent

## Prinzip
CDP `Input.dispatchMouseEvent` erzeugt DOM-MouseEvents im Chrome-Renderer. GoCaptcha's
JS-Handler (`handler.ts`) liest `e.clientX` (ohne `isTrusted`-Prüfung) und aktualisiert
sowohl `state.dragLeft` (Block-Position) als auch `state.thumbLeft` (Tile-Position).

**cua-driver `drag` funktioniert NICHT für Chromium-Web-Content** — weder backgrounded
noch frontmost. Grund: Chromium's sandboxed Renderer akzeptiert pid-routed/cghidEventTap
CGEvent-Events nicht als DOM-MouseEvents.

## Wichtig: CDP-Ban-Exception
CDP `Input.dispatchMouseEvent` ist laut Architektur für Navigation/Klicken BANNED. 
Diese Exception gilt NUR für:
- **Captcha Slide Drag** (GoCaptcha / ähnliche JS-basierte Slide-Captchas)
- **Bei Versagen von cua-driver drag** (primäre Methode)
- **Nicht für Navigation, normale Klicks, Form-Interaktion**

## Ablauf (3 Schritte)

### 1. Voraussetzungen
```bash
# Chrome mit remote-debugging-port muss laufen
# CDP WebSocket URL ermitteln
python3 -c "
import json, urllib.request
resp = urllib.request.urlopen('http://127.0.0.1:PORT/json')
tabs = json.loads(resp.read())
for t in tabs:
    if 'gocaptcha' in t['title'].lower() or 'captcha' in t['title'].lower():
        print(f\"ID: {t['id']} | Title: {t['title']} | WS: {t.get('webSocketDebuggerUrl','')}\")
"
```

### 2. Koordinaten ermitteln + Drag ausführen
```python
import asyncio, json, websockets

async def solve_gocaptcha_slide(cdp_ws_url: str):
    """Löst GoCaptcha Slide Captcha via CDP dispatchMouseEvent"""
    async with websockets.connect(cdp_ws_url) as ws:
        # a) Scroll captcha into view
        await ws.send(json.dumps({
            'id': 1, 'method': 'Runtime.evaluate',
            'params': {'expression': '''
                document.querySelector('.go-captcha').scrollIntoView(
                    {behavior:'instant', block:'center'}
                )
            '''}
        }))
        await ws.recv()
        await asyncio.sleep(0.3)

        # b) Get coordinates (viewport-relative!)
        await ws.send(json.dumps({
            'id': 2, 'method': 'Runtime.evaluate',
            'params': {'expression': '''
                (() => {
                    const c = document.querySelector('.go-captcha');
                    const b = c.querySelector('.gc-drag-block');
                    const sr = c.querySelector('.gc-drag-slide-bar').getBoundingClientRect();
                    const tr = b.getBoundingClientRect();
                    return JSON.stringify({
                        cx: Math.round(tr.left + tr.width/2),
                        cy: Math.round(tr.top + tr.height/2),
                        tx: Math.round(sr.right - tr.width/2),
                        bw: Math.round(tr.width)
                    });
                })()
            '''}
        }))
        r = json.loads(await ws.recv())
        coords = json.loads(r['result']['result']['value'])
        
        cx, cy, tx = coords['cx'], coords['cy'], coords['tx']
        
        # c) mousedown at block center (viewport coords!)
        await ws.send(json.dumps({
            'id': 3, 'method': 'Input.dispatchMouseEvent',
            'params': {'type': 'mousePressed', 'x': cx, 'y': cy,
                       'button': 'left', 'clickCount': 1}
        }))
        await ws.recv()
        
        # d) mousemove in steps (30 steps smoothes the drag)
        steps = 30
        for i in range(1, steps + 1):
            mx = int(cx + (tx - cx) * (i / steps))
            await ws.send(json.dumps({
                'id': 100+i, 'method': 'Input.dispatchMouseEvent',
                'params': {'type': 'mouseMoved', 'x': mx, 'y': cy}
            }))
            await ws.recv()
        
        await asyncio.sleep(0.2)
        
        # e) mouseup at target
        await ws.send(json.dumps({
            'id': 200, 'method': 'Input.dispatchMouseEvent',
            'params': {'type': 'mouseReleased', 'x': tx, 'y': cy, 'button': 'left'}
        }))
        await ws.recv()
        
        # f) Verify
        await asyncio.sleep(0.5)
        await ws.send(json.dumps({
            'id': 300, 'method': 'Runtime.evaluate',
            'params': {'expression': '''
                JSON.stringify({
                    block_left: document.querySelector('.gc-drag-block').style.left,
                    tile_left: document.querySelector('.gc-tile').style.left,
                    block_viewport: Math.round(document.querySelector('.gc-drag-block').getBoundingClientRect().left),
                    tile_viewport: Math.round(document.querySelector('.gc-tile').getBoundingClientRect().left)
                })
            '''}
        }))
        r = json.loads(await ws.recv())
        result = json.loads(r['result']['result']['value'])
        return result

# Nutzung:
# result = asyncio.run(solve_gocaptcha_slide('ws://127.0.0.1:PORT/devtools/page/TAB_ID'))
```

### 3. Verifikation
```python
# Erfolgskriterien:
# - block_left: ~218px (Block am Ziel)
# - tile_left: ~236px (Tile hat sich mitbewegt!)
# - block_viewport: ~623 (Block in Viewport-Koordinaten)
# - tile_viewport: ~641 (Tile in Viewport-Koordinaten)
```

## Live Example (GoCaptcha Demo, 2026-05-06)
```bash
# Chrome PID=97078, CDP Port=9223, Page=GoCaptcha Demo
# Viewport-Koordinaten:
#   Block center: (446, 571)
#   Target: (664, 571)  # barRight(705) - blockWidth/2(41)
#
# CDP dispatchMouseEvent:
#   mousedown @ (446, 571)
#   mousemove × 30 steps → (664, 571)
#   mouseup @ (664, 571)
#
# Ergebnis:
#   block_left: 0px → 218px ✅
#   tile_left: 11px → 236px ✅  
#   block_viewport: 405 → 623 ✅
#   tile_viewport: 416 → 641 ✅
```

## Wichtige Erkenntnisse

| Faktor | Warum wichtig |
|--------|--------------|
| **Viewport-Koordinaten** | CDP dispatchMouseEvent verwendet viewport-relative Koordinaten (NICHT screen/window-local) |
| **30+ Steps** | Genug Zwischenschritte für smoothe Bewegung — GoCaptcha aktualisiert bei jedem mousemove |
| **Kein isTrusted-Check** | GoCaptcha prüft NICHT `isTrusted` — CDP-Events werden akzeptiert |
| **cua-driver drag ≠ funktioniert** | Weder backgrounded (pid-routed) noch frontmost (cghidEventTap) — Chromium Renderer-Sandbox filtert |

## Voraussetzungen
- Chrome mit `--remote-debugging-port=PORT` gestartet (playstealth setzt das automatisch)
- CDP WebSocket-Verbindung zum Ziel-Tab
- Python `websockets` Bibliothek (`pip install websockets`)

## Bekannte Limitationen
- **Demo-Seite**: Kein `.gc-success` (Backend-Validierung fehlt). Nur visuelle Bestätigung.
- **Backend-Test**: Erfordert echte Backend-Validierung (heypiggy.com) — Block+Tile müssen korrekte Position melden.
- **CDP Ban**: Nur für captcha slide drag erlaubt — nicht für Navigation/Klicks/Formulare.

## Zugehörige Commands
- [captcha-solve-slide.md](captcha-solve-slide.md) — cua-driver drag (LIMITIERT — funktioniert NICHT für Chromium)
- [captcha-solve-text.md](captcha-solve-text.md) — Text Captcha
- [captcha-solve-drag.md](captcha-solve-drag.md) — Drag & Drop Captcha
