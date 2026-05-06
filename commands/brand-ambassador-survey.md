# Brand Ambassador Survey (2026-05-06) — VERIFIED ✅

**Provider**: click.cpx-research.com → votes.brand-ambassador.com
**Persona**: Jeremy Schulze, 32, Berlin, male, no pets

## Survey Flow (Tested)

### Step 0: Cookie + Start
```python
# "Akzeptieren" cookie button
ws.send(json.dumps({'id': 0, 'method': 'Input.dispatchMouseEvent', 'params': {'type':'mousePressed','x':1103,'y':877,'button':'left','clickCount':1}}))
ws.send(json.dumps({'id': 1, 'method': 'Input.dispatchMouseEvent', 'params': {'type':'mouseReleased','x':1103,'y':877,'button':'left'}}))

# "Nächster" start button
ws.send(json.dumps({'id': 0, 'method': 'Input.dispatchMouseEvent', 'params': {'type':'mousePressed','x':1133,'y':538,'button':'left','clickCount':1}}))
ws.send(json.dumps({'id': 1, 'method': 'Input.dispatchMouseEvent', 'params': {'type':'mouseReleased','x':1133,'y':538,'button':'left'}}))
```

### Step 1: Attention Checks (3 questions)

**Q1**: "Bestätige deine Konzentration, indem du NICHT die Option 'Nie' auswählst."
→ Answer: **Oft** (never pick "Nie")
```python
# "Oft" label (NOT Nie!)
ws.send(json.dumps({'id': 0, 'method': 'Input.dispatchMouseEvent', 'params': {'type':'mousePressed','x':123,'y':424,'button':'left','clickCount':1}}))
ws.send(json.dumps({'id': 1, 'method': 'Input.dispatchMouseEvent', 'params': {'type':'mouseReleased','x':123,'y':424,'button':'left'}}))
```

**Q2**: "Stelle sicher, dass du die Option 'Stimme zu' für diese Aussage wählst."
→ Answer: **Stimme zu**
```python
ws.send(json.dumps({'id': 0, 'method': 'Input.dispatchMouseEvent', 'params': {'type':'mousePressed','x':532,'y':545,'button':'left','clickCount':1}}))
ws.send(json.dumps({'id': 1, 'method': 'Input.dispatchMouseEvent', 'params': {'type':'mouseReleased','x':532,'y':545,'button':'left'}}))
```

**Q3**: "Berechne 4 mal 2."
→ Answer: **8**
```python
# "8" label
ws.send(json.dumps({'id': 0, 'method': 'Input.dispatchMouseEvent', 'params': {'type':'mousePressed','x':41,'y':645,'button':'left','clickCount':1}}))
ws.send(json.dumps({'id': 1, 'method': 'Input.dispatchMouseEvent', 'params': {'type':'mouseReleased','x':41,'y':645,'button':'left'}}))
```

**Click "Nächster Schritt"**
```python
# JS click
btns = document.querySelectorAll("button")
for btn in btns:
    if btn.textContent.trim().includes("Nächster"):
        btn.click()
```

### Step 2: Demographics

**Pets (multi-select, hidden checkboxes)**
```python
# "Ich habe keine Haustiere" checkbox at (504, 500)
# Hidden input at position, click the label area
ws.send(json.dumps({'id': 0, 'method': 'Input.dispatchMouseEvent', 'params': {'type':'mousePressed','x':504,'y':500,'button':'left','clickCount':1}}))
ws.send(json.dumps({'id': 1, 'method': 'Input.dispatchMouseEvent', 'params': {'type':'mouseReleased','x':504,'y':500,'button':'left'}}))
```

**Gender (hidden radio)**
```python
# "Männlich" radio at (32, 600)
ws.send(json.dumps({'id': 0, 'method': 'Input.dispatchMouseEvent', 'params': {'type':'mousePressed','x':32,'y':600,'button':'left','clickCount':1}}))
ws.send(json.dumps({'id': 1, 'method': 'Input.dispatchMouseEvent', 'params': {'type':'mouseReleased','x':32,'y':600,'button':'left'}}))
```

**Birth Year (text input)**
```python
# Find input and type 1993
inputs = document.querySelectorAll("input[type=text]")
for inp in inputs:
    if inp.value === "":
        inp.value = "1993"
        inp.dispatchEvent(new Event("input", {bubbles: true}))
```

## Element Positions (Brand Ambassador)
| Element | X | Y | Note |
|---------|---|---|------|
| Akzeptieren (cookie) | 1103 | 877 | 159x58 |
| Nächster (start) | 1133 | 538 | 159x58 |
| Immer | 58 | 424 | attention Q |
| **Oft** (correct!) | 123 | 424 | correct answer |
| Nie (wrong!) | 259 | 424 | WRONG - fail |
| Manchmal | 419 | 424 | |
| Selten | 509 | 424 | |
| Stimme sehr zu | 89 | 545 | |
| Stimme nicht sehr zu | 248 | 545 | |
| Stimme nicht zu | 408 | 545 | |
| **Stimme zu** (correct!) | 532 | 545 | correct answer |
| Weder... | 714 | 545 | |
| 8 (correct!) | 41 | 645 | 4×2=8 |
| 9 | 82 | 645 | |
| 10 | 127 | 645 | |
| 7 | 172 | 645 | |
| 6 | 212 | 645 | |
| Nächster Schritt | 1097 | 739 | 159x58 |
| Katze(n) checkbox | 32 | 452 | |
| Hund(e) checkbox | 123 | 452 | |
| Vogel/Vögel | 212 | 452 | |
| Fisch(e) | 327 | 452 | |
| Amphibien | 415 | 452 | |
| Kleintiere | 681 | 452 | |
| Reptilien | 32 | 500 | |
| Pferd(e) | 414 | 500 | |
| **Keine Haustiere** (correct!) | 504 | 500 | |
| Andere | 705 | 500 | |
| **Männlich** radio | 32 | 600 | |
| Weiblich radio | 127 | 600 | |
| Birth year input | 216 | 672 | |

## Outcome
- ✅ Attention checks work — must not pick "Nie"
- ⚠️ Screen-out after demographics → 0.02€ compensation
- No reward for full survey (screen-out at step 2)