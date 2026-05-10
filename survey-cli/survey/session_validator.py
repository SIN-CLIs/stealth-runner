"""Session Validator — Reusable session validation for HeyPiggy surveys.

PROBLEM:
  After Chrome restart, session cookies become invalid.
  Cookie backup becomes stale. Surveys fail because session is not valid.

SOLUTION:
  validate_session() checks if dashboard shows "Abmelden" (logged in).
  If NOT logged in: re-inject cookies from backup OR trigger fresh Google login.
  Returns True if session is valid, False otherwise.

ARCHITEKTUR:
  ┌──────────────────────────────────────────────────────────┐
  │  validate_session(port=9999)                             │
  │  1. Find dashboard tab (via Chrome CDP)                  │
  │  2. Read body.innerText via CDP Runtime.evaluate         │
  │  3. Check for "Abmelden" (logged in marker)              │
  │  4. If NOT logged in:                                    │
  │     a. Try re-injecting cookies from ~/.stealth/backup   │
  │     b. If injection fails: trigger google_login          │
  │  5. Return True/False                                    │
  └──────────────────────────────────────────────────────────┘

INTEGRATION POINTS:
  - runner.py: _pre_survey_cleanup() → validate before survey
  - runner.py: run_survey_loop() → validate before opening survey
  - opener.py: _open_in_dashboard_tab() → validate before navigation
  - opener.py: _open_in_page_modal() → validate before clicking card

COOKIE BACKUP:
  ~/.stealth/heypiggy-backup/heypiggy-cookies.json
  Structure: {"metadata": {...}, "cookies": [...]}
  Heypiggy-Cookies: PHPSESSID, user_session, user_id, user_a_b_group, lang_pig, g_state, referer

BANNED METHODS:
  ❌ pkill -f "Google Chrome" — tötet USER Chrome
  ❌ Hardcoded PIDs — dynamisch
  ❌ Frische /tmp/ Profile — Login nötig
"""

from __future__ import annotations

import json
import os
import time
from typing import Optional, Dict, Any

try:
    import websocket
except ImportError:
    websocket = None

import urllib.request

# ── Constants ────────────────────────────────────────────────────────────────

DEFAULT_COOKIE_BACKUP = os.path.expanduser("~/.stealth/heypiggy-backup/heypiggy-cookies.json")
LOGGED_IN_MARKER = "Abmelden"
LOGGED_OUT_MARKERS = ["anmelden", "einloggen", "login", "sign in"]


# ── Core Validation ──────────────────────────────────────────────────────────

def validate_session(
    port: int = 9999,
    cookie_backup: str = DEFAULT_COOKIE_BACKUP,
    auto_recover: bool = True,
) -> bool:
    """Check if HeyPiggy session is valid, optionally auto-recover.

    Args:
        port: Chrome CDP port (default: 9999)
        cookie_backup: Path to cookie backup file
        auto_recover: If True, try to recover session if invalid

    Returns:
        True if session is valid (logged in), False otherwise

    Raises:
        Nothing — all errors are handled internally, returns False on failure
    """
    if not websocket:
        return False

    # Step 1: Check current session state
    is_logged_in, dashboard_ws = _check_session_state(port)
    if is_logged_in:
        return True

    # Step 2: Session is invalid — try auto-recovery
    if not auto_recover:
        return False

    print(f"[SESSION] Not logged in — attempting recovery...")

    # Try 1: Re-inject cookies from backup
    if os.path.exists(cookie_backup):
        injected = _reinject_cookies(dashboard_ws, cookie_backup)
        if injected:
            # Verify injection worked
            time.sleep(2)
            is_logged_in, _ = _check_session_state(port)
            if is_logged_in:
                print("[SESSION] Cookies re-injected successfully — session recovered")
                return True

    # Try 2: Trigger fresh Google login
    print("[SESSION] Cookie injection failed — triggering fresh Google login...")
    recovered = _trigger_google_login(port)
    if recovered:
        print("[SESSION] Google login successful — session recovered")
        return True

    print("[SESSION] Recovery failed — session is invalid")
    return False


def is_session_valid(port: int = 9999) -> bool:
    """Quick check if session is valid (no auto-recovery).

    Use this for quick checks where you don't want side effects.

    Args:
        port: Chrome CDP port (default: 9999)

    Returns:
        True if logged in, False otherwise
    """
    is_logged_in, _ = _check_session_state(port)
    return is_logged_in


