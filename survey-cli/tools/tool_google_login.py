"""
===============================================================================
SURVEY TOOL: Google Login (ATOMAR, __frozen__=True)
===============================================================================

REGEL: Dieses Tool ist FROZEN — NICHT ändern wenn es funktioniert!

Usage:
    from tools.tool_google_login import login
    result = login()
    # → {"status": "ok", "pid": X, "wid": Y}
    # → {"status": "error", "reason": "..."}

Ablauf (single call):
    1. verify_invariants() → cua-driver daemon, Chrome auf 9999, Accessibility
    2. check_logged_in() → CDP body text scan, "Abmelden" + "Umfragen"
    3. if not logged in: cua_login() → Google OAuth flow
    4. verify() → AX-Tree check für "Abmelden" + "Umfragen"
    5. return {"status": "ok", "pid": X, "wid": Y}

Chrome Flags (UNVERBRÜCHLICH):
    --remote-debugging-port=9999
    --remote-allow-origins=*
    --force-renderer-accessibility

BANNED:
    - webauto-nodriver
    - playstealth launch (setzt nicht beide Flags!)
    - User Chrome Profile
===============================================================================
"""

from __future__ import annotations
import subprocess
import json
import time
import re
import urllib.request
import websocket
from typing import Dict, Optional

__frozen__ = True
__version__ = "2026-05-07"

# ── Constants ──────────────────────────────────────────────────────────────

EMAIL = "zukunftsorientierte.energie@gmail.com"
CUA_BIN = "cua-driver"
CDP_PORT = 9999


# ═══════════════════════════════════════════════════════════════════════════
# STEP 1: INVARIANTS — verify preconditions
# ═══════════════════════════════════════════════════════════════════════════

def _verify_invariants() -> bool:
    """Verify cua-driver daemon, Chrome on 9999, Accessibility enabled."""
    errors = []

    # 1. cua-driver daemon
    try:
        r = subprocess.run(["pgrep", "-f", "cua-driver serve"],
                          capture_output=True, text=True, timeout=5)
        if not r.stdout.strip():
            errors.append("cua-driver daemon NOT running — run: nohup cua-driver serve &")
    except Exception as e:
        errors.append(f"Cannot check cua-driver: {e}")

    # 2. Chrome on port 9999
    try:
        urllib.request.urlopen(f"http://127.0.0.1:{CDP_PORT}/json", timeout=3)
    except Exception:
        errors.append(f"Chrome NOT on port {CDP_PORT} — start with --remote-debugging-port={CDP_PORT}")

    # 3. Accessibility (AX-Tree has >100 elements)
    try:
        r = subprocess.run([CUA_BIN, "call", "list_windows"],
                          capture_output=True, text=True, timeout=10)
        data = json.loads(r.stdout)
        chrome_found = False
        for w in data.get("windows", []):
            title = str(w.get("title", "")).lower()
            if any(k in title for k in ["heypiggy", "verdienen", "google"]):
                chrome_found = True
                pid, wid = w.get("pid"), w.get("window_id")
                r2 = subprocess.run([CUA_BIN, "call", "get_window_state"],
                    input=json.dumps({"pid": pid, "window_id": wid}),
                    capture_output=True, text=True, timeout=10)
                state = json.loads(r2.stdout)
                if state.get("element_count", 0) < 100:
                    errors.append(f"Chrome AX-Tree has only {state.get('element_count',0)} elements — Accessibility NOT enabled")
                break
        if not chrome_found:
            errors.append("Chrome window not found in cua-driver list_windows")
    except Exception as e:
        errors.append(f"Cannot verify Accessibility: {e}")

    if errors:
        print("[LOGIN] ❌ INVARIANT CHECK FAILED:")
        for e in errors:
            print(f"  - {e}")
        return False
    print("[LOGIN] ✅ All invariants verified")
    return True


# ═══════════════════════════════════════════════════════════════════════════
# STEP 2: CHECK LOGGED IN — CDP body text scan
# ═══════════════════════════════════════════════════════════════════════════

def _check_logged_in() -> Dict[str, Optional[int]]:
    """CDP check: scan body text for Abmelden + Umfragen. Returns pid/wid."""
    try:
        pages = json.loads(urllib.request.urlopen(
            f"http://127.0.0.1:{CDP_PORT}/json", timeout=3).read())
        for p in pages:
            if "heypiggy" in p.get("url", "").lower():
                ws = websocket.create_connection(p["webSocketDebuggerUrl"], timeout=10)
                ws.send(json.dumps({"id": 0, "method": "Runtime.evaluate",
                    "params": {"expression": "document.body.innerText.substring(0,300)"}}))
                r = json.loads(ws.recv()); ws.close()
                text = r.get("result", {}).get("result", {}).get("value", "")
                if "Abmelden" in text and any(k in text for k in ["Umfragen", "Erhebungen", "Auszahlung"]):
                    print("[LOGIN] Already logged in (CDP check)")
                    return {"status": "ok", "pid": 0, "wid": 0}
    except Exception:
        pass
    return None


