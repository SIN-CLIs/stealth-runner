# Strat7 Audiences Survey (2026-05-06) — VERIFIED ✅

**Provider**: click.cpx-research.com → surveys.strat7audiences.com
**Persona**: Jeremy Schulze, 32, Berlin, male
**Reward**: ~0.05-0.15€ per survey

## Survey Flow (Tested)

### Step 0: Cookie Policy
```python
# "Alles klar!" button
ws.send(json.dumps({'id': 0, 'method': 'Input.dispatchMouseEvent', 'params': {'type':'mousePressed','x':1013,'y':881,'button':'left','clickCount':1}}))
ws.send(json.dumps({'id': 1, 'method': 'Input.dispatchMouseEvent', 'params': {'type':'mouseReleased','x':1013,'y':881,'button':'left'}}))
```

### Step 1: Privacy Consent
```python
# "Ich habe die Datenschutzerklärung gelesen" checkbox label
ws.send(json.dumps({'id': 0, 'method': 'Input.dispatchMouseEvent', 'params': {'type':'mousePressed','x':349,'y':380,'button':'left','clickCount':1}}))
ws.send(json.dumps({'id': 1, 'method': 'Input.dispatchMouseEvent', 'params': {'type':'mouseReleased','x':349,'y':380,'button':'left'}}))

# "Weiter" button
ws.send(json.dumps({'id': 0, 'method': 'Input.dispatchMouseEvent', 'params': {'type':'mousePressed','x':152,'y':524,'button':'left','clickCount':1}}))
ws.send(json.dumps({'id': 1, 'method': 'Input.dispatchMouseEvent', 'params': {'type':'mouseReleased','x':152,'y':524,'button':'left','clickCount':1}}))
```

### Step 2: Industry (multi-select)
```python
# "Keine der oben Genannten" label
ws.send(json.dumps({'id': 0, 'method': 'Input.dispatchMouseEvent', 'params': {'type':'mousePressed','x':765,'y':535,'button':'left','clickCount':1}}))
ws.send(json.dumps({'id': 1, 'method': 'Input.dispatchMouseEvent', 'params': {'type':'mouseReleased','x':765,'y':535,'button':'left'}}))
```

### Step 3: Age
```python
# Type 32 in number input (find via JS)
inputs = document.querySelectorAll("input[type=number]")
for inp in inputs:
    if inp.getBoundingClientRect().width > 50:
        inp.value = "32"
        inp.dispatchEvent(new Event("input", {bubbles: true}))
```

### Step 4: Gender
```python
# "Männlich" bsbutton
ws.send(json.dumps({'id': 0, 'method': 'Input.dispatchMouseEvent', 'params': {'type':'mousePressed','x':406,'y':329,'button':'left','clickCount':1}}))
ws.send(json.dumps({'id': 1, 'method': 'Input.dispatchMouseEvent', 'params': {'type':'mouseReleased','x':406,'y':329,'button':'left'}}))
```

### Step 5: State/Bundesland
```python
# "Berlin" label
ws.send(json.dumps({'id': 0, 'method': 'Input.dispatchMouseEvent', 'params': {'type':'mousePressed','x':940,'y':328,'button':'left','clickCount':1}}))
ws.send(json.dumps({'id': 1, 'method': 'Input.dispatchMouseEvent', 'params': {'type':'mouseReleased','x':940,'y':328,'button':'left'}}))
```

### Step 6: Image Selection (bsbuttons)
```python
# Click 3 bsbutton elements (motorcycle/dog/etc)
# Get positions via:
document.querySelectorAll("button.bsbutton").forEach(b => {
    r = b.getBoundingClientRect()
    console.log("btn @" + (r.left + r.width/2) + "," + (r.top + r.height/2))
})

# Grid: Row 1: @150,372 @346,372 @542,372 @738,372 @934,372
#       Row 2: @150,574 @346,574 @542,574 @738,574 @934,574
#       Row 3: @150,776 @346,776 @542,776 @738,776 @934,776
```

## Element Positions (Strat7)
| Element | X | Y | Size |
|---------|---|---|------|
| Alles klar! (cookie) | 1013 | 881 | 157x40 |
| Umfrage starten | 194 | 451 | 140x64 |
| Datenschutz checkbox | 349 | 380 | 200x40 |
| Weiter (consent) | 152 | 524 | 140x64 |
| Keine der oben Genannten | 765 | 535 | ~200x40 |
| Age input | 115 | 297 | 110x43 |
| Weiter (demographics) | 152 | 401 | 140x64 |
| Weiblich | 170 | 329 | ~80x40 |
| Männlich | 406 | 329 | ~80x40 |
| Berlin | 940 | 328 | ~80x40 |
| Baden-Württemberg | 240 | 328 | ~120x40 |
| Bayern | 590 | 328 | ~80x40 |
| Weiter (berlin) | 152 | 465 | 140x64 |

## bsbutton Grid (15 buttons, 3 rows)
```
Row 1: @150,372 | @346,372 | @542,372 | @738,372 | @934,372
Row 2: @150,574 | @346,574 | @542,574 | @738,574 | @934,574
Row 3: @150,776 | @346,776 | @542,776 | @738,776 | @934,776
```

## Outcome
- Screen-out after ~5 questions → 0.03€ compensation
- ✅ Automation works — all clicks register
- Better surveys exist but this one auto-completes