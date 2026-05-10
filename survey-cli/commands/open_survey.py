#!/usr/bin/env python3
"""
OPEN SURVEY — Survey Modal → Survey-Tab (VERIFIED 2026-05-10)

FLOW (4 Steps):
1. clickSurvey() auf Dashboard → Modal mit "Umfrage starten" Button
2. "Umfrage starten" klicken → Modal schliesst, last_link geladen
3. last_link + subids → PUT /json/new?<url> → NEUER TAB erstellt
4. 7 HeyPiggy-Cookies injizieren → Page.navigate → Survey startet

CRITICAL INSIGHT:
- window.open interception FUNKTIONIERT NICHT (openSurvey ruft window.open auf NACH
  window.open= override assignment im JS scope)
- Stattdessen: window.last_link direkt lesen + subids hinzufuegen
- Target.createTarget endpoint = PUT /json/new?<url> (NICHT /json/protocol/targets/create!)
- KEIN Runtime.enable auf neuem Tab (flooded Buffer, eval responses verloren!)

VERIFIED:
- Modal oeffnet sich nach clickSurvey()
- last_link = CPX URL mit k=...&subid_2=website&subid_1=adsplashxmas
- PUT /json/new erstellt neuen Tab
- 7 Cookies injiziert (PHPSESSID, user_session, user_id, etc.)
- Survey navigiert: CPX → Samplicio → Potloc → PureSpectrum (oder Provider)
- Session retained throughout redirect chain (abmelden found in body)
- Provider: purespectrum (URL: screener.purespectrum.com)

ABHAENGIGKEITEN:
- start_heypiggy.py (Chrome + Dashboard)
- preflight_check.py (Session validiert)
- find_survey.py (clickSurvey ausgefuehrt)

NUTZT:
- CDP HTTP: PUT /json/new?<url> (Tab erstellen)
- CDP WS: Network.setCookies (Cookies injizieren)
- CDP WS: Runtime.evaluate (last_link, subids lesen)
- CDP WS: Page.navigate (Navigieren nach Cookie-Injection)
"""

import asyncio, json, subprocess, os, sys
from urllib.parse import urlparse, parse_qs, urlunparse

CHROME_PORT = 9999
COOKIE_BACKUP = os.path.expanduser("~/.stealth/heypiggy-backup/heypiggy-cookies.json")


def load_heypiggy_cookies():
    """Lade 7 HeyPiggy-Cookies aus Backup."""
    with open(COOKIE_BACKUP) as f:
        data = json.load(f)
    return [
        {
            "name": c["name"],
            "value": c["value"],
            "domain": c["domain"],
            "path": c.get("path", "/"),
            "expires": c.get("expires", -1),
            "secure": c.get("secure", False),
            "httpOnly": c.get("httpOnly", False),
        }
        for c in data.get("cookies", [])
        if "heypiggy" in c.get("domain", "").lower()
        and c.get("value") and c.get("value") != "deleted"
    ]


async def _recv_target(ws, target_id, timeout=15):
    """Empfange Nachricht mit passender ID (draint alle Event-Nachrichten)."""
    deadline = asyncio.get_running_loop().time() + timeout
    for _ in range(200):
        remaining = max(0.1, deadline - asyncio.get_running_loop().time())
        if remaining <= 0:
            return None
        try:
            msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=remaining))
            if msg.get("id") == target_id:
                return msg
        except asyncio.TimeoutError:
            return None
    return None


async def _eval_js(ws, msg_id, expression, timeout=20):
    """Evaluiere JS auf WebSocket und returne result.value."""
    await ws.send(json.dumps({"id": msg_id, "method": "Runtime.evaluate", "params": {"expression": expression}}))
    msg = await _recv_target(ws, msg_id, timeout)
    if msg:
        return msg.get("result", {}).get("result", {}).get("value", None)
    return None


