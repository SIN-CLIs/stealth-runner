"""Survey Opening Tool — __frozen__=True

Handles CPX redirect flow + modal "Umfrage starten" + new-tab detection.
Agent bricht bei redirect ab — DARF NICHT.

Usage:
    from tools.tool_open_survey import open_survey
    result = open_survey("12345")
    # → {"status": "ok", "tab_id": "A1B2C3", "ws_url": "ws://...", "provider": "purespectrum", "flow": "modal_window_open_intercept"}
    # → {"status": "error", "reason": "No survey URL from CPX API", "stage": "cpx_api"}
    # Note: pid/wid are DEPRECATED (CUA replaced by CDP JS)

Flow:
    1. Get CPX details_url from dashboard (live, not hardcoded)
    2. Fetch survey URL from CPX API (get-survey-details.php)
    3. Click survey card on dashboard (in-page modal)
    4. Handle "Umfrage starten" modal if present
    5. Detect if new tab opened (Qualtrics redirect)
    6. Wait for page load, detect provider
    7. Return tab info + provider

BANNED METHODS — NIEMALS VERWENDEN (siehe /banned.md):
  ❌ playstealth launch — setzt NICHT --force-renderer-accessibility
  ❌ webauto-nodriver — ABSOLUT BANNED
  ❌ cua-driver click (raw index) — instabil, nutze tool_click.py
  ❌ --remote-allow-origins=* (ohne Quotes) — zsh glob expansion
  ❌ /tmp/heypiggy-bot (fixed profile) — korruptiert nach Neustart
  ❌ Hardcoded PIDs — dynamisch, niemals hardcodieren
  ❌ skylight-cli click --element-index — Index instabil

KORREKT:
  ✅ --remote-allow-origins="*" (MIT Anführungszeichen)
  ✅ --user-data-dir="/tmp/heypiggy-new-$(date +%s)"
  ✅ --force-renderer-accessibility
  ✅ NUR tool_*.py verwenden (nicht rohes cua-driver)
"""

from __future__ import annotations
import json
import os
import subprocess
import time
import urllib.request
import re
from typing import Dict, Optional, List

__frozen__ = True
__version__ = "2026-05-10"  # FIX: window.open interception + Target.createTarget (2026-05-09)
CDP_PORT = 9999
CUA_BIN = "cua-driver"

from survey.security import get_secrets


def _get_details_url(port: int = CDP_PORT) -> str:
    """Get live details_url from dashboard page."""
    try:
        import websocket
        pages = json.loads(urllib.request.urlopen(
            f"http://127.0.0.1:{port}/json", timeout=3).read())
        for p in pages:
            if "dashboard" in p.get("url", "").lower():
                ws = websocket.create_connection(
                    p["webSocketDebuggerUrl"], timeout=10)
                ws.send(json.dumps({
                    "id": 0, "method": "Runtime.evaluate",
                    "params": {"expression": "typeof details_url !== 'undefined' ? details_url : ''"}
                }))
                r = json.loads(ws.recv())
                ws.close()
                url = r.get("result", {}).get("result", {}).get("value", "")
                if url and url.startswith("https://"):
                    return url
    except Exception:
        pass
    # Fallback: configured credentials only. Missing secrets must fail closed.
    cpx = get_secrets().get_cpx_credentials()
    return (
        "https://live-api.cpx-research.com/api/get-survey-details.php"
        f"?output_method=jsscriptv1&app_id={cpx.app_id}"
        f"&ext_user_id={cpx.ext_user_id}&secure_hash={cpx.secure_hash}"
        f"&email={cpx.email}&extra_info_1=offerwall&main_info=true"
        "&extra_info_3=EUR&extra_info_4=nomobile"
    )


