"""CDP Batch Executor — Execute survey actions via WebSocket.

WARUM: NIM-Entscheidungen (@eN refs) müssen im Browser ausgeführt werden.
Dieses Modul übersetzt Actions in provider-spezifisches JavaScript
und feuert es via CDP Runtime.evaluate. Ohne korrekte Execution
bleibt der Survey-Loop stehen.

ARCHITEKTUR: BatchExecutor mit provider-spezifischen Command-Maps.
Providers: qualtrics, tolunastart, strat7, brand_ambassador, generic.
SOTA Patterns: Keyboard-Fallback (Tab+Enter) für Angular/React,
CDP dispatchMouseEvent PRIMARY (zone.js Kompatibilität),
State-Change-Verify nach jedem Click (DOM-Hash-Vergleich),
Error-Page-Detection, Anti-Stuck adaptive Backoff.

BANNED METHODS — NIEMALS VERWENDEN:
❌ playstealth launch
❌ webauto-nodriver — ABSOLUT BANNED
❌ cua-driver click (raw index)
❌ --remote-allow-origins=* (ohne Quotes)
❌ /tmp/heypiggy-bot (fixed profile)
❌ Hardcoded PIDs
❌ pkill -f "Google Chrome"
❌ killall Google Chrome
❌ skylight-cli click --element-index
"""
# ruff: noqa: E501  (long JS/HTML payloads in multi-line strings - SR-62 #61)

import json
import re
import time
import hashlib
import websocket
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field

from .cdp_client import CDPConnection
from .providers import get_provider_commands

# SOTA: State verification — wait this long before checking DOM change
EXECUTION_VERIFY_MS = 1500
EXECUTION_MAX_WAIT_MS = 3000


@dataclass
class BatchResult:
    actions: List[Dict] = field(default_factory=list)
    total_success: int = 0
    total_fail: int = 0
    total_elapsed_ms: float = 0.0


# ── Provider-Specific CDP Commands ─────────────────────

