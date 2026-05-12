#!/usr/bin/env python3
"""
================================================================================
START HEYPIGGY — Command zum Starten einer HeyPiggy Session (2026-05-10)

WAS DAS TUT:
  1. Chrome mit Profil 901 (Jeremy) Kopie starten auf Port 9999
  2. Neue Tab erstellen via Target.createTarget
  3. 7 HeyPiggy-Cookies in Tab injizieren
  4. Zur HeyPiggy Dashboard navigieren
  5. Login verifizieren

WARUM DIESER WORKFLOW?
  - Profil-Kopie allein reicht nicht (verschlüsselte Cookies)
  - Cookies MÜSSEN per CDP injiziert werden nach Tab-Erstellung
  - about:blank Tab erstellen → cookies → navigation ist die korrekte Reihenfolge

VERIFIZIERT: 2026-05-10 — Login funktioniert, Dashboard zeigt "Abmelden"

NUTZT:
  - commands/chrome/cdp-start.md (Chrome Flags)
  - survey-cli/survey/chrome.py (Profile copy, cookie names)
  - ~/.stealth/heypiggy-backup/heypiggy-cookies.json (7 cookies)

BANNED:
  ❌ pkill -f "Google Chrome" (tötet USER Chrome!)
  ❌ Frisches /tmp/ Profil ohne Cookie-Injection
  ❌ Chrome direkt mit Dashboard URL starten (keine cookies)

=================================================================================="""

import json
import os
import subprocess
import sys
import time
import urllib.request
import websocket

# ── Config ─────────────────────────────────────────────────────────────────────
CHROME_PORT = 9999
PROFILE_SRC = os.path.expanduser("~/Library/Application Support/Google Chrome/Profile 901 (Jeremy)")
COOKIE_BACKUP = os.path.expanduser("~/.stealth/heypiggy-backup/heypiggy-cookies.json")
HEYPIGGY_COOKIE_NAMES = {
    "PHPSESSID",
    "user_session",
    "user_id",
    "user_a_b_group",
    "lang_pig",
    "g_state",
    "referer",
}


def kill_bot_chrome():
    """Kill only bot Chrome on port 9999 (NOT user Chrome!)."""
    try:
        result = subprocess.run(
            ["lsof", "-i", f"TCP:{CHROME_PORT}", "-t"], capture_output=True, text=True, timeout=5
        )
        for pid_str in result.stdout.strip().split("\n"):
            pid_str = pid_str.strip()
            if not pid_str.isdigit():
                continue
            try:
                cmdline = subprocess.run(
                    ["ps", "-p", pid_str, "-o", "command="],
                    capture_output=True,
                    text=True,
                    timeout=3,
                ).stdout
                # ONLY kill bot Chrome (/tmp/heypiggy profile)
                if "/tmp/heypiggy" in cmdline:
                    subprocess.run(["kill", pid_str], timeout=3)
                    print(f"  Killed bot PID {pid_str}")
            except Exception:
                pass
    except Exception:
        pass


def load_heypiggy_cookies() -> list[dict]:
    """Load 7 HeyPiggy cookies from backup file."""
    if not os.path.exists(COOKIE_BACKUP):
        raise FileNotFoundError(f"Cookie backup not found: {COOKIE_BACKUP}")

    with open(COOKIE_BACKUP) as f:
        data = json.load(f)

    cookies = [
        {
            "name": c["name"],
            "value": c["value"],
            "domain": c.get("domain", "www.heypiggy.com"),
            "path": c.get("path", "/"),
            "expires": c.get("expires", -1),
            "secure": c.get("secure", False),
            "httpOnly": c.get("httpOnly", False),
        }
        for c in data.get("cookies", [])
        if c.get("name") in HEYPIGGY_COOKIE_NAMES
    ]

    if len(cookies) < 7:
        raise ValueError(f"Only {len(cookies)}/7 HeyPiggy cookies found")

    return cookies


def start_chrome() -> str:
    """Start Chrome with Profile 901 copy on port 9999. Returns browser WS URL."""
    # 1. Kill existing bot Chrome
    kill_bot_chrome()
    time.sleep(1)

    # 2. Copy Profile 901
    profile_dir = f"/tmp/heypiggy-new-{int(time.time())}"
    print(f"  Copying Profile 901 → {profile_dir}")
    result = subprocess.run(["cp", "-R", PROFILE_SRC, profile_dir], timeout=30, capture_output=True)
    if result.returncode != 0:
        raise RuntimeError(f"Profile copy failed: {result.stderr}")

    # 3. Start Chrome (NO URL argument — we create tabs via CDP)
    chrome_bin = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    cmd = [
        chrome_bin,
        f"--remote-debugging-port={CHROME_PORT}",
        "--remote-allow-origins=*",
        "--force-renderer-accessibility",
        "--no-first-run",
        "--no-default-browser-check",
        f"--user-data-dir={profile_dir}",
    ]
    print("  Starting Chrome...")
    subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # 4. Wait for CDP
    browser_ws = None
    for i in range(15):
        try:
            v = json.loads(
                urllib.request.urlopen(
                    f"http://127.0.0.1:{CHROME_PORT}/json/version", timeout=2
                ).read()
            )
            browser_ws = v["webSocketDebuggerUrl"]
            print(f"  Chrome ready after {i + 1}s")
            break
        except Exception:
            time.sleep(1)

    if not browser_ws:
        raise RuntimeError("Chrome not ready after 15s")

    return browser_ws


