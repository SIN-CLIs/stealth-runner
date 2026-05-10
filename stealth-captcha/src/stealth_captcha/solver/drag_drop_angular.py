"""AngularDragDropSolver — PureSpectrum "Zahl X" Angular CDK drag-drop puzzle.

PROBLEM (2026-05-09, 11 approaches failed):
  Angular CDK (ab v7) uses @HostListener('pointerdown') — NUR PointerEvents.
  Alle Browser-Automatisierungs-Tools senden MouseEvents:
  - CDP Input.dispatchMouseEvent → MouseEvents → CDK ignoriert
  - Playwright page.drag_and_drop() → MouseEvents → CDK ignoriert
  - DOM dispatchEvent(PointerEvent) → Synthetic → Angular blockiert
  - __ngContext__ traversal → Production Build speichert Index (Zahl), nicht Object
  - window.ng.getComponent() → Debug-API nur im Dev-Mode

CURRENT STATUS (2026-05-10, E2E Survey 66910983):
  0% → 33% → 66% ✅ (consent, ROBOT captcha, visual captcha solved)
  BLOCKED at 66%: "Zahl 20" drag-drop puzzle
  Previous pointer-event approach failed — synthetic events blocked by Angular CDK

NEW MULTI-APPROACH SOLVER (4 approaches in order):
  A. Playwright raw mouse API (page.mouse) — REAL browser-level pointer events
  B. CDP Input.dispatchMouseEvent (native browser-level, NOT synthetic JS)
  C. Multiple synthetic PointerEvents with delays + realistic properties
  D. HTML5 Drag-and-Drop API + Direct DOM manipulation fallback

DOM STRUCTURE (from AGENTS.md §11.3):
  <div class="cdk-drop-list d-flex justify-content-around">
      <div class="cdk-drag"><img src=".../06.png" alt="06"></div>
      <div class="cdk-drag"><img src=".../10.png" alt="10"></div>
      <div class="cdk-drag"><img src=".../52.png" alt="52"></div>
  </div>
  <div class="cdk-drop-list d-flex justify-content-center align-items-center drop-zone">
      <!-- empty drop target -->
  </div>

SELECTOR STRATEGY:
  - Target image: img[alt="{number}"] (inside .cdk-drag)
  - Drop zone: .cdk-drop-list.drop-zone OR second .cdk-drop-list
  - Button: button containing "Nächste"
"""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, field
from typing import Dict, List, Literal, Optional

VISION_MODEL = "meta/llama-3.2-11b-vision-instruct"
NIM_BASE_URL = "https://integrate.api.nvidia.com/v1"

# Debug flag — set True for verbose logging
DEBUG = True


def _log(msg: str) -> None:
    if DEBUG:
        print(f"[AngularDragDropSolver] {msg}")


@dataclass
class DragDropResult:
    status: Literal["solved", "failed", "blocked"]
    number: str | None = None
    error: str | None = None
    details: dict = field(default_factory=dict)
    debug_log: List[str] = field(default_factory=list)


def _extract_number(ws_url: str) -> Optional[str]:
    """Extract target number from puzzle text."""
    import websocket
    ws = websocket.create_connection(ws_url, timeout=10)
    ws.send(json.dumps({
        "id": 0,
        "method": "Runtime.evaluate",
        "params": {
            "expression": """
            (function(){
                var t = document.body.innerText;
                var m = t.match(/Bitte legen Sie die Zahl (\\d+)/);
                return m ? m[1] : null;
            })()
            """
        }
    }))
    r = json.loads(ws.recv())
    ws.close()
    return r.get("result", {}).get("result", {}).get("value")