PROVIDER_COMMANDS = {
    "qualtrics": {
        "click_next": '''(function(){
            var start=Date.now();
            function tryClick(){
                var btn=document.querySelector('.NextButton,.btn-next,#NextButton,button[id*=Next],.btn-primary,[aria-label*=Next],[aria-label*=Weiter]');
                if(!btn)btn=Array.from(document.querySelectorAll('button,[role=button],span[onclick]')).find(function(b){var t=(b.textContent||b.value||'').trim();return t==='>>'||t==='Nächster'||t==='Weiter'||t==='Next';});
                if(btn){btn.click();return'clicked';}
                if(Date.now()-start<8000){setTimeout(tryClick,500);return'waiting';}return'no button';
            }
            return tryClick();
        })()''',
        "click_element": '''(function(idx){
            var els=Array.from(document.querySelectorAll("input[type=radio],input[type=checkbox]"));
            els.sort(function(a,b){return a.getBoundingClientRect().top-b.getBoundingClientRect().top});
            if(els[idx])els[idx].click();
        })({idx})''',
        "fill_text": '''(function(v){
            var t=document.querySelector("textarea:not(.g-recaptcha-response)");
            if(!t){var i=document.querySelector("input[type=text],input[type=number]");
            if(i){var s=Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype,'value');
            if(s&&s.set)s.set.call(i,v);else i.value=v;
            i.dispatchEvent(new Event("input",{bubbles:true}));
            i.dispatchEvent(new Event("change",{bubbles:true}));}}
            else{var s2=Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype,'value');
            if(s2&&s2.set)s2.set.call(t,v);else t.value=v;
            t.dispatchEvent(new Event("input",{bubbles:true}));
            t.dispatchEvent(new Event("change",{bubbles:true}));}
        })("{value}")''',
        "click_select": '''(function(lang){
            var s=document.querySelector("select.Q_lang,select[id*=lang],select");
            if(!s) return JSON.stringify({found:false, reason:"no_select"});
            var langL=(lang||"").toLowerCase();
            var idx=-1;
            for(var i=0;i<s.options.length;i++){
                if(s.options[i].text.trim().toLowerCase().includes(langL)||
                   s.options[i].value.toLowerCase().includes(langL)){
                    idx=i;break;
                }
            }
            if(idx<0) return JSON.stringify({found:false, reason:"no_match", lang:lang});
            s.selectedIndex=idx;
            // Step 1: DOM events (handles Angular/React event listeners)
            s.dispatchEvent(new Event("change",{bubbles:true,cancelable:true}));
            s.dispatchEvent(new Event("input",{bubbles:true,cancelable:true}));
            // Step 2: Native setter (handles v-model / ngModel two-way binding)
            var nativeSetter=Object.getOwnPropertyDescriptor(
                window.HTMLSelectElement.prototype,"value").set;
            if(nativeSetter) nativeSetter.call(s,s.options[idx].value);
            s.dispatchEvent(new Event("change",{bubbles:true}));
            return JSON.stringify({found:true,method:"selectedIndex",idx:idx,
                                   text:s.options[idx].text.trim()});
        })("{value}")''',
        "click_qualtrics_label": '''(function(){
            var labels=document.querySelectorAll('.LabelWrapper,.ChoiceRow label,.choice');
            for(var i=0;i<labels.length;i++){
                var t=labels[i].textContent.trim();
                if(t.indexOf('{label}')>=0||t.toLowerCase().indexOf('{label}')>=0){
                    var inp=labels[i].querySelector('input');
                    if(inp&&!inp.checked){inp.click();return'clicked';}
                }
            }
            return'not found';
        })()''',
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
        "click_element": 'document.querySelectorAll("input[type=radio],input[type=checkbox]")[{idx}].click()',  # noqa: E501
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
    "click_next": 'document.querySelector("button,.NextButton,.btn-primary,input[type=submit]").click()',  # noqa: E501
    "click_element": 'document.querySelectorAll("input[type=radio],input[type=checkbox],button")[{idx}].click()',  # noqa: E501
    "fill_text": '''(function(v){
        var el=document.querySelector("textarea,input[type=text],input[type=number]");
        if(el){el.value=v;el.dispatchEvent(new Event("input",{bubbles:true}));
        el.dispatchEvent(new Event("change",{bubbles:true}));}
    })("{value}")''',
    "click_select": '''(function(lang){
        var s=document.querySelector("select");
        if(!s) return JSON.stringify({found:false});
        var langL=(lang||"").toLowerCase();
        for(var i=0;i<s.options.length;i++){
            if(s.options[i].text.trim().toLowerCase().includes(langL)||
               s.options[i].value.toLowerCase().includes(langL)){
                s.selectedIndex=i;
                s.dispatchEvent(new Event("change",{bubbles:true}));
                s.dispatchEvent(new Event("input",{bubbles:true}));
                return JSON.stringify({found:true,idx:i,text:s.options[i].text.trim()});
            }
        }
        return JSON.stringify({found:false});
    })("{value}")''',
}


# ══════════════════════════════════════════════════════════════════
# LANGUAGE SELECTION PAGE DETECTION (2026-05-09)
# ══════════════════════════════════════════════════════════════════

def detect_language_page(ws_url: str, default_lang: str = "Deutsch") -> Optional[List[Dict]]:
    """Detect Qualtrics language selection page and return select action.

    PROBLEM: Language pages have <select class="Q_lang"> but NO .NextButton.
    Calling click_next on these pages fails silently. This function
    detects the language selector and returns the correct select action.

    QUALTRICS LANGUAGE PAGE INDICATORS:
    - <select class="Q_lang"> — primary selector
    - <select id*=lang> — alternative Qualtrics pattern
    - Page text contains "Sprache", "language", "Sprache auswählen"
    - NO .NextButton present (that's how we know it's language page)

    Args:
        ws_url: CDP WebSocket URL
        default_lang: Language to select (default: "Deutsch")

    Returns:
        [{"action": "select", "value": "Deutsch", "lang_page": True}]
        or None if not a language page
    """
    try:
        ws = websocket.create_connection(ws_url, timeout=8)
        js = """
        (function() {
            var selects = document.querySelectorAll('select');
            var qLang = null;
            for (var i = 0; i < selects.length; i++) {
                var c = (selects[i].className || '').toLowerCase();
                var id = (selects[i].id || '').toLowerCase();
                if (c.indexOf('q_lang') >= 0 || c.indexOf('language') >= 0 ||
                    id.indexOf('lang') >= 0) {
                    qLang = selects[i];
                    break;
                }
            }
            if (!qLang) return JSON.stringify({is_lang_page: false});
            var opts = [];
            for (var i = 0; i < qLang.options.length; i++) {
                opts.push({
                    idx: i,
                    text: qLang.options[i].text.trim(),
                    value: qLang.options[i].value
                });
            }
            var hasNext = !!document.querySelector('.NextButton,#NextButton,.btn-next');
            return JSON.stringify({
                is_lang_page: true,
                select_id: qLang.id || qLang.className,
                options: opts,
                has_next: hasNext
            });
        })()
        """
        ws.send(json.dumps({
            "id": 0, "method": "Runtime.evaluate",
            "params": {"expression": js, "returnByValue": True}
        }))
        r = json.loads(ws.recv())
        ws.close()
        raw = r.get("result", {}).get("result", {}).get("value", "")
        if not raw:
            return None
        data = json.loads(raw) if isinstance(raw, str) else raw
        if not data.get("is_lang_page"):
            return None
        opts = data.get("options", [])
        # Pick default_lang option (case-insensitive)
        lang_lower = default_lang.lower()
        selected = 0
        for i, opt in enumerate(opts):
            if opt["text"].lower().includes(lang_lower) or opt["value"].lower().includes(lang_lower):  # noqa: E501
                selected = i
                break
        return [{"action": "select", "value": opts[selected]["text"] if selected < len(opts) else default_lang,  # noqa: E501
                 "lang_page": True, "options_count": len(opts)}]
    except Exception:
        return None


# ── Batch Executor ─────────────────────────────────────

class BatchExecutor:
    """Execute batched survey actions via CDP WebSocket.

    SOTA features:
    - State verification after each action (DOM hash comparison)
    - Keyboard fallback (Tab+Enter) for Angular/React buttons
    - CDP dispatchMouseEvent PRIMARY for zone.js compatibility
    - Comprehensive error page detection
    """

    def __init__(self, ws_url, provider="unknown", config=None):
        self.ws_url = ws_url
        self.provider = provider
        self.commands = get_provider_commands(provider) or PROVIDER_COMMANDS.get(provider, GENERIC_COMMANDS)  # noqa: E501
        self.config = config  # SOTA: access debug flag for logging

    # ── Static Helpers ──────────────────────────────────────

    @staticmethod
    def read_page_text(ws_url: str, max_len: int = 500) -> str:
        """Read page innerText via CDP WebSocket."""
        try:
            cdp = CDPConnection(ws_url, max_retries=2, timeout=10)
            cdp.connect()
            try:
                result = cdp.call("Runtime.evaluate", {
                    "expression": f"document.body.innerText.substring(0, {max_len})"
                })
                return result.get("result", {}).get("result", {}).get("value", "")
            finally:
                cdp.close()
        except Exception:
            return ""

    # NOTE: An older `detect_error_page` lived here (8 patterns, simple
    # innerText match). It was superseded by the SOTA-pattern version
    # below (covers CPX, Samplicio, Cint, Toluna, Qualtrics, completion
    # pages, screen-outs). The older copy was dead code because Python
    # bound the later definition to the class attribute -- and was
    # flagged as F811 by ruff once CI started enforcing it (SR-61).
    # Removal is safe; the surviving definition is at the end of this
    # class with a richer pattern set.

    @staticmethod
    def detect_validation_error(page_text: str) -> Optional[Dict]:
        """Detect form validation errors and extract hints for value adjustment.

        Returns:
            Dict with {'raw': str, 'hint': str, 'min': int|None, 'max': int|None}
            or None if no validation error found.
        """
        text = (page_text or "").lower()
        patterns = [
            (r"value must be.*?between\s+(\d+)\s+and\s+(\d+)", "range"),
            (r"value must be something like\s+'(\d+)'", "example"),
            (r"value must be at least\s+(\d+)", "min"),
            (r"value must be at most\s+(\d+)", "max"),
            (r"please enter a valid\s+(\d+)", "example"),
            (r"bitte geben sie.*?(\d+).*?ein", "example_de"),
            (r"muss zwischen\s+(\d+)\s+und\s+(\d+)", "range_de"),
            (r"ungefähr\s+(\d+)", "example_de2"),
        ]
        for pattern, kind in patterns:
            m = re.search(pattern, text, re.IGNORECASE)
            if m:
                result = {"raw": m.group(0), "kind": kind}
                groups = m.groups()
                if kind == "range" or kind == "range_de":
                    result["min"] = int(groups[0])
                    result["max"] = int(groups[1])
                    result["hint"] = str((int(groups[0]) + int(groups[1])) // 2)
                elif kind in ("example", "example_de", "example_de2"):
                    result["hint"] = groups[0]
                elif kind == "min":
                    result["min"] = int(groups[0])
                    result["hint"] = str(int(groups[0]))
                elif kind == "max":
                    result["max"] = int(groups[0])
                    result["hint"] = str(int(groups[0]))
                return result
        return None

    def execute(self, actions, snapshot_refs=None):
        """Execute batch of actions with auto-retry on stale connections.

        Args:
            actions: List of action dicts [{ref, action, value, ms}]
            snapshot_refs: Optional CompactSnapshot.refs dict for text enrichment

        Returns:
            BatchResult with per-action results
        """
        result = BatchResult()
        start = time.monotonic()

        # Use CDPConnection for auto-reconnect on "No such target" errors
        cdp = CDPConnection(self.ws_url, max_retries=5)
        cdp.connect()
        ws = cdp._ws  # Raw WebSocket for compatibility with _execute_single

        try:
            for action in actions:
                ar = self._execute_single(ws, action, snapshot_refs)
                result.actions.append(ar)
                if ar.get("success"):
                    result.total_success += 1
                else:
                    result.total_fail += 1
        finally:
            cdp.close()

        result.total_elapsed_ms = round((time.monotonic() - start) * 1000)
        return result

    def _execute_single(self, ws, action, snapshot_refs=None):
        """Execute single action with SOTA verification.

        SOTA patterns:
        - Normalizes ref prefix (@e handling)
        - Enriches action with text from snapshot_refs for provider-specific matching
        - Captures DOM hash BEFORE action for state verification
        - Tries CDP click → verify state change → keyboard fallback if no change
        - Proper error handling with specific messages
        """
        action_type = action.get("action", "")
        ref = action.get("ref", "")
        value = action.get("value", "")
        ms = action.get("ms", 0)
        a_start = time.monotonic()

        # Get WebSocket URL for state verification calls
        ws_url = self.ws_url

        try:
            # Normalize ref: add @e prefix if missing
            if ref and not ref.startswith("@e"):
                ref = "@" + ref

            # Enrich action with text from snapshot refs for provider-specific JS
            action_meta = {}
            if snapshot_refs and ref in snapshot_refs:
                action_meta = {
                    "text": snapshot_refs[ref].get("text", ""),
                    "role": snapshot_refs[ref].get("role", ""),
                }

            # SOTA: Capture DOM state BEFORE action (anti-stuck)
            before_hash = capture_dom_hash(ws_url, 2000) if ws_url else ""

            js = self._build_js(action_type, ref, value, action_meta)

            # Execute the action
            success = False
            method_used = ""

            # CDP click marker for Angular pages (PureSpectrum)
            if js and js.startswith("__CDP_CLICK__"):
                self._cdp_click_element(ws, js)
                success = True
                method_used = "cdp_click_element"
            elif js and js.startswith("__CDP_CLICK_BUTTON__"):
                button_text = js.replace("__CDP_CLICK_BUTTON__:", "")
                success, method_used = cdp_click_element_by_text(ws_url, button_text)
                if not success:
                    # Last resort fallback
                    self._cdp_click_button(ws, js)
                    success = True
                    method_used = "cdp_click_button_fallback"
            elif js and js.startswith("__CDP_CLICK_ROLE_BUTTON__"):
                self._cdp_click_role_button(ws, js)
                success = True
                method_used = "cdp_click_role_button"
            elif js and js.startswith("__CDP_CLICK_GENERIC__"):
                self._cdp_click_generic(ws, js)
                success = True
                method_used = "cdp_click_generic"
            elif js:
                ws.send(json.dumps({
                    "id": 0, "method": "Runtime.evaluate",
                    "params": {"expression": js}
                }))
                json.loads(ws.recv())
                success = True
                method_used = "js_evaluate"

            # SOTA: Verify state change after action
            if success and before_hash and ws_url:
                changed, after_hash = verify_state_change(
                    ws_url, before_hash, EXECUTION_VERIFY_MS
                )
                if not changed:
                    # Angular v19 / React: DOM click() fails (isTrusted=false).
                    # Retry with CDP dispatchMouseEvent — real OS-level mouse event.
                    # _cdp_click_button already implements this correctly.
                    # Re-execute JS to find element and get coordinates
                    self._cdp_click_element(ws, js)
                    method_used += "+dispatchMouseEvent"
                    # Re-verify
                    changed2, after_hash2 = verify_state_change(
                        ws_url, before_hash, EXECUTION_VERIFY_MS * 2
                    )
                    if not changed2:
                        # Last resort: try keyboard Enter.
                        # SR-61: split try/except onto separate lines AND
                        # narrow bare `except` to Exception. Same semantics.
                        try:
                            cdp_keyboard_enter(ws_url)
                        except Exception:
                            pass
                        method_used += "+keyboard_fallback"

            if action_type == "wait":
                time.sleep(ms / 1000 if ms > 0 else 1.0)

            return {
                "action": action_type, "ref": ref, "success": True,
                "elapsed_ms": round((time.monotonic() - a_start) * 1000),
                "method": method_used,
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
            "params": {"expression": f"var els=document.querySelectorAll('{selector}');if(els[{idx}]){{var r=els[{idx}].getBoundingClientRect();return r.x+r.width/2+','+(r.y+r.height/2);}}return'0,0';"}}))  # noqa: E501
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
            except Exception:
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
            except Exception:
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

    def _build_js(self, action_type, ref, value, meta=None):
        """Build CDP JS string for action.

        Args:
            action_type: 'select', 'click', 'fill', 'submit', etc.
            ref: Element reference like '@e5'
            value: Fill value or label text
            meta: Optional dict with {'text', 'role'} from snapshot refs
        """
        cmd = self.commands

        if action_type == "select":
            # select with value: use click_select (language page OR question-page dropdown)
            # Priority: value > ref (setting a value is more specific than clicking by index)
            if value:
                tpl = cmd.get("click_select", GENERIC_COMMANDS.get("click_select", ""))
                if tpl:
                    safe_value = value.replace('"', '\\"')
                    return tpl.replace("{value}", safe_value)
                return None
            # select without value but with @e ref: click_element (dropdown by index)
            if ref and ref.startswith("@e"):
                idx = int(ref[2:])
                tpl = cmd.get("click_element", GENERIC_COMMANDS["click_element"])
                return tpl.replace("{idx}", str(idx))
            # select with no ref + no value: nothing to select
            return None

        if action_type in ("click", "check"):
            if ref and ref.startswith("@e"):
                # Qualtrics: use text-based label matching for radio/checkbox
                if self.provider == "qualtrics" and meta:
                    m_role = meta.get("role", "")
                    m_text = meta.get("text", "")
                    if m_role in ("radio", "radio-selected", "checkbox", "checkbox-checked") and m_text:  # noqa: E501
                        tpl = cmd.get("click_qualtrics_label", "")
                        if tpl:
                            label = m_text.replace('"', '\\"')
                            return tpl.replace("{label}", label)

                # Generic: click by index (sorts by Y to match snapshot order)
                idx = int(ref[2:])
                tpl = cmd.get("click_element", GENERIC_COMMANDS["click_element"])
                return tpl.replace("{idx}", str(idx))

            # Fallback: click next/submit button
            return cmd.get("click_next", GENERIC_COMMANDS["click_next"])

        elif action_type == "fill":
            if not value:
                return None
            safe_value = value.replace('"', '\\"')
            tpl = cmd.get("fill_text", GENERIC_COMMANDS["fill_text"])
            # Use .replace() to avoid .format() conflicts with JS {} in templates
            return tpl.replace("{value}", safe_value)

        elif action_type == "submit":
            return cmd.get("click_next", GENERIC_COMMANDS["click_next"])

        elif action_type in ("wait", "complete", "skip"):
            return None

        return None

    # ══════════════════════════════════════════════════════════════════
    # SOTA ERROR DETECTION (2026-05-06)
    # ══════════════════════════════════════════════════════════════════

    @staticmethod
    def detect_error_page(page_text: str) -> Tuple[bool, str]:
        """Detect error/screen-out pages and return (is_error, reason).

        SOTA patterns:
        - Covers CPX expired, PureSpectrum screen-out, Samplicio,
          Cint, Toluna, Qualtrics, and generic survey errors
        - Returns specific reason for better logging
        - Uses case-insensitive matching on lowercase text
        """
        text = page_text.lower()

        # CPX / Survey aggregator errors
        cpx_errors = [
            ("no app id was specified", "CPX URL expired (no app id)"),
            ("survey not available", "CPX survey not available"),
            ("unable to start survey", "Survey expired on provider"),
            ("link has expired", "Survey link expired"),
            ("survey has ended", "Survey has ended"),
            ("survey closed", "Survey closed by researcher"),
            ("umgeleitet", "CPX redirect page (survey unavailable)"),
            ("redirect", "Generic redirect (survey moved/closed)"),
        ]
        for pattern, reason in cpx_errors:
            if pattern in text:
                return True, reason

        # Generic / provider errors
        generic_errors = [
            ("error occurred", "Generic error occurred"),
            ("leider ist ein fehler aufgetreten", "Survey error (German)"),
            ("this survey is no longer available", "Survey no longer available"),
            ("survey unavailable", "Survey unavailable"),
            ("screen out", "Screen-out (demographic disqualification)"),
            ("you do not qualify", "Did not qualify for survey"),
            ("you are not eligible", "Not eligible for survey"),
            ("thank you for your interest", "Survey completed/closed"),
            ("thank you for completing", "Survey completion page"),
            ("thank you for participating", "Survey completion page"),
            ("please close this window", "Survey completion/screen-out"),
            ("please return to the panel", "Screen-out page"),
            ("qualify for this survey", "Did not qualify"),
            ("you've reached the limit", "Survey limit reached"),
            ("maximum number of responses", "Survey full"),
            ("your session has expired", "Session expired (please re-login)"),
            ("connection error", "Connection error"),
            ("technical error", "Technical error"),
            ("503", "Server error 503"),
            ("500", "Server error 500"),
            ("oops", "Generic Oops error"),
            ("sorry, something went wrong", "Generic sorry error"),
        ]
        for pattern, reason in generic_errors:
            if pattern in text:
                return True, reason

        return False, ""


