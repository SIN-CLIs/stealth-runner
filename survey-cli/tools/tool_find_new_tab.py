#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""================================================================================
TOOL: find_new_tab — Tab Change Detector
================================================================================

WAS IST DAS?
  Erkennt wenn ein neuer Tab geöffnet wurde (z.B. nach clickSurvey()).
  Vergleicht Tab-IDs vor/nach einem Ereignis und gibt die WebSocket-URL
  des neuen Tabs zurück.

WARUM EXISTIERT DAS?
  CPX öffnet Surveys oft in einem NEUEN Tab:
  1. Dashboard-Tab: User klickt "Umfrage starten"
  2. NEUER Tab: Qualtrics Survey lädt
  → Agent muss vom Dashboard-Tab zum Survey-Tab wechseln!

  Ohne dieses Tool: Agent klickt weiter auf Dashboard (alter Tab),
  Survey läuft im Hintergrund = stuck.

ARCHITEKTUR:
  ┌──────────────────┐
  │  get_all_tabs()  │
  └──────────────────┘
         │
         ▼
  HTTP GET /json → [{id, url, webSocketDebuggerUrl}, ...]
         │
         ▼
  ┌──────────────────┐
  │  get_tab_ids()   │
  └──────────────────┘
         │
         ▼
  Set({id1, id2, ...})
         │
         ▼
  ┌──────────────────┐
  │ find_new_tab()   │
  └──────────────────┘
         │
    ┌────┴────────────────┐
    ▼                     ▼
  known_ids            current_tabs
    │                     │
    └────────┬────────────┘
             ▼
      new_id = current - known
             │
             ▼
    Ignoriere: about:blank, heypiggy, prolific
             │
             ▼
      return ws_url

BEREITS FUNKTIONIERT:
  ✓ HeyPiggy → Qualtrics (neuer Tab)
  ✓ HeyPiggy → PureSpectrum (neuer Tab)

BANNED METHODS — NIEMALS VERWENDEN (siehe /banned.md):
  ❌ playstealth launch
  ❌ webauto-nodriver
  ❌ cua-driver click (raw index)
  ❌ --remote-allow-origins=* (ohne Quotes)
  ❌ /tmp/heypiggy-bot (fixed profile)
  ❌ Hardcoded PIDs
  ❌ pkill -f "Google Chrome"
  ❌ killall Google Chrome
  ❌ skylight-cli click --element-index
