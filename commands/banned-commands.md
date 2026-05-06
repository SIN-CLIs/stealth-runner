# BANNED Commands (2026-05-06) — NEVER USE

> This file is the authoritative source of what NOT to do.
> Any banned pattern here will cause Chrome crashes, user data loss, or survey failures.

---

## 🔴 CRITICAL BANS — Hardware/OS

### Chrome Kill — ABSOLUT VERBOTEN ⚠️

```bash
# ❌ BANNED — kills ALL Chrome instances including USER Chrome!
pkill -f "heypiggy-bot"           # ← KILLS ALL Chrome with heypiggy-bot in path
killall Google Chrome             # ← KILLS EVERYTHING
pkill -f "Google Chrome"          # ← KILLS ALL Chrome
kill $(pgrep -f "heypiggy-bot")   # ← SAME PROBLEM
```

**Why banned**: These patterns match ALL Chrome processes, not just the bot. User's Chrome tabs (localhost, DeepSeek, etc.) will be killed too. Your opencode session, Claude, any user Chrome windows — ALL DEAD.

**Confirmed failures** (2026-05-06): Tested `pkill -f "heypiggy-bot"` — it killed all Chrome including user sessions.

**SAFE alternatives**:
```python
# ✅ CDP Page.close only for target tab
ws.send(json.dumps({'id': 0, 'method': 'Page.close'}))
ws.recv()

# ✅ SessionManager.close_all() — kills BOT + empties registry
from app.core.session_manager import SessionManager
sm = SessionManager()
sm.close_all()

# ✅ Kill only main chrome process with isolated profile (NEVER user chrome)
subprocess.run(['pkill', '-f', '/Contents/MacOS/Google Chrome'], 
               cwd='/tmp/heypiggy-bot-*')  # only bot profile dir
```

### Hardcoded PIDs — NEVER HARDCODE
```bash
# ❌ BANNED — PIDs are DYNAMIC, change every session!
kill 71104
kill 70293
kill 6528
kill 8649
```

**Why banned**: PIDs are assigned by the OS. Today's 71104 is tomorrow's something else. Hardcoding PIDs = chaos.

**SAFE**: Always find PIDs dynamically:
```bash
pgrep -f "heypiggy-bot" | head -1  # find bot Chrome
ps aux | grep "user-data-dir=/tmp/heypiggy-bot" | awk '{print $2}'  # exact match
```

---

## 🟡 CDP/Tool Bans

### Manual WebSocket URL
```python
# ❌ BANNED — gives 403 Forbidden!
ws_url = "ws://127.0.0.1:9999/devtools/page/ABCD..."
ws = websocket.create_connection(ws_url, timeout=5)  # ❌ FAILS

# ✅ CORRECT — use webSocketDebuggerUrl from JSON endpoint
import json, urllib.request
pages = json.loads(urllib.request.urlopen(f'http://127.0.0.1:{PORT}/json').read())
ws_url = pages[0]['webSocketDebuggerUrl']  # ← CORRECT origin header
ws = websocket.create_connection(ws_url, timeout=5)  # ✅ WORKS
```

### CDP for Navigation
```python
# ❌ BANNED — CDP should only be used for JS execute/evaluate!
ws.send(json.dumps({'id': 0, 'method': 'Page.navigate', 'params': {'url': '...'}})  # WRONG!

# ✅ CDP allowed for:
# - Runtime.evaluate (JS execution)
# - Input.dispatchMouseEvent (mouse clicks)
# - Page.captureScreenshot
# - Target.createTarget (new tabs)
# - Page.close (close tab)

# ✅ Navigation via Target.createTarget
ws.send(json.dumps({'id': 0, 'method': 'Target.createTarget', 'params': {'url': href}}))
```

### skylight-cli
```bash
# ❌ BANNED — deprecated, index-based clicking unreliable!
skylight-cli click --pid 12345 --element-index 42
skylight-cli query --label "Weiter"
```