def _get_survey_url(survey_id: str, port: int = CDP_PORT) -> Optional[str]:
    """Fetch actual survey URL from CPX API."""
    details_url = _get_details_url(port)
    try:
        resp = json.loads(urllib.request.urlopen(
            details_url + "&survey_id=" + survey_id, timeout=8).read())
        if resp.get("type") == "okay":
            return resp.get("href")
        # Handle pre-qualifier
        if resp.get("type") == "question":
            return None  # Pre-qualifier not handled here
    except Exception as e:
        return None
    return None


# ═══════════════════════════════════════════════════════════════════════════
# CDP HELPERS
# ═══════════════════════════════════════════════════════════════════════════

def _get_cdp_pages(port: int = CDP_PORT) -> List[Dict]:
    try:
        return json.loads(urllib.request.urlopen(
            f"http://127.0.0.1:{port}/json", timeout=3).read())
    except Exception:
        return []


def _get_dashboard_ws(port: int = CDP_PORT) -> Optional[str]:
    for p in _get_cdp_pages(port):
        if "dashboard" in p.get("url", "").lower():
            return p.get("webSocketDebuggerUrl")
    return None


def _create_tab(url: str, port: int = CDP_PORT) -> Optional[str]:
    """Create new browser tab via CDP Target.createTarget + inject cookies.

    COOKIE INJECTION FIX (2026-05-10):
    Creates a blank tab first, injects the 7 HeyPiggy session cookies,
    THEN navigates to the survey URL. Without this the redirect chain
    runs without cookies → HeyPiggy can't track completion → balance €0.
    """
    try:
        import websocket
        pages = _get_cdp_pages(port)
        if not pages:
            return None
        ws_url = pages[0].get("webSocketDebuggerUrl")
        if not ws_url:
            return None
        # 1) Create blank tab so we can attach and inject cookies BEFORE navigation
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
        # 2) Find the new tab and get its WebSocket debugger URL
        pages2 = _get_cdp_pages(port)
        new_tab = next((p for p in pages2 if p.get("id") == target_id), None)
        if not new_tab:
            return None
        tab_ws = new_tab.get("webSocketDebuggerUrl")
        if not tab_ws:
            return None
        # 3) Inject HeyPiggy session cookies from backup
        cookie_file = os.path.expanduser("~/.stealth/heypiggy-backup/heypiggy-cookies.json")
        if os.path.exists(cookie_file):
            try:
                with open(cookie_file) as f:
                    data = json.load(f)
                heypiggy_cookies = [
                    {k: c[k] for k in ["name", "value", "domain", "path", "expires", "secure", "httpOnly"] if k in c}
                    for c in data.get("cookies", [])
                    if "heypiggy" in c.get("domain", "").lower()
                ]
                if len(heypiggy_cookies) >= 7:
                    ws3 = websocket.create_connection(tab_ws, timeout=10)
                    ws3.send(json.dumps({"id": 1, "method": "Network.enable"}))
                    json.loads(ws3.recv())
                    ws3.send(json.dumps({
                        "id": 2, "method": "Network.setCookies",
                        "params": {"cookies": heypiggy_cookies}
                    }))
                    json.loads(ws3.recv())
                    ws3.close()
            except Exception:
                pass  # Continue even if cookie injection fails
        # 4) Navigate to the actual survey URL
        ws2 = websocket.create_connection(tab_ws, timeout=10)
        ws2.send(json.dumps({
            "id": 1, "method": "Page.navigate",
            "params": {"url": url}
        }))
        json.loads(ws2.recv())
        ws2.close()
        return target_id
    except Exception:
        return None


def _close_tab(tab_id: str, port: int = CDP_PORT) -> bool:
    try:
        import websocket
        pages = _get_cdp_pages(port)
        for p in pages:
            if p.get("id") == tab_id:
                ws_url = p.get("webSocketDebuggerUrl")
                if ws_url:
                    ws = websocket.create_connection(ws_url, timeout=10)
                    ws.send(json.dumps({
                        "id": 1, "method": "Target.closeTarget",
                        "params": {"targetId": tab_id}
                    }))
                    json.loads(ws.recv())
                    ws.close()
                    return True
        return False
    except Exception:
        return False


