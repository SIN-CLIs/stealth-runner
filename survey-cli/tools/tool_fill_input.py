#!/usr/bin/env python3
"""
================================================================================
TOOL: fill_input
================================================================================
Fuellt Input-Feld mit Validation Error Handling.
Wenn Validation fehlschlaegt, parst Hint aus Fehlermeldung und retried.

BEREITS FUNKTIONIERT: ✓ Getestet mit Qualtrics, PureSpectrum

USAGE:
    from tools.tool_fill_input import fill
    result = fill(ws_url, idx=0, value="25")
    result = fill(ws_url, selector="#age", value="25")

NICHT AENDERN! Dieser Flow funktioniert.
================================================================================
"""

import json
import websocket
from typing import Dict, Any, Optional

__version__ = "1.0.0"
__frozen__ = True


def fill(
    ws_url: str,
    value: str,
    idx: Optional[int] = None,
    selector: Optional[str] = None,
    timeout: int = 10
) -> Dict[str, Any]:
    value_json = json.dumps(value)
    
    if idx is not None:
        fill_sel = "document.querySelectorAll('input, textarea, select')[" + str(idx) + "]"
    elif selector:
        fill_sel = "document.querySelector('" + selector + "')"
    else:
        return {"success": False, "error": "idx oder selector required"}
    
    js = """
    (function() {
        var el = %s;
        if (!el) return {success: false, error: 'Element not found'};
        el.scrollIntoView({behavior: 'instant', block: 'center'});
        el.focus();
        el.value = '';
        el.value = %s;
        ['input', 'change', 'blur', 'keyup'].forEach(function(evt) {
            el.dispatchEvent(new Event(evt, {bubbles: true}));
        });
        var vm = el.validationMessage || '';
        if (vm) {
            var hint = vm.match(/like\\s+(\\d+)/i);
            return {success: false, error: 'validation', validationMessage: vm, hint: hint ? hint[1] : null};
        }
        return {success: true, value: el.value};
    })();
    """ % (fill_sel, value_json)
    
    try:
        ws = websocket.create_connection(ws_url, timeout=timeout)
        ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate",
            "params": {"expression": js, "returnByValue": True}}))
        resp = json.loads(ws.recv())
        result = resp.get("result", {}).get("result", {}).get("value", {})
        
        # Retry with hint
        if result.get("error") == "validation" and result.get("hint"):
            hint = result["hint"]
            hint_json = json.dumps(hint)
            retry_js = js.replace(value_json, hint_json)
            ws.send(json.dumps({"id": 2, "method": "Runtime.evaluate",
                "params": {"expression": retry_js, "returnByValue": True}}))
            retry_resp = json.loads(ws.recv())
            retry_result = retry_resp.get("result", {}).get("result", {}).get("value", {})
            if retry_result.get("success"):
                ws.close()
                return {"success": True, "value": hint, "method": "hint_retry"}
        
        ws.close()
        return result if result else {"success": False, "error": "No result"}
        
    except Exception as e:
        return {"success": False, "error": str(e)}


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 4:
        print("Usage: python tool_fill_input.py <ws_url> <idx|--selector=X> <value>")
        sys.exit(1)
    ws_url = sys.argv[1]
    value = sys.argv[3]
    if sys.argv[2].startswith("--selector="):
        r = fill(ws_url, value, selector=sys.argv[2].split("=",1)[1])
    else:
        r = fill(ws_url, value, idx=int(sys.argv[2]))
    print(json.dumps(r, indent=2))
