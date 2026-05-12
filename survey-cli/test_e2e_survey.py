#!/usr/bin/env python3
"""================================================================================
E2E SURVEY TEST — Vollständiger End-to-End Test (2026-05-10)

WAS TESTET DAS?
  1. Chrome starten mit korrekten Flags + Profil 901 Kopie
  2. HeyPiggy Dashboard navigieren
  3. 7 HeyPiggy-Cookies injizieren
  4. Survey öffnen via clickSurvey()
  5. Universal Survey Loop ausführen
  6. Balance vorher/nachher prüfen

KORREKTER WORKFLOW (aus AGENTS.md REGELN 1-4):
  1. Profil 901 (Jeremy) kopieren nach /tmp/
  2. Chrome starten mit --remote-debugging-port=9999 + Flags
  3. Dashboard navigieren + cookies injizieren
  4. Survey klicken → Survey-Tab öffnet sich
  5. Cookies IN Survey-Tab injizieren (KRITISCH!)
  6. Universal Loop ausführen
  7. Balance prüfen

BANNED:
  ❌ pkill -f "Google Chrome" (tötet USER Chrome!)
  ❌ Frisches /tmp/ Profil ohne Cookie-Injection
  ❌ Hardcoded PIDs
  ❌ playstealth launch

NUTZT:
  ✅ survey_cli/survey/chrome.py (ChromeLauncher, inject_heypiggy_cookies_to_tab)
  ✅ survey_cli/survey/opener.py (SurveyOpener._open_in_dashboard_tab)
  ✅ survey_cli/survey/universal/loop.py (run_universal_survey)
  ✅ survey_cli/survey/command_registry.py (acquire/release_survey_lock)
  ✅ commands/surveys/survey-answer-patterns.md (verified CDP patterns)

=================================================================================="""

import json
import os
import sys
import time
import subprocess
import urllib.request
import websocket

# ── Setup Python Path ──────────────────────────────────────────────────────────
WORKSPACE = "/Users/jeremy/dev/stealth-runner"
SURVEY_CLI = os.path.join(WORKSPACE, "survey-cli")
if SURVEY_CLI not in sys.path:
    sys.path.insert(0, SURVEY_CLI)

PROFILE_SRC = os.path.expanduser("~/Library/Application Support/Google Chrome/Profile 901 (Jeremy)")
COOKIE_BACKUP = os.path.expanduser("~/.stealth/heypiggy-backup/heypiggy-cookies.json")
CHROME_PORT = 9999


# ═══════════════════════════════════════════════════════════════════════════════
# STEP 1: Chrome starten (Profile 901 Kopie)
# ═══════════════════════════════════════════════════════════════════════════════


