#!/usr/bin/env python3
"""
================================================================================
PRE-FLIGHT CHECK — Validierung vor Command-Ausfuehrung

WAS DAS TUT:
  Prueft ob HeyPiggy Session aktiv ist, bevor ein Survey-Command ausgefuehrt wird.
  
  ┌────────────────────────────────────────────────────────────────────────┐
  │  preflight_check()                                                    │
  ├────────────────────────────────────────────────────────────────────────┤
  │                                                                         │
  │  1. Chrome alive? → Port 9999 erreichbar?                             │
  │  2. Dashboard Tab? → Non-extension, non-blank tab finden              │
  │  3. Login valid? → "abmelden" im body text?                           │
  │  4. Balance lesen → Max(alle €-Betraege >= 1.0€)                     │
  │  5. Surveys zaehlen → .survey-item Cards auf Dashboard               │
  │                                                                         │
  │  → {"ready": True, "tab_ws": "...", "balance": 2.75, "surveys": 12}  │
  │  oder: {"ready": False, "reason": "...", "action": "start_heypiggy"} │
  │                                                                         │
  └────────────────────────────────────────────────────────────────────────┘

VERWENDUNG:
  result = preflight_check()
  if not result["ready"]:
      # Session invalid → neu starten
      start_heypiggy()
  else:
      # Session OK → Command ausfuehren
      execute_survey(result["tab_ws"])

INTEGRATION:
  - command_registry.py: validate_command() ruft preflight_check() auf
  - FastAPI endpoints: preflight vor jedem /survey/* endpoint
  - Daemon loop: preflight vor jedem Survey-Loop-Durchlauf

=================================================================================="""

import json
import re
import time
import urllib.request
import websocket

CHROME_PORT = 9999


def is_chrome_alive(port: int = CHROME_PORT) -> bool:
    """Prueft ob CDP auf Port erreichbar ist."""
    try:
        urllib.request.urlopen(f"http://127.0.0.1:{port}/json", timeout=3)
        return True
    except Exception:
        return False


def find_heypiggy_tab(port: int = CHROME_PORT) -> tuple[str | None, str | None]:
    """
    Findet HeyPiggy Dashboard Tab.
    
    Returns:
        (ws_url, url) oder (None, None) wenn nicht gefunden
    """
    if not is_chrome_alive(port):
        return None, None
    
    try:
        pages = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{port}/json", timeout=5).read())
    except Exception:
        return None, None
    
    # HeyPiggy Tab: URL contains heypiggy, nicht extension/about-blank
    for p in pages:
        url = p.get("url", "")
        if "heypiggy" in url.lower() and not url.startswith("chrome-extension"):
            return p["webSocketDebuggerUrl"], url
    
    # Fallback: erste non-extension tab
    for p in pages:
        url = p.get("url", "")
        if url.startswith("http") and "heypiggy" not in url.lower():
            return p["webSocketDebuggerUrl"], url
    
    return None, None


def check_login(tab_ws: str) -> tuple[bool, str]:
    """
    Prueft Login-Status via body text.
    
    Returns:
        (logged_in, body_text_preview)
    """
    try:
        ws = websocket.create_connection(tab_ws, timeout=10)
        ws.send(json.dumps({
            "id": 1, "method": "Runtime.evaluate",
            "params": {"expression": "document.body.innerText.substring(0, 1000)"}
        }))
        r = json.loads(ws.recv())
        ws.close()
        text = r.get("result", {}).get("result", {}).get("value", "")
        logged_in = "abmelden" in text.lower()
        return logged_in, text[:200]
    except Exception:
        return False, ""


def read_balance(tab_ws: str) -> float:
    """
    Liest Balance aus Dashboard-Tab.
    
    Filter: Nur Betraege >= 1.0€ (Rewards sind < 1€)
    Return: Max aller gefundenen Betraege
    """
    try:
        ws = websocket.create_connection(tab_ws, timeout=10)
        ws.send(json.dumps({
            "id": 1, "method": "Runtime.evaluate",
            "params": {"expression": "document.body.innerText"}
        }))
        r = json.loads(ws.recv())
        ws.close()
        text = r.get("result", {}).get("result", {}).get("value", "")
        
        amounts = []
        for m in re.finditer(r"(\d+[.,]?\d*)\s*€", text):
            v = float(m.group(1).replace(",", "."))
            if v >= 1.0:
                amounts.append(v)
        
        return max(amounts) if amounts else 0.0
    except Exception:
        return 0.0


