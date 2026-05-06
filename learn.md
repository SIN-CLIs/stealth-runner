# learn.md — CRITICAL LEARNINGS (2026-05-06)

## 🚨 FATAL ERRORS — NEVER REPEAT

### 1. `playstealth launch` DOES NOT HAVE `--port`
```
❌ playstealth launch --url X --port 9999
✅ playstealth launch --url 'X'
```
The port is auto-assigned. Read it from the JSON output `{"cdp_port": XXXX}`.

### 2. NIM Nemotron 3 Omni is a REASONING model
```
❌ max_tokens=200 + system prompt = EMPTY RESPONSE
✅ max_tokens=600 + chain-of-thought user prompt = CORRECT JSON
```
The model needs tokens to THINK. Never use system prompts with reasoning models.
Chain-of-thought format: "Think step by step... Your JSON:"

### 3. Angular v19 IGNORES JS `.click()`
```
❌ button.click() or dispatchEvent(new MouseEvent(...))
✅ CDP Input.dispatchMouseEvent (real OS events, isTrusted=true)
```
PureSpectrum and all Angular surveys need CDP mouse events for buttons.

### 4. Zombie tabs ACCUMULATE and break everything
```
❌ Opening surveys without closing old tabs → tab_ws points to wrong page
✅ Clean ALL non-dashboard tabs before opening a new survey
```

### 5. CPX `details_url` MUST come from dashboard JS context
```
❌ Hardcoded DETAILS_URL → API returns "No surveys available"
✅ Get live `details_url` from dashboard page via Runtime.evaluate
```
The dashboard has additional parameters (secure_hash_offerwall, m, m_1, etc.).

### 6. Chrome tabs MUST be managed through WebSocket, not HTTP API
```
❌ curl http://127.0.0.1:9999/json/new?URL (doesn't work on all Chrome versions)
✅ CDP Target.createTarget via existing WebSocket connection
```

### 7. NEVER use `pkill -f "heypiggy-bot"` or `killall Google Chrome`
```
❌ Kills USER Chrome sessions
✅ SessionManager.close_all() or kill ONLY /tmp/heypiggy-bot-* PIDs
```

## ✅ VERIFIED WORKING PATTERNS

### Qualtrics → Toluna → Strat7 → FocusVision
```
Qualtrics:    .NextButton.click()      + input[type=radio][idx].click()
TolunaStart:  .cf-radio[idx].click()   + button.click()
Strat7:       .bsbutton.click()         + input[type=radio][idx].click()
FocusVision:  reCAPTCHA CDP click       + input[type=submit].click()
```

### reCAPTCHA v2 Solver
```
1. Find iframe[title="reCAPTCHA"] position
2. CDP Input.dispatchMouseEvent on checkbox (frame.x + 25, frame.y + frame.h/2)
3. Wait 3s
4. Click "Weiter" button
```

### PureSpectrum Full Flow
```
1. ROBOT textarea: fill + CDP click "Nächste"
2. Text captcha: extract base64 img → NVIDIA Vision OCR → fill + CDP click
3. Drag puzzle: __ngContext__ recursive search → dropListRef.drop()
```

### CDP Button Click (Angular-proof)
```python
def cdp_click_button(ws_url, button_text):
    # 1. Find button position via JS
    # 2. Input.dispatchMouseEvent: mouseMoved → mousePressed → mouseReleased
```