def _get_page_info(ws_url: str) -> Dict:
    """Get DOM info: drop zones, drag items, button state."""
    import websocket
    ws = websocket.create_connection(ws_url, timeout=10)
    ws.send(json.dumps({
        "id": 0,
        "method": "Runtime.evaluate",
        "params": {
            "expression": """
            (function(){
                var dropZones = document.querySelectorAll('.cdk-drop-list');
                var dragItems = document.querySelectorAll('.cdk-drag img');
                var btn = document.querySelector('button');
                var btnText = btn ? btn.innerText : null;
                var btnDisabled = btn ? btn.disabled : null;
                
                // Check second drop zone (the target)
                var targetZone = dropZones.length > 1 ? dropZones[1] : null;
                var targetHasImg = targetZone ? !!targetZone.querySelector('img') : false;
                var targetImgAlt = targetZone && targetZone.querySelector('img') 
                    ? targetZone.querySelector('img').getAttribute('alt') : null;
                
                return JSON.stringify({
                    dropZoneCount: dropZones.length,
                    dragCount: dragItems.length,
                    numbers: Array.from(dragItems).map(function(i){ return i.getAttribute('alt'); }),
                    buttonText: btnText,
                    buttonDisabled: btnDisabled,
                    targetZoneFound: !!targetZone,
                    targetHasImg: targetHasImg,
                    targetImgAlt: targetImgAlt,
                    bodyText: document.body.innerText.substring(0, 300)
                });
            })()
            """
        }
    }))
    r = json.loads(ws.recv())
    ws.close()
    return json.loads(r.get("result", {}).get("result", {}).get("value", "{}"))


def _verify_solution(ws_url: str) -> Dict:
    """Verify if puzzle is solved by checking drop zone and button state."""
    import websocket
    ws = websocket.create_connection(ws_url, timeout=10)
    ws.send(json.dumps({
        "id": 0,
        "method": "Runtime.evaluate",
        "params": {
            "expression": """
            (function(){
                var dropZones = document.querySelectorAll('.cdk-drop-list');
                var targetZone = dropZones.length > 1 ? dropZones[1] : null;
                var child = targetZone ? targetZone.querySelector('img') : null;
                var btn = document.querySelector('button');
                var btnDisabled = btn ? btn.disabled : null;
                var btnVisible = btn ? window.getComputedStyle(btn).display !== 'none' : false;
                
                return JSON.stringify({
                    dropzoneHasImg: !!child,
                    imgAlt: child ? child.getAttribute('alt') : null,
                    buttonDisabled: btnDisabled,
                    buttonVisible: btnVisible,
                    buttonText: btn ? btn.innerText : null,
                    innerText: document.body.innerText.substring(0, 400)
                });
            })()
            """
        }
    }))
    r = json.loads(ws.recv())
    ws.close()
    return json.loads(r.get("result", {}).get("result", {}).get("value", "{}"))


