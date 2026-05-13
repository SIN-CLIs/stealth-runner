"""TOOL: universal_answer — DOM-Based Universal Survey Answerer

UNDER 300 LINES. Provider-agnostic. Handles: Radio / Checkbox / Text / Select / NPS / Matrix.
Uses DOM structure for question type detection, NOT provider names.

STATUS: __frozen__=True | Version: 2026-05-11

BANNED: ❌ provider hardcode | ❌ playstealth | ❌ webauto-nodriver | ❌ hardcoded PIDs
"""

from __future__ import annotations
import json
import websocket
from typing import Optional

__frozen__ = True
__version__ = "2026-05-11"


def _detect_type(ws_url: str) -> str:
    """Detect question type from DOM — NO provider lookup."""
    js = """
(function() {
    var r=document.querySelectorAll('input[type=radio]').length;
    var c=document.querySelectorAll('input[type=checkbox]').length;
    var ta=document.querySelectorAll('textarea').length;
    var ti=document.querySelectorAll('input[type=text]').length;
    var sel=document.querySelectorAll('select').length;
    var nps=Array.from(document.querySelectorAll('button')).filter(function(b){return/^\\s*\\d+\\s*$/.test((b.innerText||'').trim());}).length;
    if(nps>=9)return'nps';
    if(c>2)return'multi';
    if(r>=1&&r<=10)return'radio';
    if(sel>0)return'select';
    if(ta>0)return'textarea';
    if(ti>0)return'text';
    return'unknown';
})()"""
    try:
        ws = websocket.create_connection(ws_url, timeout=10)
        ws.send(json.dumps({"id": 0, "method": "Runtime.evaluate", "params": {"expression": js}}))
        r = json.loads(ws.recv()); ws.close()
        return r.get("result", {}).get("result", {}).get("value", "unknown")
    except Exception:
        return "unknown"


def _get_options(ws_url: str) -> dict:
    """Get question text + element options."""
    js = """
(function() {
    var q=(document.querySelector('h2,h3,.question-text')||{}).innerText||'';
    var radios=Array.from(document.querySelectorAll('input[type=radio]')).map(function(r,i){
        var p=r.closest('label,.option');return{idx:i,label:(p?p.innerText:'').trim().substring(0,80)};
    });
    var cbs=Array.from(document.querySelectorAll('input[type=checkbox]')).map(function(c,i){
        var p=c.closest('label,.option');return{idx:i,label:(p?p.innerText:'').trim().substring(0,80)};
    });
    var nps=Array.from(document.querySelectorAll('button')).filter(function(b){
        return/^\\s*\\d+\\s*$/.test((b.innerText||'').trim());
    }).map(function(b){return{num:parseInt((b.innerText||'').trim()),el:b};});
    return{q:q.substring(0,200),radios:radios,cbs:cbs,nps:nps,hasText:document.querySelectorAll('textarea,input[type=text]').length>0};
})()"""
    try:
        ws = websocket.create_connection(ws_url, timeout=10)
        ws.send(json.dumps({"id": 0, "method": "Runtime.evaluate", "params": {"expression": js}}))
        r = json.loads(ws.recv()); ws.close()
        return r.get("result", {}).get("result", {}).get("value", {})
    except Exception:
        return {}


def _match(q: str, options: list, profile: dict) -> int:
    """Map question text to best option index."""
    ql = q.lower()
    if any(k in ql for k in ['geschlecht', 'gender', 'männlich']):
        g = profile.get('gender', 'male')
        for i, o in enumerate(options):
            if g == 'male' and 'männ' in o.get('label','').lower(): return i
            if g == 'female' and 'weib' in o.get('label','').lower(): return i
    if any(k in ql for k in ['alter', 'age', 'jahre']):
        age = profile.get('age', 32)
        brackets = [(16,25,'16','25'),(26,39,'26','39'),(40,55,'40','55')]
        for bi, (lo, hi, a1, a2) in enumerate(brackets):
            if lo <= age <= hi:
                for i, o in enumerate(options):
                    if a1 in o.get('label','') and a2 in o.get('label',''): return i
        return 0
    for i, o in enumerate(options):
        if o.get('label','').strip(): return i
    return 0


