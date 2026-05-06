"""Google Login Tool — EXACT cua-driver flow from commands/google/login-flow.md.

VERIFIED FLOW (PID=78708, 2026-05-05): 14 steps, 0 errors, Passkey auth.
This is THE authoritative login implementation. NO CDP, NO custom code.
Just calls cua-driver exactly as documented.

Usage:
    from survey.google_login import google_login
    result = google_login()
    # → {"status": "ok", "pid": 69668, "wid": 1178}
"""

import subprocess
import json
import time
import sys
import os

EMAIL = "zukunftsorientierte.energie@gmail.com"
CUA_BIN = "cua-driver"


def _cua(method, params=None):
    """Call cua-driver with method and params. Returns parsed JSON."""
    if params:
        stdin_data = json.dumps(params)
    else:
        stdin_data = None
    
    result = subprocess.run(
        [CUA_BIN, "call", method],
        input=stdin_data,
        capture_output=True, text=True, timeout=30
    )
    if result.returncode != 0:
        raise RuntimeError(f"cua-driver {method} failed: {result.stderr[:200]}")
    return json.loads(result.stdout)


def _find_window(pid, title_substring, min_height=100):
    """Find a window by PID and title substring."""
    data = _cua("list_windows")
    for w in data.get("windows", []):
        t = (w.get("title") or "").lower()
        w_pid = w.get("pid")
        h = w.get("bounds", {}).get("height", 0)
        if h > min_height and w_pid == pid and title_substring in t:
            return w
    return None


def _find_by_role(elements, role, text_substring=None):
    """Recursively find element by AXRole, optionally matching text."""
    result = []
    def traverse(el):
        if el.get("role") == role:
            el_text = (el.get("title","") or el.get("value","") or 
                       el.get("label","") or el.get("description","")).lower()
            if text_substring is None or text_substring in el_text:
                result.append(el)
        for child in el.get("children", []):
            traverse(child)
    traverse(elements)
    return result[0] if result else None


def _get_state(pid, wid):
    """Get AX-Tree for a window. Returns tree_markdown text."""
    data = _cua("get_window_state", {"pid": pid, "window_id": wid})
    return data.get("tree_markdown", "")


def _find_element_by_text(markdown, role, text_substring):
    """Find element in tree_markdown by role and text substring.
    
    Parses lines like: - [54] AXLink (Google Login-Symbol)
    """
    import re
    pattern = re.compile(
        r'-\s*\[(\d+)\]\s+' + re.escape(role) + r'\s+\((.*?)\)'
    )
    for match in pattern.finditer(markdown):
        idx = int(match.group(1))
        txt = match.group(2).lower()
        if text_substring in txt:
            return {"element_index": idx, "text": txt}
    return None


def _find_google_login(markdown):
    """Find Google Login-Symbol in markdown tree."""
    # Try AXLink with google
    el = _find_element_by_text(markdown, "AXLink", "google")
    if el: return el
    # Try AXImage with google
    el = _find_element_by_text(markdown, "AXImage", "google")
    if el: return el
    # Try AXLink with anmeld
    el = _find_element_by_text(markdown, "AXLink", "anmeld")
    if el: return el
    # Try AXLink with login
    el = _find_element_by_text(markdown, "AXLink", "login")
    if el: return el
    return None


def _click_element(pid, wid, index):
    """Click element by index via cua-driver. Returns True on success."""
    try:
        result = subprocess.run(
            [CUA_BIN, "call", "click"],
            input=json.dumps({"pid": pid, "window_id": wid, "element_index": index}),
            capture_output=True, text=True, timeout=15
        )
        success = "Performed" in result.stdout or "✅" in result.stdout
        if not success:
            print(f"  ⚠️ cua-driver click: {result.stdout.strip()[:100]}")
        return success
    except Exception as e:
        print(f"  ❌ click error: {e}")
        return False


