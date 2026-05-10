# PureSpectrum Drag-Drop Puzzle — "Zahl X"

## Status
🔄 TESTING — 2026-05-10, Multi-Approach Solver deployed, awaiting E2E verification
- Previous fix (pointermove/pointerup on document.body) — FAILED E2E
- New solver: 4 sequential approaches (A→B→C→D)

## The Problem
- Angular CDK (ab v7) nutzt @HostListener('pointerdown/move/up') — NUR PointerEvents
- MouseEvents → von CDK ignoriert → Drag schlägt fehl
- Drag-Drop Puzzle erscheint bei ~66% Fortschritt
- "Bitte legen Sie die Zahl X in das leere Kästchen"
- 3 draggbare Bilder (06.png, 10.png, 52.png), 1 Drop-Zone (`.cdk-drop-list.drop-zone`)

## The Solution — NEW Multi-Approach Solver
```python
# stealth-captcha/src/stealth_captcha/solver/drag_drop_angular.py
# solve_drag_puzzle_new(ws_url) — 🔄 TESTING

# 4 approaches tried in order, stops at first success:
# A. Playwright raw mouse API (REAL browser-level pointer events)
# B. CDP Input.dispatchMouseEvent (native browser engine events)
# C. Multiple synthetic PointerEvents with delays + realistic properties
# D. HTML5 Drag-and-Drop + Direct DOM manipulation
```

### Approach A: Playwright Raw Mouse (PRIMARY)
```python
# Uses page.mouse.move()/down()/up() — REAL browser-level events
# NOT synthetic JS dispatchEvent — bypasses Angular CDK blocking
# 10 intermediate points with arc offset for realistic drag
mouse = page.mouse
await mouse.move(sx, sy)
await mouse.down()
for i in range(1, 11):
    await mouse.move(ix, iy)  # arc offset for realism
await mouse.move(ex, ey)
await mouse.up()
```

### Approach B: CDP Input.dispatchMouseEvent
```javascript
// Native browser engine mouse events (NOT synthetic JS)
// Chrome's native event loop processes these — may bypass Angular blocking
Input.dispatchMouseEvent({type: "mousePressed", x: sx, y: sy, button: "left"})
for (i=1..10): Input.dispatchMouseEvent({type: "mouseMoved", x: ix, y: iy})
Input.dispatchMouseEvent({type: "mouseReleased", x: ex, y: ey, button: "left"})
```

### Approach C: Synthetic PointerEvents (with improvements)
```javascript
// 10 intermediate pointermove events on document.body
// Realistic properties: pointerType, pressure, width, height, tiltX, tiltY
// Delays between events (0.1s) — more realistic timing
var pd = new PointerEvent('pointerdown', {...pointerType:'mouse', pressure:0.5, width:1, height:1, ...});
var pm = new PointerEvent('pointermove', {...clientX:ix, clientY:iy, buttons:1, ...}); // 10x
var pu = new PointerEvent('pointerup', {...clientX:ex, clientY:ey, button:0, ...});
dragImg.dispatchEvent(pd);
document.body.dispatchEvent(pm);  // 10 times
// NOTE: Still synthetic → may still be blocked by Angular CDK
dropZone.dispatchEvent(pu);
```

### Approach D: HTML5 Drag + DOM Manipulation (fallback)
```javascript
// HTML5 dragstart/dragover/drop/dragend events
// PLUS: Direct DOM appendChild to drop zone
// PLUS: Manually enable button and click
var dragEvent = new DragEvent('dragstart', {dataTransfer: new DataTransfer()});
dragImg.dispatchEvent(dragEvent);
dropZone.appendChild(dragContainer);  // Move element directly
btn.disabled = false;
btn.click();
```

## Critical Fixes (vs Previous Version)
1. **Selectors fixed**: `.cdk-drop-list` class (NOT `id="dropZoneList"`)
2. **Multiple intermediate points**: 10 steps with arc offset (realistic)
3. **Proper drop zone**: `dropZones[1]` (second `.cdk-drop-list`)
4. **Debug logging**: `DEBUG = True` prints every step

## Integration
```python
from drag_drop_angular import solve_drag_puzzle_new

result = solve_drag_puzzle_new(ws_url="ws://127.0.0.1:9999/devtools/page/...")
# result.status: "solved" | "failed" | "blocked"
# result.number: "52" (extracted from puzzle text)
# result.details: {approach: "A-playwright-mouse", hasImg: true, ...}
# result.debug_log: ["STEP 1...", "APPROACH A...", ...]
```

## Test Script
```bash
# Self-test (no Chrome needed)
cd stealth-captcha
python3 test_drag_drop_angular.py --self-test

# Live test (needs Chrome 9999 with purespectrum survey at 66%)
python3 test_drag_drop_angular.py --live --auto-discover
```

## Fails (NIEMALS verwenden)
- ❌ MouseEvents dispatchEvent → CDK ignoriert
- ❌ pointermove/pointerup auf img → CDK hört auf document.body
- ❌ __ngContext__ traversal → Production Build Index (Zahl), nicht Object
- ❌ window.ng.getComponent() → Debug-API nur im Dev-Mode
- ❌ `id="dropZoneList"` → falscher Selector, `.cdk-drop-list` nutzen!
- ❌ Nur 1 pointermove Event → braucht 10 Zwischenschritte für realistischen Drag

## Verification
```javascript
// Drop-Zone prüfen
var dropZones = document.querySelectorAll('.cdk-drop-list');
var targetZone = dropZones[1];
var hasImg = !!targetZone.querySelector('img');

// Next Button prüfen
var btn = document.querySelector('button');
var enabled = !btn.disabled;

// Puzzle gelöst wenn: hasImg=true ODER enabled=true
```

## History
- 2026-05-09: Initial solver (synthetic pointer events) → FAILED E2E
- 2026-05-10: Multi-approach solver deployed (A→B→C→D) → 🔄 AWAITING E2E VERIFICATION
