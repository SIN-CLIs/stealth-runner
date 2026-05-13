#!/usr/bin/env python3
"""
Test open_survey flow:
1. Click survey card -> modal appears with "Umfrage starten"
2. Click "Umfrage starten" button -> capture survey URL (via last_link + subids)
3. Create new tab via Target.createTarget with captured URL
4. Inject 7 HeyPiggy cookies into new tab
5. Verify logged in (abmelden in body)
"""

# === SR-63 #62 legacy-debt skip (do not delete without unskipping) ===
import pytest
pytestmark = pytest.mark.skip(reason="SR-63 #62: E2E test requires real browser + live CDP; not suitable for CI")
# === END SR-63 skip ===

import asyncio
import json
import subprocess
import os


async def recv_target(ws, target_id, timeout=10):
    """Receive WebSocket message matching target ID (drains all event messages)."""
    deadline = asyncio.get_running_loop().time() + timeout
    for _ in range(200):
        remaining = max(0.1, deadline - asyncio.get_running_loop().time())
        if remaining <= 0:
            return None
        try:
            msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=remaining))
            if msg.get('id') == target_id:
                return msg
            # Event message (no 'id' field) - keep draining
        except asyncio.TimeoutError:
            return None
    return None


async def eval_js(ws, msg_id, expression, timeout=15):
    """Evaluate JS and return result value."""
    await ws.send(json.dumps({'id': msg_id, 'method': 'Runtime.evaluate', 'params': {'expression': expression}}))
    msg = await recv_target(ws, msg_id, timeout)
    if msg:
        return msg.get('result', {}).get('result', {}).get('value', None)
    return None


