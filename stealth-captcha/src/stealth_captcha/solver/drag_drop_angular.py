"""AngularDragDropSolver — PureSpectrum "Zahl X" Angular CDK drag-drop puzzle.

PROBLEM (2026-05-09, 11 approaches failed):
  Angular CDK (ab v7) uses @HostListener('pointerdown') — NUR PointerEvents.
  Alle Browser-Automatisierungs-Tools senden MouseEvents:
  - CDP Input.dispatchMouseEvent → MouseEvents → CDK ignoriert
  - Playwright page.drag_and_drop() → MouseEvents → CDK ignoriert
  - DOM dispatchEvent(PointerEvent) → Synthetic → Angular blockiert
  - __ngContext__ traversal → Production Build speichert Index (Zahl), nicht Object
  - window.ng.getComponent() → Debug-API nur im Dev-Mode

LÖSUNG: Playwright's locator.dragTo() + browser-level drag automation.
  - page.locator().dragTo() uses different internal routing than drag_and_drop()
  - Falls das nicht reicht: Direct Playwright CDP session für PointerEvents

VERWENDUNG:
  solver = AngularDragDropSolver(ws_url=ws)
  result = solver.solve(number="52")  # "Zahl 52 in Kästchen"
"""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, field
from typing import Literal

VISION_MODEL = "meta/llama-3.2-11b-vision-instruct"
NIM_BASE_URL = "https://integrate.api.nvidia.com/v1"


@dataclass
class DragDropResult:
    status: Literal["solved", "failed", "blocked"]
    number: str | None = None
    error: str | None = None
    details: dict = field(default_factory=dict)