# ══════════════════════════════════════════════════════════════════
# CDP CONNECTION HELPERS
# ══════════════════════════════════════════════════════════════════


def _cdp_call(ws_url: str, method: str, params: dict = None,
              max_retries: int = 3) -> dict:
    """Execute a CDP command with retry + auto-reconnect via CDPConnection."""
    cdp = CDPConnection(ws_url, max_retries=max_retries)
    cdp.connect()
    try:
        return cdp.call(method, params)
    finally:
        cdp.close()


# ══════════════════════════════════════════════════════════════════
# SOTA STATE VERIFICATION (2026-05-06)
# ══════════════════════════════════════════════════════════════════

def capture_dom_hash(ws_url: str, max_len: int = 2000) -> str:
    """Capture DOM state as hash — SOTA anti-stuck detection.

    Uses element count + first N element texts + URL for a stable,
    fast-to-compute hash. Different from page_hash (used in runner.py)
    which uses fewer elements. This function is for execution verification.
    """
    try:
        ws = websocket.create_connection(ws_url, timeout=8)
        ws.send(json.dumps({
            "id": 0, "method": "Runtime.evaluate",
            "params": {"expression": '''
(function(){
    var els = document.querySelectorAll('input,button,select,textarea,a,label');
    var texts = [];
    for(var i=0;i<els.length&&i<20;i++){
        texts.push((els[i].textContent||els[i].value||els[i].name||'')+'|'+els[i].tagName+'|'+els[i].type);
    }
    return JSON.stringify({
        n: els.length,
        t: texts.join(';;'),
        url: location.href.substring(0,100)
    });
})()
'''}
        }))
        r = json.loads(ws.recv())
        ws.close()
        raw = r.get("result", {}).get("result", {}).get("value", "")
        if not raw:
            return ""
        data = json.loads(raw) if isinstance(raw, str) else raw
        h = hashlib.sha256()
        h.update(f"{data.get('n',0)}|{data.get('t','')}|{data.get('url','')}".encode())
        return h.hexdigest()[:16]
    except Exception:
        return ""