def step1_start_chrome_and_inject():
    """Chrome starten mit Profil 901 Kopie, dann NEW TAB mit Cookies + Navigation."""
    print("\n" + "=" * 60)
    print("STEP 1: Chrome starten + NEW TAB mit Cookies + Navigation")
    print("=" * 60)

    # Existing Chrome auf Port 9999 killen
    try:
        result = subprocess.run(
            ["lsof", "-i", f"TCP:{CHROME_PORT}", "-t"], capture_output=True, text=True, timeout=5
        )
        for pid_line in result.stdout.strip().split("\n"):
            pid_str = pid_line.strip()
            if pid_str.isdigit():
                try:
                    cmdline = subprocess.run(
                        ["ps", "-p", pid_str, "-o", "command="],
                        capture_output=True,
                        text=True,
                        timeout=3,
                    ).stdout
                    if (
                        "/tmp/heypiggy" in cmdline
                        or f"remote-debugging-port={CHROME_PORT}" in cmdline
                    ):
                        subprocess.run(["kill", pid_str], timeout=3)
                        print(f"  Killed existing bot Chrome PID {pid_str}")
                except Exception:
                    pass
    except Exception:
        pass

    time.sleep(1)

    # Profile 901 kopieren
    profile_dir = f"/tmp/heypiggy-new-{int(time.time())}"
    print(f"  Copying Profile 901 → {profile_dir}")
    subprocess.run(["cp", "-R", PROFILE_SRC, profile_dir], timeout=30)

    # Chrome starten (kein URL argument - wir nutzen CDP tabs)
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
    print("  Starting Chrome (no URL)...")
    subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # Warten bis Chrome bereit
    browser_ws_url = None
    for i in range(15):
        try:
            v = json.loads(
                urllib.request.urlopen(
                    f"http://127.0.0.1:{CHROME_PORT}/json/version", timeout=2
                ).read()
            )
            browser_ws_url = v["webSocketDebuggerUrl"]
            print(f"  Chrome ready after {i + 1}s")
            break
        except Exception:
            time.sleep(1)

    if not browser_ws_url:
        print("  ERROR: Chrome not ready")
        return None, profile_dir

    # Create about:blank tab via Browser CDP (kein HTTP API!)
    print("  Creating about:blank tab via Target.createTarget...")
    try:
        ws = websocket.create_connection(browser_ws_url, timeout=15)
        ws.send(
            json.dumps({"id": 1, "method": "Target.createTarget", "params": {"url": "about:blank"}})
        )
        r = json.loads(ws.recv())
        ws.close()
        target_id = r.get("result", {}).get("targetId")
        print(f"  Created tab: {target_id[:20]}")
    except Exception as e:
        print(f"  ERROR creating tab: {e}")
        return None, profile_dir

    # Get the new tab's WS URL
    time.sleep(1)
    pages = json.loads(
        urllib.request.urlopen(f"http://127.0.0.1:{CHROME_PORT}/json", timeout=5).read()
    )
    new_tab = next((p for p in pages if p.get("id") == target_id), None)
    if not new_tab:
        print(f"  ERROR: Tab {target_id[:20]} not in list")
        return None, profile_dir

    tab_ws = new_tab["webSocketDebuggerUrl"]
    print(f"  Tab WS: {tab_ws[:60]}")

    # Enable Network domain on this tab
    print("  Enabling Network domain...")
    try:
        ws = websocket.create_connection(tab_ws, timeout=15)
        ws.send(json.dumps({"id": 1, "method": "Network.enable"}))
        r = json.loads(ws.recv())
        ws.close()
        print(f"  Network enabled: {r}")
    except Exception as e:
        print(f"  Network enable error: {e}")

    # Inject cookies into about:blank tab
    cookies_ok = inject_cookies_into_ws(tab_ws)
    if not cookies_ok:
        print("  WARNING: Cookie injection failed, continuing...")

    # Navigate tab to HeyPiggy dashboard
    print("  Navigating to HeyPiggy dashboard...")
    try:
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
        r = json.loads(ws.recv())
        ws.close()
        print(f"  Navigate result: {r.get('result', {})}")
    except Exception as e:
        print(f"  Navigation error: {e}")

    # Wait for page to load
    time.sleep(5)

    # Verify tab has dashboard URL
    pages = json.loads(
        urllib.request.urlopen(f"http://127.0.0.1:{CHROME_PORT}/json", timeout=5).read()
    )
    for p in pages:
        if p.get("id") == target_id:
            url = p.get("url", "")
            print(f"  Tab URL after navigate: {url[:80]}")
            break

    return tab_ws, profile_dir


def inject_cookies_into_ws(ws_url: str) -> bool:
    """Injiziere 7 HeyPiggy-Cookies in eine WebSocket-Verbindung."""
    if not os.path.exists(COOKIE_BACKUP):
        print(f"  ERROR: Cookie backup not found: {COOKIE_BACKUP}")
        return False

    try:
        with open(COOKIE_BACKUP) as f:
            data = json.load(f)
    except Exception as e:
        print(f"  ERROR: Failed to read cookies: {e}")
        return False

    cookie_names = {
        "PHPSESSID",
        "user_session",
        "user_id",
        "user_a_b_group",
        "lang_pig",
        "g_state",
        "referer",
    }
    heypiggy = [
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
        if c.get("name") in cookie_names
    ]

    if len(heypiggy) < 7:
        print(f"  ERROR: Only {len(heypiggy)}/7 cookies found")
        return False

    print(f"  Injecting {len(heypiggy)} cookies...")
    try:
        ws = websocket.create_connection(ws_url, timeout=15)
        ws.send(
            json.dumps({"id": 1, "method": "Network.setCookies", "params": {"cookies": heypiggy}})
        )
        r = json.loads(ws.recv())
        ws.close()
        success = r.get("result", {}).get("success") is True
        print(f"  Cookies: {'OK ✓' if success else 'FAIL ✗'} → {r}")
        return success
    except Exception as e:
        print(f"  ERROR: {e}")
        return False


# ═══════════════════════════════════════════════════════════════════════════════
# STEP 2: Dashboard Tab finden + Login verifizieren
# ═══════════════════════════════════════════════════════════════════════════════


