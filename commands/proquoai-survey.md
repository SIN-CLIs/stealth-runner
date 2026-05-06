# Proquoai Survey Automation (2026-05-06)

## STATUS
- ✅ **COMPLETED** — +0.23€ earned, redirected to dashboard

## Survey URL
```
survey.proquoai.com/en/dy/language-select?next=...
→ heypiggy dashboard redirect on completion
```

## Page Structure
Angular Material UI with:
- SUX-DY-ENTRY (survey entry wrapper)
- MAT-RADIO-GROUP (radio buttons)
- MAT-CHECKBOX (checkboxes)
- MAT-SELECT (dropdowns)
- mat-slider (sliders for age input)

## ✅ VERIFIED COMMANDS

### Get WebSocket URL
```python
pages = json.loads(urllib.request.urlopen(f'http://127.0.0.1:{PORT}/json').read())
for p in pages:
    if 'proquoai' in p.get('url',''):
        ws_url = p.get('webSocketDebuggerUrl', '')
```

### Language Selection (first page)
```python
# Click "check" button
mclick(600, 613)  # check button center
# Then click "Let's go"
mclick(600, 550)
```

### Gender (MAT-RADIO-BUTTON)
```python
# Radio buttons at cy:459 (Male), cy:489 (Female)
mclick(600, 459)  # Male
mclick(600, 489)  # Female
# Then Continue at 600,560
```

### Age Input (mat-slider + text input)
```python
# Input at (600, 471), placeholder "Enter your age here"
# Click input first, then type via Input.dispatchKeyEvent
for c in '32':
    ws.send(json.dumps({'id': 0, 'method': 'Input.dispatchKeyEvent', 'params': {'type':'keyDown','text':c,'key':c}}))
    ws.recv()
    ws.send(json.dumps({'id': 1, 'method': 'Input.dispatchKeyEvent', 'params': {'type':'keyUp','text':c,'key':c}}))
    ws.recv()
```

### State Dropdown (MAT-SELECT)
```python
# Click mat-select at (600, 471) to open dropdown
mclick(600, 471)
time.sleep(1)
# Options at cy:522, 573, 624, 675, 726, 777, 828, 879, 930, 981, 1032, 1083
# Berlin = 624, Bayern = 573, etc.
mclick(598, 624)  # Berlin
```

### Employment Dropdown (MAT-SELECT)
```python
mclick(600, 471)  # open dropdown
# Options: "Employed full-time" = 1032, "Employed part-time" = 930
# "Self-employed full-time" = 1083, etc.
mclick(598, 1032)  # Employed full-time
```

### Multi-Select (MAT-CHECKBOX)
```python
# Click at x=300, y=[391,420,449,...] using elementFromPoint
ws.send(json.dumps({'id': 0, 'method': 'Runtime.evaluate', 'params': {'expression': '(function(){var cbs=[];var ys=[391,420,449];ys.forEach(function(cy){var el=document.elementFromPoint(300,cy);if(el){var cb=el.closest("mat-checkbox")||el;cb.click();cbs.push(cy+":clicked");}});return cbs.join(", ");})()'}}))

# OR click inner-container at x=258
mclick(258, 391)
```

### Check Checked State
```python
ws.send(json.dumps({'id': 0, 'method': 'Runtime.evaluate', 'params': {'expression': '(function(){var cbs=document.querySelectorAll("mat-checkbox");var out=[];cbs.forEach(function(cb){var cls=cb.className||"";var checked=cls.includes("checked");out.push(cb.textContent.trim().substring(0,20)+" checked:"+checked);});return out.join(" | ");})()'}}))
```

### Submit/Continue Buttons
```python
# Find and click via JS
ws.send(json.dumps({'id': 0, 'method': 'Runtime.evaluate', 'params': {'expression': '(function(){var all=document.querySelectorAll("button");all.forEach(function(b){var t=b.textContent.trim();if(t==="Continue"||t==="Submit"){b.click();}});return "OK";})()'}}))
# OR via mouse
mclick(600, 560)  # Continue
mclick(600, 680)  # Submit (rating page)
```

### Rating Page (5 stars)
```python
# Star centers: 476,577 | 538,577 | 600,577 | 662,577 | 724,577
for sc in ["476,577", "538,577", "600,577", "662,577", "724,577"]:
    cx, cy = map(int, sc.split(','))
    mclick(cx, cy)
    time.sleep(0.5)
# Submit at 600,680
```

### Feedback Textarea
```python
# Click textarea at (600, 597)
mclick(600, 597)
# Type feedback
for c in "Good survey, clear questions.":
    ws.send(json.dumps({'id': 0, 'method': 'Input.dispatchKeyEvent', 'params': {'type':'keyDown','text':c,'key':c}}))
    ws.recv()
    ws.send(json.dumps({'id': 1, 'method': 'Input.dispatchKeyEvent', 'params': {'type':'keyUp','text':c,'key':c}}))
    ws.recv()
# Click Submit
mclick(600, 680)
```

## Survey Flow
```
1. Language select → English → check → Let's go
2. Gender: Male → Continue
3. Age: 32 → Continue
4. State: Berlin (dropdown) → Continue
5. Employment: Employed full-time → Continue
6. Multi-select: Buy bottled water, jewellery, coworking spaces → Continue
7. Rating: 5 stars → Submit
8. Feedback: type feedback → Submit
→ Redirects to heypiggy dashboard
```

## Balance Impact
| Survey | Earned |
|--------|--------|
| proquoai (2026-05-06) | +0.23€ |
| Previous total | 1.26€ |
| **New Balance** | **1.49€** |

## Key Learning
- Angular Material requires precise click targets (use elementFromPoint for checkboxes)
- Radio buttons: click at center (600, cy) 
- Dropdowns: click mat-select at (600, 471) then click option at (598, cy)
- Always check for elementFromPoint when direct click doesn't work
- Survey completes → auto-redirects to heypiggy dashboard