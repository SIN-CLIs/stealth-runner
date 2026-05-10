# open-survey — VERIFIED (2026-05-10)

## Status
✅ VERIFIED — 3 successful runs, Chrome 147, port 9999, Profile 901 copy

## What it does
1. **Modal detected**: Survey card clicked → "Umfrage starten" / "beginnen" modal appears
2. **URL captured**: `window.last_link` (CPX URL with `k=...&subid_2=website&subid_1=adsplashxmas`)
3. **Subids added**: `subid_2`, `subid_1` appended to URL (like `openSurvey()` does)
4. **Tab created**: `PUT /json/new?<survey_url>` — NO popup blocker (CRITICAL!)
5. **Cookies injected**: 7 HeyPiggy cookies (PHPSESSID, user_session, user_id, user_a_b_group, lang_pig, g_state, referer)
6. **Navigate**: `Page.navigate` to survey URL with subids
7. **Verify session**: Body text checked for "abmelden" (heypiggy) or survey provider page

## Verified Flows

### Samplicio.us (2026-05-10)
```
clickSurvey('67038730') -> Modal -> last_link (CPX) + subids
PUT /json/new?<CPX_URL> -> New Tab
Cookies injected -> Page.navigate
-> rx.samplicio.us/consent/?SID=8687599e-2243-4e81-94ee-c234443d7e27&PID=173644863
-> Samplicio consent page
```

### PureSpectrum (2026-05-10)
```
PUT /json/new?<CPX_URL> -> New Tab
-> screener.purespectrum.com/?survey_id=49516414&supplier_id=947&...
-> Screen-out (back to heypiggy dashboard with "Umfrage passt nicht" message)
-> Balance: €2.75 (no change for screen-out, €0.02 if disqualified mid-survey)
```

## Commands

### Get survey URL (dashboard WS)
```python
# Read last_link + subids directly
last_link = await eval_js(ws, 5, "window.last_link", 10)  # CPX URL
subid_cpx = await eval_js(ws, 6, "window.subid_cpx", 10) or ""  # "website"
subid_cpx1 = await eval_js(ws, 7, "window.subid_cpx1", 10) or ""  # "adsplashxmas"

# Build survey URL with tracking params
parsed = urlparse(last_link)
qs = parse_qs(parsed.query)
qs["subid_2"] = [subid_cpx]
qs["subid_1"] = [subid_cpx1]
survey_url = urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params,
                          "&".join(f"{k}={v[0]}" for k, v in qs.items()), ""))
```

### Create tab (CORRECT method)
```bash
# CORRECT: PUT /json/new?<url> — NO popup blocker!
curl -X PUT "http://127.0.0.1:9999/json/new?https://click.cpx-research.com/?k=..."

# WRONG: POST /json/protocol/targets/create (returns protocol JSON, NOT target!)
curl -X POST -H "Content-Type: application/json" \
  -d '{"url":"https://..."}' \
  "http://127.0.0.1:9999/json/protocol/targets/create"
```

### Inject cookies (survey tab WS)
```python
async with websockets.connect(tab_ws) as ws:
    # NO Runtime.enable / Network.enable / Page.enable on new tab!
    # These flood the buffer and eval responses get lost!

    await ws.send(json.dumps({"id": 1, "method": "Network.setCookies",
                              "params": {"cookies": heypiggy_cookies}}))
    # Wait for response...

    await asyncio.sleep(2)

    await ws.send(json.dumps({"id": 2, "method": "Page.navigate",
                              "params": {"url": survey_url}}))
    await asyncio.sleep(10)

    # Get body text
    await ws.send(json.dumps({"id": 3, "method": "Runtime.evaluate",
                              "params": {"expression": "document.body.innerText.substring(0, 500)"}}))
    # Collect responses for 15s (buffer events drain)
```

### Provider detection (URL-based)
```python
# Detect from survey_url or final URL
for p in ["purespectrum", "samplicio.us", "cint", "toluna", "ipsos", "nfield"]:
    if p in survey_url.lower():
        provider = p.split(".")[0]  # "samplicio.us" -> "samplicio"
        break
```

## Critical Lessons Learned

### ❌ window.open interception DOES NOT WORK
```javascript
// FAILS: openSurvey() runs window.open() BEFORE the override takes effect
window.open = function(url) { window._surveyUrl = url; return null; };
openSurvey(); // window._surveyUrl = null
```
**Why**: `openSurvey()` is defined BEFORE our `window.open` override executes in the same function scope.

### ✅ Read last_link directly WORKS
```javascript
window.last_link  // -> CPX URL with k=...&subid_2=website
window.subid_cpx  // -> "website"
window.subid_cpx1 // -> "adsplashxmas"
```

### ❌ Runtime.enable on new tab FLOODS buffer
```python
# WRONG: Enables consoleAPICalled events, fills buffer
await ws.send(json.dumps({"id": 1, "method": "Runtime.enable"}))
await asyncio.sleep(1)
for _ in range(50):
    msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=0.5))
# eval responses get lost in 30+ event messages!
```
**Fix**: NO enable calls on new tab. Just `Network.setCookies` + `Page.navigate` + `Runtime.evaluate`.

### ✅ PUT /json/new?url creates tab AND navigates
Chrome creates a new tab AND immediately navigates to the URL. No separate navigation step needed (but we call `Page.navigate` again for cookie injection to work on redirect chain).

### Session cookie timing
- First request to CPX goes OUT WITHOUT heypiggy session cookies (subids in URL only)
- Cookie injection happens AFTER tab creation (navigation already started)
- BUT: heypiggy session cookies are needed at END of redirect chain (when returning to heypiggy dashboard)
- Redirect chain: CPX → Samplicio → Potloc → heypiggy
- At heypiggy endpoint: cookies ARE present → balance tracking works

## History
- 2026-05-10: Verified (3 runs). Samplicio + PureSpectrum tested. Screen-out detection works.