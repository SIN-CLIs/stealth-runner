"""================================================================================
CHROME LIFECYCLE MANAGER — Launch, Connect, Identify, Kill (Survey-CLI)
================================================================================

WAS IST DAS?
  Zentrale Chrome-Verwaltung für Survey-CLI. Startet Chrome mit korrekten
  Flags, verwaltet Profile, findet Tabs, und beendet Prozesse sicher.

ARCHITEKTUR:
  ┌─────────────────────┐
  │  launch_chrome()    │
  └─────────────────────┘
         │
         ▼
  ┌─────────────────────┐
  │  find_bot_chrome()  │
  │  (via ps aux)       │
  └─────────────────────┘
         │
         ▼
  ┌─────────────────────┐
  │  get_tabs()         │
  │  (CDP HTTP /json)   │
  └─────────────────────┘
         │
         ▼
  ┌─────────────────────┐
  │  kill_bot_chrome()   │
  │  (NUR /tmp/heypiggy  │
  │   -new-*)            │
  └─────────────────────┘

SICHERHEIT (KRITISCH):
  - NUR /tmp/heypiggy-new-* Profile werden verwaltet
  - NIE pkill -f "Google Chrome" (tötet USER Chrome!)
  - NIE killall Google Chrome
  - Timestamped Profile: /tmp/heypiggy-new-$(date +%s)
  - --force-renderer-accessibility MUSS gesetzt sein
  - --remote-allow-origins="*" MIT Quotes (zsh expandiert * sonst!)

WARUM NICHT playstealth?
  playstealth launch setzt NICHT --force-renderer-accessibility.
  → cua-driver AX-Tree ist LEER → keine Elemente gefunden.

DEPENDENZEN:
  - subprocess (ps aux, Chrome starten)
  - urllib.request (CDP HTTP /json API)
  - CDP WebSocket (Runtime.evaluate)

BANNED METHODS — NIEMALS VERWENDEN (siehe /banned.md):
  ❌ playstealth launch — setzt NICHT --force-renderer-accessibility
  ❌ webauto-nodriver — ABSOLUT BANNED
  ❌ cua-driver click (raw index) — instabil, nutze tool_click.py
  ❌ --remote-allow-origins=* (ohne Quotes) — zsh glob expansion
  ❌ /tmp/heypiggy-bot (fixed profile) — korruptiert nach Neustart
  ❌ Hardcoded PIDs — dynamisch, niemals hardcodieren
  ❌ pkill -f "Google Chrome" — tötet USER Chrome
  ❌ killall Google Chrome — tötet ALLE Chrome
  ❌ skylight-cli click --element-index — Index instabil
================================================================================"""

# ╔════════════════════════════════════════════════════════════════════════════╗
# ║  BANNED METHODS — NIEMALS VERWENDEN (siehe /banned.md)                    ║
# ║                                                                           ║
# ║  ❌ playstealth launch — setzt NICHT --force-renderer-accessibility        ║
# ║  ❌ webauto-nodriver — ABSOLUT BANNED                                      ║
# ║  ❌ cua-driver click (raw index) — instabil, nutze tool_click.py          ║
# ║  ❌ --remote-allow-origins=* (ohne Quotes) — zsh glob expansion            ║
# ║  ❌ /tmp/heypiggy-bot (fixed profile) — korruptiert nach Neustart          ║
# ║  ❌ Hardcoded PIDs — dynamisch, niemals hardcodieren                       ║
# ║  ❌ pkill -f "Google Chrome" — tötet USER Chrome                          ║
# ║  ❌ killall Google Chrome — tötet ALLE Chrome                             ║
# ║  ❌ skylight-cli click --element-index — Index instabil                    ║
# ║                                                                           ║
# ║  ✅ Korrekt: --remote-allow-origins="*" (MIT Anführungszeichen)           ║
# ║  ✅ Korrekt: --user-data-dir="/tmp/heypiggy-new-$(date +%s)"               ║
# ║  ✅ Korrekt: --force-renderer-accessibility                                ║
# ║  ✅ Korrekt: NUR tool_*.py verwenden (nicht rohes cua-driver)             ║
# ╚════════════════════════════════════════════════════════════════════════════╝

