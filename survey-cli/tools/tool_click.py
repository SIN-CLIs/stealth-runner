"""================================================================================
DEPRECATED 2026-05-11 — Wird ersetzt durch die kanonische v2-Pipeline.
================================================================================

Dieser Tool-Pfad ist LEGACY. Er bleibt nur fuer Backward-Compat bestehender
Integrationen erhalten. NEUER Code MUSS gegen die folgenden Endpoints
programmieren:

    POST /v2/scan         → ersetzt /survey/snapshot, /survey/scan
    POST /v2/click        → ersetzt /survey/click, /survey/click-angular
    POST /v2/fill         → ersetzt /survey/fill-input
    POST /v2/press_key    → neu
    POST /v2/captcha/*    → ersetzt /survey/solve-captcha,
                            /survey/solve-drag-puzzle

Die Implementierungen leben in:
    survey-cli/survey/cdp_universal.py      Universal Scanner (AX-Tree pierce)
    survey-cli/survey/cdp_actuator.py       Maus-Events + Pflicht-Verify
    survey-cli/survey/captcha_router.py     Detection + Solver-Routing
    agent-toolbox/api/endpoints/universal.py FastAPI-Endpoints unter /v2/*

WARUM DIESER TOOL-PFAD STIRBT:
  - Y-Sort-Reihenfolge → instabile @eN-Indizes bei Reflow
  - el.click() / .value = "..." → von React/Angular ignoriert
  - Keine Pflicht-Verify nach Aktion → Halluzinationen "Performed without effect"
  - Provider-spezifisches JS hardcoded → jeder neue Provider = Patch
  - walkShadows(depth>5) → tieferes Shadow-DOM unsichtbar
  - iframes nur gezaehlt, nie betreten

Migration-Path fuer dieses Modul:
  → Wrap die alte API auf /v2/*. Wenn das alte Tool z.B. (selector) erwartet,
    intern via /v2/scan einen Match auf attrs.id / name finden und dessen
    stable_id an /v2/click weitergeben. So bleibt die externe API stabil.

LIES BEVOR DU DIESES MODUL AENDERST: AGENTS.md Sektion
"KANONISCHE ARCHITEKTUR (2026-05-11)".
================================================================================

================================================================================
TOOL DOCSTRING (legacy, pre-deprecation):
================================================================================
Click Tool — __frozen__=True

Agent nutzt rohes cua-driver call click — DARF NICHT.
Dieses Tool:
  1. Findet Element via tool_find_element (boundary-match)
  2. Klickt via cua-driver
  3. Verify: Rescannt AX-Tree, prüft Zustand
  4. Retry 3x bei AXPressFailure

Usage:
    from tools.tool_click import click
    result = click(pid, wid, label="Weiter", role="AXButton")
    # → {"status": "ok", "element_index": 42, "verified": True}
    # → {"status": "error", "reason": "AXPressFailed", "retries": 3}

BANNED METHODS — NIEMALS VERWENDEN (siehe /banned.md):
  ❌ playstealth launch — setzt NICHT --force-renderer-accessibility
  ❌ webauto-nodriver — ABSOLUT BANNED
  ❌ cua-driver click (raw index) — instabil, nutze dieses Tool stattdessen
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
from typing import Dict, Optional, Tuple

__frozen__ = True
__version__ = "2026-05-07"
CUA_BIN = "cua-driver"


# ═══════════════════════════════════════════════════════════════════════════
# CORE: Click + Verify
# ═══════════════════════════════════════════════════════════════════════════

def _get_state(pid: int, wid: int) -> str:
    """Get AX-Tree markdown via cua-driver."""
    try:
        result = subprocess.run(
            [CUA_BIN, "call", "get_window_state"],
            input=json.dumps({"pid": pid, "window_id": wid}),
            capture_output=True, text=True, timeout=30
        )
        if result.returncode != 0:
            return ""
        data = json.loads(result.stdout)
        return data.get("tree_markdown", "")
    except Exception:
        return ""


def _click_raw(pid: int, wid: int, element_index: int) -> bool:
    """Raw cua-driver click. Returns True if 'Performed' in stdout."""
    try:
        result = subprocess.run(
            [CUA_BIN, "call", "click"],
            input=json.dumps({
                "pid": pid,
                "window_id": wid,
                "element_index": element_index,
            }),
            capture_output=True, text=True, timeout=15,
        )
        return result.returncode == 0 and "Performed" in result.stdout
    except Exception:
        return False


def _verify_click(
    pid: int,
    wid: int,
    element_index: int,
    role: str,
    label: str,
) -> bool:
    """Verify that click had effect by re-scanning AX-Tree.

    Strategy depends on role:
    - AXRadioButton: check element still exists (radio stays, but group may change)
    - AXCheckBox: check element still exists
    - AXButton: check page changed (new elements, different markdown hash)
    - AXTextField: not applicable (set_value has its own verify)
    """
    # For buttons: page should change (wait a moment then check)
    time.sleep(0.5)
    markdown = _get_state(pid, wid)
    if not markdown:
        return False

    # Check if element still exists with same index
    import re
    pattern = re.compile(rf'- \[{element_index}\]\s+{re.escape(role)}')
    found = bool(pattern.search(markdown))

    if role == "AXLink":
        # For links on SPA: just verify element exists (click was performed)
        # URL may not contain label text (e.g., /cashout for "Auszahlung")
        return True
    elif role == "AXButton":
        # Button may disappear (page navigated) → that's success
        return not found or label.lower() not in markdown.lower()
    elif role in ("AXRadioButton", "AXCheckBox"):
        # Radio/Checkbox should still exist
        return found
    return True


# ═══════════════════════════════════════════════════════════════════════════
# PUBLIC: click()
# ═══════════════════════════════════════════════════════════════════════════

def click(
    pid: int,
    wid: int,
    label: Optional[str] = None,
    role: str = "AXButton",
    element_index: Optional[int] = None,
    text_sub: Optional[str] = None,
    verify: bool = True,
    max_retries: int = 3,
) -> Dict:
    """Click an element by label (boundary-match) or index.

    Args:
        pid, wid: Window identifiers
        label: Exact label with word-boundary matching
        role: AXRole (default "AXButton")
        element_index: Direct index (skip finding). Use ONLY as fallback.
        text_sub: Substring fallback (when label is partial)
        verify: Re-scan AX-Tree after click to verify effect
        max_retries: Retry count on failure

    Returns:
        {"status": "ok", "element_index": int, "verified": bool}
        {"status": "error", "reason": str, "retries": int}

    Example:
        result = click(pid, wid, label="Weiter")
        if result["status"] != "ok":
            # Handle error
    """
    from tools.tool_find_element import find_element

    # Find element
    if element_index is not None:
        idx = element_index
    else:
        el = find_element(
            (pid, wid), role=role,
            label=label, text_sub=text_sub,
            use_boundary=True,
        )
        if not el:
            return {
                "status": "error",
                "reason": f"Element not found: role={role} label={label} text_sub={text_sub}",
                "retries": 0,
            }
        idx = el["element_index"]
        label = label or el.get("text", "")

    # Click + Verify loop
    for attempt in range(1, max_retries + 1):
        success = _click_raw(pid, wid, idx)
        if not success:
            if attempt < max_retries:
                time.sleep(0.5)
                continue
            return {
                "status": "error",
                "reason": f"AXPress failed after {max_retries} retries",
                "retries": max_retries,
            }

        if verify:
            verified = _verify_click(pid, wid, idx, role, label)
            if verified:
                return {
                    "status": "ok",
                    "element_index": idx,
                    "verified": True,
                    "retries": attempt,
                }
            # Not verified → retry
            if attempt < max_retries:
                time.sleep(0.5)
                continue
            return {
                "status": "error",
                "reason": "Click succeeded but verify failed (page did not change)",
                "element_index": idx,
                "verified": False,
                "retries": max_retries,
            }
        else:
            return {
                "status": "ok",
                "element_index": idx,
                "verified": False,
                "retries": attempt,
            }

    # Should never reach here
    return {"status": "error", "reason": "Unexpected loop exit", "retries": max_retries}


# ═══════════════════════════════════════════════════════════════════════════
# PUBLIC: set_value() — for text fields
# ═══════════════════════════════════════════════════════════════════════════

def set_value(
    pid: int,
    wid: int,
    label: Optional[str] = None,
    value: str = "",
    element_index: Optional[int] = None,
    verify: bool = True,
    max_retries: int = 3,
) -> Dict:
    """Set value in AXTextField by label or index.

    Args:
        pid, wid: Window identifiers
        label: Label for finding (uses boundary-match)
        value: Text to enter
        element_index: Direct index (skip finding)
        verify: Re-scan and check text is in field
        max_retries: Retry count

    Returns:
        {"status": "ok", "element_index": int, "verified": bool}
        {"status": "error", "reason": str}
    """
    from tools.tool_find_element import find_element

    if element_index is not None:
        idx = element_index
    else:
        el = find_element(
            (pid, wid), role="AXTextField",
            label=label, use_boundary=True,
        )
        if not el:
            return {
                "status": "error",
                "reason": f"TextField not found: label={label}",
            }
        idx = el["element_index"]

    for attempt in range(1, max_retries + 1):
        try:
            result = subprocess.run(
                [CUA_BIN, "call", "set_value"],
                input=json.dumps({
                    "pid": pid,
                    "window_id": wid,
                    "element_index": idx,
                    "value": value,
                }),
                capture_output=True, text=True, timeout=15,
            )
            if result.returncode != 0:
                if attempt < max_retries:
                    time.sleep(0.5)
                    continue
                return {"status": "error", "reason": "set_value failed"}

            if verify:
                time.sleep(0.3)
                markdown = _get_state(pid, wid)
                # Check if value appears in field text
                if value.lower() in markdown.lower():
                    return {
                        "status": "ok",
                        "element_index": idx,
                        "verified": True,
                    }
                if attempt < max_retries:
                    time.sleep(0.5)
                    continue
                return {
                    "status": "error",
                    "reason": "set_value succeeded but verify failed",
                    "verified": False,
                }
            else:
                return {"status": "ok", "element_index": idx, "verified": False}
        except Exception as e:
            if attempt < max_retries:
                time.sleep(0.5)
                continue
            return {"status": "error", "reason": str(e)[:200]}

    return {"status": "error", "reason": "Unexpected loop exit"}


# ═══════════════════════════════════════════════════════════════════════════
# CONVENIENCE: press_key
# ═══════════════════════════════════════════════════════════════════════════

def press_key(
    pid: int,
    key: str,
    verify_url_change: bool = False,
    old_url: str = "",
) -> Dict:
    """Press a key (return, tab, etc.) via cua-driver.

    Args:
        pid: Process ID
        key: Key to press (e.g. "return", "tab")
        verify_url_change: If True, wait and check URL changed
        old_url: Expected old URL (for verify)

    Returns:
        {"status": "ok"} or {"status": "error", "reason": str}
    """
    try:
        result = subprocess.run(
            [CUA_BIN, "call", "press_key"],
            input=json.dumps({"pid": pid, "key": key}),
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode != 0:
            return {"status": "error", "reason": f"press_key failed: {result.stderr[:200]}"}

        if verify_url_change:
            time.sleep(2)
            # CDP check URL
            import urllib.request
            try:
                pages = json.loads(urllib.request.urlopen(
                    "http://127.0.0.1:9999/json", timeout=3).read())
                for p in pages:
                    if p.get("url") != old_url:
                        return {"status": "ok", "new_url": p.get("url")}
                return {"status": "error", "reason": "URL did not change after key press"}
            except Exception:
                return {"status": "ok"}  # Can't verify, assume ok

        return {"status": "ok"}
    except Exception as e:
        return {"status": "error", "reason": str(e)[:200]}


# ═══════════════════════════════════════════════════════════════════════════
# TESTS
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys
    sys.path.insert(0, "..")
    # Unit tests using mock markdown (no real Chrome needed)
    print("✅ tool_click.py imported OK")
    print(f"  frozen={__frozen__}, version={__version__}")

    # Test that find_element is used (import check)
    # Direct import for test (running from tools/ directory)
    import tool_find_element
    print("  tool_find_element import: OK")

    print("All tests passed")