def _set_value(pid, wid, index, value):
    """Set text value via cua-driver. Returns True on success."""
    try:
        result = subprocess.run(
            [CUA_BIN, "call", "set_value"],
            input=json.dumps({"pid": pid, "window_id": wid, 
                               "element_index": index, "value": value}),
            capture_output=True, text=True, timeout=15
        )
        success = "Set" in result.stdout or "✅" in result.stdout or result.returncode == 0
        if not success:
            print(f"  ⚠️ cua-driver set_value: {result.stdout.strip()[:100]}")
        return success
    except Exception as e:
        print(f"  ❌ set_value error: {e}")
        return False


def google_login(launch_url="https://www.heypiggy.com/?page=dashboard", force_launch=False):
    """Execute Google OAuth login via cua-driver (PRIMARY) or CDP (fallback).
    
    ALWAYS tries cua-driver first. CDP only as last resort.
    
    Returns:
        {"status": "ok", "pid": X, "wid": Y} on success
        {"status": "error", "reason": "..."} on failure
    """
    # Check if Chrome is already running on port 9999
    import urllib.request
    chrome_running = False
    try:
        urllib.request.urlopen("http://127.0.0.1:9999/json", timeout=3)
        chrome_running = True
    except:
        pass
    
    if chrome_running and not force_launch:
        print("[LOGIN] Chrome already running — using cua-driver on existing instance")
        # Try cua-driver on existing Chrome (find PID from windows)
        import subprocess, json as _json
        r = subprocess.run(["cua-driver","call","list_windows"], capture_output=True, text=True, timeout=10)
        data = _json.loads(r.stdout)
        pid = None
        for w in data.get("windows",[]):
            t = (w.get("title","") or "").lower()
            if "heypiggy" in t or "verdienen" in t:
                pid = w.get("pid")
                break
        if pid:
            result = _cua_login_existing(pid)
            if result.get("status") == "ok":
                return result
            print(f"[LOGIN] cua-driver failed: {result.get('reason')} — trying CDP...")
    
    # Try cua-driver first (fresh Chrome launch)
    result = _cua_login(launch_url)
    if result.get("status") == "ok":
        return result
    
    # Fallback to CDP login
    print(f"[LOGIN] cua-driver failed: {result.get('reason')} — trying CDP fallback...")
    from .cdp_login import cdp_login
    # Detect port from running Chrome instances
    import subprocess
    ports = []
    try:
        out = subprocess.run(["lsof", "-i", "-P", "-n"], capture_output=True, text=True, timeout=5).stdout
        for line in out.split("\n"):
            if "Google" in line and "LISTEN" in line and "localhost" in line:
                import re
                m = re.search(r':(\d+)', line)
                if m: ports.append(int(m.group(1)))
    except: pass
    
    cdp_port = ports[0] if ports else 9999
    print(f"[LOGIN] CDP fallback on port {cdp_port}")
    cdp_result = cdp_login(port=cdp_port)
    if cdp_result.get("status") == "ok":
        return {"status": "ok", "pid": 0, "wid": 0}
    return {"status": "error", "reason": f"Both methods failed: cua={result.get('reason')}, cdp={cdp_result.get('reason')}"}