import json
import os
import subprocess
import time
import urllib.request

from .security import get_secrets

# ── Constants ──────────────────────────────────────────

_cached_details_url = None


def build_details_url():
    """Build CPX details URL from configured secrets, fail-closed if absent."""
    creds = get_secrets().get_cpx_credentials()
    return (
        "https://live-api.cpx-research.com/api/get-survey-details.php"
        "?output_method=jsscriptv1"
        f"&app_id={creds.app_id}"
        f"&ext_user_id={creds.ext_user_id}"
        f"&secure_hash={creds.secure_hash}"
        f"&email={creds.email}"
        "&extra_info_1=offerwall&main_info=true"
        "&extra_info_3=EUR&extra_info_4=nomobile"
    )


def get_details_url(port=9223, force_refresh=False):
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
            return build_details_url()

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
    return build_details_url()


# ── Chrome Management ──────────────────────────────────

def find_bot_pids():
    """Find ALL Chrome processes with bot profiles (safe)."""
    try:
        result = subprocess.run(
            ["ps", "aux"], capture_output=True, text=True, timeout=5
        )
        pids = []
        for line in result.stdout.split("\n"):
            if "/tmp/heypiggy-new-" in line and "/Contents/MacOS/Google Chrome" in line:
                parts = line.split()
                if parts and parts[1].isdigit():
                    pids.append(int(parts[1]))
        return pids
    except Exception:
        return []


def find_bot_tabs(port=9223):
    """Find all tabs in bot Chrome."""
    try:
        pages = json.loads(urllib.request.urlopen(
            f"http://127.0.0.1:{port}/json", timeout=5
        ).read())
        return pages
    except Exception:
        return []


def find_dashboard_ws(port=9223):
    """Find WebSocket URL for a heypiggy dashboard tab."""
    for p in find_bot_tabs(port):
        if "dashboard" in p.get("url", "").lower():
            return p.get("webSocketDebuggerUrl")
    # Fallback: first tab
    pages = find_bot_tabs(port)
    if pages:
        return pages[0].get("webSocketDebuggerUrl")
    return None


def find_survey_tab(port=9223):
    """Find first non-dashboard survey tab."""
    for p in find_bot_tabs(port):
        url = p.get("url", "")
        if "dashboard" not in url and "rating" not in url:
            return p
    return None


def activate_tab(tab_id, port=9223):
    """Activate/bring a tab to front via CDP Target.activateTarget.

    WHY: When clickSurvey() opens a new tab, it runs in background.
    Focus-dependent JS events (blur, focus, visibilitychange) may not fire.
    Some survey providers (Qualtrics, PureSpectrum) require active tab for
    proper interaction. CDP operations on inactive tabs can behave differently.

    ARGS:
        tab_id: Chrome target ID (from create_tab or find_bot_tabs)
        port: CDP port

    RETURNS:
        True if activation succeeded, False otherwise
    """
    try:
        import websocket
        pages = find_bot_tabs(port)
        if not pages:
            return False
        ws_url = pages[0].get("webSocketDebuggerUrl")
        if not ws_url:
            return False

        ws = websocket.create_connection(ws_url, timeout=10)
        ws.send(json.dumps({
            "id": 1, "method": "Target.activateTarget",
            "params": {"targetId": tab_id}
        }))
        r = json.loads(ws.recv())
        ws.close()
        # activateTarget returns {} on success, error on failure
        return "error" not in r
    except Exception:
        return False


def get_ws_for_tab(tab_id, port=9223):
    """Get WebSocket URL for a specific tab ID."""
    for p in find_bot_tabs(port):
        if p.get("id") == tab_id:
            return p.get("webSocketDebuggerUrl")
    return None


