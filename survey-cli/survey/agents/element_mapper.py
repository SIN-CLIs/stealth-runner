"""
survey/agents/element_mapper.py — Universal Element Mapper Agent (2026-05-06)

FUNKTION: Scannt ALLE Elemente einer Survey-Seite (radios, checkboxes, text inputs,
textareas, buttons, selects, Angular Material, React [role=button], etc.).
Output: Element-Map mit Koordinaten, Selector, Framework-Detection.

 Thread: 1 von 5 im ParallelOrchestrator
 Model:  mistral-small (80ms, MICRO) — instant regex + CDP DOM scan
 Input:  ws_url, page_text
 Output: {elements: {radios:[], checkboxes:[], text_inputs:[], textareas:[],
            buttons:[], submit_btns:[], role_buttons:[], selects:[]},
          framework: "angular" | "react" | "standard", coordinates: {}, ms}

UNIVERSAL ELEMENT SCAN (alle Frameworks):
    Standard HTML:  document.querySelectorAll('input[type=radio]')
    Angular v19:    CDP DOM.getDocument + DOM.querySelectorAll + getContentQuads
    React:          document.querySelectorAll('[role=button]')
    Angular Material: document.querySelectorAll('.mat-radio-button, .md-radio-button')
"""

from __future__ import annotations
import time
import json
from typing import Dict, List, Any, Optional


# CDP Scripts for universal element scanning
SCAN_RADIOS = """
(function() {
    var results = [];
    var radios = document.querySelectorAll('input[type=radio]');
    radios.forEach(function(r, i) {
        var rect = r.getBoundingClientRect();
        var label = r.labels && r.labels[0] ? r.labels[0].textContent.trim() : '';
        var name = r.name || '';
        results.push({
            type: 'radio', idx: i, value: r.value,
            text: label || r.value || name,
            x: Math.round(rect.x + rect.width/2),
            y: Math.round(rect.y + rect.height/2),
            w: Math.round(rect.width), h: Math.round(rect.height),
            checked: r.checked, sel: 'input[type=radio][value=' + r.value + ']'
        });
    });
    return JSON.stringify(results);
})()
"""

SCAN_CHECKBOXES = """
(function() {
    var results = [];
    var cbs = document.querySelectorAll('input[type=checkbox]');
    cbs.forEach(function(c, i) {
        var rect = c.getBoundingClientRect();
        var label = c.labels && c.labels[0] ? c.labels[0].textContent.trim() : '';
        results.push({
            type: 'checkbox', idx: i, value: c.value,
            text: label || c.value || '',
            x: Math.round(rect.x + rect.width/2),
            y: Math.round(rect.y + rect.height/2),
            w: Math.round(rect.width), h: Math.round(rect.height),
            checked: c.checked, sel: 'input[type=checkbox][value=' + c.value + ']'
        });
    });
    return JSON.stringify(results);
})()
"""

SCAN_TEXT_INPUTS = """
(function() {
    var results = [];
    var inputs = document.querySelectorAll('input[type=text],input[type=email],input[type=number],input[type=tel]');
    inputs.forEach(function(inp, i) {
        var rect = inp.getBoundingClientRect();
        var ph = inp.placeholder || '';
        results.push({
            type: 'text_input', idx: i, value: inp.value,
            text: ph || inp.name || 'input',
            x: Math.round(rect.x + rect.width/2),
            y: Math.round(rect.y + rect.height/2),
            w: Math.round(rect.width), h: Math.round(rect.height),
            placeholder: ph, sel: 'input[placeholder*="' + ph.substring(0,10) + '"]'
        });
    });
    return JSON.stringify(results);
})()
"""

SCAN_TEXTAREAS = """
(function() {
    var results = [];
    var tas = document.querySelectorAll('textarea');
    tas.forEach(function(ta, i) {
        var rect = ta.getBoundingClientRect();
        results.push({
            type: 'textarea', idx: i, value: ta.value,
            text: ta.placeholder || 'textarea',
            x: Math.round(rect.x + rect.width/2),
            y: Math.round(rect.y + rect.height/2),
            w: Math.round(rect.width), h: Math.round(rect.height),
            placeholder: ta.placeholder || '', sel: 'textarea'
        });
    });
    return JSON.stringify(results);
})()
"""

SCAN_BUTTONS = """
(function() {
    var results = [];
    // Standard buttons
    var btns = document.querySelectorAll('button,input[type=submit],input[type=button]');
    btns.forEach(function(b, i) {
        var rect = b.getBoundingClientRect();
        var text = (b.textContent || b.value || b.name || '').trim();
        if (rect.width > 20 && rect.height > 10 && text.length > 0) {
            results.push({
                type: 'button', idx: i, tag: b.tagName,
                text: text.substring(0,50),
                x: Math.round(rect.x + rect.width/2),
                y: Math.round(rect.y + rect.height/2),
                w: Math.round(rect.width), h: Math.round(rect.height),
                disabled: b.disabled,
                sel: b.tagName === 'INPUT' ? 'input[type=' + b.type + ']'
                    : 'button:not([disabled])'
            });
        }
    });
    return JSON.stringify(results);
})()
"""

