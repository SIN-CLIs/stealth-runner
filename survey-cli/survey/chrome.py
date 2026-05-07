"""Chrome lifecycle — launch, connect, identify, kill.

RULES:
- NEVER kill user Chrome (no pkill, no killall)
- ONLY manage /tmp/heypiggy-bot-* profiles
- Use playstealth launch when available, fallback to raw subprocess
"""

import json
import os
import subprocess
import time
import urllib.request

# ── Constants ──────────────────────────────────────────

CPX_CREDENTIALS = {
    "app_id": "11644",
    "ext_user_id": "2525530",
    "secure_hash": "ae75b0feca27c0f8eb356d7117d978ec",
    "email": "zukunftsorientierte.energie@gmail.com",
}

DETAILS_URL = (
    "https://live-api.cpx-research.com/api/get-survey-details.php"
    "?output_method=jsscriptv1"
    f"&app_id={CPX_CREDENTIALS['app_id']}"
    f"&ext_user_id={CPX_CREDENTIALS['ext_user_id']}"
    f"&secure_hash={CPX_CREDENTIALS['secure_hash']}"
    f"&email={CPX_CREDENTIALS['email']}"
    "&extra_info_1=offerwall&main_info=true"
    "&extra_info_3=EUR&extra_info_4=nomobile"
)

_cached_details_url = None


def get_details_url(port=9999, force_refresh=False):
    """Get the live details_url from the dashboard page.

    The heypiggy dashboard maintains a `details_url` JS variable with
    the full CPX API URL including all session-specific parameters.
    This is more reliable than the hardcoded DETAILS_URL.

    Args:
        port: CDP port
        force_refresh: Force re-fetch from page

    Returns:
        Full CPX API URL string, or fallback to hardcoded DETAILS_URL
    """
    global _cached_details_url
    if _cached_details_url and not force_refresh:
        return _cached_details_url

    try:
        ws_url = find_dashboard_ws(port)
        if not ws_url:
            return DETAILS_URL

        import websocket
        ws = websocket.create_connection(ws_url, timeout=10)
        ws.send(json.dumps({
            "id": 0, "method": "Runtime.evaluate",
            "params": {"expression": "typeof details_url !== 'undefined' ? details_url : ''"}
        }))
        r = json.loads(ws.recv())
        ws.close()
        url = r.get("result", {}).get("result", {}).get("value", "")
        if url and url.startswith("https://"):
            _cached_details_url = url
            return url
    except Exception:
        pass
    return DETAILS_URL


# ── Chrome Management ──────────────────────────────────

def find_bot_pids():
    """Find ALL Chrome processes with bot profiles (safe)."""
    try:
        result = subprocess.run(
            ["ps", "aux"], capture_output=True, text=True, timeout=5
        )
        pids = []
        for line in result.stdout.split("\n"):
            if "/tmp/heypiggy-bot-" in line and "/Contents/MacOS/Google Chrome" in line:
                parts = line.split()
                if parts and parts[1].isdigit():
                    pids.append(int(parts[1]))
        return pids
    except Exception:
        return []


def find_bot_tabs(port=9999):
    """Find all tabs in bot Chrome."""
    try:
        pages = json.loads(urllib.request.urlopen(
            f"http://127.0.0.1:{port}/json", timeout=5
        ).read())
        return pages
    except Exception:
        return []


def find_dashboard_ws(port=9999):
    """Find WebSocket URL for a heypiggy dashboard tab."""
    for p in find_bot_tabs(port):
        if "dashboard" in p.get("url", "").lower():
            return p.get("webSocketDebuggerUrl")
    # Fallback: first tab
    pages = find_bot_tabs(port)
    if pages:
        return pages[0].get("webSocketDebuggerUrl")
    return None


def find_survey_tab(port=9999):
    """Find first non-dashboard survey tab."""
    for p in find_bot_tabs(port):
        url = p.get("url", "")
        if "dashboard" not in url and "rating" not in url:
            return p
    return None


def get_ws_for_tab(tab_id, port=9999):
    """Get WebSocket URL for a specific tab ID."""
    for p in find_bot_tabs(port):
        if p.get("id") == tab_id:
            return p.get("webSocketDebuggerUrl")
    return None


def is_chrome_alive(port=9999):
    """Check if bot Chrome is running with CDP enabled."""
    try:
        urllib.request.urlopen(f"http://127.0.0.1:{port}/json", timeout=3)
        return True
    except Exception:
        return False


def launch_chrome(url="https://www.heypiggy.com/?page=dashboard", port=9999):
    """Launch Chrome with BOTH --force-renderer-accessibility AND --remote-allow-origins="*".

    ⚠️ UNVERBRÜCHLICHE REGEL: Chrome NUR mit diesen beiden Flags starten.
    --force-renderer-accessibility = cua-driver kann AX-Tree lesen
    --remote-allow-origins="*" = CDP WebSocket funktioniert
    Ohne diese Flags: Login UNMÖGLICH. Surveys UNMÖGLICH.
    """
    profile_dir = f"/tmp/heypiggy-new-{int(time.time())}"
    cmd = [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        f"--remote-debugging-port={port}",
        "--remote-allow-origins=*",
        "--force-renderer-accessibility",
        "--no-first-run",
        "--no-default-browser-check",
        f"--user-data-dir={profile_dir}",
        url,
    ]
    subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print(f"[CHROME] Launched: port={port}, profile={profile_dir}, accessibility=ON, cdp=ON")
    time.sleep(8)
    return {"pid": None, "port": port, "profile": profile_dir}