def step2_verify_dashboard():
    """Find dashboard tab and verify logged in."""
    print("\n" + "=" * 60)
    print("STEP 2: Dashboard verifizieren")
    print("=" * 60)

    pages = json.loads(
        urllib.request.urlopen(f"http://127.0.0.1:{CHROME_PORT}/json", timeout=5).read()
    )
    dash = next(
        (p for p in pages if "dashboard" in p.get("url", "").lower() and p.get("type") == "page"),
        None,
    )
    if not dash:
        print(f"  ERROR: No dashboard tab found. Tabs: {len(pages)}")
        for p in pages:
            print(f"    - {p.get('url', '?')[:80]}")
        return None

    ws_url = dash["webSocketDebuggerUrl"]
    print(f"  Dashboard WS: {ws_url[:60]}...")

    # Check logged in
    try:
        ws = websocket.create_connection(ws_url, timeout=10)
        ws.send(
            json.dumps(
                {
                    "id": 1,
                    "method": "Runtime.evaluate",
                    "params": {"expression": "document.body.innerText.substring(0, 500)"},
                }
            )
        )
        r = json.loads(ws.recv())
        ws.close()
        text = r.get("result", {}).get("result", {}).get("value", "")
        logged_in = "abmelden" in text.lower()
        print(f"  Logged in: {'YES ✓' if logged_in else 'NO ✗'}")
        if not logged_in:
            print(f"  Body preview: {text[:200]}...")
        return ws_url if logged_in else None
    except Exception as e:
        print(f"  ERROR: {e}")
        return None


# ═══════════════════════════════════════════════════════════════════════════════
# STEP 3: HeyPiggy Cookies injizieren
# ═══════════════════════════════════════════════════════════════════════════════


def step3_inject_cookies(ws_url: str):
    """Injiziere 7 HeyPiggy-Cookies in Dashboard-Tab."""
    print("\n" + "=" * 60)
    print("STEP 3: HeyPiggy Cookies injizieren")
    print("=" * 60)

    if not os.path.exists(COOKIE_BACKUP):
        print(f"  ERROR: Cookie backup not found: {COOKIE_BACKUP}")
        return False

    try:
        with open(COOKIE_BACKUP) as f:
            data = json.load(f)
    except Exception as e:
        print(f"  ERROR: Failed to read cookies: {e}")
        return False

    cookie_names = {
        "PHPSESSID",
        "user_session",
        "user_id",
        "user_a_b_group",
        "lang_pig",
        "g_state",
        "referer",
    }
    heypiggy = [
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
        if c.get("name") in cookie_names
    ]

    if len(heypiggy) < 7:
        print(f"  ERROR: Only {len(heypiggy)}/7 cookies found")
        return False

    print(f"  Injecting {len(heypiggy)} cookies...")
    try:
        ws = websocket.create_connection(ws_url, timeout=15)
        ws.send(json.dumps({"id": 1, "method": "Network.enable"}))
        json.loads(ws.recv())
        ws.send(
            json.dumps({"id": 2, "method": "Network.setCookies", "params": {"cookies": heypiggy}})
        )
        r = json.loads(ws.recv())
        ws.close()
        success = r.get("result", {}).get("success") is True
        print(f"  Cookies injected: {'OK ✓' if success else 'FAIL ✗'}")
        return success
    except Exception as e:
        print(f"  ERROR: {e}")
        return False


# ═══════════════════════════════════════════════════════════════════════════════
# STEP 4: Survey öffnen
# ═══════════════════════════════════════════════════════════════════════════════


