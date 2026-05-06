# PureSpectrum Survey (2026-05-06) — VERIFIED

**Provider**: click.cpx-research.com → screener.purespectrum.com
**Persona**: Jeremy Schulze, 32, Berlin, male

## Known Issues
- ❌ Image CAPTCHA ("Bitte geben Sie den folgenden Code ein") — cannot read code from screenshot
- ❌ Number CAPTCHA ("Bitte legen Sie die Zahl 02 in das leere Kästchen") — input field invisible to CDP

## Working Steps (Verified)

### 1. Cookie Consent
```python
# Position: "Alle akzeptieren" button
ws.send(json.dumps({'id': 0, 'method': 'Input.dispatchMouseEvent', 'params': {'type':'mousePressed','x':383,'y':673,'button':'left','clickCount':1}}))
ws.send(json.dumps({'id': 1, 'method': 'Input.dispatchMouseEvent', 'params': {'type':'mouseReleased','x':383,'y':673,'button':'left'}}))
# OR via JS:
btns[0].click()  # find button by text "Alle akzeptieren"
```

### 2. Opinion + ROBOT CAPTCHA
```python
# Fill textarea with ROBOT + opinion text (min 5 words)
areas = document.querySelectorAll("textarea")
for area in areas:
    area.value = "ROBOT Your opinion text here with minimum 5 words"
    area.dispatchEvent(new Event("input", {bubbles: true}))
# Click Nächste
btns.forEach(b => { if(b.textContent.trim() === "Nächste") b.click() })
```

### 3. Blocked Steps
```python
# ❌ CAPTCHA CODE — cannot read image via CDP
# ❌ Number input — input field has width>0 but value not set via JS
# Fix: Skip PureSpectrum surveys, or use vision model to read code from screenshot
```

## Element Positions (PureSpectrum)
| Element | X | Y | Note |
|---------|---|---|------|
| Anpassen | 117 | 673 | |
| Alles ablehnen | 240 | 673 | |
| Alle akzeptieren | 383 | 673 | PRIMARY |
| Nächste | 987 | 267 | |
| Datenschutzrichtlinie | 581 | 731 | |

## Screenshot for Vision
```python
ws.send(json.dumps({'id': 0, 'method': 'Page.captureScreenshot', 'params': {'format': 'png'}}))
# Save base64 decode to /tmp/purespectrum_code.png
# Then analyze with NVIDIA vision model
```

## Recommendation
- ❌ **SKIP PureSpectrum surveys** — CAPTCHA blocks automation
- Better: Use Strat7, Brand Ambassador, Statista, Cint surveys instead