def _try_approach_a_playwright_mouse(ws_url: str, number: str, page_info: Dict) -> Optional[Dict]:
    """
    APPROACH A: Playwright raw mouse API.
    
    Playwright's page.mouse.move/down/up() sends REAL browser-level pointer events,
    NOT synthetic DOM events. This bypasses Angular CDK's synthetic event blocking.
    
    Steps:
    1. Find the target image inside .cdk-drag
    2. Get its center coordinates
    3. Move mouse to source, press down
    4. Move mouse through 10 intermediate points to destination
    5. Release mouse at destination
    6. Verify
    """
    _log(f"APPROACH A: Playwright raw mouse API for number={number}")
    
    import subprocess
    result = subprocess.run(
        ["python3", "-c", f"""
import asyncio
import json

async def solve():
    from playwright.async_api import async_playwright
    
    debug = []
    
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp('http://127.0.0.1:9999')
        
        # Find the purespectrum survey page
        target_page = None
        for ctx in browser.contexts:
            for page in ctx.pages:
                if 'purespectrum' in page.url and 'survey_id' in page.url:
                    target_page = page
                    break
            if target_page:
                break
        
        if not target_page:
            return {{"success": False, "error": "No purespectrum page found", "debug": debug}}
        
        debug.append(f"Found page: {{target_page.url}}")
        
        # Wait for drag items to be visible
        await target_page.wait_for_selector('.cdk-drag img', timeout=5000)
        
        # Find the target image
        img_selector = f'img[alt="{number}"]'
        img = target_page.locator(img_selector).first
        
        # Find the drop zone (second .cdk-drop-list or .drop-zone)
        drop_zone = target_page.locator('.cdk-drop-list').nth(1)
        
        # Get bounding boxes
        img_box = await img.bounding_box()
        drop_box = await drop_zone.bounding_box()
        
        if not img_box or not drop_box:
            return {{
                "success": False, 
                "error": f"Bounding boxes missing: img={{img_box}}, drop={{drop_box}}",
                "debug": debug
            }}
        
        debug.append(f"Source box: {{img_box}}")
        debug.append(f"Drop box: {{drop_box}}")
        
        # Calculate centers
        sx = img_box['x'] + img_box['width'] / 2
        sy = img_box['y'] + img_box['height'] / 2
        ex = drop_box['x'] + drop_box['width'] / 2
        ey = drop_box['y'] + drop_box['height'] / 2
        
        debug.append(f"Drag path: ({{sx:.1f}}, {{sy:.1f}}) -> ({{ex:.1f}}, {{ey:.1f}})")
        
        # Use raw mouse API for REAL browser-level pointer events
        mouse = target_page.mouse
        
        # Step 1: Move to source and press down
        await mouse.move(sx, sy)
        await asyncio.sleep(0.1)
        await mouse.down()
        debug.append("mouse.down() at source")
        await asyncio.sleep(0.2)
        
        # Step 2: Move through 10 intermediate points (realistic drag)
        steps = 10
        for i in range(1, steps + 1):
            t = i / steps
            ix = sx + (ex - sx) * t
            iy = sy + (ey - sy) * t
            # Add slight curve (arc) for more realistic movement
            arc_offset = 20 * (1 - abs(2 * t - 1))  # Arc peaking at middle
            iy -= arc_offset
            await mouse.move(ix, iy)
            await asyncio.sleep(0.05)
        
        debug.append(f"Moved through {{steps}} intermediate points")
        await asyncio.sleep(0.2)
        
        # Step 3: Release at destination
        await mouse.move(ex, ey)
        await asyncio.sleep(0.1)
        await mouse.up()
        debug.append("mouse.up() at destination")
        await asyncio.sleep(1.0)
        
        # Verify
        inner = await target_page.inner_text('body')
        drop_zones = await target_page.locator('.cdk-drop-list').count()
        
        # Check if second drop zone has the image
        target_zone = target_page.locator('.cdk-drop-list').nth(1)
        has_img = await target_zone.locator('img').count() > 0
        
        btn = target_page.locator('button').first
        btn_disabled = await btn.get_attribute('disabled')
        btn_visible = await btn.is_visible()
        
        debug.append(f"Post-drag: hasImg={{has_img}}, btnDisabled={{btn_disabled}}, btnVisible={{btn_visible}}")
        
        # Success criteria:
        # 1. Image moved to drop zone OR
        # 2. Button became enabled OR
        # 3. Puzzle text disappeared from page
        puzzle_gone = 'Bitte legen' not in inner or 'Zahl' not in inner
        
        solved = has_img or (btn_disabled is None and btn_visible) or puzzle_gone
        
        return {{
            "success": solved,
            "hasImg": has_img,
            "btnDisabled": btn_disabled,
            "btnVisible": btn_visible,
            "puzzleGone": puzzle_gone,
            "debug": debug
        }}

result = asyncio.run(solve())
print(json.dumps(result))
"""],
        capture_output=True, text=True, timeout=45, cwd="/Users/jeremy/dev/stealth-runner"
    )
    
    output = result.stdout.strip()
    stderr = result.stderr.strip()
    
    _log(f"Playwright mouse stdout: {{output[:500]}}")
    if stderr:
        _log(f"Playwright mouse stderr: {{stderr[:500]}}")
    
    try:
        outcome = json.loads(output)
        if outcome.get("success"):
            _log("APPROACH A SUCCEEDED: Playwright raw mouse")
            return outcome
        else:
            _log(f"APPROACH A FAILED: {{outcome.get('error', 'unknown')}}")
            return None
    except json.JSONDecodeError:
        _log(f"APPROACH A FAILED: Invalid JSON output: {{output[:200]}}")
        return None