def step4_find_survey():
    """Find first available survey on dashboard."""
    print("\n" + "=" * 60)
    print("STEP 4: Survey finden")
    print("=" * 60)

    pages = json.loads(
        urllib.request.urlopen(f"http://127.0.0.1:{CHROME_PORT}/json", timeout=5).read()
    )
    dash = next(
        (p for p in pages if "dashboard" in p.get("url", "").lower() and p.get("type") == "page"),
        None,
    )
    if not dash:
        return None, None

    ws_url = dash["webSocketDebuggerUrl"]

    try:
        ws = websocket.create_connection(ws_url, timeout=10)
        ws.send(
            json.dumps(
                {
                    "id": 1,
                    "method": "Runtime.evaluate",
                    "params": {
                        "expression": """
(function() {
    var cards = document.querySelectorAll('[data-survey-id], .survey-item, .survey-card');
    if (cards.length === 0) {
        // Try finding by onclick containing surveyId
        var allLinks = document.querySelectorAll('a[onclick*="survey"], div[onclick*="survey"], button[onclick*="survey"]');
        if (allLinks.length === 0) {
            // Try survey cards by text pattern
            allLinks = document.querySelectorAll('a, button, div[role="button"]');
        }
        var results = [];
        for (var i = 0; i < allLinks.length && results.length < 5; i++) {
            var onclick = allLinks[i].getAttribute('onclick') || '';
            var text = (allLinks[i].textContent || '').trim().substring(0, 50);
            var href = allLinks[i].href || '';
            if (onclick.includes('survey') || href.includes('survey') || text.includes('€')) {
                results.push({text: text, onclick: onclick, href: href, idx: i});
            }
        }
        return JSON.stringify({type: 'links', surveys: results, count: results.length});
    }
    var results = [];
    for (var i = 0; i < Math.min(cards.length, 5); i++) {
        var card = cards[i];
        var onclick = card.getAttribute('onclick') || '';
        var text = (card.textContent || '').trim().substring(0, 100).replace(/\\s+/g, ' ');
        results.push({text: text, onclick: onclick, idx: i});
    }
    return JSON.stringify({type: 'cards', surveys: results, count: cards.length});
})()
"""
                    },
                }
            )
        )
        r = json.loads(ws.recv())
        ws.close()

        raw = r.get("result", {}).get("result", {}).get("value", "{}")
        data = json.loads(raw)

        surveys = data.get("surveys", [])
        print(f"  Found {len(surveys)} survey elements")

        for i, s in enumerate(surveys[:3]):
            print(f"    [{i}] {s.get('text', '')[:80]}")
            onclick = s.get("onclick", "")
            if "surveyId" in onclick or "survey" in onclick.lower():
                print(f"       onclick: {onclick[:100]}")

        # Find clickSurvey() call
        for s in surveys:
            onclick = s.get("onclick", "")
            import re

            m = re.search(r"clickSurvey\(['\"](.+?)['\"]\)", onclick)
            if m:
                survey_id = m.group(1)
                print(f"  Survey ID: {survey_id}")
                return ws_url, survey_id

        return ws_url, None

    except Exception as e:
        print(f"  ERROR: {e}")
        return None, None


def step4_click_survey(dashboard_ws: str, survey_id: str):
    """Click survey card to open modal."""
    print(f"\n  Clicking survey {survey_id}...")
    try:
        ws = websocket.create_connection(dashboard_ws, timeout=10)
        ws.send(
            json.dumps(
                {
                    "id": 1,
                    "method": "Runtime.evaluate",
                    "params": {"expression": f"clickSurvey('{survey_id}')"},
                }
            )
        )
        json.loads(ws.recv())
        ws.close()
        time.sleep(3)

        # Check for modal
        ws = websocket.create_connection(dashboard_ws, timeout=10)
        ws.send(
            json.dumps(
                {
                    "id": 2,
                    "method": "Runtime.evaluate",
                    "params": {
                        "expression": """
(function() {
    var modals = document.querySelectorAll('[class*="modal"], [class*="overlay"], [class*="popup"]');
    var buttons = document.querySelectorAll('button, a[href]');
    var startBtns = [];
    for (var i = 0; i < buttons.length; i++) {
        var t = (buttons[i].textContent || '').trim().toLowerCase();
        if (t.includes('start') || t.includes('beginnen') || t.includes(' teilnehmen')) {
            startBtns.push({text: t, onclick: buttons[i].getAttribute('onclick') || '', href: buttons[i].href || '', idx: i});
        }
    }
    return JSON.stringify({modals: modals.length, startButtons: startBtns, bodyText: document.body.innerText.substring(0, 500)});
})()
"""
                    },
                }
            )
        )
        r = json.loads(ws.recv())
        ws.close()

        raw = r.get("result", {}).get("result", {}).get("value", "{}")
        data = json.loads(raw)

        print(
            f"  Modals: {data.get('modals', 0)}, Start buttons: {len(data.get('startButtons', []))}"
        )

        for btn in data.get("startButtons", []):
            print(
                f"    - {btn.get('text')} | onclick={btn.get('onclick', 'none')[:80]} | href={btn.get('href', '')[:80]}"
            )

        # Check if survey tab opened
        pages = json.loads(
            urllib.request.urlopen(f"http://127.0.0.1:{CHROME_PORT}/json", timeout=5).read()
        )
        non_dash = [
            p
            for p in pages
            if "dashboard" not in p.get("url", "").lower() and "about:blank" not in p.get("url", "")
        ]
        print(f"  Non-dashboard tabs: {len(non_dash)}")

        if non_dash:
            tab = non_dash[0]
            tab_ws = tab["webSocketDebuggerUrl"]
            tab_url = tab.get("url", "")
            print(f"  New tab URL: {tab_url[:80]}")
            return tab_ws

        # If no new tab, survey might open in-page → use dashboard ws
        return dashboard_ws

    except Exception as e:
        print(f"  ERROR: {e}")
        return dashboard_ws