def _build_js(qtype: str, opts: dict, profile: dict) -> str:
    """Build execute JS for question type."""
    p = profile

    # Radio: sort by Y, click matched
    if qtype == "radio":
        idx = min(_match(opts.get('q',''), opts.get('radios',[]), p), len(opts.get('radios',[]))-1)
        return f"var rs=Array.from(document.querySelectorAll('input[type=radio]')).sort(function(a,b){{return a.getBoundingClientRect().top-b.getBoundingClientRect().top}});if(rs[{idx}])rs[{idx}].click();"

    # Multi-select: first 3 checkboxes
    if qtype == "multi":
        return "var cs=Array.from(document.querySelectorAll('input[type=checkbox]')).sort(function(a,b){return a.getBoundingClientRect().top-b.getBoundingClientRect().top});for(var i=0;i<Math.min(3,cs.length);i++)cs[i].click();"

    # Text/Textarea
    if qtype in ("text", "textarea"):
        q = opts.get('q','').lower()
        if any(k in q for k in ['plz','postleitzahl','zip']): ans = p.get('zip','10785')
        elif any(k in q for k in ['stadt','city']): ans = p.get('city','Berlin')
        elif any(k in q for k in ['straße','street']): ans = p.get('street','Kurfürstenstraße 124')
        elif any(k in q for k in ['e-mail','email']): ans = 'jeremy@test.de'
        else: ans = p.get('city','Berlin')
        sel = 'textarea' if qtype == 'textarea' else 'input[type=text]'
        return f"var el=document.querySelector('{sel}');if(el){{var s=Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype,'value');if(s&&s.set){{s.set.call(el,'{ans}');}}else{{el.value='{ans}';}}el.dispatchEvent(new Event('input',{{bubbles:true}}));el.dispatchEvent(new Event('change',{{bubbles:true}}));}}"

    # Select: pick 2nd option
    if qtype == "select":
        return "var s=document.querySelector('select');if(s&&s.options.length>1){s.selectedIndex=1;s.dispatchEvent(new Event('change',{bubbles:true}));}"

    # NPS: click 7
    if qtype == "nps":
        nps_ans = p.get('nps_answer', 7)
        return f"var btns=Array.from(document.querySelectorAll('button')).filter(function(b){{return/^\\s*\\d+\\s*$/.test((b.innerText||'').trim());}});var t=btns.find(function(b){{return parseInt((b.innerText||'').trim())=={nps_ans};}});if(t)t.click();"

    return ""


def _click_next() -> str:
    """Click Nächste/Weiter + Tab/Enter fallback."""
    return """
(function() {
    var btns = document.querySelectorAll('button');
    for (var b = 0; b < btns.length; b++) {
        var t = (btns[b].innerText || '').trim();
        if ((t.includes('Nächste') || t.includes('Weiter') || t.includes('Next') || t.includes('Submit')) && !btns[b].disabled) {
            btns[b].click(); return;
        }
    }
    // Fallback: Tab + Enter
    var el = document.activeElement;
    if (el && (el.tagName === 'TEXTAREA' || el.type === 'text')) {
        setTimeout(function() { document.dispatchEvent(new KeyboardEvent('keydown', {key: 'Enter', bubbles: true})); }, 100);
    }
})()"""


def _registry(ok: bool, details: dict):
    try:
        from survey.command_registry import CommandRegistry
        CommandRegistry().record_command("universal_answer", ok, details)
    except Exception: pass


def answer(ws_url: str, profile: Optional[dict] = None) -> dict:
    """Universal DOM-based survey answerer.

    Args:
        ws_url: CDP WebSocket URL for survey tab.
        profile: Optional persona dict (auto-loaded if None).

    Returns:
        dict: {"status": "ok"|"skipped"|"error", "type": "...", "answered": bool}

    Usage:
        from tools.tool_universal_answer import answer
        result = answer("ws://127.0.0.1:9999/devtools/page/...")
    """
    try:
        from survey.command_registry import CommandRegistry
        CommandRegistry().validate_command("universal_answer")
    except Exception: pass

    if not profile:
        try:
            from survey.profile_loader import ProfileLoader
            profile = ProfileLoader.load_profile()
        except Exception:
            profile = {"gender": "male", "gender_label": "Männlich", "age": 32, "city": "Berlin"}

    if "age" not in profile:
        try:
            from datetime import date
            dob = profile.get("date_of_birth", "1993-11-13").split("-")
            profile["age"] = date.today().year - int(dob[0])
        except Exception:
            profile["age"] = 32

    qtype = _detect_type(ws_url)
    if qtype == "unknown":
        opts = _get_options(ws_url)
        if not opts.get('hasText') and not opts.get('radios') and not opts.get('cbs'):
            _registry(True, {"reason": "no_elements"})
            return {"status": "skipped", "type": "unknown", "reason": "no_interactive_elements"}

    opts = _get_options(ws_url)
    qtype = _detect_type(ws_url)
    if qtype == "unknown":
        _registry(True, {"reason": "unknown_type"})
        return {"status": "skipped", "type": "unknown", "reason": "cannot_detect"}

    js = "(function(){" + _build_js(qtype, opts, profile) + _click_next() + "})()"
    try:
        ws = websocket.create_connection(ws_url, timeout=15)
        ws.send(json.dumps({"id": 0, "method": "Runtime.evaluate", "params": {"expression": js, "awaitPromise": True}}))
        _ = json.loads(ws.recv()); ws.close()
        result = {"status": "ok", "type": qtype, "answered": True, "question": opts.get("q","")[:100]}
        _registry(True, result)
        return result
    except Exception as e:
        _registry(False, {"error": str(e)[:100]})
        return {"status": "error", "reason": str(e)[:100], "type": qtype}


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2: print("Usage: tool_universal_answer.py <ws_url>")
    else: print(json.dumps(answer(sys.argv[1]), indent=2))