def count_surveys(tab_ws: str) -> int:
    """
    Zaehlt verfügbare Surveys auf Dashboard.
    
    Sucht nach survey-item cards, clickSurvey() onclick, oder
    Preis-Beträgen im Format "0.XX €".
    """
    try:
        ws = websocket.create_connection(tab_ws, timeout=10)
        ws.send(json.dumps({
            "id": 1, "method": "Runtime.evaluate",
            "params": {"expression": """
(function() {
    // Try: survey-item class
    var items = document.querySelectorAll('.survey-item, [data-survey-id]');
    if (items.length > 0) return String(items.length);
    
    // Try: clickSurvey() calls
    var scripts = document.querySelectorAll('script');
    var count = 0;
    for (var i = 0; i < scripts.length; i++) {
        var matches = (scripts[i].textContent || '').match(/clickSurvey\\(['\"]([^'\"]+)['\"]\\)/g);
        if (matches) count += matches.length;
    }
    if (count > 0) return String(count);
    
    // Try: Preis-Muster (0.XX €)
    var text = document.body.innerText;
    var prices = text.match(/\\d+\\.\\d+\\s*€/g);
    return prices ? String(prices.length) : '0';
})()
"""}
        }))
        r = json.loads(ws.recv())
        ws.close()
        raw = r.get("result", {}).get("result", {}).get("value", "0")
        return int(raw) if raw.isdigit() else 0
    except Exception:
        return 0


def preflight_check(port: int = CHROME_PORT) -> dict:
    """
    Vollstaendiger Pre-Flight Check vor Command-Ausfuehrung.
    
    Returns:
        {
            "ready": bool,           # Session ist bereit
            "tab_ws": str | None,    # Dashboard WebSocket URL
            "url": str | None,       # Dashboard URL
            "logged_in": bool,       # Login-Status
            "balance": float,        # Guthaben in Euro
            "surveys": int,          # Anzahl verfuegbarer Surveys
            "chrome_alive": bool,    # Chrome laeuft auf Port
            "reason": str | None,    # Warum nicht ready
            "action": str | None,    # Was zu tun ist
        }
    """
    result = {
        "ready": False,
        "tab_ws": None,
        "url": None,
        "logged_in": False,
        "balance": 0.0,
        "surveys": 0,
        "chrome_alive": is_chrome_alive(port),
        "reason": None,
        "action": None,
    }
    
    # Step 1: Chrome alive?
    if not result["chrome_alive"]:
        result["reason"] = "Chrome nicht erreichbar auf Port 9999"
        result["action"] = "start_heypiggy"
        return result
    
    # Step 2: Find HeyPiggy tab
    tab_ws, url = find_heypiggy_tab(port)
    if not tab_ws:
        result["reason"] = "Kein HeyPiggy Dashboard Tab gefunden"
        result["action"] = "start_heypiggy"
        return result
    
    result["tab_ws"] = tab_ws
    result["url"] = url
    
    # Step 3: Check login
    logged_in, _ = check_login(tab_ws)
    result["logged_in"] = logged_in
    
    if not logged_in:
        result["reason"] = "Session abgelaufen (kein 'Abmelden' Button)"
        result["action"] = "start_heypiggy"
        return result
    
    # Step 4: Read balance
    result["balance"] = read_balance(tab_ws)
    
    # Step 5: Count surveys
    result["surveys"] = count_surveys(tab_ws)
    
    # All checks passed
    result["ready"] = True
    return result


def preflight_or_start() -> dict:
    """
    Pre-Flight Check, bei Bedarf Session neu starten.
    
    Returns:
        preflight_check() result mit aktiver Session
    """
    check = preflight_check()
    if check["ready"]:
        return check
    
    print(f"  [PREFLIGHT] Session nicht bereit: {check['reason']}")
    print("  [PREFLIGHT] Starte neue Session...")
    
    # Import start_heypiggy only if needed
    try:
        from survey_cli.commands.start_heypiggy import main as start_heypiggy
        start_result = start_heypiggy()
        
        if start_result.get("status") == "ok":
            # Verify the new session
            time.sleep(2)
            check2 = preflight_check()
            return check2
        else:
            return check
    except ImportError:
        return check


if __name__ == "__main__":
    result = preflight_check()
    print(f"\n{'='*50}")
    print("  PRE-FLIGHT CHECK")
    print(f"{'='*50}")
    print(f"  Chrome alive:  {'YES ✓' if result['chrome_alive'] else 'NO ✗'}")
    print(f"  Tab WS:        {result['tab_ws'][:50] if result['tab_ws'] else 'NONE'}")
    print(f"  Logged in:     {'YES ✓' if result['logged_in'] else 'NO ✗'}")
    print(f"  Balance:       €{result['balance']:.2f}")
    print(f"  Surveys:       {result['surveys']}")
    print(f"  Ready:         {'YES ✓' if result['ready'] else 'NO ✗'}")
    if not result["ready"]:
        print(f"  Reason:        {result['reason']}")
        print(f"  Action:        {result['action']}")
    print(f"{'='*50}")