# ═══════════════════════════════════════════════════════════════════════════════
# STEP 5: Survey Tab finden (nach clickSurvey)
# ═══════════════════════════════════════════════════════════════════════════════


def step5_find_survey_tab():
    """Find the survey tab WebSocket URL."""
    print("\n" + "=" * 60)
    print("STEP 5: Survey-Tab finden")
    print("=" * 60)

    pages = json.loads(
        urllib.request.urlopen(f"http://127.0.0.1:{CHROME_PORT}/json", timeout=5).read()
    )
    print(f"  Total tabs: {len(pages)}")

    for p in pages:
        url = p.get("url", "")
        print(f"  - {p.get('id', '?')[:20]} | {url[:70]}")

    # Find non-dashboard, non-blank tab
    for p in pages:
        url = p.get("url", "").lower()
        if "dashboard" not in url and "about:blank" not in url and url.startswith("http"):
            ws_url = p["webSocketDebuggerUrl"]
            print(f"  Survey tab found: {url[:80]}")
            return ws_url, url

    # Fallback: dashboard tab
    for p in pages:
        if "dashboard" in p.get("url", "").lower():
            return p["webSocketDebuggerUrl"], p.get("url", "")

    return None, None


def step5_inject_survey_cookies(survey_ws: str):
    """Inject cookies into survey tab (CRITICAL for balance tracking)."""
    print("\n  Injecting cookies into survey tab...")

    if not os.path.exists(COOKIE_BACKUP):
        return False

    try:
        with open(COOKIE_BACKUP) as f:
            data = json.load(f)

        cookie_names = {
            "PHPSESSID",
            "user_session",
            "user_id",
            "user_a_b_group",
            "lang_pig",
            "g_state",
            "referer",
        }
        heypiggy = [
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
            if c.get("name") in cookie_names
        ]

        if len(heypiggy) < 7:
            print(f"  ERROR: Only {len(heypiggy)}/7 cookies")
            return False

        ws = websocket.create_connection(survey_ws, timeout=15)
        ws.send(json.dumps({"id": 1, "method": "Network.enable"}))
        json.loads(ws.recv())
        ws.send(
            json.dumps({"id": 2, "method": "Network.setCookies", "params": {"cookies": heypiggy}})
        )
        r = json.loads(ws.recv())
        ws.close()

        success = r.get("result", {}).get("success") is True
        print(f"  Survey tab cookies: {'OK ✓' if success else 'FAIL ✗'}")
        return success
    except Exception as e:
        print(f"  ERROR: {e}")
        return False


# ═══════════════════════════════════════════════════════════════════════════════
# STEP 6: Balance lesen
# ═══════════════════════════════════════════════════════════════════════════════


def step6_read_balance():
    """Read heypiggy balance from dashboard."""
    print("\n" + "=" * 60)
    print("STEP 6: Balance lesen (vor Survey)")
    print("=" * 60)

    pages = json.loads(
        urllib.request.urlopen(f"http://127.0.0.1:{CHROME_PORT}/json", timeout=5).read()
    )
    dash = next((p for p in pages if "dashboard" in p.get("url", "").lower()), None)

    if not dash:
        print("  No dashboard found")
        return 0.0

    try:
        ws = websocket.create_connection(dash["webSocketDebuggerUrl"], timeout=10)
        ws.send(
            json.dumps(
                {
                    "id": 1,
                    "method": "Runtime.evaluate",
                    "params": {"expression": "document.body.innerText"},
                }
            )
        )
        r = json.loads(ws.recv())
        ws.close()

        text = r.get("result", {}).get("result", {}).get("value", "")
        amounts = []
        for line in text.split("\n"):
            import re

            found = re.findall(r"(\d+[.,]?\d*)\s*€", line)
            amounts.extend([float(x.replace(",", ".")) for x in found])

        # Filter: balance ≥1.0€, rewards <1€
        valid = [a for a in amounts if a >= 1.0]
        balance = max(valid) if valid else 0.0
        print(f"  Balance: €{balance:.2f}")
        return balance
    except Exception as e:
        print(f"  ERROR: {e}")
        return 0.0