**Why banned**: Element indices change between page renders. Index 42 one day is Index 15 the next.

### webauto-nodriver MCP
```bash
# ❌ ABSOLUT BANNED — violates CUA-ONLY Trinity architecture!
# Using this MCP causes CDP WebSocket conflicts and bypasses
# the established automation pipeline.
```

**Why banned**: Competes with CDP for browser control. Origin conflicts.

---

## 🔵 Browser Launch Bans

### Chrome without --remote-allow-origins
```bash
# ❌ BANNED — CDP connections get 403 Forbidden!
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  --remote-debugging-port=9999 \
  "https://www.heypiggy.com/"

# ✅ CORRECT — always include --remote-allow-origins="*"
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  --remote-debugging-port=9999 \
  --remote-allow-origins="*" \
  --user-data-dir="/tmp/heypiggy-bot-$(date +%s)" \
  "https://www.heypiggy.com/"
```

---

## 🟢 Survey Automation Bans

### JS .click() on React/Angular buttons
```python
# ❌ BANNED for Civey/Angular — React events don't fire!
cdp('document.querySelector("button").click()')  # WRONG!

# ✅ CORRECT — use mouse events
ws.send(json.dumps({'id': 0, 'method': 'Input.dispatchMouseEvent', 
    'params': {'type':'mousePressed','x':600,'y':180,'button':'left','clickCount':1}}))
ws.recv()
ws.send(json.dumps({'id': 1, 'method': 'Input.dispatchMouseEvent', 
    'params': {'type':'mouseReleased','x':600,'y':180,'button':'left'}}))
```

**Why banned**: React/Angular use synthetic events. Native `.click()` bypasses event system.

### Clicking Apple Menu Bar
```python
# ❌ BANNED — depth < 5 = system menu, not web content!
# CUA queries with depth > 5 filter avoid this, but coordinate clicks don't!
# If you're clicking at y < 50, you might hit the menu bar!
```

**Why banned**: Menu bar elements have depth 1-4. Clicking them has no effect on web content.

### CPX URL Expiration
```python
# ❌ BANNED — CPX survey URLs expire after single use!
href = data.get('href', '')  # URL from get-survey-details.php
# This URL is VALID for ONE tab creation only
ws.send(json.dumps({'id': 0, 'method': 'Target.createTarget', 'params': {'url': href}}))
# ❌ If you try to open it again in a second tab → "No app id specified"

# ✅ Solution: Call get-survey-details.php again for fresh URL
resp = urllib.request.urlopen(details_url + '&survey_id=' + sid, timeout=15)
data = json.loads(resp.read().decode())
new_href = data.get('href', '')  # Fresh URL
```

---

## 📋 Banned Files in /commands/

| File | Status |
|------|--------|
| `banned-pkill-heypiggy-bot.md` | ❌ BANNED |
| `banned-killall-chrome.md` | ❌ BANNED |
| `banned-hardcoded-pids.md` | ❌ BANNED |
| `banned-skylight-cli.md` | ❌ BANNED |
| `banned-webauto-nodriver.md` | ❌ BANNED |
| `banned-cdp-commands.md` | ❌ BANNED |

---

## ✅ Verified Commands (see /commands/*.md)

| Survey | File | Status |
|--------|------|--------|
| Strat7 Audiences | `strat7-survey.md` | ✅ VERIFIED |
| Brand Ambassador | `brand-ambassador-survey.md` | ✅ VERIFIED |
| PureSpectrum | `purespectrum-survey.md` | ❌ CAPTCHA BLOCKED |
| Civey | `cdp-civey-survey.md` | ✅ VERIFIED |
| Nfield/Kantar | `nfield-survey.md` | ✅ VERIFIED |
| My-Take | `my-take-survey.md` | ✅ VERIFIED |
| Proquoai | `proquoai-survey.md` | ✅ VERIFIED |