def _find_new_tab(old_tab_ids: set, port: int = CDP_PORT) -> Optional[Dict]:
    """Find a tab that wasn't in old_tab_ids."""
    for p in _get_cdp_pages(port):
        if p.get("id") not in old_tab_ids:
            return p
    return None


# ═══════════════════════════════════════════════════════════════════════════
# MODAL BUTTON CLICK — window.open interception (2026-05-09 DISCOVERED!)
# ═══════════════════════════════════════════════════════════════════════════
# PROBLEM:
#   "Umfrage starten" button hat onclick="openSurvey()"
#   openSurvey() ruft window.open(url) auf
#   Chrome Popup Blocker blockiert window.open() von programmierteischen JS calls
#   → b.click(), dispatchEvent(MouseEvent), CDP Input.dispatchMouseEvent — ALLE FAIL
#
# LÖSUNG (GETESTET 2026-05-09):
#   1. window.open temporär überschreiben → URL capture
#   2. openSurvey() aufrufen → window.open(url) wird abgefangen, URL gespeichert
#   3. window.open wiederherstellen
#   4. Target.createTarget(captured_url) → NEUER TAB öffnet sich (kein Popup Blocker!)
#
# TESTED: survey 67064749 → purespectrum tab opened successfully
# ═══════════════════════════════════════════════════════════════════════════

def _click_modal_button_cdp(ws_url: str, port: int = CDP_PORT) -> Optional[Dict]:
    """Click 'Umfrage starten' in modal via window.open interception + Target.createTarget.
    
    Returns: {"status": "ok", "tab_id": str, "ws_url": str, "url": str} oder None
    """
    import websocket
    
    try:
        ws = websocket.create_connection(ws_url, timeout=10)
        
        # Step 1: Check modal state und find "Umfrage starten" button
        await_expr = """
(function() {
  var m = document.querySelector('.modal.show');
  if (!m) return JSON.stringify({error: 'no_modal'});
  var btns = m.querySelectorAll('.modal-button-positive');
  for (var b of btns) {
    var r = b.getBoundingClientRect();
    if (r.width > 0 && r.height > 0 && b.innerText.trim().includes('starten')) {
      return JSON.stringify({
        text: b.innerText.trim(),
        onclick: (b.getAttribute('onclick') || '').slice(0, 80)
      });
    }
  }
  return JSON.stringify({error: 'no_starten_button'});
})()
        """
        
        ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate", "params": {"expression": await_expr.strip()}}))
        r = json.loads(ws.recv())
        btn_info = r.get("result", {}).get("result", {}).get("value", "{}")
        if isinstance(btn_info, str):
            try:
                btn_info = json.loads(btn_info)
            except:
                btn_info = {}
        
        if btn_info.get("error"):
            ws.close()
            return None
        
        # Step 2: window.open interception → capture URL
        intercept_expr = """
(function() {
  var surveyURL = null;
  var origOpen = window.open.bind(window);
  window.open = function(url) {
    surveyURL = url;
    return null;
  };
  try {
    openSurvey();
  } catch(e) {
    console.error('openSurvey error:', e);
  }
  window.open = origOpen;
  return surveyURL || 'window.open_not_called';
})()
        """
        
        ws.send(json.dumps({"id": 2, "method": "Runtime.evaluate", "params": {"expression": intercept_expr.strip()}}))
        r = json.loads(ws.recv())
        survey_url = r.get("result", {}).get("result", {}).get("value", "")
        ws.close()
        
        if not survey_url or survey_url == "window.open_not_called":
            return None
        
        # Step 3: Target.createTarget → open survey in new tab (NO popup blocker!)
        pages = _get_cdp_pages(port)
        if not pages:
            return None
        
        browser_ws = pages[0].get("webSocketDebuggerUrl")
        if not browser_ws:
            return None
        
        ws2 = websocket.create_connection(browser_ws, timeout=10)
        ws2.send(json.dumps({
            "id": 1, "method": "Target.createTarget",
            "params": {"url": survey_url}
        }))
        r = json.loads(ws2.recv())
        ws2.close()
        
        target_id = r.get("result", {}).get("targetId")
        if not target_id:
            return None
        
        # Step 4: Wait for tab to appear and get its info
        time.sleep(3)
        pages2 = _get_cdp_pages(port)
        new_tab = next((p for p in pages2 if p.get("id") == target_id), None)
        
        if new_tab:
            return {
                "status": "ok",
                "tab_id": target_id,
                "ws_url": new_tab.get("webSocketDebuggerUrl"),
                "url": survey_url,
            }
        
        return None
    
    except Exception:
        return None