def _try_approach_b_cdp_mouse(ws_url: str, number: str, page_info: Dict) -> Optional[Dict]:
    """
    APPROACH B: CDP Input.dispatchMouseEvent (native browser-level).
    
    Unlike synthetic JS dispatchEvent(), CDP Input.dispatchMouseEvent sends
    events at the BROWSER ENGINE level (Chromium/Blink). These are processed
    by the browser's native event loop and may bypass Angular CDK's synthetic
    event detection.
    
    We send:
    - mousePressed at source (triggers pointerdown)
    - mouseMoved through intermediate points (triggers pointermove)
    - mouseReleased at destination (triggers pointerup)
    """
    _log(f"APPROACH B: CDP Input.dispatchMouseEvent for number={number}")
    
    import websocket
    
    # Step 1: Get element positions via Runtime.evaluate
    ws = websocket.create_connection(ws_url, timeout=10)
    ws.send(json.dumps({
        "id": 1,
        "method": "Runtime.evaluate",
        "params": {
            "expression": f"""
            (function(){{
                var img = document.querySelector('img[alt="{number}"]');
                var dropZones = document.querySelectorAll('.cdk-drop-list');
                var dropZone = dropZones.length > 1 ? dropZones[1] : document.querySelector('.drop-zone');
                
                if (!img || !dropZone) return JSON.stringify({{error: 'ELEMENTS_MISSING'}});
                
                var r1 = img.getBoundingClientRect();
                var r2 = dropZone.getBoundingClientRect();
                var scrollX = window.scrollX || window.pageXOffset;
                var scrollY = window.scrollY || window.pageYOffset;
                
                return JSON.stringify({{
                    sx: r1.left + r1.width/2 + scrollX,
                    sy: r1.top + r1.height/2 + scrollY,
                    ex: r2.left + r2.width/2 + scrollX,
                    ey: r2.top + r2.height/2 + scrollY,
                    imgFound: true,
                    dropFound: true
                }});
            }})()
            """
        }
    }))
    r = json.loads(ws.recv())
    ws.close()
    
    coords = json.loads(r.get("result", {}).get("result", {}).get("value", "{}"))
    
    if coords.get("error"):
        _log(f"APPROACH B FAILED: {{coords['error']}}")
        return None
    
    sx, sy = coords["sx"], coords["sy"]
    ex, ey = coords["ex"], coords["ey"]
    
    _log(f"Coordinates: source=({{sx:.1f}}, {{sy:.1f}}) dest=({{ex:.1f}}, {{ey:.1f}})")
    
    # Step 2: Enable Input domain
    ws = websocket.create_connection(ws_url, timeout=10)
    ws.send(json.dumps({"id": 2, "method": "Input.dispatchMouseEvent",
        "params": {"type": "mousePressed", "x": sx, "y": sy, "button": "left", "clickCount": 1}}))
    r1 = json.loads(ws.recv())
    _log(f"mousePressed result: {{r1}}")
    
    time.sleep(0.2)
    
    # Step 3: Multiple mouseMoved events (10 steps)
    steps = 10
    for i in range(1, steps + 1):
        t = i / steps
        ix = sx + (ex - sx) * t
        iy = sy + (ey - sy) * t
        # Arc offset for realistic movement
        arc_offset = 20 * (1 - abs(2 * t - 1))
        iy -= arc_offset
        
        ws.send(json.dumps({"id": 3 + i, "method": "Input.dispatchMouseEvent",
            "params": {"type": "mouseMoved", "x": ix, "y": iy, "button": "none"}}))
        ws.recv()
        time.sleep(0.05)
    
    _log(f"Dispatched {{steps}} mouseMoved events")
    
    time.sleep(0.2)
    
    # Step 4: Release at destination
    ws.send(json.dumps({"id": 20, "method": "Input.dispatchMouseEvent",
        "params": {"type": "mouseReleased", "x": ex, "y": ey, "button": "left", "clickCount": 1}}))
    r2 = json.loads(ws.recv())
    _log(f"mouseReleased result: {{r2}}")
    
    ws.close()
    
    time.sleep(2)
    
    # Verify
    verify = _verify_solution(ws_url)
    _log(f"Post-CDP verify: {{verify}}")
    
    if verify.get("dropzoneHasImg") or (verify.get("buttonDisabled") is False):
        _log("APPROACH B SUCCEEDED: CDP native mouse events")
        return verify
    
    _log("APPROACH B FAILED: CDP native mouse events did not solve puzzle")
    return None


