#!/usr/bin/env python3
"""
================================================================================
TOOL: snapshot
================================================================================
Erstellt Snapshot aller interaktiven Elemente.
Findet Qualtrics LabelWrapper, Selects, Radios, Buttons.

BEREITS FUNKTIONIERT: ✓ Getestet mit Qualtrics, PureSpectrum, Generic

USAGE:
    from tools.tool_snapshot import snapshot
    data = snapshot(ws_url)
    elements = data["elements"]
    dom_hash = data["hash"]

NICHT AENDERN! Dieser Flow funktioniert.
================================================================================
"""

import json
import hashlib
import websocket
from typing import Dict, Any, List, Optional

__version__ = "1.0.0"
__frozen__ = True


EXTRACTOR_JS = """
(function() {
    var MAX = 50;
    var out = [];
    var seen = new Set();
    function add(el, type) {
        if (out.length >= MAX) return;
        var rect = el.getBoundingClientRect();
        if (rect.width === 0 || rect.height === 0) return;
        var style = window.getComputedStyle(el);
        if (style.display === 'none' || style.visibility === 'hidden') return;
        if (rect.top > window.innerHeight + 300) return;
        var text = (el.getAttribute('aria-label') || el.innerText || el.value || '').trim().substring(0, 80);
        var key = type + ':' + text.toLowerCase();
        if (seen.has(key) && text) return;
        seen.add(key);
        out.push({idx: out.length, type: type, text: text,
            x: Math.round(rect.left + rect.width/2),
            y: Math.round(rect.top + rect.height/2),
            tag: el.tagName.toLowerCase(), name: el.name || '', checked: el.checked || false});
    }
    document.querySelectorAll('.LabelWrapper, .ChoiceStructure, .mat-radio-button, .mat-checkbox').forEach(function(el) {
        var inp = el.querySelector('input[type=radio], input[type=checkbox]');
        if (inp) add(el, inp.type==='radio'?(inp.checked?'radio-selected':'radio'):(inp.checked?'checkbox-selected':'checkbox'));
    });
    document.querySelectorAll('select').forEach(function(el) { add(el, 'select'); });
    document.querySelectorAll('input:not([type=hidden])').forEach(function(el) {
        var t=el.type||'text';
        if(t==='radio') add(el, el.checked?'radio-selected':'radio');
        else if(t==='checkbox') add(el, el.checked?'checkbox-selected':'checkbox');
        else if(t==='submit') add(el, 'submit');
        else add(el, 'input');
    });
    document.querySelectorAll('textarea').forEach(function(el) { add(el, 'textarea'); });
    document.querySelectorAll('button, [role=button]').forEach(function(el) {
        var txt=(el.innerText||'').toLowerCase();
        if(txt.includes('next')||txt.includes('weiter')||txt.includes('submit')||txt.includes('continue')) add(el, 'submit');
        else add(el, 'button');
    });
    document.querySelectorAll('label[for]').forEach(function(el) { add(el, 'label'); });
    out.sort(function(a,b){if(a.type==='submit'&&b.type!=='submit')return 1;if(b.type==='submit'&&a.type!=='submit')return -1;return a.y-b.y;});
    out.forEach(function(el,i){el.idx=i;});
    return {elements: out, url: window.location.href, title: document.title,
        bodyText: (document.body.innerText||'').substring(0,500)};
})();
"""


def snapshot(ws_url: str, timeout: int = 15) -> Dict[str, Any]:
    try:
        ws = websocket.create_connection(ws_url, timeout=timeout)
        ws.send(json.dumps({"id":1,"method":"Runtime.evaluate",
            "params":{"expression":EXTRACTOR_JS,"returnByValue":True}}))
        resp = json.loads(ws.recv())
        ws.close()
        data = resp.get("result",{}).get("result",{}).get("value",{})
        body_text = data.get("bodyText","")
        dom_hash = hashlib.md5(body_text.encode()).hexdigest()[:12]
        return {"elements": data.get("elements",[]), "url": data.get("url",""),
            "title": data.get("title",""), "hash": dom_hash}
    except Exception as e:
        return {"elements":[], "url":"", "title":"", "hash":"error", "error": str(e)}


def find_submit(elements: List[Dict]) -> Optional[Dict]:
    for el in elements:
        if el.get("type") == "submit":
            return el
    return None


def find_unfilled(elements: List[Dict]) -> List[Dict]:
    return [el for el in elements if el.get("type") in ("input","textarea","radio","checkbox")]


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python tool_snapshot.py <ws_url>")
        sys.exit(1)
    data = snapshot(sys.argv[1])
    print("URL: " + data['url'])
    print("Hash: " + data['hash'])
    print("Elements (" + str(len(data['elements'])) + "):")
    for el in data["elements"]:
        print("  [{0}] {1}: {2}".format(el['idx'], el['type'], el['text'][:40]))