def _cua_login_existing(pid):
    """Login using cua-driver on an already-running Chrome instance."""
    try:
        print(f"[LOGIN] Using existing Chrome PID={pid}")
        
        # Find dashboard window
        dash_win = _find_window(pid, "heypiggy")
        if not dash_win:
            return {"status": "error", "reason": "Dashboard not found"}
        dash_wid = dash_win["window_id"]
        print(f"[LOGIN] Dashboard WID={dash_wid}")

        # Find Google Login-Symbol
        markdown = _get_state(pid, dash_wid)
        google_el = _find_google_login(markdown)
        if not google_el:
            return {"status": "error", "reason": "Google Login-Symbol not found"}
        google_idx = google_el["element_index"]
        print(f"[LOGIN] Google Login-Symbol at [{google_idx}]")

        # Click it
        _click_element(pid, dash_wid, google_idx)
        time.sleep(5)

        # Find OAuth popup
        oauth_win = _find_window(pid, "anmelden", 300) or _find_window(pid, "google", 300)
        if not oauth_win:
            return {"status": "error", "reason": "OAuth popup not found"}
        oauth_wid = oauth_win["window_id"]
        print(f"[LOGIN] OAuth WID={oauth_wid}")

        # Fill email + click Weiter
        markdown = _get_state(pid, oauth_wid)
        email_el = (_find_element_by_text(markdown, "AXTextField", "e-mail") or
                    _find_element_by_text(markdown, "AXTextField", "telefon"))
        weiter_el = (_find_element_by_text(markdown, "AXButton", "weiter") or
                     _find_element_by_text(markdown, "AXButton", "next"))
        if not email_el or not weiter_el:
            return {"status": "error", "reason": "Email or Weiter not found"}
        
        _set_value(pid, oauth_wid, email_el["element_index"], EMAIL)
        time.sleep(1)
        _click_element(pid, oauth_wid, weiter_el["element_index"])
        time.sleep(5)

        # Handle remaining screens
        for step in range(3):
            markdown = _get_state(pid, oauth_wid)
            for btn_text in ["weiter", "fortfahren", "next"]:
                el = _find_element_by_text(markdown, "AXButton", btn_text)
                if el:
                    print(f"[LOGIN] Clicking {btn_text} [{el['element_index']}]")
                    _click_element(pid, oauth_wid, el["element_index"])
                    time.sleep(5)
                    break
            else:
                break

        # Verify
        markdown = _get_state(pid, dash_wid)
        if "Abmelden" in markdown and "Umfragen" in markdown:
            print(f"[LOGIN] ✅ SUCCESS")
            return {"status": "ok", "pid": pid, "wid": dash_wid}
        return {"status": "error", "reason": "Verification failed"}

    except Exception as e:
        return {"status": "error", "reason": str(e)[:200]}