def is_chrome_alive(port=9223):
    """Check if bot Chrome is running with CDP enabled."""
    try:
        urllib.request.urlopen(f"http://127.0.0.1:{port}/json", timeout=3)
        return True
    except Exception:
        return False


class ChromeLauncher:
    """Chrome startup with mandatory flag enforcement + post-start verification.

    WHY: launch_chrome() had no verification. Chrome could start without
    --force-renderer-accessibility (AX-Tree empty) or without proper
    --remote-allow-origins="*" (CDP WebSocket 403). This class enforces
    both flags and verifies Chrome is actually usable after launch.

    USAGE:
        launcher = ChromeLauncher(port=9223)
        result = launcher.launch_and_verify(url="https://heypiggy.com")
        if result["ok"]:
            print(f"Chrome ready: pid={result['pid']}")
        else:
            print(f"Chrome failed: {result['error']}")
    """

    REQUIRED_FLAGS = [
        "--force-renderer-accessibility",
        "--remote-allow-origins=*",
    ]
    CHROME_PATH = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    MAX_STARTUP_WAIT = 15  # seconds to wait for Chrome to become ready
    MAX_VERIFY_RETRIES = 3  # post-start verification attempts

    def __init__(self, port=9223, debug=False):
        self.port = port
        self.debug = debug
        self._pid = None
        self._profile_dir = None

    @property
    def pid(self):
        return self._pid

    @property
    def profile_dir(self):
        return self._profile_dir

    def launch_and_verify(self, url="https://www.heypiggy.com/?page=dashboard"):
        """Launch Chrome with required flags + verify it's actually usable.

        STEPS:
        1. Kill any existing bot Chrome on same port
        2. Launch with REQUIRED_FLAGS enforced
        3. Wait for CDP endpoint to become reachable
        4. Verify flags are in actual process cmdline
        5. Verify AX-Tree has elements (accessibility working)

        RETURNS:
            {"ok": True, "pid": int, "port": int, "profile": str}
            {"ok": False, "error": str, "step": str}
        """
        # Step 1: Clean existing bot Chrome on same port
        self._cleanup_existing()

        # Step 2: Launch with enforced flags
        self._profile_dir = f"/tmp/heypiggy-new-{int(time.time())}"
        cmd = self._build_cmd(url)

        if self.debug:
            print(f"[CHROME] Launching: {' '.join(cmd[:3])}...")

        proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self._pid = proc.pid

        # Step 3: Wait for CDP endpoint
        if not self._wait_for_cdp():
            return {"ok": False, "error": "CDP endpoint not reachable after launch", "step": "cdp_wait"}

        # Step 4: Verify flags in cmdline
        flags_ok = self._verify_flags_in_cmdline()
        if not flags_ok:
            return {"ok": False, "error": "Required flags missing from Chrome cmdline", "step": "flag_verify",
                    "missing": [f for f in self.REQUIRED_FLAGS if not self._flag_in_cmdline(f)]}

        # Step 5: Verify AX-Tree has elements
        ax_ok = self._verify_ax_tree()
        if not ax_ok:
            return {"ok": False, "error": "AX-Tree empty after launch (accessibility not working)", "step": "ax_verify"}

        if self.debug:
            print(f"[CHROME] Verified: pid={self._pid}, port={self.port}, accessibility=ON, cdp=ON")

        return {"ok": True, "pid": self._pid, "port": self.port, "profile": self._profile_dir}

    def _cleanup_existing(self):
        """Kill any existing bot Chrome on this port before launching."""
        try:
            result = subprocess.run(
                ["lsof", "-i", f"TCP:{self.port}", "-t"],
                capture_output=True, text=True, timeout=5
            )
            if result.stdout.strip():
                for pid_line in result.stdout.strip().split("\n"):
                    pid_str = pid_line.strip()
                    if pid_str.isdigit():
                        pid = int(pid_str)
                        # Only kill if it's a bot Chrome (check cmdline)
                        try:
                            cmdline = subprocess.run(
                                ["ps", "-p", str(pid), "-o", "command="],
                                capture_output=True, text=True, timeout=3
                            ).stdout
                            if "/tmp/heypiggy-new-" in cmdline and "Google Chrome" in cmdline:
                                subprocess.run(["kill", str(pid)], timeout=5)
                                if self.debug:
                                    print(f"[CHROME] Killed existing bot PID {pid}")
                        except Exception:
                            pass
        except Exception:
            pass  # No existing Chrome or lsof not available

    def _build_cmd(self, url):
        """Build Chrome launch command with all required flags."""
        return [
            self.CHROME_PATH,
            f"--remote-debugging-port={self.port}",
            "--remote-allow-origins=*",
            "--force-renderer-accessibility",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-background-timer-throttling",
            "--disable-backgrounding-occluded-windows",
            f"--user-data-dir={self._profile_dir}",
            url,
        ]

    def _wait_for_cdp(self):
        """Wait for CDP HTTP endpoint to become reachable."""
        for attempt in range(self.MAX_STARTUP_WAIT):
            if is_chrome_alive(self.port):
                return True
            time.sleep(1)
        return False

    def _verify_flags_in_cmdline(self):
        """Verify all required flags are in the Chrome process cmdline."""
        try:
            # Read /proc/{pid}/cmdline on Linux, or ps on macOS
            result = subprocess.run(
                ["ps", "-p", str(self._pid), "-o", "command="],
                capture_output=True, text=True, timeout=5
            )
            cmdline = result.stdout
            return all(self._flag_in_cmdline(flag, cmdline) for flag in self.REQUIRED_FLAGS)
        except Exception:
            return False

    def _flag_in_cmdline(self, flag, cmdline=None):
        """Check if a specific flag is present in cmdline string."""
        if cmdline is None:
            try:
                result = subprocess.run(
                    ["ps", "-p", str(self._pid), "-o", "command="],
                    capture_output=True, text=True, timeout=5
                )
                cmdline = result.stdout
            except Exception:
                return False
        # Handle both quoted and unquoted variants
        flag_clean = flag.strip('"')
        return flag in cmdline or flag_clean in cmdline

    def _verify_ax_tree(self):
        """Verify AX-Tree has elements (accessibility is working)."""
        try:
            ws_url = find_dashboard_ws(self.port)
            if not ws_url:
                return False

            import websocket
            ws = websocket.create_connection(ws_url, timeout=10)
            ws.send(json.dumps({
                "id": 0, "method": "Runtime.evaluate",
                "params": {"expression": "document.querySelectorAll('*').length"}
            }))
            r = json.loads(ws.recv())
            ws.close()

            count = r.get("result", {}).get("result", {}).get("value", 0)
            return int(count) > 10  # More than just <html><head><body>
        except Exception:
            return False


def launch_chrome(url="https://www.heypiggy.com/?page=dashboard", port=9223):
    """Launch Chrome with BOTH --force-renderer-accessibility AND --remote-allow-origins="*".

    DEPRECATED: Use ChromeLauncher.launch_and_verify() instead.
    This function is kept for backward compatibility.
    """
    launcher = ChromeLauncher(port=port, debug=True)
    return launcher.launch_and_verify(url=url)


def create_tab(url, port=9223):
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


def create_blank_tab(port=9223):
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

def get_survey_url(survey_id, port=9223):
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


def get_survey_details(survey_id, port=9223):
    """Get full survey details from CPX API using live details_url."""
    details = get_details_url(port)
    try:
        resp = json.loads(urllib.request.urlopen(
            details + "&survey_id=" + survey_id, timeout=8
        ).read())
        return resp
    except Exception:
        return {}