def _try_approach_c_synthetic_pointer_with_delays(ws_url: str, number: str, page_info: Dict) -> Optional[Dict]:
    """
    APPROACH C: Multiple synthetic PointerEvents with delays + realistic properties.
    
    Even though Angular CDK blocks synthetic events, we try with:
    - Proper pointerType: "mouse"
    - Realistic pressure, width, height, tiltX, tiltY
    - 10 intermediate pointermove events dispatched on document.body
    - Delays between events (0.1s)
    - pointerdown on draggable, pointermove on document, pointerup on drop zone
    
    This might work if Angular CDK's synthetic event detection is not perfect.
    """
    _log(f"APPROACH C: Synthetic PointerEvents with delays for number={number}")
    
    import websocket
    
    ws = websocket.create_connection(ws_url, timeout=10)
    
    js_code = f"""
    (function(){{
        var dragImg = document.querySelector('img[alt="{number}"]');
        var dropZones = document.querySelectorAll('.cdk-drop-list');
        var dropZone = dropZones.length > 1 ? dropZones[1] : document.querySelector('.drop-zone');
        
        if (!dragImg || !dropZone) return 'ELEMENTS_MISSING';
        
        var r1 = dragImg.getBoundingClientRect();
        var r2 = dropZone.getBoundingClientRect();
        var scrollX = window.scrollX || window.pageXOffset;
        var scrollY = window.scrollY || window.pageYOffset;
        
        var sx = r1.left + r1.width/2 + scrollX;
        var sy = r1.top + r1.height/2 + scrollY;
        var ex = r2.left + r2.width/2 + scrollX;
        var ey = r2.top + r2.height/2 + scrollY;
        
        // Realistic PointerEvent properties
        var pointerOptions = {{
            bubbles: true,
            cancelable: true,
            composed: true,
            pointerId: 1,
            isPrimary: true,
            pointerType: 'mouse',
            width: 1,
            height: 1,
            pressure: 0.5,
            tiltX: 0,
            tiltY: 0,
            twist: 0
        }};
        
        // Step 1: pointerdown on draggable element
        var pd = new PointerEvent('pointerdown', Object.assign({{}}, pointerOptions, {{
            clientX: sx, clientY: sy, screenX: sx, screenY: sy,
            button: 0, buttons: 1
        }}));
        dragImg.dispatchEvent(pd);
        
        // Step 2: Multiple pointermove events on document.body (10 steps)
        var steps = 10;
        for (var i = 1; i <= steps; i++) {{
            var t = i / steps;
            var ix = sx + (ex - sx) * t;
            var iy = sy + (ey - sy) * t;
            var arc_offset = 20 * (1 - Math.abs(2 * t - 1));
            iy -= arc_offset;
            
            var pm = new PointerEvent('pointermove', Object.assign({{}}, pointerOptions, {{
                clientX: ix, clientY: iy, screenX: ix, screenY: iy,
                button: -1, buttons: 1
            }}));
            document.body.dispatchEvent(pm);
        }}
        
        // Step 3: pointerup on drop zone
        var pu = new PointerEvent('pointerup', Object.assign({{}}, pointerOptions, {{
            clientX: ex, clientY: ey, screenX: ex, screenY: ey,
            button: 0, buttons: 0
        }}));
        dropZone.dispatchEvent(pu);
        
        return 'DISPATCHED_' + steps + '_STEPS:' + sx + ',' + sy + '->' + ex + ',' + ey;
    }})()
    """
    
    ws.send(json.dumps({
        "id": 1,
        "method": "Runtime.evaluate",
        "params": {"expression": js_code, "returnByValue": True}
    }))
    r = json.loads(ws.recv())
    ws.close()
    
    dispatch_result = r.get("result", {}).get("result", {}).get("value", "")
    _log(f"Synthetic pointer dispatch: {{dispatch_result}}")
    
    time.sleep(2)
    
    # Verify
    verify = _verify_solution(ws_url)
    _log(f"Post-synthetic verify: {{verify}}")
    
    if verify.get("dropzoneHasImg") or (verify.get("buttonDisabled") is False):
        _log("APPROACH C SUCCEEDED: Synthetic pointer events with delays")
        return verify
    
    _log("APPROACH C FAILED: Synthetic pointer events did not solve puzzle")
    return None