# ═══════════════════════════════════════════════════════════════════════════
# STEP 3: CUA LOGIN FLOW — Google OAuth via cua-driver
# ═══════════════════════════════════════════════════════════════════════════

def _cua(method: str, params: Optional[Dict] = None) -> Dict:
    """Call cua-driver. Returns parsed JSON."""
    stdin = json.dumps(params) if params else None
    result = subprocess.run([CUA_BIN, "call", method],
                           input=stdin, capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        raise RuntimeError(f"cua-driver {method} failed: {result.stderr[:200]}")
    return json.loads(result.stdout)


def _find_window(pid: int, title_sub: str, min_height: int = 100) -> Optional[Dict]:
    """Find window by PID + title substring."""
    data = _cua("list_windows")
    for w in data.get("windows", []):
        t = (w.get("title") or "").lower()
        if w.get("pid") == pid and w.get("bounds", {}).get("height", 0) > min_height and title_sub in t:
            return w
    return None


def _get_state(pid: int, wid: int) -> str:
    """Get tree_markdown for window."""
    return _cua("get_window_state", {"pid": pid, "window_id": wid}).get("tree_markdown", "")


def _find_el(markdown: str, role: str, text_sub: str) -> Optional[Dict]:
    """Find element [idx] Role "text" in markdown."""
    pattern = re.compile(r'-\s*\[(\d+)\]\s+' + re.escape(role) + r'\s+[\(""](' + re.escape(text_sub) + r')')
    for m in pattern.finditer(markdown):
        return {"element_index": int(m.group(1)), "text": m.group(2)}
    # Fallback: partial match
    pattern2 = re.compile(r'-\s*\[(\d+)\]\s+' + re.escape(role) + r'\s+[\(""]([^\)""]+)')
    for m in pattern2.finditer(markdown):
        if text_sub.lower() in m.group(2).lower():
            return {"element_index": int(m.group(1)), "text": m.group(2)}
    return None


def _click(pid: int, wid: int, idx: int) -> bool:
    try:
        result = subprocess.run([CUA_BIN, "call", "click"],
            input=json.dumps({"pid": pid, "window_id": wid, "element_index": idx}),
            capture_output=True, text=True, timeout=15)
        return "Performed" in result.stdout or "✅" in result.stdout
    except:
        return False


def _set_value(pid: int, wid: int, idx: int, value: str) -> bool:
    try:
        result = subprocess.run([CUA_BIN, "call", "set_value"],
            input=json.dumps({"pid": pid, "window_id": wid, "element_index": idx, "value": value}),
            capture_output=True, text=True, timeout=15)
        return result.returncode == 0
    except:
        return False


def _do_login(pid: int, dash_wid: int) -> Dict:
    """Execute Google OAuth login flow. Returns result dict."""
    try:
        markdown = _get_state(pid, dash_wid)

        # Already logged in?
        if "Abmelden" in markdown and any(k in markdown for k in ["Umfragen", "Auszahlung"]):
            print(f"[LOGIN] Already logged in — PID={pid}, WID={dash_wid}")
            return {"status": "ok", "pid": pid, "wid": dash_wid}

        # Find Google Login-Symbol
        google_el = (_find_el(markdown, "AXLink", "google") or
                     _find_el(markdown, "AXImage", "google") or
                     _find_el(markdown, "AXLink", "anmeld") or
                     _find_el(markdown, "AXLink", "login"))
        if not google_el:
            links = re.findall(r'-\s*\[(\d+)\]\s+AXLink\s+\("([^"]+)"', markdown)
            print(f"[LOGIN] Google-Symbol not found. AXLinks: {links[:5]}")
            return {"status": "error", "reason": f"Google Login-Symbol not found. {len(links)} AXLinks."}
        g_idx = google_el["element_index"]
        print(f"[LOGIN] Google Login at [{g_idx}]")

        # Click Google
        if not _click(pid, dash_wid, g_idx):
            return {"status": "error", "reason": "Google Login click failed"}
        time.sleep(5)

        # Find OAuth popup
        oauth_win = (_find_window(pid, "anmelden", 300) or
                     _find_window(pid, "google", 300) or
                     _find_window(pid, "sign in", 300))
        if not oauth_win:
            return {"status": "error", "reason": "OAuth popup not found"}
        oauth_wid = oauth_win["window_id"]
        print(f"[LOGIN] OAuth WID={oauth_wid}")

        # Fill email + Weiter
        markdown = _get_state(pid, oauth_wid)
        email_el = (_find_el(markdown, "AXTextField", "e-mail") or
                    _find_el(markdown, "AXTextField", "telefon") or
                    _find_el(markdown, "AXTextField", "email"))
        weiter_el = (_find_el(markdown, "AXButton", "weiter") or
                     _find_el(markdown, "AXButton", "next"))
        if not email_el or not weiter_el:
            return {"status": "error", "reason": "Email/Weiter not found in OAuth"}
        _set_value(pid, oauth_wid, email_el["element_index"], EMAIL)
        time.sleep(1)
        if not _click(pid, oauth_wid, weiter_el["element_index"]):
            return {"status": "error", "reason": "Weiter click failed"}
        time.sleep(5)

        # Passkey + Fortfahren + Consent
        for _ in range(3):
            markdown = _get_state(pid, oauth_wid)
            for btn_text in ["weiter", "fortfahren", "next"]:
                el = _find_el(markdown, "AXButton", btn_text)
                if el:
                    print(f"[LOGIN] Clicking {btn_text} [{el['element_index']}]")
                    _click(pid, oauth_wid, el["element_index"])
                    time.sleep(5)
                    break
            else:
                break

        # Verify
        time.sleep(3)
        markdown = _get_state(pid, dash_wid)
        if "Abmelden" in markdown and any(k in markdown for k in ["Umfragen", "umfragen"]):
            print(f"[LOGIN] ✅ SUCCESS — PID={pid}, WID={dash_wid}")
            return {"status": "ok", "pid": pid, "wid": dash_wid}
        return {"status": "error", "reason": "Verification failed — Abmelden/Umfragen not in AX-Tree"}

    except Exception as e:
        return {"status": "error", "reason": str(e)[:200]}


# ═══════════════════════════════════════════════════════════════════════════
# MAIN ENTRY — SINGLE FUNCTION
# ═══════════════════════════════════════════════════════════════════════════

def login(launch_url: str = "https://www.heypiggy.com/?page=dashboard",
          force: bool = False) -> Dict:
    """Single atomic Google OAuth login for heypiggy.com.

    Usage:
        from tools.tool_google_login import login
        result = login()
        # → {"status": "ok", "pid": X, "wid": Y}
        # → {"status": "error", "reason": "..."}

    Args:
        launch_url: URL to open after Chrome launch
        force: Force fresh Chrome launch (ignore existing)

    Returns:
        {"status": "ok", "pid": int, "wid": int} or {"status": "error", "reason": str}
    """
    # Step 1: Verify invariants
    if not _verify_invariants():
        return {"status": "error", "reason": "Invariant check failed — see errors above"}

    # Step 2: CDP check for already logged in
    if not force:
        result = _check_logged_in()
        if result:
            return result

    # Step 3: Use existing Chrome (find PID)
    try:
        r = subprocess.run([CUA_BIN, "call", "list_windows"],
                          capture_output=True, text=True, timeout=10)
        data = json.loads(r.stdout)
        pid = next((w.get("pid") for w in data.get("windows", [])
                   if any(k in (w.get("title") or "").lower()
                          for k in ["heypiggy", "verdienen"])), None)
        if pid:
            dash_win = _find_window(pid, "heypiggy")
            if dash_win:
                result = _do_login(pid, dash_win["window_id"])
                if result.get("status") == "ok":
                    return result

        # Step 4: Launch fresh Chrome
        print("[LOGIN] Launching Chrome with flags...")
        subprocess.run(["pkill", "-f", "Google Chrome"], capture_output=True)
        time.sleep(3)
        subprocess.Popen([
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            f"--remote-debugging-port={CDP_PORT}",
            "--remote-allow-origins=*",
            "--force-renderer-accessibility",
            "--no-first-run",
            "--user-data-dir=/tmp/heypiggy-bot",
            launch_url,
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(8)

        r = subprocess.run([CUA_BIN, "call", "list_windows"],
                          capture_output=True, text=True, timeout=10)
        data = json.loads(r.stdout)
        pid = next((w.get("pid") for w in data.get("windows", [])
                   if any(k in (w.get("title") or "").lower()
                          for k in ["heypiggy", "verdienen"])), None)
        if not pid:
            return {"status": "error", "reason": "Chrome PID not found after launch"}

        dash_win = _find_window(pid, "heypiggy")
        if not dash_win:
            return {"status": "error", "reason": "Dashboard not found"}

        result = _do_login(pid, dash_win["window_id"])
        if result.get("status") == "ok":
            return result

        # Step 5: CDP fallback
        print(f"[LOGIN] cua-driver failed: {result.get('reason')} — CDP fallback...")
        from survey.cdp_login import cdp_login
        cdp_result = cdp_login(port=CDP_PORT)
        if cdp_result.get("status") == "ok":
            return {"status": "ok", "pid": 0, "wid": 0}
        return {"status": "error",
                "reason": f"Both methods failed: cua={result.get('reason')}, cdp={cdp_result.get('reason')}"}

    except Exception as e:
        return {"status": "error", "reason": str(e)[:200]}


# ── CLI entry ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    result = login()
    print(json.dumps(result, indent=2))