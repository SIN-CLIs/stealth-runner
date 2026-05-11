"""================================================================================
DEPRECATED 2026-05-11 — Wird ersetzt durch die kanonische v2-Pipeline.
================================================================================

Dieser Tool-Pfad ist LEGACY. Er bleibt nur fuer Backward-Compat bestehender
Integrationen erhalten. NEUER Code MUSS gegen die folgenden Endpoints
programmieren:

    POST /v2/scan         → ersetzt /survey/snapshot, /survey/scan
    POST /v2/click        → ersetzt /survey/click, /survey/click-angular
    POST /v2/fill         → ersetzt /survey/fill-input
    POST /v2/press_key    → neu
    POST /v2/captcha/*    → ersetzt /survey/solve-captcha,
                            /survey/solve-drag-puzzle

Die Implementierungen leben in:
    survey-cli/survey/cdp_universal.py      Universal Scanner (AX-Tree pierce)
    survey-cli/survey/cdp_actuator.py       Maus-Events + Pflicht-Verify
    survey-cli/survey/captcha_router.py     Detection + Solver-Routing
    agent-toolbox/api/endpoints/universal.py FastAPI-Endpoints unter /v2/*

WARUM DIESER TOOL-PFAD STIRBT:
  - Y-Sort-Reihenfolge → instabile @eN-Indizes bei Reflow
  - el.click() / .value = "..." → von React/Angular ignoriert
  - Keine Pflicht-Verify nach Aktion → Halluzinationen "Performed without effect"
  - Provider-spezifisches JS hardcoded → jeder neue Provider = Patch
  - walkShadows(depth>5) → tieferes Shadow-DOM unsichtbar
  - iframes nur gezaehlt, nie betreten

Migration-Path fuer dieses Modul:
  → Wrap die alte API auf /v2/*. Wenn das alte Tool z.B. (selector) erwartet,
    intern via /v2/scan einen Match auf attrs.id / name finden und dessen
    stable_id an /v2/click weitergeben. So bleibt die externe API stabil.

LIES BEVOR DU DIESES MODUL AENDERST: AGENTS.md Sektion
"KANONISCHE ARCHITEKTUR (2026-05-11)".
================================================================================
"""

"""TOOL: solve_drag_puzzle — Angular CDK Drag-Drop (PureSpectrum "Zahl X")

UNDER 300 LINES. APPROACH B (PRIMARY): CDP Input.dispatchMouseEvent chain.
NOT synthetic PointerEvents — Angular CDK ignores synthetic events!

VERIFIED: Survey 49517969 (Zahl 28) → 100% ✅
PROBLEM: __ngContext__ is Number (not Object) in Angular Ivy Production Build.

STATUS: __frozen__=True | Version: 2026-05-11

BANNED: ❌ dispatchEvent(PointerEvent) | ❌ __ngContext__ traversal | ❌ window.ng
        ❌ playstealth | ❌ webauto-nodriver | ❌ hardcoded PIDs | ❌ pkill Chrome
"""

from __future__ import annotations
import json, asyncio, random, websocket
from typing import Optional

__frozen__ = True
__version__ = "2026-05-11"


def _extract_number(ws_url: str) -> Optional[str]:
    js = "var m=(document.body.innerText||'').match(/Bitte legen Sie die Zahl (\\d+)/);return m?m[1]:null;"
    try:
        ws = websocket.create_connection(ws_url, timeout=10)
        ws.send(json.dumps({"id": 0, "method": "Runtime.evaluate", "params": {"expression": js}}))
        r = json.loads(ws.recv()); ws.close()
        return r.get("result", {}).get("result", {}).get("value")
    except Exception:
        return None


def _get_page_info(ws_url: str) -> dict:
    js = """(function(){
    var imgs=document.querySelectorAll('.cdk-drag img,[class*=cdk-drag] img');
    var numbers=[];imgs.forEach(function(i){var a=i.getAttribute('alt');if(a&&/^\\d+$/.test(a))numbers.push(a);});
    var btn=null;
    document.querySelectorAll('button').forEach(function(b){var t=(b.innerText||'').trim();
        if(t.includes('Nächste')||t.includes('Weiter'))btn={text:t,disabled:b.disabled};});
    return{dragCount:document.querySelectorAll('.cdk-drag').length,numbers:numbers,button:btn};
})()"""
    try:
        ws = websocket.create_connection(ws_url, timeout=10)
        ws.send(json.dumps({"id": 0, "method": "Runtime.evaluate", "params": {"expression": js}}))
        r = json.loads(ws.recv()); ws.close()
        return r.get("result", {}).get("result", {}).get("value", {})
    except Exception:
        return {}