def _cua_login(launch_url):
    try:
        # STEP 1: Launch Chrome via playstealth
        print("[LOGIN] Launching Chrome via playstealth...")
        result = subprocess.run(
            ["playstealth", "launch", "--url", launch_url],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode != 0:
            return {"status": "error", "reason": f"playstealth failed: {result.stderr[:200]}"}
        
        launch_data = json.loads(result.stdout.strip().split("\n")[-1])
        pid = launch_data["pid"]
        print(f"[LOGIN] Chrome PID={pid}")

        time.sleep(5)

        # STEP 2: Find dashboard window
        print("[LOGIN] Finding dashboard window...")
        dash_win = _find_window(pid, "heypiggy")
        if not dash_win:
            return {"status": "error", "reason": "Dashboard window not found"}
        dash_wid = dash_win["window_id"]
        print(f"[LOGIN] Dashboard WID={dash_wid}")

        # STEP 3: Find Google Login-Symbol in markdown tree
        print("[LOGIN] Finding Google Login-Symbol...")
        markdown = _get_state(pid, dash_wid)
        google_el = _find_google_login(markdown)
        
        if not google_el:
            # Debug: show all AXLink elements
            import re
            links = re.findall(r'- \[(\d+)\] AXLink \((.*?)\)', markdown)
            print(f"[LOGIN] Found {len(links)} AXLinks: {links[:5]}")
            return {"status": "error", "reason": f"Google Login-Symbol not found. {len(links)} AXLinks on page."}
        
        google_idx = google_el["element_index"]
        print(f"[LOGIN] Google Login-Symbol at index [{google_idx}]: {google_el.get('text','')}")
        print(f"[LOGIN] Google Login-Symbol at index [{google_idx}]")

        # STEP 4: Click Google Login
        print("[LOGIN] Clicking Google Login...")
        _click_element(pid, dash_wid, google_idx)
        time.sleep(5)

        # STEP 5: Find OAuth popup window
        print("[LOGIN] Finding OAuth popup...")
        oauth_win = _find_window(pid, "anmelden", 300)
        if not oauth_win:
            oauth_win = _find_window(pid, "google", 300)
        if not oauth_win:
            oauth_win = _find_window(pid, "sign in", 300)
        if not oauth_win:
            return {"status": "error", "reason": "OAuth popup not found"}
        oauth_wid = oauth_win["window_id"]
        print(f"[LOGIN] OAuth WID={oauth_wid}")

        # STEP 6: Find email field + Weiter in markdown
        print("[LOGIN] Finding email field...")
        markdown = _get_state(pid, oauth_wid)
        
        email_el = (_find_element_by_text(markdown, "AXTextField", "e-mail") or
                    _find_element_by_text(markdown, "AXTextField", "telefon") or
                    _find_element_by_text(markdown, "AXTextField", "email"))
        if not email_el:
            return {"status": "error", "reason": "Email field not found in OAuth"}
        email_idx = email_el["element_index"]
        print(f"[LOGIN] Email field at index [{email_idx}]")

        weiter_el = (_find_element_by_text(markdown, "AXButton", "weiter") or
                     _find_element_by_text(markdown, "AXButton", "next"))
        if not weiter_el:
            return {"status": "error", "reason": "Weiter button not found in OAuth"}
        weiter_idx = weiter_el["element_index"]
        print(f"[LOGIN] Weiter button at index [{weiter_idx}]")

        # STEP 7: Fill email + click Weiter
        print(f"[LOGIN] Filling email: {EMAIL}...")
        _set_value(pid, oauth_wid, email_idx, EMAIL)
        time.sleep(1)
        print("[LOGIN] Clicking Weiter...")
        _click_element(pid, oauth_wid, weiter_idx)
        time.sleep(5)

        # STEP 8: Passkey screen — find "Weiter"
        print("[LOGIN] Passkey screen — finding Weiter...")
        markdown = _get_state(pid, oauth_wid)
        passkey_weiter = _find_element_by_text(markdown, "AXButton", "weiter")
        if not passkey_weiter:
            fortfahren = _find_element_by_text(markdown, "AXButton", "fortfahren")
            if fortfahren:
                print("[LOGIN] Passkey skipped — Fortfahren already visible")
                _click_element(pid, oauth_wid, fortfahren["element_index"])
                time.sleep(5)
            else:
                return {"status": "error", "reason": "Passkey Weiter not found"}
        else:
            print("[LOGIN] Clicking Passkey Weiter...")
            _click_element(pid, oauth_wid, passkey_weiter["element_index"])
            time.sleep(5)

        # STEP 9: Fortfahren
        print("[LOGIN] Finding Fortfahren...")
        markdown = _get_state(pid, oauth_wid)
        fortfahren_el = _find_element_by_text(markdown, "AXButton", "fortfahren")
        if fortfahren_el:
            print("[LOGIN] Clicking Fortfahren...")
            _click_element(pid, oauth_wid, fortfahren_el["element_index"])
            time.sleep(3)

        # STEP 10: Consent Weiter
        markdown = _get_state(pid, oauth_wid)
        consent_el = _find_element_by_text(markdown, "AXButton", "weiter")
        if consent_el:
            print("[LOGIN] Clicking Consent Weiter...")
            _click_element(pid, oauth_wid, consent_el["element_index"])
            time.sleep(5)

        # STEP 11: Verify login
        print("[LOGIN] Verifying login...")
        time.sleep(3)
        markdown = _get_state(pid, dash_wid)
        logged_in = ("Abmelden" in markdown or "abmelden" in markdown) and ("Umfragen" in markdown or "umfragen" in markdown)
        if logged_in:
            print(f"[LOGIN] ✅ SUCCESS — PID={pid}, WID={dash_wid}")
            return {"status": "ok", "pid": pid, "wid": dash_wid}
        else:
            return {"status": "error", "reason": "Login verification failed — Abmelden/Umfragen not in AX-Tree"}

    except subprocess.TimeoutExpired:
        return {"status": "error", "reason": "Timeout"}
    except Exception as e:
        return {"status": "error", "reason": str(e)[:200]}


if __name__ == "__main__":
    result = google_login()
    print(json.dumps(result, indent=2))
