# captcha-solve-slide.md — Slide-Captcha via cua-driver drag + AppleEvents JS ❌

## Status
**DEPRECATED** — 2026-05-06, cua-driver drag funktioniert NICHT für Chromium DOM-Content.
Siehe [captcha-solve-slide-cdp.md](captcha-solve-slide-cdp.md) für die funktionierende Lösung.

## ⚠️ WICHTIG: cua-driver drag Limitierung
cua-driver `drag` erzeugt CGEvent-Mausbewegungen (pid-routed backgrounded / cghidEventTap frontmost).
Diese Events werden von Chromium's sandboxed Renderer NICHT in DOM-MouseEvents übersetzt.
GoCaptcha's JS-Handler liest `e.clientX` aus DOM-MouseEvents — ohne diese bleibt das Puzzle-Teil stehen.

**Getestet und fehlgeschlagen:**
- ❌ cua-driver drag backgrounded (pid-routed) — Block+Tile unbewegt
- ❌ cua-driver drag frontmost (cghidEventTap) — Block+Tile unbewegt

**Funktionierende Alternative:**
- ✅ CDP `Input.dispatchMouseEvent` — erzeugt DOM-MouseEvents mit korrektem `clientX`
- ✅ Block: 0px → 218px, Tile: 11px → 236px
- Siehe [captcha-solve-slide-cdp.md](captcha-solve-slide-cdp.md)

## Altes Prinzip (DEPRECATED)
cua-driver `drag` postet CGEvent-Mausbewegungen. Diese erzeugen NICHT die benötigten DOM-MouseEvents in Chromium.

## Command (3 Schritte)

```bash
# 1. Captcha in Viewport scrollen (via AppleEvents JS)
python3 -c "
import subprocess, json
js = 'document.querySelector(\".go-captcha\").scrollIntoView({behavior:\"instant\",block:\"center\"})'
subprocess.run(['cua-driver','page',json.dumps({'pid':PID,'window_id':WID,'action':'execute_javascript','javascript':js})])
"

# 2. DOM-Koordinaten ermitteln → Window-Koordinaten konvertieren
python3 -c "
import subprocess, json
js = '''
const b=document.querySelector('.gc-drag-block'),s=document.querySelector('.gc-drag-slide-bar');
const br=b.getBoundingClientRect(),sr=s.getBoundingClientRect();
JSON.stringify({fx:br.left+br.width/2,fy:br.top+br.height/2,tx:sr.right-br.width/2-2,ty:sr.top+sr.height/2})
'''
r = subprocess.run(['cua-driver','page',json.dumps({'pid':PID,'window_id':WID,'action':'execute_javascript','javascript':js})],capture_output=True,text=True)
coords = json.loads(r.stdout.split('\`\`\`')[1])
from_x = 73 + coords['fx']  # 73 = AXWindow.x
from_y = 70 + coords['fy']  # 70 = AXWindow.y
to_x   = 73 + coords['tx']
to_y   = 70 + coords['ty']
"

# 3. Drag ausführen
echo '{"pid":PID,"from_x":from_x,"from_y":from_y,"to_x":to_x,"to_y":to_y,"speed":80,"steps":100}' | cua-driver call drag
```

## Live Example (GoCaptcha, 2026-05-05)
```bash
# BOT Chrome PID=47022, WID=57980
# 1. Scroll to captcha
# 2. DOM: block(446,571) slide(405,705) → window(519,641)→(735,641)
# 3. Drag
echo '{"pid":47022,"from_x":519,"from_y":641,"to_x":735,"to_y":641,"speed":80,"steps":100}' | cua-driver call drag
# → ✅ Block moved from 0px to slide end
# → isComplete: true
```

## Wichtige Erkenntnisse

| Faktor | Warum wichtig |
|--------|--------------|
| **Viewport** | Element MUSS sichtbar sein. scrollIntoView VOR drag! |
| **isTrusted** | dispatchEvent = false → abgelehnt. cua-driver drag = echte Events → true |
| **Koordinaten** | DOM-Koordinaten (viewport-relativ) → Window-Koordinaten (+AXWindow.x/y) |
| **AppleEvents JS** | Nur für scrollIntoView + DOM-Koordinaten. Drag selbst = cua-driver CGEvent |

## Voraussetzungen
- Chrome mit `allow_javascript_apple_events = true` (Preferences-Datei)
- Chrome-Neustart nach Pref-Änderung
- cua-driver Daemon läuft

## Zugehörige Commands
- [captcha-solve-slide-cdp.md](captcha-solve-slide-cdp.md) — ✅ FUNKTIONIEREND: GoCaptcha via CDP dispatchMouseEvent
- [captcha-solve-text.md](captcha-solve-text.md) — Text Captcha
- [captcha-solve-drag.md](captcha-solve-drag.md) — Drag & Drop Captcha
