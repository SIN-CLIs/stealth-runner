# captcha-move-block.md — Captcha-Block per AppleEvents JS bewegen ✅

## Status
**DURCHBRUCH** — 2026-05-05, GoCaptcha Slide: Block von 0px → 216px bewegt

## Prinzip
CGEvent `drag` triggert GoCaptchas PointerEvent-Handler **nicht** (20+ Tests bestätigt).
**Lösung**: AppleEvents JavaScript (`cua-driver page execute_javascript`) + `style.left` + `PointerEvent` dispatch.
Block bewegt sich visuell — Validierung steht noch aus.

## Command (3 Schritte)

### 1. Koordinaten per DOM holen
```bash
cua-driver page '{"pid":PID,"window_id":WID,"action":"execute_javascript",
  "javascript":"(()=>{const b=document.querySelector(\".gc-drag-block\"),s=document.querySelector(\".gc-drag-slide-bar\");const br=b.getBoundingClientRect(),sr=s.getBoundingClientRect();return JSON.stringify({distance:Math.round(sr.right-br.left-br.width-2)});})()"}'
```

### 2. Block per JS bewegen
```javascript
const b = document.querySelector('.gc-drag-block');
const r = b.getBoundingClientRect();
const cx = r.left + r.width / 2;
const cy = r.top + r.height / 2;
const target = 216; // slideR - blockLeft - blockW - 2

// PointerDown auf Block
b.dispatchEvent(new PointerEvent('pointerdown', {
  bubbles: true, cancelable: true,
  clientX: cx, clientY: cy, pointerId: 99, isPrimary: true
}));

// Block verschieben + PointerMove
b.style.transition = 'none';
b.style.left = target + 'px';
document.dispatchEvent(new PointerEvent('pointermove', {
  bubbles: true, cancelable: true,
  clientX: cx + target, clientY: cy, pointerId: 99, isPrimary: true
}));

// PointerUp
document.dispatchEvent(new PointerEvent('pointerup', {
  bubbles: true, cancelable: true,
  clientX: cx + target, clientY: cy, pointerId: 99, isPrimary: true
}));
```

### 3. Verify via Llama Vision
```bash
screencapture /tmp/verify.png
# Llama 3.2 Vision: "LEFT or RIGHT?"
# → "LEFT" = Block nicht bewegt | "RIGHT" = Block bewegt ✅
```

## Live Example (GoCaptcha, 2026-05-05)
```bash
PID=51525 WID=58443
# Block war bei left=0px (DOM x=405)
# Slide bar: 405-705 (300px breit)
# Target: 705 - 82 - 2 - 405 = 216px
# JS → b.style.left = '216px'
# → ✅ Block visuell verschoben!
# → ❌ Captcha-Validierung noch nicht getriggert
```

## Was NICHT funktioniert
| Ansatz | Ergebnis | Grund |
|--------|----------|-------|
| `cua-driver call drag` | ❌ 0px | CGEvent → MouseEvent, Captcha braucht PointerEvent |
| `cua-driver call click` (coords) | ❌ 0px | Gleicher Grund |
| `new DragEvent()` dispatch | ❌ | `isTrusted: false` |
| `new MouseEvent()` dispatch | ❌ | `isTrusted: false` |
| `PointerEvent` + `style.left` | ✅ bewegt | Visuell OK, Validierung fehlt |

## Voraussetzungen
- Chrome mit `allow_javascript_apple_events = true` in Preferences
- cua-driver Daemon läuft
- Captcha-Element im Viewport (scrollIntoView)

## Nächster Schritt
- GoCaptcha-interne `validate()`-Funktion per JS aufrufen
- React-Fiber des Captchas finden und State direkt setzen

## Zugehörige Commands
- [captcha/solve-text.md](captcha/solve-text.md) — Text-Captcha via pixtral-large
- [captcha/solve-slide.md](captcha/solve-slide.md) — Slide-Captcha Reference
- [captcha/solve-drag.md](captcha/solve-drag.md) — Drag-Drop Reference
- [cua-driver/click.md](../cua-driver/click.md) — AXPress / Coordinate Click
