#!/usr/bin/env python3
"""
================================================================================
TOOL: click_angular
================================================================================
Klickt Element mit isTrusted=true via CDP Mouse Events.
Funktioniert bei Angular/React wo .click() ignoriert wird.

BEREITS FUNKTIONIERT: ✓ Getestet mit PureSpectrum, CloudResearch, Qualtrics

USAGE:
    from tools.tool_click_angular import click
    result = click(ws_url, element_index)
    result = click(ws_url, selector=".NextButton")
    result = click(ws_url, text="Weiter")

NICHT AENDERN! Dieser Flow funktioniert.
================================================================================
"""

import json
import time
import websocket
from typing import Optional, Dict, Any, Union

__version__ = "1.0.0"
__frozen__ = True  # NICHT AENDERN!


def click(
    ws_url: str,
    idx: Optional[int] = None,
    selector: Optional[str] = None,
    text: Optional[str] = None,
    timeout: int = 10
) -> Dict[str, Any]:
    try:
        ws = websocket.create_connection(ws_url, timeout=timeout)
        
        if idx is not None:
            js = """
            (function() {
                var els = document.querySelectorAll(
                    'button, a, input, select, textarea, label, [role=button], ' +
                    '[role=checkbox], [role=radio], [onclick], .LabelWrapper, ' +
                    '.ChoiceStructure, .mat-radio-button, .mat-checkbox'
                );
                var el = els[%d];
                if (!el) return null;
                el.scrollIntoView({behavior: 'instant', block: 'center'});
                var r = el.getBoundingClientRect();
                return {x: r.left + r.width/2, y: r.top + r.height/2, tag: el.tagName};
            })();
            """ % idx
        elif selector:
            js = """
            (function() {
                var el = document.querySelector('%s');
                if (!el) return null;
                el.scrollIntoView({behavior: 'instant', block: 'center'});
                var r = el.getBoundingClientRect();
                return {x: r.left + r.width/2, y: r.top + r.height/2, tag: el.tagName};
            })();
            """ % selector
        elif text:
            text_esc = text.replace("'", "\\'")
            js = """
            (function() {
                var els = document.querySelectorAll('button, a, [role=button], label, span, div');
                for (var i = 0; i < els.length; i++) {
                    var t = (els[i].innerText || '').trim().toLowerCase();
                    if (t === '%s'.toLowerCase() || t.includes('%s'.toLowerCase())) {
                        els[i].scrollIntoView({behavior: 'instant', block: 'center'});
                        var r = els[i].getBoundingClientRect();
                        return {x: r.left + r.width/2, y: r.top + r.height/2, tag: els[i].tagName};
                    }
                }
                return null;
            })();
            """ % (text_esc, text_esc)
        else:
            ws.close()
            return {"success": False, "error": "idx, selector oder text required"}
        
        ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate",
            "params": {"expression": js, "returnByValue": True}}))
        resp = json.loads(ws.recv())
        coords = resp.get("result", {}).get("result", {}).get("value")
        
        if not coords:
            ws.close()
            return {"success": False, "error": "Element not found"}
        
        x, y = coords["x"], coords["y"]
        
        ws.send(json.dumps({"id": 2, "method": "Input.dispatchMouseEvent",
            "params": {"type": "mouseMoved", "x": x, "y": y}}))
        ws.recv()
        time.sleep(0.05)
        
        ws.send(json.dumps({"id": 3, "method": "Input.dispatchMouseEvent",
            "params": {"type": "mousePressed", "x": x, "y": y, "button": "left", "clickCount": 1}}))
        ws.recv()
        time.sleep(0.02)
        
        ws.send(json.dumps({"id": 4, "method": "Input.dispatchMouseEvent",
            "params": {"type": "mouseReleased", "x": x, "y": y, "button": "left", "clickCount": 1}}))
        ws.recv()
        
        ws.close()
        return {"success": True, "method": "cdp_mouse", "coords": [x, y]}
        
    except Exception as e:
        if 'ws' in dir() and ws: ws.close()
        return {"success": False, "error": str(e)}


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 3:
        print("Usage: python tool_click_angular.py <ws_url> <idx|--selector=X|--text=X>")
        sys.exit(1)
    ws_url = sys.argv[1]
    if sys.argv[2].startswith("--selector="):
        r = click(ws_url, selector=sys.argv[2].split("=",1)[1])
    elif sys.argv[2].startswith("--text="):
        r = click(ws_url, text=sys.argv[2].split("=",1)[1])
    else:
        r = click(ws_url, idx=int(sys.argv[2]))
    print(json.dumps(r, indent=2))
