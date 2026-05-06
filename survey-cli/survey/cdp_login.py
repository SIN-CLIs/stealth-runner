"""CDP Google Login — Fallback when cua-driver AX-Tree is empty.

Uses CDP Runtime.evaluate + Input.dispatchMouseEvent for all steps.
Handles Passkey via CDP (clicks "Passwort eingeben" as fallback).

Usage:
    from survey.cdp_login import cdp_login
    result = cdp_login(port=9999)
"""

import json
import time
import urllib.request
import websocket

EMAIL = "zukunftsorientierte.energie@gmail.com"


def _click(ws, x, y):
    """CDP mouse click at coordinates."""
    for et in ["mouseMoved", "mousePressed", "mouseReleased"]:
        ws.send(json.dumps({"id": 0, "method": "Input.dispatchMouseEvent",
            "params": {"type": et, "x": x, "y": y, "button": "left", "clickCount": 1}}))
        json.loads(ws.recv())
        time.sleep(0.1)


def _js(ws, expression):
    """Execute JS via Runtime.evaluate."""
    ws.send(json.dumps({"id": 0, "method": "Runtime.evaluate",
        "params": {"expression": expression}}))
    r = json.loads(ws.recv())
    return r.get("result", {}).get("result", {}).get("value", "")


def _find_google_tab(port):
    """Find Google OAuth tab URL."""
    pages = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{port}/json").read())
    for p in pages:
        url = p.get("url", "")
        if "accounts.google" in url and "CheckConnection" not in url:
            return p["webSocketDebuggerUrl"]
    return None


def cdp_login(port=9999):
    """Full CDP Google OAuth login.

    Returns:
        {"status": "ok"} or {"status": "error", "reason": "..."}
    """
    try:
        pages = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{port}/json").read())
        dash_ws = None
        for p in pages:
            if "heypiggy" in p.get("url", "").lower():
                dash_ws = p["webSocketDebuggerUrl"]
                break
        if not dash_ws:
            return {"status": "error", "reason": "Dashboard not found"}

        # STEP 1: Click Google login SVG at (775, 480)
        print("[CDP-LOGIN] Clicking Google login...")
        ws = websocket.create_connection(dash_ws, timeout=10)
        _click(ws, 775, 480)
        ws.close()
        time.sleep(5)

        # STEP 2: Fill email on Google OAuth page
        google_ws = _find_google_tab(port)
        if not google_ws:
            return {"status": "error", "reason": "Google OAuth tab not found"}

        ws = websocket.create_connection(google_ws, timeout=10)
        _js(ws, f"var e=document.querySelector('input[type=email]');if(e){{e.value='{EMAIL}';e.dispatchEvent(new Event('input',{{bubbles:true}}));e.dispatchEvent(new Event('change',{{bubbles:true}}));}}")
        ws.close()
        time.sleep(1)

        # Click Weiter
        ws = websocket.create_connection(google_ws, timeout=10)
        pos = _js(ws, "var b=document.querySelector('button');if(b){var r=b.getBoundingClientRect();return JSON.stringify({x:r.x+r.width/2,y:r.y+r.height/2});}return'{}';")
        ws.close()
        pos = json.loads(pos) if isinstance(pos, str) else pos
        if pos.get("x"):
            ws = websocket.create_connection(google_ws, timeout=10)
            _click(ws, pos["x"], pos["y"])
            ws.close()
        print("[CDP-LOGIN] Email filled, Weiter clicked")
        time.sleep(5)

        # STEP 3: Handle Passkey / Password fallback
        google_ws = _find_google_tab(port)
        if not google_ws:
            return {"status": "error", "reason": "Google tab lost"}

        ws = websocket.create_connection(google_ws, timeout=10)
        text = _js(ws, "document.body.innerText.substring(0,300)")
        ws.close()

        # If passkey screen, click "Weiter" at documented position
        if "Identität" in text or "bestätigt" in text:
            ws = websocket.create_connection(google_ws, timeout=10)
            _click(ws, 1095, 753)  # Documented Weiter position
            ws.close()
            time.sleep(5)

        # Check for alternative login screen
        google_ws = _find_google_tab(port)
        if google_ws:
            ws = websocket.create_connection(google_ws, timeout=10)
            text = _js(ws, "document.body.innerText.substring(0,500)")
            ws.close()

            # If "Passkey verwenden" visible
            if "Passkey verwenden" in text:
                ws = websocket.create_connection(google_ws, timeout=10)
                pos = _js(ws, "var all=document.querySelectorAll('*');for(var i=0;i<all.length;i++){if((all[i].textContent||'').trim()==='Passkey verwenden'){var r=all[i].getBoundingClientRect();return JSON.stringify({x:r.x+r.width/2,y:r.y+r.height/2});}}return'{}';")
                ws.close()
                pos = json.loads(pos) if isinstance(pos, str) else pos
                if pos.get("x"):
                    ws = websocket.create_connection(google_ws, timeout=10)
                    _click(ws, pos["x"], pos["y"])
                    ws.close()
                    time.sleep(8)

            # Click Fortfahren if visible
            google_ws = _find_google_tab(port)
            if google_ws:
                ws = websocket.create_connection(google_ws, timeout=10)
                # Try to find and click any Weiter/Fortfahren button
                for btn_text in ["Fortfahren", "Weiter", "Next", "Continue"]:
                    pos = _js(ws, f"var all=document.querySelectorAll('*');for(var i=0;i<all.length;i++){{if((all[i].textContent||'').trim()==='{btn_text}'){{var r=all[i].getBoundingClientRect();return JSON.stringify({{x:r.x+r.width/2,y:r.y+r.height/2}});}}}}return'{{}}';")
                    pos = json.loads(pos) if isinstance(pos, str) else pos
                    if pos.get("x"):
                        _click(ws, pos["x"], pos["y"])
                        time.sleep(5)
                        break
                ws.close()

        # STEP 4: Verify login
        time.sleep(5)
        pages = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{port}/json").read())
        for p in pages:
            if "heypiggy" in p.get("url", "").lower() and "dashboard" in p.get("url", "").lower():
                ws = websocket.create_connection(p["webSocketDebuggerUrl"], timeout=10)
                text = _js(ws, "document.body.innerText.substring(0,300)")
                ws.close()
                logged_in = "Abmelden" in text and "Umfragen" in text
                if logged_in:
                    print("[CDP-LOGIN] ✅ SUCCESS")
                    return {"status": "ok"}
                break

        return {"status": "error", "reason": "Login verification failed"}

    except Exception as e:
        return {"status": "error", "reason": str(e)[:200]}