def verify_state_change(ws_url: str, before_hash: str,
                        verify_ms: int = EXECUTION_VERIFY_MS) -> Tuple[bool, str]:
    """Verify DOM changed after action (SOTA anti-stuck).

    After a click/fill action, wait verify_ms, then capture new DOM hash.
    Return (changed, new_hash).

    Why this matters:
    - Angular buttons may visually respond but not change DOM
    - Radio buttons may stay unselected after click
    - Survey pages may auto-advance without URL change
    - Stale element indices can click wrong element
    """
    time.sleep(verify_ms / 1000)
    after_hash = capture_dom_hash(ws_url)
    changed = before_hash != after_hash and after_hash != ""
    return changed, after_hash


def cdp_keyboard_enter(ws_url: str) -> bool:
    """SOTA: Keyboard Tab+Enter for Angular/React buttons.

    Why Tab+Enter instead of JS .click():
    - Zone.js in Angular v19+ intercepts keyboard events, not click events
    - Tab focuses the first focusable element (usually a button)
    - Enter fires keydown+keypress+keyup which zone.js handles correctly
    - Works on React, Vue, and standard HTML forms too

    Returns True if Enter was dispatched, False otherwise.
    """
    try:
        ws = websocket.create_connection(ws_url, timeout=8)

        # Tab to focus first focusable element (usually the submit button)
        ws.send(json.dumps({
            "id": 0, "method": "Input.dispatchKeyEvent",
            "params": {"type": "keyDown", "modifiers": 0, "windowsVirtualKeyCode": 9,
                       "key": "Tab", "code": "Tab"}
        }))
        json.loads(ws.recv())
        time.sleep(0.05)

        # Enter
        ws.send(json.dumps({
            "id": 0, "method": "Input.dispatchKeyEvent",
            "params": {"type": "keyDown", "modifiers": 0, "windowsVirtualKeyCode": 13,
                       "key": "Enter", "code": "Enter"}
        }))
        json.loads(ws.recv())
        ws.send(json.dumps({
            "id": 0, "method": "Input.dispatchKeyEvent",
            "params": {"type": "keyUp", "modifiers": 0, "windowsVirtualKeyCode": 13,
                       "key": "Enter", "code": "Enter"}
        }))
        json.loads(ws.recv())
        ws.close()
        return True
    except Exception:
        return False


