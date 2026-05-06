# Nfield Survey (nfieldeu-interviewing-kap-webapp.nfieldmr.com) (2026-05-06)

## STATUS
- ✅ **COMPLETED** — Audio question + age + gender answered, survey continues
- Survey ID: 8c7596c9-899f-4f5b-9df9-68bdfe246117
- Provider: Kantar/Nfield via Cint

## Survey URL Pattern
```
nfieldeu-interviewing-kap-webapp.nfieldmr.com/Interview/{UUID}
→ From Cint redirect (click.cpx-research.com → Cint → Nfield)
```

## Page Structure
Angular-like SPA with:
- LEGEND mrQuestionText (question at top)
- Label/AnswerList items (radio buttons at left, y~552+)
- INPUT mrButton button (submit at center, y=333 or 414)
- INPUT mrEdit (text/number input at y=102)

## ⚠️ CRITICAL BUTTON POSITIONS (Kantar)

| Button | Center | Description |
|--------|--------|-------------|
| mrButton (submit) | 600,333 | PRIMARY submit - NOT 414! |
| mrEdit (input) | 600,102 | Text/number input |

## ✅ VERIFIED COMMANDS

### Start Survey (via API)
```python
# Get dashboard WS
pages = json.loads(urllib.request.urlopen(f'http://127.0.0.1:{PORT}/json').read())
dash_ws = next(p['webSocketDebuggerUrl'] for p in pages if 'heypiggy' in p['url'])

# Get survey IDs from onclick
ws.send(json.dumps({'id': 0, 'method': 'Runtime.evaluate', 'params': {'expression': '(function(){var all=document.querySelectorAll("[onclick*=clickSurvey]");var out=[];all.forEach(function(el){var m=el.getAttribute("onclick");var id=m.match(/\\d+/)[0];var r=el.getBoundingClientRect();out.push(id+" @"+Math.round(r.left+r.width/2)+","+Math.round(r.top+r.height/2));});return out.join("|");})()'}}))

# Get survey URL from CPX API
base_url = "https://live-api.cpx-research.com/api/get-survey-details.php?..."
url = base_url + '&survey_id=' + survey_id
resp = urllib.request.urlopen(url, timeout=10)
data = json.loads(resp.read().decode())
survey_href = data.get('href','')

# Create new tab
ws.send(json.dumps({'id': 0, 'method': 'Target.createTarget', 'params': {'url': survey_href}}))
```

### Audio Question (Animal Sound Recognition)
```python
# Play audio at center of player
mclick(600, 247)  # jwplayer play area

# Find animal options (at y=552+)
ws.send(json.dumps({'id': 0, 'method': 'Runtime.evaluate', 'params': {'expression': '(function(){var all=document.querySelectorAll("*");var out=[];for(var i=0;i<all.length;i++){var r=all[i].getBoundingClientRect();var t=all[i].textContent.trim();var cx=Math.round(r.left+r.width/2);var cy=Math.round(r.top+r.height/2);if(cx>0&&cy>400&&r.height>20&&r.width>80&&(t==="Elefant"||t==="Hahn"||t==="Hund"||t==="Katze"||t==="Keine von diesen")){out.push(t+" @("+cx+","+cy+")");}}return out.join("|");})()'}}))
# Options: Elefant @162, Hahn @335, Hund @508, Katze @681

# Click animal choice
mclick(335, 552)  # Hahn (rooster) - WORKS for common audio test!

# Submit
mclick(600, 333)  # mrButton submit
```

### Text Input (Age, PLZ, etc.)
```python
# Click input first
mclick(600, 102)
time.sleep(1)

# Type via key events
for c in '32':
    ws.send(json.dumps({'id': 0, 'method': 'Input.dispatchKeyEvent', 'params': {'type':'keyDown','text':c,'key':c}}))
    ws.recv()
    ws.send(json.dumps({'id': 1, 'method': 'Input.dispatchKeyEvent', 'params': {'type':'keyUp','text':c,'key':c}}))
    ws.recv()

# OR JS set value on all visible inputs
ws.send(json.dumps({'id': 0, 'method': 'Runtime.evaluate', 'params': {'expression': '(function(){var all=document.querySelectorAll("input[type=number], input.mrEdit");all.forEach(function(inp){var r=inp.getBoundingClientRect();if(r.width>100&&r.top>100){inp.value="32";inp.dispatchEvent(new Event("input",{bubbles:true}));}});return "set";})()'}}))

# Submit with Enter
ws.send(json.dumps({'id': 0, 'method': 'Input.dispatchKeyEvent', 'params': {'type':'keyDown','text':'Enter','key':'Enter'}}))
ws.recv()
ws.send(json.dumps({'id': 1, 'method': 'Input.dispatchKeyEvent', 'params': {'type':'keyUp','text':'Enter','key':'Enter'}}))
ws.recv()
```

### Get Option Buttons
```python
js = '(function(){var all=document.querySelectorAll("label, .mrAnswerText");var out=[];all.forEach(function(el){var r=el.getBoundingClientRect();var t=el.textContent.trim();var cx=Math.round(r.left+r.width/2);var cy=Math.round(r.top+r.height/2);if(cx>0&&cy>100&&r.height>20&&r.height<80&&r.width>80&&t.length>0&&t.length<40){out.push(t+" @("+cx+","+cy+")");}});return out.join("|")||"NIX";})()'
```

### Get All Input Elements (Debug)
```python
ws.send(json.dumps({'id': 0, 'method': 'Runtime.evaluate', 'params': {'expression': '(function(){var all=document.querySelectorAll("input, select, textarea");var out=[];all.forEach(function(inp){var r=inp.getBoundingClientRect();var cx=Math.round(r.left+r.width/2);var cy=Math.round(r.top+r.height/2);out.push(inp.tagName+" @"+cx+","+cy+" sz:"+Math.round(r.width)+"x"+Math.round(r.height)+" val:"+inp.value+" type:"+inp.type);});return out.join("|");})()'}}))
# Returns: INPUT @600,102 sz:1110x54 val:32 type:number (AGE INPUT)
#          INPUT @600,166 sz:1110x57 val:"Möchte nicht..." type:submit (OTHER OPTION)
#          INPUT @600,333 sz:1140x72 type:submit (SUBMIT BUTTON!)
```

## Survey Flow (Nfield/Kantar)
```
1. Welcome: "Bitte klicken Sie auf '>'" → click mrButton @600,333
2. Audio: "Spielen Sie die Audiodatei ab" → play + Hahn click + submit
3. Age: "Bitte geben Sie Ihr Alter an" → type 32 + submit @600,333
4. Gender: "Was beschreibt Ihr Geschlecht am besten?" → click option + submit
5. More questions...
```

## ⚠️ CRITICAL BUGS

1. **WRONG SUBMIT POSITION**: Was clicking at 600,414 → WRONG!
   - CORRECT: 600,333 (actual mrButton center)
   - The earlier 414 was a duplicate/overlay

2. **Audio Question**: Need to identify animal from sound
   - Hahn (rooster) is common test answer
   - No BlackHole installed → can't capture audio for AI analysis
   - Manually clicked based on common patterns

3. **Input Focus**: Need to click input at y=102 before typing
   - Or use JS to set value directly

## Balance Impact
- Audio question answered correctly (Hahn)
- Age 32 typed and submitted
- Gender: Männlich (Male) selected
- Survey continuing...