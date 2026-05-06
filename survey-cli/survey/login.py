"""Google OAuth login via CDP WebSocket.

Uses Keychain auto-fill. No passwords stored in code.
6-step verified flow (PID 71104, 2026-05-05).
"""

import json
import time
import websocket
from . import chrome


def execute(port=9999, url="https://www.heypiggy.com/?page=dashboard"):
    """Execute full Google OAuth login flow.

    Returns:
        {"status": "ok", "pid": X, "wid": Y} or {"status": "error", "reason": "..."}
    """
    ws_url = chrome.find_dashboard_ws(port)
    if not ws_url:
        # Try launching Chrome
        chrome.launch_chrome(url=url, port=port)
        ws_url = chrome.find_dashboard_ws(port)
        if not ws_url:
            return {"status": "error", "reason": "chrome_launch_failed"}

    # Check if already logged in
    if _check_logged_in(ws_url):
        return {"status": "ok", "message": "already_logged_in"}

    # Step 1: Click Google Login symbol
    # The Google login is an AXLink in the browser content
    # We navigate via CDP to trigger login
    _navigate_and_wait(ws_url, "https://accounts.google.com/signin/oauth/identifier")

    # Step 2-6: Full OAuth flow via CDP JS
    try:
        ws = websocket.create_connection(ws_url, timeout=15)

        # Check if email field exists
        email_js = '''
(function() {
    var el = document.querySelector('input[type=email], input[name=identifier], #identifierId');
    if (el) {
        el.value = 'zukunftsorientierte.energie@gmail.com';
        el.dispatchEvent(new Event('input', {bubbles: true}));
        el.dispatchEvent(new Event('change', {bubbles: true}));
        return 'email_filled';
    }
    return 'no_email_field';
})()
'''
        ws.send(json.dumps({
            "id": 0, "method": "Runtime.evaluate",
            "params": {"expression": email_js}
        }))
        result = json.loads(ws.recv())
        status = result.get("result", {}).get("result", {}).get("value", "")
        ws.close()

        if status == "email_filled":
            # Click Next button
            ws = websocket.create_connection(ws_url, timeout=15)
            ws.send(json.dumps({
                "id": 0, "method": "Runtime.evaluate",
                "params": {"expression": '''
(function() {
    var btn = document.querySelector('#identifierNext button, [jscontroller=soHxf]');
    if (btn) { btn.click(); return 'clicked_next'; }
    return 'no_next_button';
})()
'''
                }
            }))
            json.loads(ws.recv())
            ws.close()
            time.sleep(3)

        # Wait for Keychain auto-fill or password page
        time.sleep(5)

        # Check if we're on password page or already logged in
        ws = websocket.create_connection(ws_url, timeout=15)
        ws.send(json.dumps({
            "id": 0, "method": "Runtime.evaluate",
            "params": {"expression": '''
(function() {
    var body = document.body.innerText;
    if (body.includes('Jeremy Schulze') || body.includes('zukunftsorientierte')) {
        // Click Continue
        var btn = document.querySelector('#passwordNext button, [jscontroller=soHxf]');
        if (btn) { btn.click(); return 'clicked_continue'; }
        return 'already_logged_in';
    }
    return 'waiting';
})()
'''
            }
        }))
        result = json.loads(ws.recv())
        ws.close()
        time.sleep(3)

    except Exception as e:
        return {"status": "error", "reason": str(e)[:200]}

    # Navigate to dashboard
    ws = websocket.create_connection(ws_url, timeout=15)
    ws.send(json.dumps({
        "id": 0, "method": "Runtime.evaluate",
        "params": {"expression": "document.location.href='https://www.heypiggy.com/?page=dashboard'"}
    }))
    json.loads(ws.recv())
    ws.close()
    time.sleep(3)

    # Verify login
    if _check_logged_in(chrome.find_dashboard_ws(port)):
        return {"status": "ok", "pid": 0, "wid": 0}
    return {"status": "error", "reason": "login_verification_failed"}


def _check_logged_in(ws_url):
    """Check if ACTUALLY logged in to heypiggy dashboard.

    Must see 'Abmelden' AND 'Erhebungen' AND a balance amount.
    The landing page has none of these.
    """
    try:
        ws = websocket.create_connection(ws_url, timeout=10)
        ws.send(json.dumps({
            "id": 0, "method": "Runtime.evaluate",
            "params": {
                "expression": "document.body.innerText"
            }
        }))
        r = json.loads(ws.recv())
        ws.close()
        text = r.get("result", {}).get("result", {}).get("value", "")
        # Must have ALL three indicators
        has_logout = "Abmelden" in text
        has_surveys = "Erhebungen" in text or "Umfragen" in text
        has_balance = bool(re.search(r'\d+[.,]\d+\s*\n?\s*€', text))
        return has_logout and has_surveys and has_balance
    except Exception:
        return False


def _navigate_and_wait(ws_url, target_url):
    """Navigate to URL and wait for page load."""
    try:
        ws = websocket.create_connection(ws_url, timeout=15)
        ws.send(json.dumps({
            "id": 0, "method": "Runtime.evaluate",
            "params": {"expression": f"document.location.href='{target_url}'"}
        }))
        json.loads(ws.recv())
        ws.close()
        time.sleep(5)
    except Exception:
        pass