SCAN_ROLE_BUTTONS = """
(function() {
    var results = [];
    // React / Vue / Angular role=button divs
    var rbs = document.querySelectorAll('[role=button],.mat-button,.mat-raised-button,.mat-flat-button,.mat-stroked-button,.md-button,.btn');
    rbs.forEach(function(b, i) {
        var rect = b.getBoundingClientRect();
        var text = (b.textContent || b.innerText || '').trim();
        if (rect.width > 20 && rect.height > 10 && text.length > 0) {
            results.push({
                type: 'role_button', idx: i,
                text: text.substring(0,50),
                x: Math.round(rect.x + rect.width/2),
                y: Math.round(rect.y + rect.height/2),
                w: Math.round(rect.width), h: Math.round(rect.height),
                sel: '[role=button]:not([disabled])'
            });
        }
    });
    return JSON.stringify(results);
})()
"""

SCAN_SELECTS = """
(function() {
    var results = [];
    var sels = document.querySelectorAll('select');
    sels.forEach(function(s, i) {
        var rect = s.getBoundingClientRect();
        var opts = Array.from(s.options).slice(0,5).map(function(o){ return o.text.trim(); });
        results.push({
            type: 'select', idx: i,
            text: s.name || 'select',
            x: Math.round(rect.x + rect.width/2),
            y: Math.round(rect.y + rect.height/2),
            w: Math.round(rect.width), h: Math.round(rect.height),
            options: opts, sel: 'select'
        });
    });
    return JSON.stringify(results);
})()
"""

DETECT_FRAMEWORK = """
(function() {
    var ng = document.querySelector('[ng-version],[_nghost-c],[_ngcontent-c],.ng-star-inserted');
    var rct = document.querySelector('[data-reactroot],#root>[data-reactid],.react-root');
    var vue = document.querySelector('[data-v-app],#__nuxt,#__vueapp');
    if (ng) return 'angular';
    if (rct) return 'react';
    if (vue) return 'vue';
    return 'standard';
})()
"""


class ElementMapper:
    """Universal element scanner for all survey frameworks.

    COVERS:
    - Standard HTML (Qualtrics, Toluna, Strat7)
    - Angular v19 (PureSpectrum, CloudResearch, EdgeSurvey)
    - React (CloudResearch, etc.)
    - Angular Material (mat-radio-button, mat-button)
    - Vue (Nuxt apps)
    """

    def __init__(self, router=None):
        self.router = router

    def map(self, ws_url: str, page_text: str) -> Dict[str, Any]:
        """Scan all elements on current page."""
        start = time.monotonic()
        elements = {}
        framework = "standard"

        try:
            import websocket
            ws = websocket.create_connection(ws_url, timeout=10)
            msg_id = 0

            def send_eval(script: str) -> Optional[Dict]:
                nonlocal msg_id
                msg_id += 1
                ws.send(json.dumps({
                    "id": msg_id, "method": "Runtime.evaluate",
                    "params": {"expression": script, "returnByValue": True}
                }))
                try:
                    r = json.loads(ws.recv())
                    return json.loads(r.get("result", {}).get("result", {}).get("value", "[]"))
                except Exception:
                    return []

            def send_eval_str(script: str) -> str:
                nonlocal msg_id
                msg_id += 1
                ws.send(json.dumps({
                    "id": msg_id, "method": "Runtime.evaluate",
                    "params": {"expression": script, "returnByValue": True}
                }))
                try:
                    r = json.loads(ws.recv())
                    return r.get("result", {}).get("result", {}).get("value", "standard")
                except Exception:
                    return "standard"

            # Detect framework
            framework = send_eval_str(DETECT_FRAMEWORK)

            # Scan all element types in parallel
            radios = send_eval(SCAN_RADIOS) or []
            checkboxes = send_eval(SCAN_CHECKBOXES) or []
            text_inputs = send_eval(SCAN_TEXT_INPUTS) or []
            textareas = send_eval(SCAN_TEXTAREAS) or []
            buttons = send_eval(SCAN_BUTTONS) or []
            role_buttons = send_eval(SCAN_ROLE_BUTTONS) or []
            selects = send_eval(SCAN_SELECTS) or []

            ws.close()

            elements = {
                "radios": radios,
                "checkboxes": checkboxes,
                "text_inputs": text_inputs,
                "textareas": textareas,
                "buttons": buttons,
                "role_buttons": role_buttons,
                "selects": selects,
            }

            # Extract submit buttons (large buttons with submit keywords)
            submit_btns = [b for b in buttons
                           if any(kw in b.get("text", "").lower()
                                  for kw in ["weiter", "next", "submit", "fortfahren",
                                            "nächste", "continue", "send", "einreichen", "forwardbtn"])]
            elements["submit_btns"] = submit_btns

        except Exception as e:
            elements = {"error": str(e)[:100]}

        elapsed_ms = round((time.monotonic() - start) * 1000)

        # Count total elements
        total = sum(len(v) for v in elements.values() if isinstance(v, list))

        return {
            "agent": "element_mapper",
            "elapsed_ms": elapsed_ms,
            "elements": elements,
            "framework": framework,
            "total_elements": total,
            "radios_count": len(elements.get("radios", [])),
            "buttons_count": len(elements.get("buttons", [])) + len(elements.get("role_buttons", [])),
        }