def get_session_status(port: int = 9999) -> Dict[str, Any]:
    """Get detailed session status.

    Returns:
        Dict with:
        - logged_in: bool — is the session valid?
        - dashboard_ws: str — dashboard WebSocket URL or empty
        - has_cookie_backup: bool — does backup file exist?
        - page_text_preview: str — first 200 chars of dashboard text
    """
    is_logged_in, dashboard_ws = _check_session_state(port)

    result: Dict[str, Any] = {
        "logged_in": is_logged_in,
        "dashboard_ws": dashboard_ws,
        "has_cookie_backup": os.path.exists(DEFAULT_COOKIE_BACKUP),
        "page_text_preview": "",
    }

    # Read page text for debugging
    if dashboard_ws and websocket:
        try:
            ws = websocket.create_connection(dashboard_ws, timeout=8)
            ws.send(json.dumps({
                "id": 0,
                "method": "Runtime.evaluate",
                "params": {
                    "expression": "document.body.innerText.slice(0, 200)",
                    "returnByValue": True,
                },
            }))
            r = json.loads(ws.recv())
            ws.close()
            result["page_text_preview"] = r.get("result", {}).get("result", {}).get("value", "")
        except Exception:
            pass

    return result


# ── Internal Helpers ─────────────────────────────────────────────────────────

def _check_session_state(port: int) -> tuple[bool, str]:
    """Check if dashboard shows 'Abmelden' (logged in) or 'Anmelden' (not).

    Returns:
        (is_logged_in, dashboard_ws_url)
    """
    if not websocket:
        return False, ""

    try:
        # Find dashboard tab
        pages = json.loads(
            urllib.request.urlopen(f"http://127.0.0.1:{port}/json", timeout=3).read()
        )

        for p in pages:
            url = p.get("url", "").lower()
            if "dashboard" not in url:
                continue

            ws_url = p.get("webSocketDebuggerUrl", "")
            if not ws_url:
                continue

            # Read page text
            ws = websocket.create_connection(ws_url, timeout=10)
            ws.send(json.dumps({
                "id": 0,
                "method": "Runtime.evaluate",
                "params": {
                    "expression": "document.body.innerText",
                    "returnByValue": True,
                },
            }))
            r = json.loads(ws.recv())
            ws.close()

            text = r.get("result", {}).get("result", {}).get("value", "")

            # Check for logged-in marker
            if LOGGED_IN_MARKER in text:
                return True, ws_url

            # Also return dashboard_ws so we can inject cookies if needed
            return False, ws_url

        return False, ""

    except Exception:
        return False, ""


def _reinject_cookies(dashboard_ws: str, cookie_backup: str) -> bool:
    """Re-inject heypiggy cookies from backup file.

    Args:
        dashboard_ws: WebSocket URL of dashboard tab
        cookie_backup: Path to cookie backup file

    Returns:
        True if injection succeeded, False otherwise
    """
    if not dashboard_ws or not websocket:
        return False

    try:
        # Load cookies from backup
        with open(cookie_backup, "r") as f:
            data = json.load(f)

        # Filter heypiggy cookies only
        all_cookies = data.get("cookies", [])
        heypiggy_cookies = [
            {
                "name": c["name"],
                "value": c["value"],
                "domain": c["domain"],
                "path": c.get("path", "/"),
                "expires": c.get("expires", -1),
                "secure": c.get("secure", False),
                "httpOnly": c.get("httpOnly", False),
            }
            for c in all_cookies
            if "heypiggy" in c.get("domain", "").lower()
        ]

        if not heypiggy_cookies:
            print(f"[SESSION] No heypiggy cookies found in {cookie_backup}")
            return False

        # Inject cookies via CDP Network.setCookies
        ws = websocket.create_connection(dashboard_ws, timeout=15)
        ws.send(json.dumps({
            "id": 1,
            "method": "Network.setCookies",
            "params": {"cookies": heypiggy_cookies},
        }))
        json.loads(ws.recv())
        ws.close()

        # Navigate to dashboard to refresh session
        ws2 = websocket.create_connection(dashboard_ws, timeout=15)
        ws2.send(json.dumps({
            "id": 2,
            "method": "Page.navigate",
            "params": {"url": "https://www.heypiggy.com/?page=dashboard"},
        }))
        json.loads(ws2.recv())
        ws2.close()

        print(f"[SESSION] Injected {len(heypiggy_cookies)} cookies from backup")
        return True

    except Exception as e:
        print(f"[SESSION] Cookie injection failed: {e}")
        return False


def _trigger_google_login(port: int) -> bool:
    """Trigger fresh Google login via auto_google_login module.

    Args:
        port: Chrome CDP port (unused, kept for future use)

    Returns:
        True if login succeeded, False otherwise
    """
    try:
        import sys
        from pathlib import Path

        # Add workspace root to sys.path (auto_google_login is in cli/modules)
        root = str(Path(__file__).parent.parent.parent)
        if root not in sys.path:
            sys.path.insert(0, root)

        from cli.modules.auto_google_login import execute as google_login

        result = google_login()
        return result.get("status") == "ok"

    except Exception as e:
        print(f"[SESSION] Google login failed: {e}")
        return False