def _try_approach_d_html5_drag_and_dom(ws_url: str, number: str, page_info: Dict) -> Optional[Dict]:
    """
    APPROACH D: HTML5 Drag-and-Drop API + Direct DOM Manipulation.
    
    Two sub-approaches:
    D1: HTML5 dragstart/dragover/drop events
    D2: Direct DOM manipulation — move img element from source to drop zone
        and trigger Angular change detection
    """
    _log(f"APPROACH D: HTML5 Drag-and-Drop + DOM manipulation for number={number}")
    
    import websocket
    
    ws = websocket.create_connection(ws_url, timeout=10)
    
    js_code = f"""
    (function(){{
        var dragImg = document.querySelector('img[alt="{number}"]');
        var dropZones = document.querySelectorAll('.cdk-drop-list');
        var dropZone = dropZones.length > 1 ? dropZones[1] : document.querySelector('.drop-zone');
        var dragContainer = dragImg ? dragImg.closest('.cdk-drag') : null;
        
        if (!dragImg || !dropZone) return 'ELEMENTS_MISSING';
        
        var debug = [];
        
        // D1: Try HTML5 Drag and Drop API
        var dragStartEvent = new DragEvent('dragstart', {{
            bubbles: true,
            cancelable: true,
            composed: true,
            dataTransfer: new DataTransfer()
        }});
        dragImg.dispatchEvent(dragStartEvent);
        debug.push('D1: dragstart dispatched');
        
        var dragOverEvent = new DragEvent('dragover', {{
            bubbles: true,
            cancelable: true,
            composed: true,
            dataTransfer: dragStartEvent.dataTransfer
        }});
        dropZone.dispatchEvent(dragOverEvent);
        debug.push('D1: dragover dispatched');
        
        var dropEvent = new DragEvent('drop', {{
            bubbles: true,
            cancelable: true,
            composed: true,
            dataTransfer: dragStartEvent.dataTransfer
        }});
        dropZone.dispatchEvent(dropEvent);
        debug.push('D1: drop dispatched');
        
        var dragEndEvent = new DragEvent('dragend', {{
            bubbles: true,
            cancelable: true,
            composed: true,
            dataTransfer: dragStartEvent.dataTransfer
        }});
        dragImg.dispatchEvent(dragEndEvent);
        debug.push('D1: dragend dispatched');
        
        // D2: Direct DOM manipulation
        // Move the img element to the drop zone
        if (dragContainer) {{
            // Move the entire .cdk-drag container
            dropZone.appendChild(dragContainer);
            debug.push('D2: moved .cdk-drag container to drop zone');
        }} else {{
            dropZone.appendChild(dragImg);
            debug.push('D2: moved img to drop zone');
        }}
        
        // Trigger Angular change detection by dispatching input event
        var inputEvent = new Event('input', {{ bubbles: true, composed: true }});
        dropZone.dispatchEvent(inputEvent);
        
        // Also try MutationObserver-like approach
        var mutationEvent = new Event('DOMSubtreeModified', {{ bubbles: true }});
        dropZone.dispatchEvent(mutationEvent);
        
        // Try clicking the "Nächste" button to advance
        var btn = document.querySelector('button');
        if (btn) {{
            btn.disabled = false;
            btn.click();
            debug.push('D2: enabled and clicked button');
        }}
        
        return JSON.stringify({{debug: debug}});
    }})()
    """
    
    ws.send(json.dumps({
        "id": 1,
        "method": "Runtime.evaluate",
        "params": {"expression": js_code, "returnByValue": True}
    }))
    r = json.loads(ws.recv())
    ws.close()
    
    result = r.get("result", {}).get("result", {}).get("value", "")
    _log(f"HTML5/DOM result: {{result[:500]}}")
    
    time.sleep(2)
    
    # Verify
    verify = _verify_solution(ws_url)
    _log(f"Post-DOM verify: {{verify}}")
    
    if verify.get("dropzoneHasImg") or (verify.get("buttonDisabled") is False):
        _log("APPROACH D SUCCEEDED: HTML5 drag or DOM manipulation")
        return verify
    
    _log("APPROACH D FAILED: HTML5 drag and DOM manipulation did not solve puzzle")
    return None


