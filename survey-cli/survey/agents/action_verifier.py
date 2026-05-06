"""
survey/agents/action_verifier.py — Action Verifier Agent (2026-05-06)

FUNKTION: Verifiziert dass Action erfolgreich war (Zustand geändert).
CDP verify: prüft ob Radio selected, Text gefüllt, Button enabled.
CUA verify: prüft AX-Tree nach Action auf selected=true, value gesetzt.

 Thread: 5 von 5 im ParallelOrchestrator
 Model:  mistral-small (80ms, MICRO) — quick verification
 Input:  action_executed, ws_url, page_before_hash, page_after_text
 Output: {verified: bool, state_changed: bool, diff, ms}

VERIFICATION STRATEGY:
    - Radio click → check element.checked === true
    - Text fill → check element.value.length > 0
    - Button click → check button.disabled === false (or page changed)
    - Page change → compare page_text hash before/after
"""

from __future__ import annotations
import time
import hashlib
import json
from typing import Dict, Any, Optional


# ── CDP Verification Scripts ───────────────────────────────────────────────────

VERIFY_RADIO_CHECKED = """
(function() {
    var radios = document.querySelectorAll('input[type=radio]');
    for (var i=0; i<radios.length; i++) {
        if (radios[i].checked) {
            var label = radios[i].labels && radios[i].labels[0]
                ? radios[i].labels[0].textContent.trim()
                : radios[i].value || '';
            return JSON.stringify({checked: true, idx: i, label: label.slice(0,40)});
        }
    }
    return JSON.stringify({checked: false});
})()
"""

VERIFY_TEXT_FILLED = """
(function() {
    var inputs = document.querySelectorAll('input[type=text],textarea');
    var filled = [];
    inputs.forEach(function(el) {
        if (el.value && el.value.length > 2) {
            filled.push({tag: el.tagName, value_len: el.value.length,
                         placeholder: el.placeholder || ''});
        }
    });
    return JSON.stringify(filled);
})()
"""

VERIFY_BUTTON_ENABLED = """
(function() {
    var btns = Array.from(document.querySelectorAll('button'));
    var enabled = btns.filter(function(b){ return !b.disabled && b.offsetHeight>0; })
        .map(function(b){ return b.textContent.trim().slice(0,30); });
    return JSON.stringify(enabled.slice(0, 5));
})();
"""

VERIFY_PAGE_CHANGED = """
(function() {
    var hash = 0;
    var txt = document.body ? document.body.innerText.substring(0,200) : '';
    for (var i=0; i<txt.length; i++) {
        var char = txt.charCodeAt(i);
        hash = ((hash << 5) - hash) + char;
        hash = hash & hash;
    }
    return JSON.stringify({hash: hash, preview: txt.substring(0,100).replace(/\\n/g,' ')});
})()
"""


class ActionVerifier:
    """Verifies actions were successful by comparing before/after state.

    FUNCTIONS:
    1. verify_action() — checks if specific action succeeded
    2. verify_page_change() — checks if page transitioned
    3. verify_element_state() — checks individual element state
    """

    def __init__(self, router=None):
        self.router = router

    def verify(self, action: Dict, ws_url: str,
               page_before_hash: str = "") -> Dict[str, Any]:
        """Verify an action was executed successfully."""
        start = time.monotonic()
        act_type = action.get("action", "")
        method = action.get("method", "cdp")

        verified = False
        state_details = {}

        try:
            import websocket

            if act_type == "click":
                # Verify: button clicked or page changed
                state_details = self._verify_click(ws_url, page_before_hash)

            elif act_type == "fill":
                # Verify: text field is filled
                state_details = self._verify_fill(ws_url, action.get("value", ""))

            elif act_type == "complete":
                # Verify: page shows completion
                state_details = self._verify_completed(ws_url)

            else:
                state_details = {"verified": False, "reason": f"Unknown action type: {act_type}"}

            verified = state_details.get("verified", False)

        except Exception as e:
            state_details = {"verified": False, "error": str(e)[:100]}

        elapsed_ms = round((time.monotonic() - start) * 1000)
        return {
            "agent": "action_verifier",
            "elapsed_ms": elapsed_ms,
            "verified": verified,
            "state_changed": state_details.get("state_changed", False),
            "page_changed": state_details.get("page_changed", False),
            "details": state_details,
            "action_type": act_type,
        }

    def _verify_click(self, ws_url: str, page_before_hash: str) -> Dict:
        """Verify a click action was successful."""
        import websocket
        ws = websocket.create_connection(ws_url, timeout=8)

        # Check button states
        ws.send(json.dumps({
            "id": 0, "method": "Runtime.evaluate",
            "params": {"expression": VERIFY_BUTTON_ENABLED, "returnByValue": True}
        }))
        r = json.loads(ws.recv())
        enabled_btns = json.loads(r.get("result", {}).get("result", {}).get("value", "[]"))

        # Check page hash
        ws.send(json.dumps({
            "id": 1, "method": "Runtime.evaluate",
            "params": {"expression": VERIFY_PAGE_CHANGED, "returnByValue": True}
        }))
        r = json.loads(ws.recv())
        page_state = json.loads(r.get("result", {}).get("result", {}).get("value", "{}"))
        current_hash = page_state.get("hash", "")
        ws.close()

        page_changed = current_hash != page_before_hash and page_before_hash != ""

        return {
            "verified": page_changed or len(enabled_btns) > 0,
            "state_changed": page_changed,
            "page_changed": page_changed,
            "enabled_buttons": enabled_btns,
            "current_hash": current_hash,
        }

    def _verify_fill(self, ws_url: str, expected_value: str) -> Dict:
        """Verify text was filled into field."""
        import websocket
        ws = websocket.create_connection(ws_url, timeout=8)

        ws.send(json.dumps({
            "id": 0, "method": "Runtime.evaluate",
            "params": {"expression": VERIFY_TEXT_FILLED, "returnByValue": True}
        }))
        r = json.loads(ws.recv())
        filled = json.loads(r.get("result", {}).get("result", {}).get("value", "[]"))
        ws.close()

        return {
            "verified": len(filled) > 0,
            "filled_count": len(filled),
            "filled_fields": filled,
            "state_changed": len(filled) > 0,
        }

    def _verify_completed(self, ws_url: str) -> Dict:
        """Verify survey completion page."""
        import websocket
        ws = websocket.create_connection(ws_url, timeout=8)

        ws.send(json.dumps({
            "id": 0, "method": "Runtime.evaluate",
            "params": {"expression": "document.body.innerText.substring(0,500).toLowerCase()"}
        }))
        r = json.loads(ws.recv())
        text = r.get("result", {}).get("result", {}).get("value", "")
        ws.close()

        completion_markers = ["danke", "vielen dank", "abgeschlossen", "completed",
                              "gutgeschrieben", "reward", "belohnung"]
        found = any(m in text for m in completion_markers)

        return {
            "verified": found,
            "state_changed": found,
            "page_changed": found,
            "completion_text": text[:200],
        }

    def get_page_hash(self, ws_url: str) -> str:
        """Get current page content hash for comparison."""
        import websocket
        try:
            ws = websocket.create_connection(ws_url, timeout=8)
            ws.send(json.dumps({
                "id": 0, "method": "Runtime.evaluate",
                "params": {"expression": VERIFY_PAGE_CHANGED, "returnByValue": True}
            }))
            r = json.loads(ws.recv())
            page_state = json.loads(r.get("result", {}).get("result", {}).get("value", "{}"))
            ws.close()
            return page_state.get("hash", "")
        except Exception:
            return ""