async def get_survey_url(dashboard_ws: str) -> dict:
    """
    Lese window.last_link + subids und baue Survey-URL mit Tracking-Parametern.

    Returns:
        {
            "status": "ok" | "error",
            "last_link": str,       # Original CPX URL
            "subid_cpx": str,       # subid_2 value
            "subid_cpx1": str,      # subid_1 value
            "survey_url": str,      # URL mit subid_2 + subid_1 Parameter
            "provider": str,        # Provider name
        }
    """
    import websockets
    async with websockets.connect(dashboard_ws) as ws:
        # Runtime.enable noetig fuer JS click handlers
        await ws.send(json.dumps({"id": 1, "method": "Runtime.enable"}))
        await asyncio.sleep(0.5)
        # Drain events
        for _ in range(50):
            try:
                await asyncio.wait_for(ws.recv(), timeout=0.5)
            except:
                break

        # Check ob Modal bereits offen (find_survey hat clickSurvey schon aufgerufen)
        body = await _eval_js(ws, 2, "document.body.innerText", 10)
        modal_open = "Umfrage starten" in (body or "") and "beginnen" in (body or "")
        print(f"    [MODAL] Open: {modal_open}")

        if not modal_open:
            return {"status": "error", "reason": "Modal nicht offen — find_survey muss zuerst clickSurvey ausfuehren"}

        # Lese last_link + subids
        last_link = await _eval_js(ws, 5, "window.last_link", 10)
        subid_cpx = await _eval_js(ws, 6, "window.subid_cpx", 10) or ""
        subid_cpx1 = await _eval_js(ws, 7, "window.subid_cpx1", 10) or ""

        if not last_link:
            return {"status": "error", "reason": "window.last_link ist undefined"}

        # Baue URL mit subids (wie openSurvey() es macht)
        parsed = urlparse(last_link)
        qs = parse_qs(parsed.query)
        qs["subid_2"] = [subid_cpx]
        qs["subid_1"] = [subid_cpx1]
        new_query = "&".join(f"{k}={v[0]}" for k, v in qs.items())
        survey_url = urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_query, parsed.fragment))

        # Provider erkennen (URL-basiert)
        provider = "unknown"
        for p in ["purespectrum", "cint", "toluna", "qualtrics", "samplicio", "ipsos", "nfield", "samplicious", "potloc", "samplicio.us", "click.cpx", "screener.purespectrum"]:
            if p in survey_url.lower():
                provider = p.replace(".us", "").replace(".cpx", "").replace("screener.", "").split(".")[0]
                break

        print(f"    [URL] last_link: {last_link[:60]}...")
        print(f"    [URL] subid_2: {subid_cpx}, subid_1: {subid_cpx1}")
        print(f"    [URL] Survey URL: {survey_url[:80]}...")
        print(f"    [URL] Provider: {provider}")

        return {
            "status": "ok",
            "last_link": last_link,
            "subid_cpx": subid_cpx,
            "subid_cpx1": subid_cpx1,
            "survey_url": survey_url,
            "provider": provider,
        }


async def click_start_button(dashboard_ws: str) -> dict:
    """Klicke 'Umfrage starten' Button im Modal (schliesst Modal)."""
    import websockets
    async with websockets.connect(dashboard_ws) as ws:
        await ws.send(json.dumps({"id": 1, "method": "Runtime.enable"}))
        await asyncio.sleep(0.5)
        for _ in range(50):
            try:
                await asyncio.wait_for(ws.recv(), timeout=0.5)
            except:
                break

        result = await _eval_js(ws, 2, """
(function() {
    var btns = [...document.querySelectorAll('button')];
    var btn = btns.find(function(b) {
        return b.textContent.trim() === 'Umfrage starten' && b.offsetParent !== null;
    });
    if (btn) { btn.click(); return 'CLICKED'; }
    return 'NOT_FOUND';
})()
""", 10)

        await asyncio.sleep(2)
        return {"status": "ok" if result == "CLICKED" else "error", "result": result}


async def create_survey_tab(survey_url: str) -> dict:
    """
    Erstelle neuen Tab via PUT /json/new?<url> (KEIN Popup Blocker!).

    KRITISCH: Endpoint ist PUT /json/new?<url>, NICHT POST /json/protocol/targets/create!

    Returns:
        {
            "status": "ok" | "error",
            "tab_ws": str,           # WebSocket URL des neuen Tabs
            "tab_id": str,           # Tab ID
        }
    """
    try:
        result = subprocess.run(
            ["curl", "-s", "-X", "PUT", f"http://127.0.0.1:{CHROME_PORT}/json/new?{survey_url}"],
            capture_output=True, text=True, timeout=30
        )
        target = json.loads(result.stdout)
        tab_ws = target.get("webSocketDebuggerUrl", "")
        tab_id = target.get("id", "")

        if not tab_ws:
            return {"status": "error", "reason": f"Kein WS URL: {json.dumps(target)}"}

        print(f"    [TAB] Created: id={tab_id[:20]}, ws={tab_ws[:60]}...")
        return {"status": "ok", "tab_ws": tab_ws, "tab_id": tab_id}
    except Exception as e:
        return {"status": "error", "reason": str(e)}