def _cdp_mouse(ws_url: str, event_type: str, x: float, y: float, button: str = "left", cc: int = 1):
    ws = websocket.create_connection(ws_url, timeout=10)
    ws.send(json.dumps({"id": 0, "method": "Input.dispatchMouseEvent", "params": {
        "type": event_type, "x": x, "y": y, "button": button,
        "clickCount": cc, "pointerType": "mouse"}}))
    _ = json.loads(ws.recv()); ws.close()


async def _solve_async(ws_url: str, number: str) -> dict:
    js = f"""(function(){{
    var t=document.querySelector('img[alt="{number}"]');
    var dz=document.querySelector('.drop-zone,[class*=drop-zone]')||document.querySelectorAll('.cdk-drop-list')[document.querySelectorAll('.cdk-drop-list').length-1];
    if(!t||!dz)return null;
    var tr=t.getBoundingClientRect(),dr=dz.getBoundingClientRect();
    return{{sx:tr.left+tr.width/2,sy:tr.top+tr.height/2,ex:dr.left+dr.width/2,ey:dr.top+dr.height/2}};
}})()"""
    try:
        ws = websocket.create_connection(ws_url, timeout=10)
        ws.send(json.dumps({"id": 0, "method": "Runtime.evaluate", "params": {"expression": js}}))
        r = json.loads(ws.recv()); ws.close()
        geo = r.get("result", {}).get("result", {}).get("value")
        if not geo: return {"status": "error", "reason": "no_positions"}
    except Exception as e:
        return {"status": "error", "reason": str(e)[:100]}

    sx, sy, ex, ey = geo["sx"], geo["sy"], geo["ex"], geo["ey"]

    # Build arc path (10 points, upward arc)
    points = [(sx + (ex-sx)*(i/10), sy + (ey-sy)*(i/10) - 20*(1-abs(2*i/10-1)) + random.uniform(-1,1))
              for i in range(1, 11)]

    _cdp_mouse(ws_url, "mousePressed", sx, sy)
    await asyncio.sleep(0.05)
    for px, py in points:
        _cdp_mouse(ws_url, "mouseMoved", px, py)
        await asyncio.sleep(0.03)
    _cdp_mouse(ws_url, "mouseReleased", ex, ey)
    await asyncio.sleep(0.5)

    # Verify button enabled + click
    verify_js = "(function(){var btns=document.querySelectorAll('button');for(var b=0;b<btns.length;b++){var t=(btns[b].innerText||'').trim();if((t.includes('Nächste')||t.includes('Weiter'))&&!btns[b].disabled){btns[b].click();return true;}}return false;})()"
    try:
        ws = websocket.create_connection(ws_url, timeout=10)
        ws.send(json.dumps({"id": 0, "method": "Runtime.evaluate", "params": {"expression": verify_js}}))
        r = json.loads(ws.recv()); ws.close()
        clicked = r.get("result", {}).get("result", {}).get("value", False)
    except Exception:
        clicked = False

    return {"status": "ok", "number": number, "button_clicked": clicked,
            "source": (round(sx,1), round(sy,1)), "target": (round(ex,1), round(ey,1))}


def _registry(ok: bool, details: dict):
    try:
        from survey.command_registry import CommandRegistry
        CommandRegistry().record_command("solve_drag_puzzle", ok, details)
    except Exception: pass


def solve(ws_url: str) -> dict:
    """Solve Angular CDK drag-drop puzzle.

    Args:
        ws_url: CDP WebSocket URL for survey tab.

    Returns:
        dict: {"status": "ok"|"error"|"skipped", "number": "...", "button_clicked": bool}

    Usage:
        from tools.tool_solve_drag_puzzle import solve
        result = solve("ws://127.0.0.1:9999/devtools/page/...")
    """
    try:
        from survey.command_registry import CommandRegistry
        CommandRegistry().validate_command("solve_drag_puzzle")
    except Exception: pass

    page_info = _get_page_info(ws_url)
    if not page_info.get("dragCount"):
        _registry(True, {"reason": "no_puzzle"})
        return {"status": "skipped", "reason": "no_drag_puzzle"}

    number = _extract_number(ws_url)
    if not number:
        _registry(False, {"reason": "no_number"})
        return {"status": "error", "reason": "no_target_number"}

    result = asyncio.run(_solve_async(ws_url, number))
    _registry(result["status"] == "ok", result)
    return result


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2: print("Usage: tool_solve_drag_puzzle.py <ws_url>")
    else: print(json.dumps(solve(sys.argv[1]), indent=2))