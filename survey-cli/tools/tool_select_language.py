#!/usr/bin/env python3
"""
================================================================================
TOOL: select_language
================================================================================
Waehlt Sprache auf Qualtrics Language Page.
Handled sowohl <select> Dropdowns als auch Radio Buttons.

BEREITS FUNKTIONIERT: ✓ Getestet mit Qualtrics DE/EN

USAGE:
    from tools.tool_select_language import select_language
    result = select_language(ws_url, "Deutsch")
    result = select_language(ws_url, "English")

NICHT AENDERN! Dieser Flow funktioniert.
================================================================================
"""

import json
import websocket
from typing import Dict, Any

__version__ = "1.0.0"
__frozen__ = True


def select_language(ws_url: str, language: str = "Deutsch", timeout: int = 10) -> Dict[str, Any]:
    lang_lower = language.lower()
    
    js = """
    (function() {
        var lang = '%s';
        
        var selects = document.querySelectorAll('select');
        for (var i = 0; i < selects.length; i++) {
            var sel = selects[i];
            for (var j = 0; j < sel.options.length; j++) {
                if (sel.options[j].text.toLowerCase().includes(lang)) {
                    sel.selectedIndex = j;
                    sel.dispatchEvent(new Event('change', {bubbles: true}));
                    return {success: true, method: 'select', value: sel.options[j].text};
                }
            }
        }
        
        var containers = document.querySelectorAll(
            '.LabelWrapper, .ChoiceStructure, label, [role=radio], ' +
            '.mat-radio-button, .q-radio'
        );
        for (var i = 0; i < containers.length; i++) {
            var text = (containers[i].innerText || '').toLowerCase();
            if (text.includes(lang)) {
                containers[i].click();
                var inp = containers[i].querySelector('input[type=radio]');
                if (inp) inp.click();
                return {success: true, method: 'radio', value: text.trim()};
            }
        }
        
        var all = document.querySelectorAll('*');
        for (var i = 0; i < all.length; i++) {
            var el = all[i];
            if (el.children.length === 0) {
                var t = (el.innerText || '').toLowerCase().trim();
                if (t === lang || t.includes(lang)) {
                    el.click();
                    return {success: true, method: 'text_match', value: t};
                }
            }
        }
        
        return {success: false, error: 'Language not found: ' + lang};
    })();
    """ % lang_lower
    
    try:
        ws = websocket.create_connection(ws_url, timeout=timeout)
        ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate",
            "params": {"expression": js, "returnByValue": True}}))
        resp = json.loads(ws.recv())
        ws.close()
        result = resp.get("result", {}).get("result", {}).get("value", {})
        return result if result else {"success": False, "error": "No result"}
    except Exception as e:
        return {"success": False, "error": str(e)}


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python tool_select_language.py <ws_url> [language]")
        sys.exit(1)
    ws_url = sys.argv[1]
    lang = sys.argv[2] if len(sys.argv) > 2 else "Deutsch"
    r = select_language(ws_url, lang)
    print(json.dumps(r, indent=2))