async def inject_cookies_and_navigate(tab_ws: str, survey_url: str, cookies: list) -> dict:
    """
    Injiziere 7 HeyPiggy-Cookies in neuen Tab und navigiere zum Survey.

    WICHTIG: Keine Runtime.enable / Network.enable / Page.enable auf dem neuen Tab!
    Diese erzeugen Events die den WebSocket-Buffer flooden und eval-Responses gehen verloren!

    Returns:
        {
            "status": "ok" | "error",
            "url": str,              # Aktuelle URL nach Navigation
            "body": str,             # Body Text (fuer completion detection)
            "logged_in": bool,       # abmelden in body?
        }
    """
    import websockets
    async with websockets.connect(tab_ws) as ws:
        # KEINE Runtime.enable / Network.enable hier!
        # Nur inject cookies, dann navigate

        # Inject 7 HeyPiggy Cookies
        await ws.send(json.dumps({"id": 1, "method": "Network.setCookies", "params": {"cookies": cookies}}))
        msg = await _recv_target(ws, 1, 10)
        print(f"    [COOKIES] Injected: {len(cookies)}, result={msg}")

        await asyncio.sleep(2)

        # Navigate to survey URL
        await ws.send(json.dumps({"id": 2, "method": "Page.navigate", "params": {"url": survey_url}}))
        await asyncio.sleep(10)

        # Get body text (collect messages 15s)
        body = None
        await ws.send(json.dumps({"id": 3, "method": "Runtime.evaluate",
                                  "params": {"expression": "document.body ? document.body.innerText.substring(0, 500) : 'NO_BODY'"}}))
        for _ in range(50):
            try:
                msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
                if msg.get("id") == 3:
                    body = msg.get("result", {}).get("result", {}).get("value", "")
                    break
            except:
                pass

        # Get URL
        url = None
        await ws.send(json.dumps({"id": 4, "method": "Runtime.evaluate",
                                  "params": {"expression": "window.location.href"}}))
        for _ in range(30):
            try:
                msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
                if msg.get("id") == 4:
                    url = msg.get("result", {}).get("result", {}).get("value", "")
                    break
            except:
                pass

        logged_in = "abmelden" in (body or "").lower()
        print(f"    [NAV] URL: {url[:100] if url else 'NONE'}")
        print(f"    [NAV] Body: {len(body or '')} chars, logged_in={logged_in}")

        return {"status": "ok", "url": url, "body": body, "logged_in": logged_in}


async def open_survey(dashboard_ws: str) -> dict:
    """
    Kompletter Workflow: Modal → Survey-Tab mit Cookies + Session.

    Args:
        dashboard_ws: WebSocket URL des Dashboard-Tabs

    Returns:
        {
            "status": "ok" | "error",
            "survey_url": str,       # Survey URL mit subids
            "tab_ws": str,           # Survey Tab WebSocket URL
            "provider": str,         # Provider name
            "url": str,              # Aktuelle URL im Tab
            "body": str,             # Body Text
            "logged_in": bool,       # Session aktive?
            "screen_out": bool,      # Screen-out erkannt?
            "completion": bool,      # Survey komplett?
        }
    """
    print(f"\n{'='*50}")
    print(f"  OPEN SURVEY")
    print(f"{'='*50}")

    # 1. Get survey URL + subids
    url_info = await get_survey_url(dashboard_ws)
    if url_info["status"] != "ok":
        return {"status": "error", "reason": url_info.get("reason")}

    survey_url = url_info["survey_url"]
    provider = url_info["provider"]

    # 2. Click "Umfrage starten" (schliesst Modal)
    click_result = await click_start_button(dashboard_ws)
    print(f"    [CLICK] Button: {click_result['result']}")

    # 3. Create new tab
    tab_info = await create_survey_tab(survey_url)
    if tab_info["status"] != "ok":
        return {"status": "error", "reason": tab_info.get("reason")}

    tab_ws = tab_info["tab_ws"]

    # 4. Load cookies
    cookies = load_heypiggy_cookies()
    print(f"    [COOKIES] Loaded: {len(cookies)} HeyPiggy cookies")

    # 5. Inject cookies + navigate
    nav_info = await inject_cookies_and_navigate(tab_ws, survey_url, cookies)

    # 6. Detect screen-out / completion
    body_lower = (nav_info.get("body") or "").lower()
    screen_out = any(kw in body_lower for kw in ["umfrage passt nicht", "leider", "nicht geeignet", "vorzeitig beendet"])
    completion = any(kw in body_lower for kw in ["vielen dank", "thank you", "abgeschlossen", "fertig"])

    print(f"    [DETECT] screen_out={screen_out}, completion={completion}")

    return {
        "status": "ok",
        "survey_url": survey_url,
        "tab_ws": tab_ws,
        "provider": provider,
        "url": nav_info.get("url"),
        "body": nav_info.get("body"),
        "logged_in": nav_info.get("logged_in"),
        "screen_out": screen_out,
        "completion": completion,
    }


# CLI entry point
if __name__ == "__main__":
    sys.path.insert(0, "/Users/jeremy/dev/stealth-runner/survey-cli")
    from commands.preflight_check import preflight_check

    check = preflight_check()
    if not check["ready"]:
        print("Session not ready. Run start_heypiggy.py first.")
        sys.exit(1)

    print(f"  Dashboard WS: {check['tab_ws'][:60]}...")

    result = asyncio.run(open_survey(check["tab_ws"]))

    print(f"\n{'='*50}")
    if result["status"] == "ok":
        print(f"  Status: OK ✓")
        print(f"  Provider: {result.get('provider')}")
        print(f"  Tab WS: {result.get('tab_ws', '')[:60]}...")
        print(f"  URL: {result.get('url', '')[:80]}")
        print(f"  Logged in: {result.get('logged_in')}")
        print(f"  Screen-out: {result.get('screen_out')}")
        print(f"  Completion: {result.get('completion')}")
    else:
        print(f"  Status: ERROR")
        print(f"  Reason: {result.get('reason')}")
    print(f"{'='*50}")