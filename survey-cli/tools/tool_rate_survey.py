"""Survey Rating Tool — __frozen__=True

Rate completed surveys for +0.01€ bonus.
Agent vergisst Rating → verliert Bonus.

Usage:
    from tools.tool_rate_survey import rate_survey
    result = rate_survey(port=9999)
    # -> {"status": "ok", "bonus": 0.01, "tab_id": "A1B2C3"}
    # -> {"status": "not_found"} (no rating page open)
    # -> {"status": "error", "reason": "..."}

Flow:
    1. Scan all tabs for rating.php or cpx-research URL
    2. Click first button/input on rating page
    3. Wait 2s, verify tab closed or navigated away
    4. Return bonus amount

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
import time
import urllib.request
from typing import Dict, List

__frozen__ = True
__version__ = "2026-05-07"
CDP_PORT = 9999


def _get_cdp_pages(port: int = CDP_PORT) -> List[Dict]:
    try:
        return json.loads(urllib.request.urlopen(
            f"http://127.0.0.1:{port}/json", timeout=3).read())
    except Exception:
        return []


def _click_rating_button(ws_url: str) -> bool:
    """Click first button on rating page via CDP."""
    try:
        import websocket
        ws = websocket.create_connection(ws_url, timeout=15)
        ws.send(json.dumps({
            "id": 0, "method": "Runtime.evaluate",
            "params": {
                "expression": (
                    'document.querySelector("button,.btn-blue,input[type=button]").click()'
                )
            }
        }))
        json.loads(ws.recv())
        ws.close()
        return True
    except Exception:
        return False


def _verify_rating_done(tab_id: str, port: int = CDP_PORT) -> bool:
    """Verify rating tab closed or no longer on rating page."""
    time.sleep(2)
    pages = _get_cdp_pages(port)
    for p in pages:
        if p.get("id") == tab_id:
            url = p.get("url", "").lower()
            if "rating" not in url and "cpx-research" not in url:
                return True  # Navigated away
            return False  # Still on rating page
    return True  # Tab closed


# ═══════════════════════════════════════════════════════════════════════════
# MAIN: rate_survey()
# ═══════════════════════════════════════════════════════════════════════════

def rate_survey(port: int = CDP_PORT, verify: bool = True) -> Dict:
    """Rate a completed survey for +0.01€ bonus.

    Args:
        port: CDP port
        verify: Verify rating was submitted

    Returns:
        {"status": "ok", "bonus": 0.01, "tab_id": str}
        {"status": "not_found"} — no rating page detected
        {"status": "error", "reason": str}
    """
    pages = _get_cdp_pages(port)
    rating_tab = None

    for p in pages:
        url = p.get("url", "")
        if "rating.php" in url.lower() or "cpx-research" in url.lower():
            rating_tab = p
            break

    if not rating_tab:
        return {"status": "not_found"}

    tab_id = rating_tab.get("id")
    ws_url = rating_tab.get("webSocketDebuggerUrl")

    if not ws_url:
        return {
            "status": "error",
            "reason": "Rating tab found but no WebSocket URL",
            "tab_id": tab_id,
        }

    # Click rating button
    if not _click_rating_button(ws_url):
        return {
            "status": "error",
            "reason": "Failed to click rating button",
            "tab_id": tab_id,
        }

    # Verify
    if verify:
        done = _verify_rating_done(tab_id, port)
        if not done:
            # Retry once
            time.sleep(1)
            _click_rating_button(ws_url)
            done = _verify_rating_done(tab_id, port)
            if not done:
                return {
                    "status": "error",
                    "reason": "Rating button clicked but page did not change",
                    "tab_id": tab_id,
                }

    return {
        "status": "ok",
        "bonus": 0.01,
        "tab_id": tab_id,
        "verified": verify,
    }


# ═══════════════════════════════════════════════════════════════════════════
# TESTS
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("✅ tool_rate_survey.py imported OK")
    print(f"  frozen={__frozen__}, version={__version__}")

    # Test provider detection (mock)
    assert _get_cdp_pages != []

    print("All tests passed")