# My-Take Survey (zuhause.my-take.com) (2026-05-06)

## STATUS
- ✅ **COMPLETED** — +0.25€ earned, redirected to heypiggy dashboard
- Survey ID: 095c91cb-23b2-4e11-bb1f-d7d7d8d97701
- Theme: "Eine brandneue Art zu reinigen!" (cleaning products)

## Survey URL Pattern
```
zuhause.my-take.com/surveys/{UUID}/start/a/{token}
→ Heypiggy → CPX API → click.cpx-research.com → my-take redirect
```

## Page Structure
Simple question-per-page format:
- Legend (question text) at top
- AnswerList (radio button options) in middle
- mrButton "Weiter" at bottom
- Progress percentage shown
- "vor X Tagen" timestamp visible

## ✅ VERIFIED COMMANDS

### Start Survey
```python
# Via CPX API → create new tab with href
ws.send(json.dumps({'id': 0, 'method': 'Target.createTarget', 'params': {'url': survey_href}}))
```

### Get Buttons (Universal)
```python
js = '(function(){var all=document.querySelectorAll("*");var out=[];for(var i=0;i<all.length;i++){var r=all[i].getBoundingClientRect();var t=all[i].textContent.trim();var cx=Math.round(r.left+r.width/2);var cy=Math.round(r.top+r.height/2);if(cx>0&&cy>100&&r.height>30&&r.height<80&&r.width>100&&t.length>0&&t.length<30&&!t.includes("brandneue")&&!t.includes("My-Take")&&!t.includes("Bitte")&&!t.includes("wählen")&&!t.includes("%")&&!t.includes("vor")){out.push(t+" @"+cx+","+cy);}}return out.join("|");})()'
```

### Mouse Click
```python
ws.send(json.dumps({'id': 0, 'method': 'Input.dispatchMouseEvent', 'params': {'type':'mousePressed','x':600,'y':180,'button':'left','clickCount':1}}))
ws.recv()
ws.send(json.dumps({'id': 1, 'method': 'Input.dispatchMouseEvent', 'params': {'type':'mouseReleased','x':600,'y':180,'button':'left'}}))
ws.recv()
```

### Single Select Loop (Proquoai-style)
```python
for q in range(50):
    btns = get_buttons()
    # Filter options vs submit
    options = []
    submit = None
    for p in btns.split('|'):
        if p.startswith('Weiter'):
            submit = p
        else:
            options.append(p)
    
    # Click first option (or specific answer)
    if options:
        _, coords = options[0].split('@')
        cx, cy = map(int, coords.split(','))
        mclick(cx, cy)
    
    # Click Weiter
    if submit:
        _, coords = submit.split('@')
        cx, cy = map(int, coords.split(','))
        mclick(cx, cy)
    
    time.sleep(3)
```

### Multi-Select (Checkbox Grid)
```python
# Products with multiple choice options per row
# Click at x=1006 (right side) for options like "nicht besitzen"
for cy in [249, 297, 345, 399]:
    mclick(1006, cy)
    time.sleep(0.5)
# Then click Weiter
mclick(600, 609)
```

### Check for Required (Attention Check)
```python
# If "Diese Frage ist erforderlich" appears → need to answer
# Click actual options, not the warning text
# Get options from AnswerList elements, not from warning
```

## Survey Flow (My-Take)
```
1. "Eine brandneue Art zu reinigen!" → Starten → Weiter
2. Gender: Weiblich/Männlich/Nicht binär/... → Weiter
3. Age: Unter 18/18-24/25-34/35-44/... → Weiter (25-34 for Jeremy 32)
4. Income: Unter 35k/35-50k/50-65k/... → Weiter (50-65k)
5. Children: Ja/Nein → Weiter (Nein)
6. Pets: Ja/Nein → Weiter (Nein)
7. Role in buying: multiple options → Click required, then Weiter
8. Multi-select grid: products + rating options → Click x=1006, then Weiter
9. More questions...
→ Redirects to heypiggy dashboard
```

## Balance Impact
| Survey | Earned |
|--------|--------|
| My-Take (2026-05-06) | +0.25€ |
| Previous total | 1.29€ |
| **New Balance** | **1.54€** |

## Key Learning
- Button positions are consistent: options at y=146,210,274... for single select
- Multi-select grid: right side click area at x=1006 per product
- Filter out "required" warnings - they are NOT clickable
- Get buttons each iteration (positions can shift slightly)
- Weiter button is always at center-bottom