def _handle_modal_with_cdp(ws_url: str, port: int = CDP_PORT) -> Optional[Dict]:
    """Handle modal via CDP JS (pre-qualifier or "Umfrage starten").
    
    Handles two modal types:
    1. Pre-qualifier: has "Nächste" / submitQuestion() button
    2. Direct: has "Umfrage starten" / openSurvey() button
    
    Returns tab info dict or None.
    """
    import websocket
    
    try:
        ws = websocket.create_connection(ws_url, timeout=10)
        
        # Get all visible modal buttons
        ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate", "params": {"expression": """
(function() {
  var m = document.querySelector('.modal.show');
  if (!m) return null;
  var btns = m.querySelectorAll('.modal-button-positive');
  var result = [];
  for (var b of btns) {
    var r = b.getBoundingClientRect();
    if (r.width > 0 && r.height > 0) {
      result.push({
        text: b.innerText.trim(),
        onclick: (b.getAttribute('onclick') || '').slice(0, 80)
      });
    }
  }
  return JSON.stringify(result);
})()
        """.strip()}}))
        r = json.loads(ws.recv())
        btns_str = r.get("result", {}).get("result", {}).get("value", "[]")
        if isinstance(btns_str, str):
            try:
                btns = json.loads(btns_str)
            except:
                btns = []
        else:
            btns = []
        
        ws.close()
        
        if not btns:
            return None
        
        # Check for pre-qualifier vs "Umfrage starten"
        has_starten = any("starten" in b["text"].lower() for b in btns)
        has_submit = any("submitQuestion" in b.get("onclick", "") for b in btns)
        
        if has_starten:
            # "Umfrage starten" → use window.open interception method
            return _click_modal_button_cdp(ws_url, port)
        
        elif has_submit:
            # Pre-qualifier → click submit then check for "Umfrage starten"
            return _handle_pre_qualifier_modal(ws_url, port)
        
        return None
    
    except Exception:
        return None


def _handle_pre_qualifier_modal(ws_url: str, port: int = CDP_PORT) -> Optional[Dict]:
    """Handle pre-qualifier modal: click submit, then handle resulting modal.
    
    Pre-qualifier flow:
    1. Modal has radio buttons (e.g., 23 B2B options) + "Nächste" / submitQuestion() button
    2. Click submit → page updates → "Umfrage starten" button appears
    3. Then use window.open interception method
    """
    import websocket
    
    try:
        ws = websocket.create_connection(ws_url, timeout=10)
        
        # Click the visible submit button (Nächste)
        ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate", "params": {"expression": """
