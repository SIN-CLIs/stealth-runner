#!/usr/bin/env python3
"""
================================================================================
TOOL: detect_completion
================================================================================
Erkennt ob Survey abgeschlossen oder Screen-Out.
Prueft URL, Title UND Body Text!

BEREITS FUNKTIONIERT: ✓ Getestet mit Qualtrics, Heypiggy

USAGE:
    from tools.tool_detect_completion import detect
    status = detect(ws_url)  # "completed" | "screen_out" | "running"

NICHT AENDERN! Dieser Flow funktioniert.
================================================================================
"""

import json
import websocket
from typing import Literal

__version__ = "1.0.0"
__frozen__ = True


COMPLETION_MARKERS = [
    "vielen dank", "danke fuer", "gutgeschrieben", "abgeschlossen",
    "thank you for completing", "survey complete", "you have completed",
    "your response has been recorded", "successfully submitted",
    "zurueck zur website", "zurueck zum panel", "end of survey",
    "survey is now complete", "completed successfully", "fertig",
    "ihre antwort wurde gespeichert", "response recorded"
]

SCREEN_OUT_MARKERS = [
    "not eligible", "nicht qualifiziert", "quota full", "quote erreicht",
    "screened out", "sorry, you", "unfortunately", "leider",
    "disqualified", "do not qualify", "qualifizieren sich nicht",
    "survey is closed", "umfrage geschlossen", "nicht teilnehmen"
]

DASHBOARD_MARKERS = [
    "heypiggy.com", "prolific.co/submissions", "mturk.com/mturk/preview"
]


def detect(ws_url: str, timeout: int = 10) -> str:
    js = """
    (function() {
        return {
            url: window.location.href.toLowerCase(),
            title: document.title.toLowerCase(),
            text: (document.body.innerText || '').toLowerCase().substring(0, 2000)
        };
    })();
    """
    try:
        ws = websocket.create_connection(ws_url, timeout=timeout)
        ws.send(json.dumps({"id":1,"method":"Runtime.evaluate",
            "params":{"expression":js,"returnByValue":True}}))
        resp = json.loads(ws.recv())
        ws.close()
        data = resp.get("result",{}).get("result",{}).get("value",{})
        url = data.get("url","")
        title = data.get("title","")
        text = data.get("text","")
        combined = url + " " + title + " " + text

        for marker in DASHBOARD_MARKERS:
            if marker in url:
                return "completed"
        if any(m in url for m in ["complete","success","finished","done","thankyou"]):
            return "completed"
        for marker in SCREEN_OUT_MARKERS:
            if marker in combined:
                return "screen_out"
        for marker in COMPLETION_MARKERS:
            if marker in combined:
                return "completed"
        return "running"
    except Exception:
        return "running"


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python tool_detect_completion.py <ws_url>")
        sys.exit(1)
    r = detect(sys.argv[1])
    print("Status: " + r)