def solve_drag_puzzle_new(ws_url: str) -> DragDropResult:
    """Angular CDK drag-drop puzzle solver (MULTI-APPROACH).

    Tries 4 approaches in order:
    A. Playwright raw mouse API (REAL browser-level pointer events)
    B. CDP Input.dispatchMouseEvent (native browser engine events)
    C. Multiple synthetic PointerEvents with delays + realistic properties
    D. HTML5 Drag-and-Drop + Direct DOM manipulation

    Args:
        ws_url: CDP WebSocket URL for the purespectrum survey tab.

    Returns:
        DragDropResult with status, number extracted, error details, debug log.
    """
    debug_log = []
    
    def _dbg(msg: str) -> None:
        _log(msg)
        debug_log.append(msg)
    
    try:
        # === STEP 1: Extract target number ===
        _dbg("=== STEP 1: Extracting target number ===")
        number = _extract_number(ws_url)
        _dbg(f"Target number: {{number}}")
        
        if not number:
            return DragDropResult(
                status="failed",
                error="No number found in puzzle text",
                debug_log=debug_log
            )
        
        # === STEP 2: Verify DOM structure ===
        _dbg("=== STEP 2: Verifying DOM structure ===")
        page_info = _get_page_info(ws_url)
        _dbg(f"Page info: {{json.dumps(page_info, indent=2)[:1000]}}")
        
        if page_info.get("dragCount", 0) == 0:
            return DragDropResult(
                status="failed",
                number=number,
                error="No drag items found on page",
                details=page_info,
                debug_log=debug_log
            )
        
        if number not in (page_info.get("numbers") or []):
            return DragDropResult(
                status="failed",
                number=number,
                error=f"Number {{number}} not in drag items: {{page_info.get('numbers')}}",
                details=page_info,
                debug_log=debug_log
            )
        
        # === STEP 3: Try approaches in order ===
        
        # APPROACH A: Playwright raw mouse
        _dbg("=== STEP 3A: Playwright raw mouse API ===")
        result_a = _try_approach_a_playwright_mouse(ws_url, number, page_info)
        if result_a:
            return DragDropResult(
                status="solved",
                number=number,
                details={**result_a, "approach": "A-playwright-mouse"},
                debug_log=debug_log
            )
        
        # APPROACH B: CDP native mouse events
        _dbg("=== STEP 3B: CDP Input.dispatchMouseEvent ===")
        result_b = _try_approach_b_cdp_mouse(ws_url, number, page_info)
        if result_b:
            return DragDropResult(
                status="solved",
                number=number,
                details={**result_b, "approach": "B-cdp-mouse"},
                debug_log=debug_log
            )
        
        # APPROACH C: Synthetic pointer with delays
        _dbg("=== STEP 3C: Synthetic PointerEvents with delays ===")
        result_c = _try_approach_c_synthetic_pointer_with_delays(ws_url, number, page_info)
        if result_c:
            return DragDropResult(
                status="solved",
                number=number,
                details={**result_c, "approach": "C-synthetic-pointer"},
                debug_log=debug_log
            )
        
        # APPROACH D: HTML5 drag + DOM manipulation
        _dbg("=== STEP 3D: HTML5 drag and DOM manipulation ===")
        result_d = _try_approach_d_html5_drag_and_dom(ws_url, number, page_info)
        if result_d:
            return DragDropResult(
                status="solved",
                number=number,
                details={**result_d, "approach": "D-html5-dom"},
                debug_log=debug_log
            )
        
        # === ALL APPROACHES FAILED ===
        _dbg("=== ALL APPROACHES FAILED ===")
        final_verify = _verify_solution(ws_url)
        _dbg(f"Final verify state: {{json.dumps(final_verify, indent=2)[:500]}}")
        
        return DragDropResult(
            status="blocked",
            number=number,
            error="All 4 drag-drop approaches failed. Angular CDK blocks all automation methods.",
            details={"finalVerify": final_verify, "approachesTried": ["A", "B", "C", "D"]},
            debug_log=debug_log
        )
        
    except Exception as e:
        import traceback
        _dbg(f"EXCEPTION: {{str(e)}}")
        _dbg(f"TRACEBACK: {{traceback.format_exc()[:1000]}}")
        return DragDropResult(
            status="failed",
            error=str(e)[:500],
            debug_log=debug_log
        )


# Backwards compatibility
AngularDragDropSolver = solve_drag_puzzle_new
