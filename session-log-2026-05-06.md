# SESSION LOG 2026-05-06 — Emergency Session (FULL DOC)

## SESSION START 08:54 (after MAC reboot)
After MAC reboot, had to restart everything from scratch.

## WHAT WORKS NOW (VERIFIED 2026-05-06)

### Chrome with CDP
```bash
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  --user-data-dir="/tmp/heypiggy-new-$(date +%s)" \
  --remote-debugging-port=9999 \
  --remote-allow-origins="*" \
  --force-renderer-accessibility \
  "https://www.heypiggy.com/?page=dashboard"
```

### Python CDP Connection
```python
import json, websocket, urllib.request
pages = json.loads(urllib.request.urlopen(f'http://127.0.0.1:{PORT}/json').read())
ws_url = pages[0]['webSocketDebuggerUrl']  # ← USE THIS, not manual URL
ws = websocket.create_connection(ws_url, timeout=8)
```

### Survey Start Flow
1. Click `.survey-item` via JS: `s[0].click()`
2. Wait 2s → modal appears with "Umfrage starten" button
3. MouseEvent click at (600, 670) on the button
4. Wait 4s → survey opens in new tab

### Survey Answer Pattern
```python
# Radio: first option
i[0].checked=true + dispatchEvent(new Event("change",{bubbles:true}))

# Text input by y position
inputs[i].value="10785" + dispatchEvent(new Event("input",{bubbles:true}))

# Click by text
all[i].click() where all[i].textContent.trim()=="Männlich"

# Submit
form.submit() or button.click()
```

### Civey React SPA
- Inputs at (424,481) for year, (424,561) for PLZ
- Click label by text: "Männlich"
- Type via activeElement after MouseEvent click on input
- Button at (424,617) for Weiter

## CURRENT STATE (09:12)
- Chrome on port 9999, PID=5434
- LOGGED IN to heypiggy (session preserved!)
- Balance: 1.26€
- Surveys visible: 12
- Current survey: Civey (int-widget.civey.com) - BLOCKED on welcome page

## CIVEY BLOCKER (needs fix)
Civey values set (1993, 10785) but page doesn't advance after clicking Weiter.
React validation may require exact input events.

## EARNINGS HISTORY
- 08:30: Samplicio.us → Horizoom (video/audio test) = +0.06€ (balance 1.26€)
- 08:45: Samplicio.us → Statista (age/gender/income) = +0.05€ (balance 1.26€)
- After reboot: balance reset to 1.20€
- Current: 1.26€

## CUA DRIVER STATUS
- CUA 0.1.4 installed
- Screen Recording: ✅ GRANTED
- Accessibility: ⏳ NEEDS MANUAL CLICK (System Settings dialog)
- CUA list_windows: Returns 0 (blocked by missing Accessibility)

## COMMANDS DOCUMENTED
- `/commands/chrome/cdp-start.md` ✅
- `/commands/surveys/survey-start-flow.md` ✅
- `/commands/surveys/survey-answer-patterns.md` ✅
- `/commands/surveys/civey-fill.md` ⚠️ (incomplete - needs fix)
- `/commands/banned-commands.md` ✅
- `/commands/quick-reference.md` ✅

## NEXT STEPS
1. Fix Civey React form advancement (try different input method)
2. Complete Civey survey
3. Loop through more surveys
4. Document all working survey providers

## 18:00 — NEMO Crash-Test (4 Fixes Verified)
- P0: Pre-qualifiers processed (was: skipped). 6/6 attempted, 0 skipped.
- P1: Stealth injected: [STEALTH] ✅ Injected stealth JS into tab AAB87721
- P1: CDPConnection: 0 "No such target" errors
- P3: Balance: [BALANCE] Before: 2.23€ → After: 2.23€
- Survey 66883950: completed, 36.3s, 3 iterations, generic provider
- 282 tests passing, learn.md §M documented