def create_tab_with_cookies(browser_ws: str) -> tuple[str, str]:
    """Create about:blank tab, inject cookies, return (tab_ws, target_id)."""
    # 1. Create about:blank tab
    print("  Creating about:blank tab...")
    ws = websocket.create_connection(browser_ws, timeout=15)
    ws.send(
        json.dumps({"id": 1, "method": "Target.createTarget", "params": {"url": "about:blank"}})
    )
    r = json.loads(ws.recv())
    ws.close()
    target_id = r.get("result", {}).get("targetId")
    if not target_id:
        raise RuntimeError(f"Target.createTarget failed: {r}")
    print(f"  Tab created: {target_id[:20]}")

    time.sleep(1)

    # 2. Find tab's WS URL
    pages = json.loads(
        urllib.request.urlopen(f"http://127.0.0.1:{CHROME_PORT}/json", timeout=5).read()
    )
    tab = next((p for p in pages if p.get("id") == target_id), None)
    if not tab:
        raise RuntimeError(f"Tab {target_id[:20]} not in list")
    tab_ws = tab["webSocketDebuggerUrl"]
    print(f"  Tab WS: {tab_ws[:60]}")

    # 3. Enable Network domain
    print("  Enabling Network domain...")
    ws = websocket.create_connection(tab_ws, timeout=15)
    ws.send(json.dumps({"id": 1, "method": "Network.enable"}))
    json.loads(ws.recv())
    ws.close()

    # 4. Inject cookies
    print(f"  Injecting {len(load_heypiggy_cookies())} cookies...")
    cookies = load_heypiggy_cookies()
    ws = websocket.create_connection(tab_ws, timeout=15)
    ws.send(json.dumps({"id": 2, "method": "Network.setCookies", "params": {"cookies": cookies}}))
    r = json.loads(ws.recv())
    ws.close()
    success = r.get("result", {}).get("success") is True
    print(f"  Cookies injected: {'OK ✓' if success else 'FAIL ✗'}")

    return tab_ws, target_id


def navigate_to_dashboard(tab_ws: str):
    """Navigate tab to HeyPiggy dashboard."""
    print("  Navigating to HeyPiggy dashboard...")
    ws = websocket.create_connection(tab_ws, timeout=15)
    ws.send(
        json.dumps(
            {
                "id": 1,
                "method": "Page.navigate",
                "params": {"url": "https://www.heypiggy.com/?page=dashboard"},
            }
        )
    )
    json.loads(ws.recv())  # consume response
    ws.close()
    print("  Navigation sent, waiting 5s for page load...")
    time.sleep(5)


def verify_login(tab_ws: str) -> dict:
    """Verify HeyPiggy login. Returns {logged_in, balance, text_preview}."""
    try:
        ws = websocket.create_connection(tab_ws, timeout=15)
        ws.send(
            json.dumps(
                {
                    "id": 1,
                    "method": "Runtime.evaluate",
                    "params": {"expression": "document.body.innerText.substring(0, 800)"},
                }
            )
        )
        r = json.loads(ws.recv())
        ws.close()
        text = r.get("result", {}).get("result", {}).get("value", "")

        logged_in = "abmelden" in text.lower()

        # Balance extraction (filter rewards < 1€, balance ≥ 1€)
        balance = 0.0
        amounts = []
        import re

        all_amounts = re.findall(r"(\d+[.,]?\d*)\s*€", text)
        for a in all_amounts:
            v = float(a.replace(",", "."))
            if v >= 1.0:
                amounts.append(v)
        if amounts:
            balance = max(amounts)  # Take HIGHEST (balance, not reward)

        return {
            "logged_in": logged_in,
            "balance": balance,
            "text_preview": text[:200],
        }
    except Exception as e:
        return {"logged_in": False, "balance": 0.0, "text_preview": "", "error": str(e)}


def main() -> dict:
    """
    Execute the full start-heypiggy workflow.

    Returns:
        {
            "status": "ok" | "error",
            "tab_ws": str,       # Dashboard tab WebSocket URL
            "target_id": str,    # Tab target ID
            "logged_in": bool,
            "balance": float,
            "profile_dir": str,
        }
    """
    print("=" * 60)
    print("  START HEYPIGGY — Step-by-Step")
    print("=" * 60)

    try:
        # 1. Start Chrome
        print("\n[1] Starting Chrome...")
        browser_ws = start_chrome()

        # 2. Create tab + inject cookies
        print("\n[2] Creating tab + injecting cookies...")
        tab_ws, target_id = create_tab_with_cookies(browser_ws)

        # 3. Navigate to dashboard
        print("\n[3] Navigating to HeyPiggy dashboard...")
        navigate_to_dashboard(tab_ws)

        # 4. Verify login
        print("\n[4] Verifying login...")
        result = verify_login(tab_ws)
        result["status"] = "ok" if result["logged_in"] else "error"
        result["tab_ws"] = tab_ws
        result["target_id"] = target_id
        result["profile_dir"] = f"/tmp/heypiggy-new-{int(time.time()) - 10}"  # approximate

        print(f"\n  Logged in: {'YES ✓' if result['logged_in'] else 'NO ✗'}")
        print(f"  Balance: €{result['balance']:.2f}")
        print(f"  Tab WS: {tab_ws[:60]}")

        if not result["logged_in"]:
            print(f"  Text preview: {result['text_preview'][:200]}...")

        print("\n" + "=" * 60)
        print("  RESULT: " + ("OK ✓" if result["logged_in"] else "ERROR ✗"))
        print("=" * 60)

        return result

    except Exception as e:
        print(f"\n  ERROR: {e}")
        import traceback

        traceback.print_exc()
        return {"status": "error", "error": str(e)}


if __name__ == "__main__":
    result = main()
    if result.get("status") == "ok":
        sys.exit(0)
    else:
        sys.exit(1)