def create_tab(url, port=9999):
    """Create a new browser tab via CDP WebSocket.

    Uses Target.createTarget through an existing WebSocket connection.
    Does NOT use HTTP API (which is unreliable across Chrome versions).
    """
    try:
        import websocket
        # Find any existing tab to get a WebSocket
        pages = find_bot_tabs(port)
        if not pages:
            return None
        ws_url = pages[0].get("webSocketDebuggerUrl")
        if not ws_url:
            return None

        ws = websocket.create_connection(ws_url, timeout=10)
        ws.send(json.dumps({
            "id": 1, "method": "Target.createTarget",
            "params": {"url": url}
        }))
        r = json.loads(ws.recv())
        ws.close()
        return r.get("result", {}).get("targetId")
    except Exception:
        return None


# ── Stealth Injection ───────────────────────────────────
STEALTH_DIR = os.path.join(os.path.dirname(__file__), "stealth")
STEALTH_BUNDLE = os.path.join(STEALTH_DIR, "injection.js")


def _get_stealth_js() -> str:
    """Load stealth injection bundle, or fallback to inline minimal overrides."""
    if os.path.exists(STEALTH_BUNDLE):
        try:
            with open(STEALTH_BUNDLE) as f:
                return f.read()
        except Exception:
            pass
    # Minimal fallback: hide automation flags
    return """/* Minimal stealth fallback */
Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
Object.defineProperty(navigator, 'languages', {get: () => ['de-DE', 'de', 'en-US', 'en']});
window.chrome = {runtime: {}};
"""


def create_blank_tab(port=9999):
    """Create a new browser tab at about:blank via CDP Target.createTarget.

    Unlike create_tab(), this creates the tab WITHOUT navigating to a URL.
    Use inject_stealth_to_tab() then navigate_tab() to set up the survey.

    Returns:
        dict with 'id' (targetId) and 'ws_url' (webSocketDebuggerUrl), or None
    """
    _cached_details_url = None  # noqa: F841
    try:
        import websocket
        pages = find_bot_tabs(port)
        if not pages:
            return None
        ws_url = pages[0].get("webSocketDebuggerUrl")
        if not ws_url:
            return None

        ws = websocket.create_connection(ws_url, timeout=10)
        ws.send(json.dumps({
            "id": 1, "method": "Target.createTarget",
            "params": {"url": "about:blank"}
        }))
        r = json.loads(ws.recv())
        ws.close()

        target_id = r.get("result", {}).get("targetId")
        if not target_id:
            return None

        # Get the new tab's WS URL
        for p in find_bot_tabs(port):
            if p.get("id") == target_id:
                return {"id": target_id, "ws_url": p.get("webSocketDebuggerUrl")}

        # Fallback: use Target.attachToTarget to get WS URL
        ws = websocket.create_connection(ws_url, timeout=10)
        ws.send(json.dumps({
            "id": 2, "method": "Target.attachToTarget",
            "params": {"targetId": target_id, "flatten": True}
        }))
        r = json.loads(ws.recv())
        ws.close()
        tab_ws_url = r.get("result", {}).get("webSocketDebuggerUrl", "")
        return {"id": target_id, "ws_url": tab_ws_url} if tab_ws_url else None

    except Exception:
        return None


def inject_stealth_to_tab(tab_ws_url: str) -> bool:
    """Inject stealth JS into a tab via Page.addScriptToEvaluateOnNewDocument.

    The script runs on EVERY document load in the tab, BEFORE any page JS.
    This ensures survey pages never see automation flags.

    Args:
        tab_ws_url: WebSocket debugger URL for the tab

    Returns:
        True if injection succeeded
    """
    stealth_js = _get_stealth_js()
    try:
        import websocket
        ws = websocket.create_connection(tab_ws_url, timeout=10)
        ws.send(json.dumps({
            "id": 1, "method": "Page.addScriptToEvaluateOnNewDocument",
            "params": {"source": stealth_js}
        }))
        resp = json.loads(ws.recv())
        ws.close()
        identifier = resp.get("result", {}).get("identifier")
        return identifier is not None
    except Exception:
        return False


def navigate_tab(tab_ws_url: str, url: str) -> bool:
    """Navigate a tab to a URL via Page.navigate.

    Args:
        tab_ws_url: WebSocket debugger URL for the tab
        url: URL to navigate to

    Returns:
        True if navigation was initiated
    """
    try:
        import websocket
        ws = websocket.create_connection(tab_ws_url, timeout=10)
        ws.send(json.dumps({
            "id": 1, "method": "Page.navigate",
            "params": {"url": url}
        }))
        resp = json.loads(ws.recv())
        ws.close()
        return resp.get("result", {}).get("frameId") is not None
    except Exception:
        return False


def safe_kill_bot():
    """Safely kill ONLY bot Chrome processes."""
    pids = find_bot_pids()
    if not pids:
        print("[CHROME] No bot Chrome processes found")
        return False
    for pid in pids:
        try:
            subprocess.run(["kill", str(pid)], timeout=5)
            print(f"[CHROME] Killed bot PID: {pid}")
        except Exception as e:
            print(f"[CHROME] Failed to kill {pid}: {e}")
    return True


# ── CPX API ────────────────────────────────────────────

def get_survey_url(survey_id, port=9999):
    """Get survey URL from CPX API using live details_url."""
    details = get_details_url(port)
    try:
        resp = json.loads(urllib.request.urlopen(
            details + "&survey_id=" + survey_id, timeout=8
        ).read())
        if resp.get("type") == "okay":
            return resp.get("href")
        return None
    except Exception:
        return None


def get_survey_details(survey_id, port=9999):
    """Get full survey details from CPX API using live details_url."""
    details = get_details_url(port)
    try:
        resp = json.loads(urllib.request.urlopen(
            details + "&survey_id=" + survey_id, timeout=8
        ).read())
        return resp
    except Exception:
        return {}
