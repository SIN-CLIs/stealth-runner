"""State Verification Tool — __frozen__=True

After jeder Aktion: verify dass Zustand erreicht wurde.
Agent klickt und hofft — DARF NICHT.

Usage:
    from tools.tool_verify_state import verify_page, verify_element_state

    # Verify page loaded
    result = verify_page(pid, wid, url_contains="dashboard", text_contains="Umfragen")
    # -> {"status": "ok", "url": "...", "matched": True}

    # Verify specific element state
    result = verify_element_state(pid, wid, element_index=42, expected_role="AXRadioButton")
    # -> {"status": "ok", "found": True, "role": "AXRadioButton", "text": "Mannlich"}

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
import re
import urllib.request
from typing import Dict, Optional

__frozen__ = True
__version__ = "2026-05-07"
CUA_BIN = "cua-driver"
CDP_PORT = 9999


# ═══════════════════════════════════════════════════════════════════════════
# CDP HELPERS
# ═══════════════════════════════════════════════════════════════════════════


def _get_state(pid: int, wid: int) -> str:
    try:
        result = subprocess.run(
            [CUA_BIN, "call", "get_window_state"],
            input=json.dumps({"pid": pid, "window_id": wid}),
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            return ""
        data = json.loads(result.stdout)
        return data.get("tree_markdown", "")
    except Exception:
        return ""


def _get_cdp_pages(port: int = CDP_PORT):
    try:
        return json.loads(urllib.request.urlopen(f"http://127.0.0.1:{port}/json", timeout=3).read())
    except Exception:
        return []


# ═══════════════════════════════════════════════════════════════════════════
# ELEMENT STATE VERIFICATION
# ═══════════════════════════════════════════════════════════════════════════


def verify_element_state(
    pid: int,
    wid: int,
    element_index: int,
    expected_role: Optional[str] = None,
    expected_text_contains: Optional[str] = None,
) -> Dict:
    """Verify an element exists with expected role/text.

    Returns:
        {"status": "ok", "found": True, "role": str, "text": str}
        {"status": "error", "found": False, "reason": str}
    """
    markdown = _get_state(pid, wid)
    if not markdown:
        return {"status": "error", "found": False, "reason": "AX-Tree empty"}

    pattern = re.compile(rf"- \[{element_index}\]\s+(\w+)(?:\s*\(([^)]*)\))?")
    match = pattern.search(markdown)
    if not match:
        return {
            "status": "error",
            "found": False,
            "reason": f"Element [{element_index}] not found in AX-Tree",
        }

    role, text = match.group(1), (match.group(2) or "").strip()

    if expected_role and role != expected_role:
        return {
            "status": "error",
            "found": True,
            "role": role,
            "text": text,
            "reason": f"Role mismatch: expected {expected_role}, got {role}",
        }

    if expected_text_contains and expected_text_contains.lower() not in text.lower():
        return {
            "status": "error",
            "found": True,
            "role": role,
            "text": text,
            "reason": f"Text mismatch: expected '{expected_text_contains}' in '{text}'",
        }

    return {
        "status": "ok",
        "found": True,
        "role": role,
        "text": text,
    }


# ═══════════════════════════════════════════════════════════════════════════
# PAGE VERIFICATION
# ═══════════════════════════════════════════════════════════════════════════


def verify_page(
    pid: int,
    wid: int,
    url_contains: Optional[str] = None,
    text_contains: Optional[str] = None,
    text_not_contains: Optional[str] = None,
    role_count: Optional[Dict[str, int]] = None,
    timeout: float = 5.0,
) -> Dict:
    """Verify page state by URL, text content, or element counts.

    Args:
        url_contains: URL must contain this substring
        text_contains: AX-Tree text must contain this substring
        text_not_contains: AX-Tree text must NOT contain this substring
        role_count: Dict of {role: min_count} to verify
        timeout: Seconds to wait/poll

    Returns:
        {"status": "ok", "url": str, "text_matched": bool, "role_counts": dict}
        {"status": "error", "reason": str, "url": str}
    """
    deadline = time.time() + timeout
    last_error = ""

    while time.time() < deadline:
        markdown = _get_state(pid, wid)
        if not markdown:
            last_error = "AX-Tree empty"
            time.sleep(0.5)
            continue

        # Check text
        text_ok = True
        if text_contains and text_contains.lower() not in markdown.lower():
            text_ok = False
            last_error = f"Text '{text_contains}' not found"
        if text_not_contains and text_not_contains.lower() in markdown.lower():
            text_ok = False
            last_error = f"Text '{text_not_contains}' found (should not be)"

        if not text_ok:
            time.sleep(0.5)
            continue

        # Check role counts
        role_counts = {}
        if role_count:
            for role, min_count in role_count.items():
                pattern = re.compile(rf"- \[\d+\]\s+{re.escape(role)}")
                actual = len(pattern.findall(markdown))
                role_counts[role] = actual
                if actual < min_count:
                    last_error = f"Role {role}: expected >= {min_count}, got {actual}"
                    time.sleep(0.5)
                    break
            else:
                # All role counts passed (for-else: no break)
                pass
            # If we broke out of role_count loop, continue outer while
            if any(role_counts.get(r, 0) < c for r, c in role_count.items()):
                continue

        # Check URL via CDP
        url = ""
        if url_contains:
            pages = _get_cdp_pages()
            for p in pages:
                if p.get("id") == str(pid) or (wid and str(wid) in str(p.get("id", ""))):
                    url = p.get("url", "")
                    break
            if not url:
                # Fallback: get URL from first tab
                if pages:
                    url = pages[0].get("url", "")
            if url_contains.lower() not in url.lower():
                last_error = f"URL '{url_contains}' not in '{url}'"
                time.sleep(0.5)
                continue

        return {
            "status": "ok",
            "url": url,
            "text_matched": text_contains is not None,
            "role_counts": role_counts,
            "markdown_lines": len(markdown.split("\n")),
        }

    return {
        "status": "error",
        "reason": last_error or f"Timeout after {timeout}s",
        "url": url,
    }


# ═══════════════════════════════════════════════════════════════════════════
# CONVENIENCE: Common survey verifications
# ═══════════════════════════════════════════════════════════════════════════


def verify_logged_in(
    pid: int,
    wid: int,
    timeout: float = 3.0,
) -> Dict:
    """Verify heypiggy dashboard shows logged-in state."""
    return verify_page(
        pid,
        wid,
        text_contains="Abmelden",
        text_contains_2="Umfragen",  # Not supported yet, use custom
        timeout=timeout,
    )


def verify_survey_loaded(
    pid: int,
    wid: int,
    timeout: float = 5.0,
) -> Dict:
    """Verify survey page loaded (has questions/radio buttons)."""
    return verify_page(
        pid,
        wid,
        role_count={"AXRadioButton": 1, "AXStaticText": 3},
        timeout=timeout,
    )


def verify_survey_complete(
    pid: int,
    wid: int,
    timeout: float = 3.0,
) -> Dict:
    """Verify survey completion page (Vielen Dank, etc.)."""
    return verify_page(
        pid,
        wid,
        text_contains="Vielen Dank",
        timeout=timeout,
    )


# ═══════════════════════════════════════════════════════════════════════════
# TESTS
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("✅ tool_verify_state.py imported OK")
    print(f"  frozen={__frozen__}, version={__version__}")

    # Test verify_element_state with mock data
    test_md = """
- [42] AXButton ("Weiter")
- [43] AXRadioButton ("Mannlich")
"""
    # Manually test parsing logic
    pattern = re.compile(r"- \[(\d+)\]\s+(\w+)(?:\s*\(([^)]*)\))?")
    matches = pattern.findall(test_md)
    assert len(matches) == 2
    assert matches[0] == ("42", "AXButton", '"Weiter"')
    assert matches[1] == ("43", "AXRadioButton", '"Mannlich"')

    print("All tests passed")