async def test_open_survey():
    print("=" * 60)
    print("OPEN_SURVEY TEST - modal -> tab -> cookies -> verify")
    print("=" * 60)

    # 1. Verify Chrome running
    try:
        version = json.loads(subprocess.run(
            ['curl', '-s', 'http://127.0.0.1:9999/json/version'], capture_output=True, text=True).stdout)
        print(f"[1] Chrome OK: {version.get('Browser', 'unknown')}")
    except:
        print("[1] ERROR: Chrome not running on port 9999")
        return

    # 2. Get dashboard tab WS
    pages = json.loads(subprocess.run(
        ['curl', '-s', 'http://127.0.0.1:9999/json/list'], capture_output=True, text=True).stdout)
    dashboard = next((p for p in pages if 'dashboard' in p.get('url', '') and p.get('type') == 'page'), None)
    if not dashboard:
        print("[2] ERROR: No dashboard tab found")
        return
    ws_url = dashboard['webSocketDebuggerUrl']
    print(f"[2] Dashboard WS: {ws_url[:60]}...")

    # 3. Load 7 Heypiggy cookies
    cookie_file = os.path.expanduser('~/.stealth/heypiggy-backup/heypiggy-cookies.json')
    with open(cookie_file) as f:
        cookie_data = json.load(f)
    heypiggy_cookies = [
        {
            'name': c['name'],
            'value': c['value'],
            'domain': c['domain'],
            'path': c.get('path', '/'),
            'expires': c.get('expires', -1),
            'secure': c.get('secure', False),
            'httpOnly': c.get('httpOnly', False)
        }
        for c in cookie_data.get('cookies', [])
        if 'heypiggy' in c.get('domain', '').lower()
        and c.get('value') and c.get('value') != 'deleted'
    ]
    print(f"[3] Cookies to inject: {len(heypiggy_cookies)} (PHPSESSID, user_session, user_id, etc.)")

    # 4. Connect to dashboard
    import websockets
    async with websockets.connect(ws_url) as ws:
        # IMPORTANT: Runtime.enable must be called for JS click handlers to work
        await ws.send(json.dumps({'id': 1, 'method': 'Runtime.enable'}))
        await asyncio.sleep(0.5)
        # Drain event messages (consoleAPICalled, etc.)
        for _ in range(50):
            try:
                await asyncio.wait_for(ws.recv(), timeout=0.5)
            except:
                break

        # 4a. Check modal state - if closed, re-open by clicking highest-value survey
        body_text = await eval_js(ws, 2, 'document.body.innerText', 10)
        modal_open = 'Umfrage starten' in (body_text or '') and 'beginnen' in (body_text or '')
        print(f"[4a] Modal open: {modal_open}")

        if not modal_open:
            print("[4a] Re-opening modal by clicking survey card...")
            # Click highest-value survey (€0.40, ID 67038730)
            await eval_js(ws, 3, 'clickSurvey("67038730")', 10)
            await asyncio.sleep(3)
            body_text = await eval_js(ws, 4, 'document.body.innerText', 10)
            modal_open = 'Umfrage starten' in (body_text or '') and 'beginnen' in (body_text or '')
            print(f"[4a] Modal re-opened: {modal_open}")

        if not modal_open:
            print("[4a] ERROR: Modal did not open. Body text:")
            print((body_text or '')[:500])
            return

        print("[4b] Modal confirmed open. Getting survey URL...")

        # 5. Get last_link + subids to build survey URL
        last_link = await eval_js(ws, 5, 'window.last_link', 10)
        subid_cpx = await eval_js(ws, 6, 'window.subid_cpx', 10)
        subid_cpx1 = await eval_js(ws, 7, 'window.subid_cpx1', 10)
        print(f"[5] last_link: {last_link[:100] if last_link else 'UNDEFINED'}...")
        print(f"[5] subid_cpx: {subid_cpx}")
        print(f"[5] subid_cpx1: {subid_cpx1}")

        if not last_link:
            print("[5] ERROR: window.last_link is undefined!")
            return

        # Build survey URL with subids (like openSurvey() does)
        from urllib.parse import urlparse, parse_qs, urlunparse
        parsed = urlparse(last_link)
        qs = parse_qs(parsed.query)
        qs['subid_2'] = [subid_cpx or '']
        qs['subid_1'] = [subid_cpx1 or '']
        new_query = '&'.join(f'{k}={v[0]}' for k, v in qs.items())
        survey_url = urlunparse((
            parsed.scheme, parsed.netloc, parsed.path,
            parsed.params, new_query, parsed.fragment
        ))
        print(f"[5] Survey URL (with subids): {survey_url[:200]}...")

        # 6. Click "Umfrage starten" button (closes modal)
        click_result = await eval_js(ws, 8, '''
(function() {
    const btns = [...document.querySelectorAll('button')];
    const btn = btns.find(b => b.textContent.trim() === 'Umfrage starten' && b.offsetParent !== null);
    if (btn) { btn.click(); return 'CLICKED'; }
    return 'BUTTON_NOT_FOUND';
})()
''', 10)
        print(f"[6] Button click: {click_result}")
        await asyncio.sleep(2)

        # 7. Create new tab via Target.createTarget
        print("\n[7] Creating survey tab via Target.createTarget...")
        target_resp = subprocess.run([
            'curl', '-s', '-X', 'PUT',
            f'http://127.0.0.1:9999/json/new?{survey_url}'
        ], capture_output=True, text=True)

        try:
            new_target = json.loads(target_resp.stdout)
            new_ws = new_target.get('webSocketDebuggerUrl', '')
        except:
            print(f"[7] Target.createTarget failed: {target_resp.stdout[:200]}")
            return

        if not new_ws:
            print(f"[7] ERROR: No WS URL in target response: {json.dumps(new_target)}")
            return

        print(f"[7] New tab WS: {new_ws[:80]}...")

        # 8. Connect to new tab, inject cookies, navigate
        # IMPORTANT: DO NOT enable Page/Network events — they flood the buffer!
        async with websockets.connect(new_ws) as new_tab:
            # NO Runtime.enable, Network.enable, or Page.enable on new tab
            
            # Inject 7 Heypiggy cookies (no enable needed)
            await new_tab.send(json.dumps({
                'id': 1,
                'method': 'Network.setCookies',
                'params': {'cookies': heypiggy_cookies}
            }))
            msg = await recv_target(new_tab, 1, 10)
            print(f"[8] Cookie injection result: {msg}")

            # Wait 2s for cookies to settle
            await asyncio.sleep(2)

            # Navigate to survey URL (Target.createTarget already navigated but re-navigate for cookies)
            await new_tab.send(json.dumps({
                'id': 2,
                'method': 'Page.navigate',
                'params': {'url': survey_url}
            }))
            
            # Wait for page to load (10s for SPA)
            await asyncio.sleep(10)

            # Get body text — use single-shot recv with high timeout
            await new_tab.send(json.dumps({
                'id': 3,
                'method': 'Runtime.evaluate',
                'params': {'expression': 'document.body ? document.body.innerText.substring(0, 500) : "NO_BODY"'}
            }))
            
            # Collect messages for 15 seconds
            body = None
            for _ in range(50):
                try:
                    msg = json.loads(await asyncio.wait_for(new_tab.recv(), timeout=5))
                    if msg.get('id') == 3:
                        body = msg.get('result', {}).get('result', {}).get('value', '')
                        break
                except:
                    pass
            
            logged_in = 'abmelden' in (body or '').lower()
            print(f"[9] Body length: {len(body or '')}, Logged in: {logged_in}")
            print(f"[9] Survey body text:\n{(body or '')[:500]}")

            # Get current URL
            await new_tab.send(json.dumps({
                'id': 4,
                'method': 'Runtime.evaluate',
                'params': {'expression': 'window.location.href'}
            }))
            for _ in range(30):
                try:
                    msg = json.loads(await asyncio.wait_for(new_tab.recv(), timeout=5))
                    if msg.get('id') == 4:
                        url = msg.get('result', {}).get('result', {}).get('value', '')
                        print(f"[9] Current URL: {url[:200] if url else 'NONE'}")
                        break
                except:
                    pass

            # Check if logged in
            body = await eval_js(new_tab, 5, 'document.body ? document.body.innerText.substring(0, 500) : "NO_BODY"', 15)
            logged_in = 'abmelden' in (body or '').lower()
            print(f"[9] Logged in (abmelden found): {logged_in}")
            print(f"[9] Survey body text:\n{(body or '')[:500]}")

            # Get current URL
            url = await eval_js(new_tab, 6, 'window.location.href', 10)
            print(f"[9] Current URL: {url[:200] if url else 'NONE'}")

            # Check for completion keywords
            body_lower = (body or '').lower()
            comp_kws = ['vielen dank', 'thank you', 'abgeschlossen', 'completed', 'fertig', 'danke für']
            for kw in comp_kws:
                if kw in body_lower:
                    print(f"[9] COMPLETION KEYWORD: '{kw}'")
            so_kws = ['leider', 'nicht geeignet', 'screen out', 'disqualifiziert']
            for kw in so_kws:
                if kw in body_lower:
                    print(f"[9] SCREEN-OUT KEYWORD: '{kw}'")

    print("\n=== TEST COMPLETE ===")
    print("RESULT: open_survey.py verified" if logged_in else "RESULT: FAILED - needs fix")


if __name__ == '__main__':
    asyncio.run(test_open_survey())