================================================================================"""

import time  # Sleep zwischen Vorher/Nachher-Scan
import requests  # HTTP GET /json (kein WebSocket nötig)
from typing import Dict, List, Set, Optional

__version__ = "1.0.0"
__frozen__ = True  # 🔒 NICHT AENDERN! Getestet mit HeyPiggy Tab-Wechsel.


def get_all_tabs(port: int = 9222, timeout: int = 5) -> List[Dict]:
    """Holt alle Tabs von Chrome DevTools HTTP API.

    ARGS:
        port (int): Chrome DevTools Port (default: 9222)
        timeout (int): HTTP Timeout in Sekunden

    RETURNS:
        list: [{"id": "...", "url": "...", "type": "page",
                "webSocketDebuggerUrl": "ws://..."}, ...]

    WARUM HTTP statt WebSocket?
      Chrome DevTools Protocol hat eine HTTP-API für Meta-Daten:
      GET http://127.0.0.1:<port>/json → Liste aller Tabs.
      → Kein WebSocket nötig (einfacher, schneller).

    WARUM type == "page" filtern?
      Chrome hat auch "background_page" (Extensions), "service_worker".
      → Nur "page" Tabs = sichtbare Webseiten.

    WARUM requests statt urllib?
      Einfachheit. requests ist standard, hat bessere Fehlerbehandlung.
      → Wenn requests nicht installiert: pip install requests.

    EXCEPTION HANDLING:
      ConnectionError (Chrome nicht erreichbar) → return [].
    """
    try:
        resp = requests.get("http://127.0.0.1:" + str(port) + "/json", timeout=timeout)
        # Nur "page" Tabs (keine Extensions, Service Workers)
        return [t for t in resp.json() if t.get("type") == "page"]
    except Exception:
        return []


def get_tab_ids(port: int = 9222) -> Set[str]:
    """Extrahiert Tab-IDs als Set.

    ARGS:
        port (int): Chrome DevTools Port

    RETURNS:
        set: {"id1", "id2", ...}

    WARUM Set?
      Effizienter für Vergleich: tab_id in known_ids (O(1)).
      → List wäre O(n) für jeden Check.
    """
    return {t.get("id") for t in get_all_tabs(port) if t.get("id")}


def find_new_tab(
    port: int, known_tab_ids: Set[str], ignore_urls: List[str] = None, wait_s: float = 3.0
) -> Optional[str]:
    """Findet neuen Tab nach einem Ereignis.

    ARGS:
        port (int): Chrome DevTools Port
        known_tab_ids (set): Bekannte Tab-IDs VOR dem Ereignis
        ignore_urls (list): URLs die ignoriert werden sollen
                            (default: ["about:blank", "heypiggy", "prolific.co/submissions"])
        wait_s (float): Wartezeit in Sekunden vor Scan (default: 3.0)

    RETURNS:
        str oder None: WebSocket-URL des neuen Tabs oder None

    ALGORITHMUS:
      1. wait_s Sekunden warten (Tab braucht Zeit zum Öffnen)
      2. Aktuelle Tabs holen (get_all_tabs)
      3. Für jeden aktuellen Tab:
         - Tab-ID in known_tab_ids? → Skip (alter Tab)
         - URL enthält ignore_urls? → Skip (z.B. about:blank)
         - WebSocketDebuggerUrl vorhanden? → Return
      4. Kein neuer Tab → Return None

    WARUM wait_s = 3.0s?
      Tab braucht Zeit zum Öffnen:
      - 0-1s: Chrome öffnet Tab (Renderer startet)
      - 1-2s: URL lädt (DNS, HTTP)
      - 2-3s: Seite rendert (DOM, JS)
      → <2s: Tab existiert noch nicht oder ist leer.
      → >5s: Zu lang, Agent-Loop blockiert.

    WARUM ignore_urls?
      Chrome öffnet manchmal leere Tabs (about:blank) oder leitet
      zum Panel zurück (heypiggy, prolific). → Diese sind NICHT der Survey-Tab.

    WARUM Optional[str] statt str?
      Kein neuer Tab = None (nicht Fehler).
      Aufrufer muss prüfen: if ws_url: ... else: ...

    RACE CONDITION:
      Tab öffnet sich, aber schliesst sich sofort (Redirect).
      → ws_url ist vorhanden, aber Tab ist tot.
      → Aufrufer muss validieren (WebSocket connect testen).
    """
    # Default ignore URLs (kann überschrieben werden)
    ignore_urls = ignore_urls or [
        "about:blank",  # Leerer Tab
        "heypiggy",  # Zurück zum Panel
        "prolific.co/submissions",  # Prolific Dashboard
    ]

    # Warten für Tab-Öffnung
    time.sleep(wait_s)

    # Aktuelle Tabs holen
    current_tabs = get_all_tabs(port)

    for tab in current_tabs:
        tab_id = tab.get("id")

        # NEUER Tab: ID nicht in known_tab_ids
        if tab_id and tab_id not in known_tab_ids:
            url = tab.get("url", "").lower()

            # Ignoriere unerwünschte URLs
            if any(ign.lower() in url for ign in ignore_urls):
                continue

            # WebSocket-URL holen
            ws_url = tab.get("webSocketDebuggerUrl")
            if ws_url:
                return ws_url

    # Kein neuer Tab gefunden
    return None


def find_tab_by_url(port: int, url_contains: str) -> Optional[str]:
    """Findet Tab anhand URL-Substring.

    ARGS:
        port (int): Chrome DevTools Port
        url_contains (str): Substring der gesuchten URL

    RETURNS:
        str oder None: WebSocket-URL des Tabs oder None

    WARUM?
      Manchmal wissen wir die Ziel-URL (z.B. "qualtrics.com").
      → Einfacher als Tab-ID-Vergleich.
    """
    for tab in get_all_tabs(port):
        if url_contains.lower() in tab.get("url", "").lower():
            return tab.get("webSocketDebuggerUrl")
    return None


# ═════════════════════════════════════════════════════════════════════════════
# CLI INTERFACE
# ═════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    import sys

    port = int(sys.argv[1]) if len(sys.argv) > 1 else 9222

    tabs = get_all_tabs(port)
    print("Found " + str(len(tabs)) + " tabs:")
    for t in tabs:
        print("  - " + str(t.get("id")) + ": " + t.get("url", "")[:60])