def cdp_click_element_by_text(ws_url: str, search_text: str,
                               selectors: List[str] = None) -> Tuple[bool, str]:
    """SOTA: Find element by text + CDP click with verification.

    Strategy:
    1. Try keyboard Tab+Enter (works on Angular v19 zone.js)
    2. Try CDP dispatchMouseEvent at element center
    3. Try JS .click() as last resort

    Returns: (success, method_used)
    """
    if selectors is None:
        selectors = ['button', 'input[type=submit]', 'input[type=button]',
                     '[role=button]', 'a[href]', '.btn', '.button']

    try:
        ws = websocket.create_connection(ws_url, timeout=10)

        # Step 1: Try keyboard Tab+Enter (fastest, most Angular-compatible)
        before = capture_dom_hash(ws_url)
        if cdp_keyboard_enter(ws_url):
            changed, _ = verify_state_change(ws_url, before, verify_ms=1200)
            ws.close()
            if changed:
                return True, "keyboard_enter"
            # Fall through to element-specific click

        # Step 2: Find element position + CDP mouse click
        js_find = f'''
(function(){{
    var text = {repr(search_text)};
    var selectors = {json.dumps(selectors)};
    var result = null;
    for(var si=0; si<selectors.length && !result; si++){{
        var els = document.querySelectorAll(selectors[si]);
        for(var i=0; i<els.length && !result; i++){{
            var el = els[i];
            if(!el.offsetWidth || !el.offsetHeight) continue;
            if(el.disabled && el.tagName !== 'A') continue;
            var t = (el.textContent||el.value||'').trim().toLowerCase();
            if(t && (t === text.toLowerCase() || t.includes(text.toLowerCase()) || text.toLowerCase().includes(t))){{
                var r = el.getBoundingClientRect();
                result = JSON.stringify({{x: r.x+r.width/2, y: r.y+r.height/2,
                                          tag: el.tagName, text: t.substring(0,30)}});
            }}
        }}
    }}
    return result || 'null';
}})()
'''
        ws.send(json.dumps({"id": 0, "method": "Runtime.evaluate",
                            "params": {"expression": js_find}}))
        r = json.loads(ws.recv())
        raw_val = r.get("result", {}).get("result", {}).get("value", "null")

        if raw_val and raw_val != "null":
            before = capture_dom_hash(ws_url)
            pos = json.loads(raw_val)
            x, y = pos["x"], pos["y"]

            # CDP dispatchMouseEvent: mouseMoved → mousePressed → mouseReleased
            for etype in ["mouseMoved", "mousePressed", "mouseReleased"]:
                ws.send(json.dumps({
                    "id": 0, "method": "Input.dispatchMouseEvent",
                    "params": {"type": etype, "x": x, "y": y,
                               "button": "left", "clickCount": 1, "modifiers": 0}
                }))
                try:
                    json.loads(ws.recv())
                except Exception:
                    pass

            changed, _ = verify_state_change(ws_url, before, verify_ms=1500)
            ws.close()
            if changed:
                return True, "cdp_mouse"

        ws.close()
    except Exception:
        pass

    # Step 3: JS .click() as last resort
    try:
        ws = websocket.create_connection(ws_url, timeout=10)
        before = capture_dom_hash(ws_url)
        js_click = f'''
(function(){{
    var selectors = {json.dumps(selectors)};
    for(var si=0; si<selectors.length; si++){{
        var els = document.querySelectorAll(selectors[si]);
        for(var i=0; i<els.length; i++){{
            var t = (els[i].textContent||'').trim().toLowerCase();
            if(t.includes({repr(search_text.lower())})){{els[i].click(); return 'clicked';}}
        }}
    }}
    return 'not_found';
}})()
'''
        ws.send(json.dumps({"id": 0, "method": "Runtime.evaluate",
                            "params": {"expression": js_click}}))
        r = json.loads(ws.recv())
        val = r.get("result", {}).get("result", {}).get("value", "")
        ws.close()
        if val == "clicked":
            time.sleep(1.5)
            return True, "js_click"
    except Exception:
        pass

    return False, "none"
