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
        # Angular v19: JS .click() IGNORED — use CDP marker
        "click_next": "__CDP_CLICK_BUTTON__:Nächste",
        "click_element": '__CDP_CLICK__:input[type=radio]:{idx}',
        "fill_text": '''(function(v){
            var t=document.querySelector("textarea");
            if(t){t.value=v;t.dispatchEvent(new Event("input",{bubbles:true}));
            t.dispatchEvent(new Event("change",{bubbles:true}));}
        })("{value}")''',
    },
    "insights_today": {
        "click_next": 'document.querySelector("button[type=submit]").click()',
        "click_element": 'document.querySelectorAll("input[type=radio]")[{idx}].click()',
    },
    "cloudresearch": {
        # CloudResearch Sentry: <div role="button"> elements (not <input type=radio>)
        "click_next": "__CDP_CLICK_BUTTON__:Nächster",
        "click_element": '__CDP_CLICK_ROLE_BUTTON__:{idx}',
        "fill_text": '''(function(v){
            var ta = document.querySelector("textarea");
            if(!ta){ta = document.querySelector("input[type=text],input[type=number]");}
            if(ta){
                var nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype,"value").set;
                if(nativeSetter) nativeSetter.call(ta, v);
                else ta.value = v;
                ta.dispatchEvent(new Event("input",{bubbles:true,cancelable:true}));
                ta.dispatchEvent(new Event("change",{bubbles:true,cancelable:true}));
                ta.dispatchEvent(new Event("blur",{bubbles:true,cancelable:true}));
            }
        })("{value}")''',
    },
    "edgesurvey": {
        # EdgeSurvey innovatemr.net: Angular Material <mat-radio-button>
        "click_next": "__CDP_CLICK_BUTTON__:Weiter",
        "click_element": '__CDP_CLICK__:input[type=radio]:{idx}',
        "fill_text": '''(function(v){
            var ta = document.querySelector("textarea,input[type=text]");
            if(ta){
                var nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype,"value").set;
                if(nativeSetter) nativeSetter.call(ta, v);
                else ta.value = v;
                ta.dispatchEvent(new Event("input",{bubbles:true}));
                ta.dispatchEvent(new Event("change",{bubbles:true}));
                ta.dispatchEvent(new Event("blur",{bubbles:true}));
            }
        })("{value}")''',
    },
    "reach3insights": {
        # Reach3Insights: standard form inputs + submit buttons
        "click_next": 'document.querySelector("input[type=submit]").click()',
        "click_element": 'document.querySelectorAll("input[type=radio],input[type=checkbox]")[{idx}].click()',
        "fill_text": '''(function(v){
            var ta = document.querySelector("textarea,input[type=text]");
            if(ta){
                ta.value = v;
                ta.dispatchEvent(new Event("input",{bubbles:true}));
                ta.dispatchEvent(new Event("change",{bubbles:true}));
            }
        })("{value}")''',
    },
    "generic": {
        # Universal fallback for unknown providers: CDP click + textarea fill
        "click_next": "__CDP_CLICK_BUTTON__:Weiter",
        "click_element": '__CDP_CLICK_GENERIC__:{idx}',
        "fill_text": '''(function(v){
            var ta = document.querySelector("textarea,input[type=text]");
            if(ta){
                var nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype,"value").set;
                if(nativeSetter) nativeSetter.call(ta, v);
                else ta.value = v;
                ta.dispatchEvent(new Event("input",{bubbles:true,cancelable:true}));
                ta.dispatchEvent(new Event("change",{bubbles:true,cancelable:true}));
            }
        })("{value}")''',
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
        """Execute single action. Handles __CDP_CLICK__ marker for Angular."""
        action_type = action.get("action", "")
        ref = action.get("ref", "")
        value = action.get("value", "")
        ms = action.get("ms", 0)
        a_start = time.monotonic()

        try:
            # Normalize ref: add @e prefix if missing
            # (NIM output may return "e0" instead of "@e0" per the prompt example)
            if ref and not ref.startswith("@e"):
                ref = "@" + ref
            js = self._build_js(action_type, ref, value)
            
            # CDP click marker for Angular pages (PureSpectrum)
            if js and js.startswith("__CDP_CLICK__"):
                self._cdp_click_element(ws, js)
            elif js and js.startswith("__CDP_CLICK_BUTTON__"):
                self._cdp_click_button(ws, js)
            elif js and js.startswith("__CDP_CLICK_ROLE_BUTTON__"):
                self._cdp_click_role_button(ws, js)
            elif js and js.startswith("__CDP_CLICK_GENERIC__"):
                self._cdp_click_generic(ws, js)
            elif js:
                ws.send(json.dumps({
                    "id": 0, "method": "Runtime.evaluate",
                    "params": {"expression": js}
                }))
                json.loads(ws.recv())

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

    def _cdp_click_element(self, ws, js):
        """CDP click on element (for Angular pages). js format: __CDP_CLICK__:selector:idx"""
        parts = js.replace("__CDP_CLICK__:", "").split(":")
        selector = parts[0] if parts else "button"
        idx = int(parts[1]) if len(parts) > 1 else 0
        
        # Find element position
        ws.send(json.dumps({
            "id": 0, "method": "Runtime.evaluate",
            "params": {"expression": f"var els=document.querySelectorAll('{selector}');if(els[{idx}]){{var r=els[{idx}].getBoundingClientRect();return r.x+r.width/2+','+(r.y+r.height/2);}}return'0,0';"}}))
        r = json.loads(ws.recv())
        coords = r.get("result",{}).get("result",{}).get("value","0,0")
        x, y = map(float, coords.split(","))
        if x > 0:
            for et in ["mouseMoved","mousePressed","mouseReleased"]:
                ws.send(json.dumps({"id":0,"method":"Input.dispatchMouseEvent",
                    "params":{"type":et,"x":x,"y":y,"button":"left","clickCount":1}}))
                json.loads(ws.recv())

    def _cdp_click_button(self, ws, js):
        """CDP click on button by text. js format: __CDP_CLICK_BUTTON__:text
        
        Strategy: PRIMARY = CDP dispatchMouseEvent (works on Angular v19, React, all).
        Fallback = JS .click() (works on standard HTML, Qualtrics, etc.)
        
        Angular v19 PROBLEM: element.click() and dispatchEvent ignored.
        SOLUTION: Real OS mouse event via Input.dispatchMouseEvent (isTrusted=true).
        """
        text = js.replace("__CDP_CLICK_BUTTON__:", "")
        
        # 1. Find element position (viewport coords) via JS
        ws.send(json.dumps({
            "id": 0, "method": "Runtime.evaluate",
            "params": {"expression": f'''
(function(){{
    var text = '{text}';
    var selectors = ['button', 'input[type=submit]', 'input[type=button]',
                     '[role=button]', 'a[href]', '[class*=btn]', '.btn', '.button'];
    var result = null;
    selectors.forEach(function(sel){{
        if(result) return;
        document.querySelectorAll(sel).forEach(function(el){{
            if(result) return;
            if(!el.offsetWidth || !el.offsetHeight) return;  // invisible
            if(el.disabled && el.tagName !== 'A') return;
            var elText = (el.textContent||el.value||'').trim();
            if(!elText) return;
            // Word-boundary match: exact, contains, or starts-with
            if(elText === text || elText.includes(text) || text.includes(elText)){{
                var r = el.getBoundingClientRect();
                var vp = {{w: window.innerWidth, h: window.innerHeight}};
                result = JSON.stringify({{
                    x: Math.round(r.x + r.width/2),
                    y: Math.round(r.y + r.height/2),
                    tag: el.tagName,
                    text: elText.substring(0,30),
                    inView: r.x >= 0 && r.y >= 0 && r.x + r.width <= vp.w && r.y + r.height <= vp.h
                }});
            }}
        }});
    }});
    return result || 'null';
}})();
'''}}))
        try:
            r = json.loads(ws.recv())
            raw_val = r.get("result",{}).get("result",{}).get("value","null")
            if raw_val == "null" or not raw_val:
                pos = None
            else:
                pos = json.loads(raw_val)
        except (json.JSONDecodeError, TypeError):
            pos = None
        
        if not pos:
            # Button not found — try JS click as last resort
            ws.send(json.dumps({
                "id": 0, "method": "Runtime.evaluate",
                "params": {"expression": f'''
(function(){{
    var text = '{text}';
    var selectors = ['button', 'input[type=submit]', '[role=button]'];
    for(var sel of selectors){{
        var els = document.querySelectorAll(sel);
        for(var i=0;i<els.length;i++){{
            var t = (els[i].textContent||'').trim();
            if(t === text || t.includes(text)){{els[i].click(); return 'clicked';}}
        }}
    }}
    return 'not_found';
}})();
'''}}))
            try:
                r2 = json.loads(ws.recv())
                val = r2.get("result",{}).get("result",{}).get("value","")
                if val == "clicked":
                    return
            except:
                pass
            return
        
        x, y = pos["x"], pos["y"]
        
        # 2. CDP dispatchMouseEvent (Angular v19 needs this!)
        if pos.get("inView", False) and x > 0 and y > 0:
            for et in ["mouseMoved", "mousePressed", "mouseReleased"]:
                ws.send(json.dumps({
                    "id": 0, "method": "Input.dispatchMouseEvent",
                    "params": {
                        "type": et,
                        "x": x, "y": y,
                        "button": "left",
                        "clickCount": 1,
                        "modifiers": 0
                    }
                }))
                try:
                    json.loads(ws.recv())
                except Exception:
                    pass  # Don't fail on response parse error
        else:
            # Out of viewport — use JS click as fallback
            ws.send(json.dumps({
                "id": 0, "method": "Runtime.evaluate",
                "params": {"expression": f'''
(function(){{
    var text = '{text}';
    var selectors = ['button', 'input[type=submit]', '[role=button]'];
    for(var sel of selectors){{
        var els = document.querySelectorAll(sel);
        for(var i=0;i<els.length;i++){{
            var t = (els[i].textContent||'').trim();
            if(t === text || t.includes(text)){{els[i].click(); return 'clicked';}}
        }}
    }}
    return 'not_found';
}})();
'''}}))
            try:
                json.loads(ws.recv())
            except:
                pass

    def _cdp_click_role_button(self, ws, js):
        """CDP click on [role=button] element by index. For CloudResearch."""
        parts = js.replace("__CDP_CLICK_ROLE_BUTTON__:", "").split(":")
        idx = int(parts[0]) if parts else 0
        ws.send(json.dumps({
            "id": 0, "method": "Runtime.evaluate",
            "params": {"expression": f'''
(function(){{
    var els = Array.from(document.querySelectorAll('[role=button]'));
    var visible = els.filter(function(e){{ return e.offsetHeight > 0; }});
    if(visible[{idx}]){{
        var r = visible[{idx}].getBoundingClientRect();
        return r.x+r.width/2+','+(r.y+r.height/2);
    }}
    return '0,0';
}})();
'''}}))
        r = json.loads(ws.recv())
        coords = r.get("result",{}).get("result",{}).get("value","0,0")
        x, y = map(float, coords.split(","))
        if x > 0:
            for et in ["mouseMoved","mousePressed","mouseReleased"]:
                ws.send(json.dumps({"id":0,"method":"Input.dispatchMouseEvent",
                    "params":{"type":et,"x":x,"y":y,"button":"left","clickCount":1}}))
                json.loads(ws.recv())

    def _cdp_click_generic(self, ws, js):
        """Universal click: tries [role=button], input[radio], button by index."""
        parts = js.replace("__CDP_CLICK_GENERIC__:", "").split(":")
        idx = int(parts[0]) if parts else 0
        ws.send(json.dumps({
            "id": 0, "method": "Runtime.evaluate",
            "params": {"expression": f'''
(function(){{
    // Try [role=button] first (CloudResearch pattern)
    var rb = Array.from(document.querySelectorAll('[role=button]')).filter(function(e){{return e.offsetHeight>0;}});
    if(rb[{idx}]){{var r=rb[{idx}].getBoundingClientRect();return r.x+r.width/2+','+(r.y+r.height/2)+',rb';}}
    // Try radio buttons (Qualtrics, Strat7 pattern)
    var ra = document.querySelectorAll('input[type=radio]');
    if(ra[{idx}]){{var r=ra[{idx}].getBoundingClientRect();return r.x+r.width/2+','+(r.y+r.height/2)+',radio';}}
    // Try buttons
    var bt = document.querySelectorAll('button');
    if(bt[{idx}] && bt[{idx}].offsetHeight>0){{var r=bt[{idx}].getBoundingClientRect();return r.x+r.width/2+','+(r.y+r.height/2)+',button';}}
    return '0,0,none';
}})();
'''}}))
        r = json.loads(ws.recv())
        coords = r.get("result",{}).get("result",{}).get("value","0,0")
        parts = coords.split(",")
        x, y = float(parts[0]), float(parts[1])
        if x > 0:
            for et in ["mouseMoved","mousePressed","mouseReleased"]:
                ws.send(json.dumps({"id":0,"method":"Input.dispatchMouseEvent",
                    "params":{"type":et,"x":x,"y":y,"button":"left","clickCount":1}}))
                json.loads(ws.recv())

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
