"""================================================================================
DRAG-DROP-PUZZLE SOLVER für PureSpectrum (Angular CDK Drag-Drop)

================================================================================
MODUL-KONZEPT (Operator-Dokumentation, NICHT in separate .md auslagern!)
================================================================================

Dieses Modul löst PureSpectrum-spezifische Drag-Drop-Puzzles (z.B. "Zahl 28")
über echte Browser-Level-Mouse-Events (Chrome DevTools Protocol Input.dispatchMouseEvent).

WARUM ECHTE MOUSE-EVENTS?
  Angular CDK (Material Design Library) reagiert NUR auf echte Browser-Events,
  nicht auf synthetische PointerEvents, die vom JavaScript generiert werden.

ARCHITEKTUR (3 Phasen):
  1. DETECT: DOM-Scan findet .cdk-drag + .drop-zone + zielzahl-Bild
  2. COMPUTE: Bezier-Pfad von Source zu Target
  3. EXECUTE: CDP Input.dispatchMouseEvent (mousePressed → mouseMoved × n → mouseReleased)

SUPPORTED PROVIDERS:
  ✅ PureSpectrum — "Bitte legen Sie die Zahl X"
  ❌ Qualtrics / Toluna — kein Standard-Angular-CDK

Module Status: PRODUCTION (SR-68, 2026-05-11)
"""

from __future__ import annotations
import json, asyncio, random, websocket
from typing import Optional

__frozen__ = True
__version__ = "2026-05-11"


def _extract_target_number(ws_url: str) -> Optional[str]:
    """Extract 'Zahl X' from DOM text."""
    js = ("var m=(document.body.innerText||'').match(/Bitte legen Sie die Zahl (\\d+)/i);"
          "return m?m[1]:null;")
    try:
        ws = websocket.create_connection(ws_url, timeout=10)
        ws.send(json.dumps({"id": 0, "method": "Runtime.evaluate", "params": {"expression": js}}))
        r = json.loads(ws.recv()); ws.close()
        return r.get("result", {}).get("result", {}).get("value")
    except Exception:
        return None


def _detect_puzzle_dom(ws_url: str) -> dict:
    """Detect .cdk-drag + .drop-zone + button state."""
    js = (
        "(function(){var c=document.querySelectorAll('.cdk-drag').length;"
        "var z=document.querySelector('.drop-zone,[class*=drop-zone]');"
        "var b=null;document.querySelectorAll('button').forEach(function(btn){"
        "var t=(btn.innerText||'').trim();if((t.includes('Nächste')||t.includes('Weiter'))&&!btn.disabled)"
        "b={text:t,enabled:true};});return{drag_count:c,drop_zone_exists:!!z,button:b};})()"
    )
    try:
        ws = websocket.create_connection(ws_url, timeout=10)
        ws.send(json.dumps({"id": 0, "method": "Runtime.evaluate", "params": {"expression": js}}))
        r = json.loads(ws.recv()); ws.close()
        return r.get("result", {}).get("result", {}).get("value", {})
    except Exception:
        return {}


def _cdp_dispatch_mouse(ws_url: str, event_type: str, x: float, y: float, button: str = "left"):
    """Dispatch single mouse event via CDP."""
    try:
        ws = websocket.create_connection(ws_url, timeout=10)
        ws.send(json.dumps({"id": 0, "method": "Input.dispatchMouseEvent",
                           "params": {"type": event_type, "x": x, "y": y, "button": button,
                                     "clickCount": 1, "pointerType": "mouse"}}))
        _ = json.loads(ws.recv()); ws.close()
    except Exception as e:
        raise RuntimeError(f"CDP dispatch failed: {e}")


async def _compute_bezier_path(ws_url: str, number: str) -> Optional[dict]:
    """Compute source + target positions."""
    js = (f"(function(){{var img=document.querySelector('img[alt=\"{number}\"]');"
          f"var zone=document.querySelector('.drop-zone,[class*=drop-zone]')||"
          f"document.querySelectorAll('.cdk-drop-list')[0];if(!img||!zone)return null;"
          f"var ir=img.getBoundingClientRect();var zr=zone.getBoundingClientRect();"
          f"return{{source_x:ir.left+ir.width/2,source_y:ir.top+ir.height/2,"
          f"target_x:zr.left+zr.width/2,target_y:zr.top+zr.height/2}};"
          f"}})()")
    try:
        ws = websocket.create_connection(ws_url, timeout=10)
        ws.send(json.dumps({"id": 0, "method": "Runtime.evaluate", "params": {"expression": js}}))
        r = json.loads(ws.recv()); ws.close()
        return r.get("result", {}).get("result", {}).get("value")
    except Exception:
        return None


