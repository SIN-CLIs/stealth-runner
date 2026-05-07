#!/usr/bin/env python3
"""
================================================================================
TOOL: close_modals
================================================================================
Schliesst alle sichtbaren Modals, Overlays, Popups.
Muss VOR Survey-Start aufgerufen werden!

BEREITS FUNKTIONIERT: ✓ Getestet mit Heypiggy, Qualtrics, PureSpectrum

USAGE:
    from tools.tool_close_modals import close_modals
    closed_count = close_modals(ws_url)

NICHT AENDERN! Dieser Flow funktioniert.
================================================================================
"""

import json
import websocket

__version__ = "1.0.0"
__frozen__ = True


def close_modals(ws_url: str, timeout: int = 10) -> int:
    js = """
    (function() {
        var closed = 0;
        var closeTexts = ['Schließen','Close','x','X','Ablehnen','Dismiss',
            'Cancel','Abbrechen','No thanks','Nein danke','Nein','No',
            'Spater','Later','Skip','Uberspringen'];
        document.querySelectorAll('button, span, div[role="button"], a, [class*="close"]').forEach(function(el) {
            var text = (el.textContent || el.innerText || '').trim();
            var ariaLabel = el.getAttribute('aria-label') || '';
            for (var i = 0; i < closeTexts.length; i++) {
                if (text === closeTexts[i] || ariaLabel.includes(closeTexts[i])) {
                    try { el.click(); closed++; } catch(e) {}
                    break;
                }
            }
        });
        document.querySelectorAll('.modal-backdrop, .overlay, [class*="backdrop"], [class*="overlay"]').forEach(function(el) {
            try { el.click(); closed++; } catch(e) {}
        });
        document.dispatchEvent(new KeyboardEvent('keydown', {key:'Escape',keyCode:27,bubbles:true}));
        document.querySelectorAll('[class*="cookie"] button,[id*="cookie"] button').forEach(function(el) {
            var t = (el.innerText||'').toLowerCase();
            if (t.includes('accept')||t.includes('akzept')||t.includes('ablehnen')||t.includes('reject')) {
                try { el.click(); closed++; } catch(e) {}
            }
        });
        return closed;
    })();
    """
    try:
        ws = websocket.create_connection(ws_url, timeout=timeout)
        ws.send(json.dumps({"id":1,"method":"Runtime.evaluate",
            "params":{"expression":js,"returnByValue":True}}))
        resp = json.loads(ws.recv())
        ws.close()
        result = resp.get("result",{}).get("result",{}).get("value",0)
        return result if isinstance(result, int) else 0
    except Exception:
        return 0


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python tool_close_modals.py <ws_url>")
        sys.exit(1)
    r = close_modals(sys.argv[1])
    print("Closed {0} modals".format(r))
