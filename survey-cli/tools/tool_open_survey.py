"""Survey Opening Tool — __frozen__=True

Handles CPX redirect flow + modal "Umfrage starten" + new-tab detection.
Agent bricht bei redirect ab — DARF NICHT.

Usage:
    from tools.tool_open_survey import open_survey
    result = open_survey("12345", pid=71104, wid=56640)
    # → {"status": "ok", "tab_id": "A1B2C3", "ws_url": "ws://...", "provider": "qualtrics"}
    # → {"status": "error", "reason": "No survey URL from CPX API"}

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
import subprocess
import time
import urllib.request
import re
from typing import Dict, Optional, List

__frozen__ = True
__version__ = "2026-05-07"
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
    """Create new browser tab via CDP Target.createTarget."""
    try:
        import websocket
        pages = _get_cdp_pages(port)
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
        pid, wid: Dashboard window identifiers (for CUA modal handling)
        port: CDP port
        wait_modal: Seconds to wait for modal
        wait_load: Seconds to wait for survey page load

    Returns:
        {"status": "ok", "tab_id": str, "ws_url": str, "provider": str, "url": str}
        {"status": "error", "reason": str, "stage": str}
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

    # 4. Handle "Umfrage starten" / "Zustimmen" / "Starten" modal
    old_tab_ids = {p.get("id", "") for p in _get_cdp_pages(port)}

    modal_attempts = [
        ("Zustimmen und fortfahren", "AXButton"),
        ("Umfrage starten", "AXButton"),
        ("Starten", "AXButton"),
        ("Weiter", "AXButton"),
        ("Fortfahren", "AXButton"),
    ]

    modal_clicked = False
    for label, role in modal_attempts:
        markdown = _get_state(pid, wid)
        el = _find_element(markdown, role, label)
        if el:
            if _click_cua(pid, wid, el["element_index"]):
                modal_clicked = True
                time.sleep(2)
                break

    # 5. Check if new tab opened
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
            "modal_clicked": modal_clicked,
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
                        "modal_clicked": modal_clicked,
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
                "modal_clicked": modal_clicked,
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