# ═══════════════════════════════════════════════════════════════════════════════
# STEP 7: Universal Survey Loop
# ═══════════════════════════════════════════════════════════════════════════════


def step7_run_survey_loop(survey_ws: str, survey_id: str):
    """Run the universal survey loop."""
    print("\n" + "=" * 60)
    print("STEP 7: Universal Survey Loop")
    print("=" * 60)

    try:
        from survey.universal.loop import run_universal_survey
        from survey.profile_loader import ProfileLoader

        profile = ProfileLoader.load_profile()
        print(
            f"  Profile: {profile.get('age')}yo {profile.get('gender')} from {profile.get('city')}"
        )

        # Survey lock
        from survey.command_registry import acquire_survey_lock, release_survey_lock

        if not acquire_survey_lock(survey_id):
            print("  ERROR: Survey already locked (another survey running)")
            return None

        try:
            result = run_universal_survey(
                ws_url=survey_ws,
                profile=profile,
                survey_id=survey_id,
                max_steps=30,
                cdp_port=CHROME_PORT,
            )

            print(f"\n  RESULT: {result.status}")
            print(f"  Steps: {result.steps}")
            print(f"  Earned: €{result.earned:.2f}")
            print(
                f"  Balance before/after: €{result.balance_before:.2f} → €{result.balance_after:.2f}"
            )
            print(f"  Completion: {'YES ✓' if result.completion_detected else 'NO ✗'}")
            print(f"  Screen-out: {'YES' if result.screen_out else 'NO'}")

            if result.history:
                print(f"  History ({len(result.history)} steps):")
                for h in result.history[-5:]:
                    print(f"    - {h[:100]}")

            return result
        finally:
            release_survey_lock()

    except ImportError as e:
        print(f"  Import error: {e}")
        # Fallback: run universal agent
        try:
            from survey.universal.agent import run_universal_agent
            import os as _os

            result = run_universal_agent(
                ws_url=survey_ws,
                max_steps=20,
                task="Complete the survey",
                api_key=_os.environ.get("NVIDIA_API_KEY"),
            )
            print(f"  Agent result: {result}")
            return result
        except Exception as e2:
            print(f"  Fallback also failed: {e2}")
            return None


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════


def main():
    print("=" * 60)
    print("  E2E SURVEY TEST — Stealth-Runner")
    print("=" * 60)

    # STEP 1: Chrome starten + Cookies injizieren
    result = step1_start_chrome_and_inject()
    if not result:
        print("FAILED: Chrome not started")
        return
    dashboard_ws, profile_dir = result
    print(f"  Dashboard WS: {dashboard_ws[:60]}...")

    # STEP 2: Login verifizieren
    logged_in = step2_verify_dashboard()
    if not logged_in:
        print("FAILED: Not logged in to HeyPiggy")
        return

    # STEP 3: Survey finden auf Dashboard
    dash_ws, survey_id = step4_find_survey()
    if not survey_id:
        print("FAILED: No survey found")
        return

    # STEP 4: Survey klicken → Modal oder Tab öffnet sich
    survey_ws = step4_click_survey(dash_ws, survey_id)

    # STEP 5: Survey-Tab finden
    survey_ws, survey_url = step5_find_survey_tab()
    if not survey_ws:
        print("FAILED: No survey tab found")
        return

    print(f"\n  Survey Tab WS: {survey_ws[:60]}")
    print(f"  Survey URL: {survey_url[:80]}")

    # STEP 6: Cookies in Survey-Tab injizieren (KRITISCH für balance tracking)
    step5_inject_survey_cookies(survey_ws)

    # STEP 7: Balance lesen (vor)
    balance_before = step6_read_balance()

    # STEP 8: Universal Survey Loop
    result = step7_run_survey_loop(survey_ws, survey_id)

    # STEP 9: Balance lesen (nach)
    print("\n" + "=" * 60)
    print("STEP 9: Balance nach Survey")
    print("=" * 60)
    balance_after = step6_read_balance()
    print(f"  Balance: €{balance_after:.2f} (before: €{balance_before:.2f})")
    print(f"  Delta: €{balance_after - balance_before:.2f}")

    print("\n" + "=" * 60)
    print("  E2E TEST COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    main()