def solve_drag_puzzle_new(ws_url: str) -> DragDropResult:
    """Angular CDK drag-drop puzzle solver (sync wrapper).

    Tries in order:
    1. Playwright locator.dragTo() (best available method)
    2. CDP JS pointer simulation at browser-level
    3. Graceful fallback (blocks survey, doesn't crash)

    Args:
        ws_url: CDP WebSocket URL for the purespectrum survey tab.

    Returns:
        DragDropResult with status, number extracted, error details.
    """
    try:
        # Extract the target number from page text
        import websocket
        ws = websocket.create_connection(ws_url, timeout=10)
        ws.send(json.dumps({"id":0,"method":"Runtime.evaluate",
            "params":{"expression":"(function(){var t=document.body.innerText; var m=t.match(/Bitte legen Sie die Zahl (\\d+)/); return m ? m[1] : null;})()"}}))
        r = json.loads(ws.recv())
        number = r.get("result",{}).get("result",{}).get("value")
        ws.close()

        if not number:
            return DragDropResult(status="failed", error="No number found in puzzle text")

        # Verify drop zone and drag items exist
        ws2 = websocket.create_connection(ws_url, timeout=10)
        ws2.send(json.dumps({"id":0,"method":"Runtime.evaluate",
            "params":{"expression":"(function(){var dz=document.getElementById('dropZoneList'); var imgs=document.querySelectorAll('.cdk-drag img'); return JSON.stringify({dropzoneFound: !!dz, dragCount: imgs.length, numbers: Array.from(imgs).map(function(i){return i.getAttribute('alt');})});})()"}}))
        r2 = json.loads(ws2.recv())
        ws2.close()
        info = json.loads(r2.get("result",{}).get("result",{}).get("value","{}"))

        if not info.get("dropzoneFound"):
            return DragDropResult(status="failed", number=number, error="Drop zone not found")
        if number not in (info.get("numbers") or []):
            return DragDropResult(status="failed", number=number, error=f"Number {number} not in drag items: {info.get('numbers')}")

        # Try Playwright drag via subprocess (different mechanism than direct CDP)
        import subprocess
        result = subprocess.run(
            ["python3", "-c", f"""
import asyncio
import json

async def solve():
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp('http://127.0.0.1:9999')
        # Find the purespectrum page
        for ctx in browser.contexts:
            for page in ctx.pages:
                url = page.url
                if 'purespectrum' in url and 'survey_id' in url:
                    # Locate the number image and drop zone
                    alt_selector = 'img[alt="{number}"]'
                    drop_selector = '#dropZoneList'
                    try:
                        source = page.locator(alt_selector)
                        target = page.locator(drop_selector)
                        # dragTo uses different internal path than drag_and_drop
                        await source.drag_to(target, target_position={{"x": 75, "y": 75}})
                        await asyncio.sleep(2)
                        # Check if drop succeeded
                        inner = await page.inner_text('body')
                        if 'Bitte legen' not in inner or 'Zahl' not in inner.split('Bitte')[1]:
                            return True  # page advanced, puzzle solved
                        # Check button state
                        btn = page.locator('button:has-text("Nächste")')
                        btn_disabled = await btn.get_attribute('disabled')
                        return btn_disabled is None  # True if button not disabled = puzzle solved
                    except Exception as e:
                        return f"error: {{e}}"
        return False

result = asyncio.run(solve())
print(json.dumps({{"success": result}}))
"""],
            capture_output=True, text=True, timeout=30, cwd="/Users/jeremy/dev/stealth-runner"
        )

        output = result.stdout.strip()
        try:
            outcome = json.loads(output)
            if outcome.get("success") is True:
                return DragDropResult(
                    status="solved",
                    number=number,
                    details={"method": "playwright-locator-dragTo", "dragTarget": number}
                )
            elif isinstance(outcome.get("success"), str) and "error" in outcome["success"]:
                return DragDropResult(
                    status="failed",
                    number=number,
                    error=outcome["success"]
                )
        except:
            pass

        # Fallback: browser-level pointer event via CDP runtime
        # Try injecting pointer event via window.chrome debugging API
        ws3 = websocket.create_connection(ws_url, timeout=10)
        js_pointer = f"""
(function(){{
  var dragImg = document.querySelector('img[alt="{number}"]');
  var dropZone = document.getElementById('dropZoneList');
  if (!dragImg || !dropZone) return 'ELEMENTS_MISSING';

  var r1 = dragImg.getBoundingClientRect();
  var r2 = dropZone.getBoundingClientRect();
  var sx = r1.left + r1.width/2;
  var sy = r1.top + r1.height/2;
  var ex = r2.left + r2.width/2;
  var ey = r2.top + r2.height/2;

  // Try: use element.dispatchEvent with pointer events
  var pd = new PointerEvent('pointerdown', {{bubbles:true, cancelable:true, pointerId:1, isPrimary:true, clientX:sx, clientY:sy, button:0}});
  var pm = new PointerEvent('pointermove', {{bubbles:true, cancelable:true, pointerId:1, isPrimary:true, clientX:(sx+ex)/2, clientY:(sy+ey)/2, buttons:1}});
  var pu = new PointerEvent('pointerup', {{bubbles:true, cancelable:true, pointerId:1, isPrimary:true, clientX:ex, clientY:ey, button:0}});

  dragImg.dispatchEvent(pd);
  return 'POINTER_EVENTS_DISPATCHED:' + sx + ',' + sy + '->' + ex + ',' + ey;
}})()
"""
        ws3.send(json.dumps({"id":0,"method":"Runtime.evaluate",
            "params":{"expression": js_pointer, "returnByValue": True}}))
        r3 = json.loads(ws3.recv())
        ws3.close()
        dispatch_result = r3.get("result",{}).get("result",{}).get("value","")

        time.sleep(2)

        # Verify if drop worked
        ws4 = websocket.create_connection(ws_url, timeout=10)
        ws4.send(json.dumps({"id":0,"method":"Runtime.evaluate",
            "params":{"expression":"(function(){var dz=document.getElementById('dropZoneList'); var child=dz ? dz.querySelector('img') : null; var btn=document.querySelector('button'); var btnDis=btn?btn.disabled:null; return JSON.stringify({{dropzoneHasImg:!!child, imgAlt:child?child.getAttribute('alt'):null, buttonDisabled:btnDis, innerText:document.body.innerText.substring(0,200)}});})()"}}))
        r4 = json.loads(ws4.recv())
        ws4.close()
        verify = json.loads(r4.get("result",{}).get("result",{}).get("value","{}"))

        if verify.get("dropzoneHasImg"):
            return DragDropResult(
                status="solved",
                number=number,
                details={"method": "pointer-events", "dropzoneImg": verify.get("imgAlt")}
            )

        return DragDropResult(
            status="blocked",
            number=number,
            error=f"Drag puzzle UNSOLVED after all methods. Dispatch: {dispatch_result}. Verify: {verify}"
        )

    except Exception as e:
        return DragDropResult(status="failed", error=str(e)[:200])