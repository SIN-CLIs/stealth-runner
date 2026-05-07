#!/usr/bin/env python3
"""
================================================================================
TOOL: find_new_tab
================================================================================
Findet neuen Tab der nach clickSurvey() geoeffnet wurde.
Vergleicht Tab-IDs vor/nach Click.

BEREITS FUNKTIONIERT: ✓ Getestet mit Heypiggy -> Qualtrics

USAGE:
    from tools.tool_find_new_tab import find_new_tab, get_all_tabs
    
    tabs_before = get_all_tabs(9222)
    # ... Click Survey ...
    new_ws = find_new_tab(9222, tabs_before)

NICHT AENDERN! Dieser Flow funktioniert.
================================================================================
"""

import time
import requests
from typing import Dict, List, Set, Optional

__version__ = "1.0.0"
__frozen__ = True


def get_all_tabs(port: int = 9222, timeout: int = 5) -> List[Dict]:
    try:
        resp = requests.get("http://127.0.0.1:" + str(port) + "/json", timeout=timeout)
        return [t for t in resp.json() if t.get("type") == "page"]
    except Exception:
        return []


def get_tab_ids(port: int = 9222) -> Set[str]:
    return {t.get("id") for t in get_all_tabs(port) if t.get("id")}


def find_new_tab(
    port: int,
    known_tab_ids: Set[str],
    ignore_urls: List[str] = None,
    wait_s: float = 3.0
) -> Optional[str]:
    ignore_urls = ignore_urls or ["about:blank", "heypiggy", "prolific.co/submissions"]
    time.sleep(wait_s)
    
    current_tabs = get_all_tabs(port)
    for tab in current_tabs:
        tab_id = tab.get("id")
        if tab_id and tab_id not in known_tab_ids:
            url = tab.get("url", "").lower()
            if any(ign.lower() in url for ign in ignore_urls):
                continue
            ws_url = tab.get("webSocketDebuggerUrl")
            if ws_url:
                return ws_url
    return None


def find_tab_by_url(port: int, url_contains: str) -> Optional[str]:
    for tab in get_all_tabs(port):
        if url_contains.lower() in tab.get("url", "").lower():
            return tab.get("webSocketDebuggerUrl")
    return None


if __name__ == "__main__":
    import sys
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 9222
    tabs = get_all_tabs(port)
    print("Found " + str(len(tabs)) + " tabs:")
    for t in tabs:
        print("  - " + str(t.get('id')) + ": " + t.get('url', '')[:60])
