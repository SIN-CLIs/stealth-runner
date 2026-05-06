"""CDP Batch Executor — Execute survey actions via WebSocket.

Translates high-level actions (@eN refs) to provider-specific CDP JS.
Supports: qualtrics, tolunastart, strat7, brand_ambassador, generic.
"""

import json
import time
import websocket
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field


@dataclass
class BatchResult:
    actions: List[Dict] = field(default_factory=list)
    total_success: int = 0
    total_fail: int = 0
    total_elapsed_ms: float = 0.0


# ── Provider-Specific CDP Commands ─────────────────────

PROVIDER_COMMANDS = {
    "qualtrics": {
        "click_next": 'document.querySelector(".NextButton").click()',
        "click_element": 'document.querySelectorAll("input[type=radio],input[type=checkbox]")[{idx}].click()',
        "fill_text": '''(function(v){
            var t=document.querySelector("textarea:not(.g-recaptcha-response)");
            if(!t){var i=document.querySelector("input[type=text],input[type=number]");
            if(i){i.value=v;i.dispatchEvent(new Event("input",{bubbles:true}));
            i.dispatchEvent(new Event("change",{bubbles:true}));}}
            else{t.value=v;t.dispatchEvent(new Event("input",{bubbles:true}));
            t.dispatchEvent(new Event("change",{bubbles:true}));}
        })("{value}")''',
    },
    "tolunastart": {
        "click_next": 'document.querySelector("button").click()',
        "click_element": '''(function(){
            var rs=document.querySelectorAll(".cf-radio,.cf-checkbox");
            if(rs[{idx}]) rs[{idx}].click();
        })()''',
        "fill_text": '''(function(v){
            var i=document.querySelector("input[type=number],input[type=text]");
            if(i){i.value=v;i.dispatchEvent(new Event("input",{bubbles:true}));
            i.dispatchEvent(new Event("change",{bubbles:true}));}
        })("{value}")''',
    },
    "strat7": {
        "click_next": 'document.querySelector(".bsbutton:not([disabled])").click()',
        "click_element": 'document.querySelectorAll("input[type=radio]")[{idx}].click()',
        "fill_text": '''(function(v){
            var i=document.querySelector("input[type=text],input[type=number]");
            if(i){i.value=v;i.dispatchEvent(new Event("input",{bubbles:true}));
            i.dispatchEvent(new Event("change",{bubbles:true}));}
        })("{value}")''',
    },
    "brand_ambassador": {
        "click_next": 'document.querySelector(".submit-btn,button[type=submit]").click()',
        "click_element": 'document.querySelectorAll("input[type=radio]")[{idx}].click()',
    },
    "purespectrum": {
        "click_next": 'document.querySelector("button[type=submit]").click()',
        "fill_text": '''(function(v){
            var t=document.querySelector("textarea");
            if(t){t.value=v;t.dispatchEvent(new Event("input",{bubbles:true}));
            t.dispatchEvent(new Event("change",{bubbles:true}));}
        })("{value}")''',
    },
    "insights_today": {
        "click_next": 'document.querySelector("button[type=submit]").click()',
        "click_element": 'document.querySelectorAll("input[type=radio]")[{idx}].click()',
        "select_option": '''(function(){
            var s=document.querySelector("select");
            if(s){s.value="{value}";s.dispatchEvent(new Event("change",{bubbles:true}));}
        })()''',
    },
}

GENERIC_COMMANDS = {
    "click_next": 'document.querySelector("button,.NextButton,.btn-primary,input[type=submit]").click()',
    "click_element": 'document.querySelectorAll("input[type=radio],input[type=checkbox],button")[{idx}].click()',
    "fill_text": '''(function(v){
        var el=document.querySelector("textarea,input[type=text],input[type=number]");
        if(el){el.value=v;el.dispatchEvent(new Event("input",{bubbles:true}));
        el.dispatchEvent(new Event("change",{bubbles:true}));}
    })("{value}")''',
}


# ── Batch Executor ─────────────────────────────────────

class BatchExecutor:
    """Execute batched survey actions via CDP WebSocket."""

    def __init__(self, ws_url, provider="unknown"):
        self.ws_url = ws_url
        self.provider = provider
        self.commands = PROVIDER_COMMANDS.get(provider, GENERIC_COMMANDS)

    def execute(self, actions):
        """Execute batch of actions.

        Args:
            actions: List of action dicts [{ref, action, value, ms}]

        Returns:
            BatchResult with per-action results
        """
        result = BatchResult()
        start = time.monotonic()

        ws = websocket.create_connection(self.ws_url, timeout=15)

        for action in actions:
            ar = self._execute_single(ws, action)
            result.actions.append(ar)
            if ar.get("success"):
                result.total_success += 1
            else:
                result.total_fail += 1

        ws.close()
        result.total_elapsed_ms = round((time.monotonic() - start) * 1000)
        return result

    def _execute_single(self, ws, action):
        """Execute single action."""
        action_type = action.get("action", "")
        ref = action.get("ref", "")
        value = action.get("value", "")
        ms = action.get("ms", 0)
        a_start = time.monotonic()

        try:
            js = self._build_js(action_type, ref, value)
            if js:
                ws.send(json.dumps({
                    "id": 0, "method": "Runtime.evaluate",
                    "params": {"expression": js}
                }))
                json.loads(ws.recv())  # consume response

            if action_type == "wait":
                time.sleep(ms / 1000 if ms > 0 else 1.0)

            return {
                "action": action_type, "ref": ref, "success": True,
                "elapsed_ms": round((time.monotonic() - a_start) * 1000),
            }
        except Exception as e:
            return {
                "action": action_type, "ref": ref, "success": False,
                "error": str(e)[:200],
                "elapsed_ms": round((time.monotonic() - a_start) * 1000),
            }

    def _build_js(self, action_type, ref, value):
        """Build CDP JS string for action."""
        cmd = self.commands

        if action_type in ("click", "select", "check"):
            if ref and ref.startswith("@e"):
                idx = int(ref[2:])
                return cmd.get("click_element", GENERIC_COMMANDS["click_element"]).format(idx=idx)
            # Fallback: click next/submit
            return cmd.get("click_next", GENERIC_COMMANDS["click_next"])

        elif action_type == "fill":
            if not value:
                return None
            safe_value = value.replace('"', '\\"')
            tpl = cmd.get("fill_text", GENERIC_COMMANDS["fill_text"])
            if "{value}" in tpl:
                return tpl.format(value=safe_value)
            return tpl

        elif action_type == "submit":
            return cmd.get("click_next", GENERIC_COMMANDS["click_next"])

        elif action_type in ("wait", "complete", "skip"):
            return None

        return None

    @staticmethod
    def read_page_text(ws_url, max_len=500):
        """Read page text for completion check."""
        try:
            ws = websocket.create_connection(ws_url, timeout=10)
            ws.send(json.dumps({
                "id": 0, "method": "Runtime.evaluate",
                "params": {"expression": f"document.body.innerText.substring(0, {max_len})"}
            }))
            r = json.loads(ws.recv())
            ws.close()
            return r.get("result", {}).get("result", {}).get("value", "")
        except Exception:
            return ""