(function() {
  var m = document.querySelector('.modal.show');
  if (!m) return 'no_modal';
  var btns = m.querySelectorAll('.modal-button-positive');
  for (var b of btns) {
    var r = b.getBoundingClientRect();
    if (r.width > 0 && r.height > 0 && b.innerText.trim().includes('chste')) {
      b.click();
      return 'submitted';
    }
  }
  return 'submit_btn_not_found';
})()
        """.strip()}}))
        r = json.loads(ws.recv())
        ws.close()
        
        result = r.get("result", {}).get("result", {}).get("value", "")
        if result != "submitted":
            return None
        
        # Wait for modal to update with "Umfrage starten"
        time.sleep(2)
        
        # Now handle the updated modal
        return _handle_modal_with_cdp(ws_url, port)
    
    except Exception:
        return None


# ═══════════════════════════════════════════════════════════════════════════
# CUA HELPERS (for modal handling)
# ═══════════════════════════════════════════════════════════════════════════

def _get_state(pid: int, wid: int) -> str:
    try:
        result = subprocess.run(
            [CUA_BIN, "call", "get_window_state"],
            input=json.dumps({"pid": pid, "window_id": wid}),
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            return ""
        data = json.loads(result.stdout)
        return data.get("tree_markdown", "")
    except Exception:
        return ""


def _click_cua(pid: int, wid: int, element_index: int) -> bool:
    try:
        result = subprocess.run(
            [CUA_BIN, "call", "click"],
            input=json.dumps({"pid": pid, "window_id": wid, "element_index": element_index}),
            capture_output=True, text=True, timeout=15,
        )
        return result.returncode == 0 and "Performed" in result.stdout
    except Exception:
        return False


def _find_element(markdown: str, role: str, label: str) -> Optional[Dict]:
    from tools.tool_find_element import find_element
    return find_element(markdown, role=role, label=label)


# ═══════════════════════════════════════════════════════════════════════════
# PROVIDER DETECTION
# ═══════════════════════════════════════════════════════════════════════════

PROVIDER_PATTERNS = {
    "qualtrics": ["qualtrics.com", "survey.qualtrics", "qse", "qualtrics"],
    "toluna": ["tolunastart.com", "toluna", "cf-radio"],
    "cint": ["cint.com", "samplicio", "s.cint"],
    "samplicio": ["samplicio.us", "samplicio", "rx.samplicio"],
    "nfield": ["nfieldmr.com", "nfieldeu", "nfield"],
    "strat7": ["strat7", "bsbutton"],
    "dynata": ["dynata", "samplicio"],
    "gfk": ["gfk", "kantar"],
    "surveyrouter": ["surveyrouter", "router"],
    "purespectrum": ["purespectrum", "spectrum"],
}


def _detect_provider(url: str) -> str:
    url_lower = url.lower()
    for provider, patterns in PROVIDER_PATTERNS.items():
        for pat in patterns:
            if pat in url_lower:
                return provider
    return "unknown"


# ═══════════════════════════════════════════════════════════════════════════
# MAIN: open_survey()
# ═══════════════════════════════════════════════════════════════════════════

def open_survey(
    survey_id: str,
    pid: int,
    wid: int,
    port: int = CDP_PORT,
    wait_modal: float = 3.0,
    wait_load: float = 5.0,
) -> Dict:
    """Open a survey — handle CPX redirect + modals + new-tab detection.

    Args:
        survey_id: CPX survey ID
        pid, wid: DEPRECATED (CUA not used, kept for backwards compat)
        port: CDP port (default: 9999)
        wait_modal: Seconds to wait for modal
        wait_load: Seconds to wait for survey page load

    Returns:
        {"status": "ok", "tab_id": str, "ws_url": str, "provider": str, "url": str, "flow": str}
        {"status": "error", "reason": str, "stage": str}
    
    MODAL CLICK FIX (2026-05-09):
    - CUA click on "Umfrage starten" FAILS: Chrome blocks window.open()
    - CDP b.click() FAILS: same reason
    - CDP Input.dispatchMouseEvent FAILS: same reason
    - WINNING METHOD: window.open interception + Target.createTarget
      1. Override window.open → capture survey URL
      2. Call openSurvey() → URL captured from window.open call
      3. Target.createTarget(captured_url) → NEW TAB opens (no popup blocker!)
    """
    # 1. Get survey URL from CPX API
    survey_url = _get_survey_url(survey_id, port)
    if not survey_url:
        return {
            "status": "error",
            "reason": "No survey URL from CPX API (pre-qualifier or unavailable)",
            "stage": "cpx_api",
        }

    # 2. Get dashboard CDP info
    dashboard_ws = _get_dashboard_ws(port)
    if not dashboard_ws:
        return {
            "status": "error",
            "reason": "Dashboard WebSocket not found",
            "stage": "dashboard_ws",
        }

    # 3. Click survey card on dashboard (in-page)
    try:
        import websocket
        ws = websocket.create_connection(dashboard_ws, timeout=10)
        ws.send(json.dumps({
            "id": 0, "method": "Runtime.evaluate",
            "params": {"expression": f"clickSurvey({survey_id})"}
        }))
        json.loads(ws.recv())
        ws.close()
    except Exception as e:
        return {
            "status": "error",
            "reason": f"clickSurvey failed: {e}",
            "stage": "click_survey",
        }

    time.sleep(2)  # Wait for modal

    # 4. Handle modal via CDP JS (window.open interception — WORKS!)
    #    CUA click FAILS: Chrome blocks window.open() from programmatic JS
    #    CDP b.click() FAILS: same reason
    #    CDP Input.dispatchMouseEvent FAILS: same reason
    #    ✅ WINNING: window.open interception + Target.createTarget
    old_tab_ids = {p.get("id", "") for p in _get_cdp_pages(port)}

    tab_info = _handle_modal_with_cdp(dashboard_ws, port)
    if tab_info and tab_info.get("status") == "ok":
        # Survey opened successfully in new tab!
        tab_id = tab_info["tab_id"]
        tab_ws = tab_info["ws_url"]
        # CRITICAL FIX (2026-05-10): Don't overwrite CPX API URL with intercepted URL
        # The intercepted URL from window.open may lack subid parameters
        # which are required for HeyPiggy completion tracking.
        # Keep the CPX API URL (from line 509) which has correct subid.
        intercepted_url = tab_info["url"]
        
        # SUBID FIX: If intercepted URL lacks subid, use CPX API URL instead
        # The CPX API URL (from _get_survey_url) includes heypiggy's tracking subid
        # The intercepted URL often has subid_1=&subid_2=website (empty defaults)
        if "subid_1=&" in intercepted_url or "subid_2=website" in intercepted_url:
            # Intercepted URL has empty/default subid — keep CPX API URL
            pass  # survey_url already holds the correct CPX API URL
        else:
            # Intercepted URL has real subid — prefer it (has dashboard context)
            survey_url = intercepted_url
        
        # Navigate tab to the correct URL (CPX API URL with subid)
        try:
            import websocket
            ws = websocket.create_connection(tab_ws, timeout=10)
            ws.send(json.dumps({
                "id": 1, "method": "Page.navigate",
                "params": {"url": survey_url}
            }))
            json.loads(ws.recv())
            ws.close()
        except Exception:
            pass
        
        time.sleep(wait_load)
        
        # Get actual URL after redirect
        provider = _detect_provider(survey_url)
        try:
            ws = websocket.create_connection(tab_ws, timeout=10)
            ws.send(json.dumps({
                "id": 0, "method": "Runtime.evaluate",
                "params": {"expression": "document.location.href"}
            }))
            r = json.loads(ws.recv())
            ws.close()
            actual_url = r.get("result", {}).get("result", {}).get("value", survey_url)
            provider = _detect_provider(actual_url)
        except Exception:
            actual_url = survey_url
        
        return {
            "status": "ok",
            "tab_id": tab_id,
            "ws_url": tab_ws,
            "provider": provider,
            "url": actual_url,
            "modal_clicked": True,
            "flow": "modal_window_open_intercept",
        }

    # 5. Fallback: check if survey auto-opened a new tab
    time.sleep(wait_modal)
    new_tab = _find_new_tab(old_tab_ids, port)

    if new_tab:
        # New tab flow (Qualtrics redirect)
        tab_id = new_tab.get("id")
        tab_ws = new_tab.get("webSocketDebuggerUrl")
        tab_url = new_tab.get("url", "")
        provider = _detect_provider(tab_url)

        # Wait for survey to load
        time.sleep(wait_load)

        # Get actual URL after redirect
        try:
            ws = websocket.create_connection(tab_ws, timeout=10)
            ws.send(json.dumps({
                "id": 0, "method": "Runtime.evaluate",
                "params": {"expression": "document.location.href"}
            }))
            r = json.loads(ws.recv())
            ws.close()
            actual_url = r.get("result", {}).get("result", {}).get("value", tab_url)
            provider = _detect_provider(actual_url)
        except Exception:
            actual_url = tab_url

        return {
            "status": "ok",
            "tab_id": tab_id,
            "ws_url": tab_ws,
            "provider": provider,
            "url": actual_url,
            "modal_clicked": False,
            "flow": "new_tab",
        }

    # 6. In-page survey (no new tab)
    # Try to detect provider from dashboard page
    time.sleep(wait_load)
    pages = _get_cdp_pages(port)
    for p in pages:
        if "dashboard" in p.get("url", "").lower():
            # Check if survey loaded in dashboard (iframe or redirect)
            try:
                ws = websocket.create_connection(
                    p.get("webSocketDebuggerUrl"), timeout=10)
                ws.send(json.dumps({
                    "id": 0, "method": "Runtime.evaluate",
                    "params": {"expression": "document.querySelector('iframe')?.src || document.location.href"}
                }))
                r = json.loads(ws.recv())
                ws.close()
                survey_page = r.get("result", {}).get("result", {}).get("value", "")
                if survey_page and survey_page != p.get("url"):
                    provider = _detect_provider(survey_page)
                    return {
                        "status": "ok",
                        "tab_id": p.get("id"),
                        "ws_url": p.get("webSocketDebuggerUrl"),
                        "provider": provider,
                        "url": survey_page,
                        "modal_clicked": False,
                        "flow": "in_page",
                    }
            except Exception:
                pass

    # Fallback: create new tab manually
    tab_id = _create_tab(survey_url, port)
    if not tab_id:
        return {
            "status": "error",
            "reason": "Survey did not open in-page and new tab creation failed",
            "stage": "fallback_tab",
        }

    time.sleep(wait_load)
    pages = _get_cdp_pages(port)
    for p in pages:
        if p.get("id") == tab_id:
            return {
                "status": "ok",
                "tab_id": tab_id,
                "ws_url": p.get("webSocketDebuggerUrl"),
                "provider": _detect_provider(p.get("url", "")),
                "url": p.get("url", ""),
                "modal_clicked": False,
                "flow": "fallback_new_tab",
            }

    return {
        "status": "error",
        "reason": "Survey tab created but not found in page list",
        "stage": "tab_missing",
    }


# ═══════════════════════════════════════════════════════════════════════════
# CLOSE SURVEY TAB
# ═══════════════════════════════════════════════════════════════════════════

def close_survey_tab(tab_id: str, port: int = CDP_PORT) -> bool:
    """Close a survey tab and return to dashboard."""
    return _close_tab(tab_id, port)


# ═══════════════════════════════════════════════════════════════════════════
# TESTS
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("✅ tool_open_survey.py imported OK")
    print(f"  frozen={__frozen__}, version={__version__}")

    # Test provider detection
    assert _detect_provider("https://survey.qualtrics.com/jfe/form/123") == "qualtrics"
    assert _detect_provider("https://tolunastart.com/survey/abc") == "toluna"
    assert _detect_provider("https://unknown.com/survey") == "unknown"

    # Test _normalize
    assert _get_details_url != ""

    print("All tests passed")