async def _execute_drag_sequence(ws_url: str, sx: float, sy: float, ex: float, ey: float) -> bool:
    """Execute drag sequence: mousePressed → mouseMoved × 10 → mouseReleased."""
    try:
        _cdp_dispatch_mouse(ws_url, "mousePressed", sx, sy)
        await asyncio.sleep(0.05)
        for i in range(1, 11):
            t = i / 10.0
            px = sx + (ex - sx) * t
            py = sy + (ey - sy) * t - 20 * (1 - abs(2 * t - 1)) + random.uniform(-1, 1)
            _cdp_dispatch_mouse(ws_url, "mouseMoved", px, py)
            await asyncio.sleep(0.03)
        _cdp_dispatch_mouse(ws_url, "mouseReleased", ex, ey)
        await asyncio.sleep(0.5)
        return True
    except Exception:
        return False


async def _click_next_button(ws_url: str) -> bool:
    """Find + click 'Nächste' or 'Weiter' button."""
    js = ("(function(){var bs=document.querySelectorAll('button');"
          "for(var i=0;i<bs.length;i++){var t=(bs[i].innerText||'').trim();"
          "if((t.includes('Nächste')||t.includes('Weiter'))&&!bs[i].disabled){bs[i].click();return true;}}"
          "return false;})()")
    try:
        ws = websocket.create_connection(ws_url, timeout=10)
        ws.send(json.dumps({"id": 0, "method": "Runtime.evaluate", "params": {"expression": js}}))
        r = json.loads(ws.recv()); ws.close()
        return r.get("result", {}).get("result", {}).get("value", False)
    except Exception:
        return False


def solve_puzzle(ws_url: str, number: Optional[str] = None) -> dict:
    """Solve PureSpectrum drag-drop puzzle via real mouse events.
    
    Args:
        ws_url: CDP WebSocket URL
        number: Optional target number (auto-detect if None)
    
    Returns:
        dict: {"status": "ok"|"error"|"skipped", "number": "...", "button_clicked": bool,
               "source": (x, y), "target": (x, y), "reason": "..."}
    
    Module-Docs: siehe top-of-file (Operator-Workflow, Failure-Modes, etc)
    """
    puzzle_info = _detect_puzzle_dom(ws_url)
    if not puzzle_info.get("drag_count"):
        return {"status": "skipped", "reason": "no_puzzle", "number": None, "button_clicked": False}

    target = number or _extract_target_number(ws_url)
    if not target:
        return {"status": "error", "reason": "no_number", "number": None, "button_clicked": False}

    positions = asyncio.run(_compute_bezier_path(ws_url, target))
    if not positions:
        return {"status": "error", "reason": "no_positions", "number": target, "button_clicked": False}

    sx, sy, ex, ey = positions["source_x"], positions["source_y"], positions["target_x"], positions["target_y"]
    success = asyncio.run(_execute_drag_sequence(ws_url, sx, sy, ex, ey))
    if not success:
        return {"status": "error", "reason": "drag_execution_failed", "number": target,
                "button_clicked": False, "source": (round(sx, 1), round(sy, 1)),
                "target": (round(ex, 1), round(ey, 1))}

    button_clicked = asyncio.run(_click_next_button(ws_url))
    return {"status": "ok", "number": target, "button_clicked": button_clicked,
            "source": (round(sx, 1), round(sy, 1)), "target": (round(ex, 1), round(ey, 1))}


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: drag_drop_solver.py <ws_url> [number]")
        sys.exit(1)
    ws_url = sys.argv[1]
    number = sys.argv[2] if len(sys.argv) > 2 else None
    result = solve_puzzle(ws_url, number)
    print(json.dumps(result, indent=2))
