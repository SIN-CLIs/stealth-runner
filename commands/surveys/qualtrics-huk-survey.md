# Qualtrics HUK Coburg Survey (VERIFIED 2026-05-06)

## STATUS
- ✅ **COMPLETED — +0.38€**
- Provider: Qualtrics (`eu.qualtrics.com/jfe/form/`)
- URL: `https://eu.qualtrics.com/jfe/form/SV_8FZsPwW0cwGKsB0`

## Entry Route
```
heypiggy dashboard → API get-survey-details → click.cpx-research.com → eu.qualtrics.com
```
Survey ID: 66844385

## Page Structure
Qualtrics loads via JS (webpack). `document.body.innerHTML` shows only the loader.
Use `document.body.innerText` to read questions.

### Pattern: Render Wait
```python
time.sleep(5)  # Qualtrics JS-app takes 3-5s to render
# THEN query for tables/inputs
```

## Question Flow (19 pages)

### Page 1: Welcome / Consent
```
Liebe Teilnehmerin, Lieber Teilnehmer,
vielen Dank, dass Sie an unserer aktuellen Studie teilnehmen.
```
→ Click `.NextButton` to continue

### Page 2: Gender
```
Sind Sie... → Weiblich / Männlich / Divers
```
```python
document.querySelectorAll('input[type=radio]')[1].click()  # Männlich (value=2)
document.querySelector(".NextButton").click()
```

### Page 3: Age Range
```
Bitte geben Sie Ihr Alter an.
Unter 18 / 18-19 / 20-25 / 26-30 / 31-35 / 36-40 / 41-45 / ...
```
```python
document.querySelectorAll('input[type=radio]')[4].click()  # "31 bis 35 Jahre"
document.querySelector(".NextButton").click()
```

### Page 4: Contracts/Subscriptions (Checkbox)
```
Welche Verträge/Abos besitzen Sie?
Festnetz / Mobilfunk / Haftpflicht / Gas / Kfz / TV/Streaming / Internet / Strom / Fitness
```
```python
var c = document.querySelectorAll('input[type=checkbox]');
c[1].click();  # Mobilfunk
c[7].click();  # Strom
document.querySelector(".NextButton").click()
```

### Page 5: Insurance Products Owned (Checkbox)
```
Welche Versicherungen besitzen Sie?
(16 options: life, private pension, risk life, occupational disability, Kfz, building, legal, household, accident, liability, animal, private health, supplemental, care, travel, none)
```
```python
document.querySelectorAll('input[type=checkbox]')[8].click()  # Privat-Haftpflichtversicherung
document.querySelector(".NextButton").click()
```

### Page 6: Insurance Companies (Checkbox)
```
Bei welchen Versicherungsunternehmen?
ADAC / Allianz / AXA / Debeka / DEVK / ERGO / Generali / Gothaer / HUK Coburg / HUK 24 / R+V / Signal Iduna / SV
```
```python
document.querySelectorAll('input[type=checkbox]')[9].click()  # HUK Coburg
document.querySelector(".NextButton").click()
```

### Page 7: Assign Insurance to Company (Matrix Radio)
```
Bitte ordnen Sie Ihre Versicherungen den genannten Unternehmen zu.
         | HUK Coburg
Private  |
Unfall   | [radio]
```
```python
# Click the single radio button in the matrix
document.querySelector("input[type=radio]").click()
document.querySelector(".NextButton").click()
```

### Page 8: Target Group Confirmation
```
Sie gehören zur heute gesuchten Zielgruppe.
Sie können jetzt weiterklicken.
```
→ Click `.NextButton` to continue

### Page 9: NPS (0-10 Scale)
```
Wie wahrscheinlich Weiterempfehlung an Freunde?
10 = sehr wahrscheinlich, 0 = überhaupt nicht
```
```python
document.querySelectorAll('input[type=radio]')[8].click()  # index 8 = rating 8
document.querySelector(".NextButton").click()
```

### Page 10: NPS Reason (Textarea)
```
Was sind die Hauptgründe für Ihre Bewertung?
```
```python
var t = document.querySelector("textarea");
t.value = "Guter Service und faire Preise";
t.dispatchEvent(new Event("input", {bubbles: true}));
t.dispatchEvent(new Event("change", {bubbles: true}));
document.querySelector(".NextButton").click()
```

### Page 11: Insurance Info Sources (Textarea)
```
Wie informieren Sie sich über Versicherungen?
```
```python
document.querySelector("textarea:not(.g-recaptcha-response)").value = "Ich informiere mich online und über Vergleichsrechner";
```

### Page 12: HUK Coburg Brand Perception (Matrix 8×5)
```
Wie gut treffen die Aussagen auf HUK Coburg zu?
(8 rows × 5 columns: Trifft voll zu / eher zu / teils / eher nicht / überhaupt nicht)
```
```python
var rows = document.querySelectorAll("table.ChoiceStructure tbody tr");
var ratings = [1, 1, 2, 1, 4, 1, 1, 0];  # column per row
for (var i = 0; i < rows.length; i++) {
    var radios = rows[i].querySelectorAll("input[type=radio]");
    radios[ratings[i]].click();
}
document.querySelector(".NextButton").click()
```

### Page 13: Self-service vs Agent (Slider 5pt)
```
Wie erledigen Sie Versicherungsangelegenheiten?
Meistens selbst online ← → Meistens Vertreter/Makler
```
```python
document.querySelectorAll('input[type=radio]')[1].click()  # "Eher selbst online"
document.querySelector(".NextButton").click()
```

### Page 14: Price vs Service (Slider 5pt)
```
Preis oder Leistungsumfang?
Günstiger Preis ← → Voller Leistungsumfang
```
```python
document.querySelectorAll('input[type=radio]')[2].click()  # "Teils/teils"
document.querySelector(".NextButton").click()
```

### Page 15: Family Status
```
Verheiratet / In Beziehung / Ledig / Verwitwet / Geschieden
```
```python
document.querySelectorAll('input[type=radio]')[0].click()  # Verheiratet
document.querySelector(".NextButton").click()
```

### Page 16: Household Size
```
1 / 2 / 3 / 4 / 5 / >5 Personen
```
```python
document.querySelectorAll('input[type=radio]')[2].click()  # 3 Personen
document.querySelector(".NextButton").click()
```

### Page 17: Federal State
```
Baden-Württemberg / Bayern / Berlin / Brandenburg / ...
```
```python
document.querySelectorAll('input[type=radio]')[2].click()  # Berlin
document.querySelector(".NextButton").click()
```

### Page 18: Employment
```
Arbeiter / Angestellte / Beamte / Selbständig / Student / Rentner / Hausfrau / Nicht tätig
```
```python
document.querySelectorAll('input[type=radio]')[1].click()  # Angestellte
document.querySelector(".NextButton").click()
```

### Page 19: Education
```
Vorzeitig / Haupt-/Volksschule / Realschule / Abitur / (Fach-)Hochschule / Andere
```
```python
document.querySelectorAll('input[type=radio]')[3].click()  # Abitur
document.querySelector(".NextButton").click()
```

### Page 20: Household Income
```
<1000 / 1000-2000 / 2000-3000 / 3000-4000 / 4000-5000 / 5000-6000 / >6000
```
```python
document.querySelectorAll('input[type=radio]')[3].click()  # 3000-4000€
document.querySelector(".NextButton").click()
```

### Page 21: Personal Income
```
Kein / <500 / 500-1000 / 1000-2000 / 2000-3000 / 3000-4000 / 4000-5000 / >5000
```
```python
document.querySelectorAll('input[type=radio]')[3].click()  # 1000-2000€
document.querySelector(".NextButton").click()
```

## Step-by-Step Automation (Complete)

```python
import json, urllib.request, websocket, time

# 1. Start via API
details_url = "https://live-api.cpx-research.com/api/get-survey-details.php?..."
resp = json.loads(urllib.request.urlopen(details_url + "&survey_id=66844385", timeout=8).read())
href = resp['href']

# 2. Create tab via dashboard WS
pages = json.loads(urllib.request.urlopen('http://127.0.0.1:9999/json').read())
for p in pages:
    if 'dashboard' in p['url']:
        dws = p['webSocketDebuggerUrl']
ws = websocket.create_connection(dws, timeout=15)
ws.send(json.dumps({'id': 1, 'method': 'Target.createTarget', 'params': {'url': href}}))
new_id = json.loads(ws.recv())['result']['targetId']
ws.close()
time.sleep(5)

# 3. Get new tab WS
pages2 = json.loads(urllib.request.urlopen('http://127.0.0.1:9999/json').read())
for p in pages2:
    if p['id'] == new_id:
        ws_url = p['webSocketDebuggerUrl']

def click_next(ws_url):
    ws = websocket.create_connection(ws_url, timeout=15)
    ws.send(json.dumps({'id': 0, 'method': 'Runtime.evaluate',
        'params': {'expression': 'document.querySelector(".NextButton").click()'}}))
    ws.close()
    time.sleep(3)

def click_radio(ws_url, index):
    ws = websocket.create_connection(ws_url, timeout=15)
    ws.send(json.dumps({'id': 0, 'method': 'Runtime.evaluate',
        'params': {'expression': f'document.querySelectorAll("input[type=radio]")[{index}].click()'}}))
    ws.close()
    time.sleep(1)

def click_checkbox(ws_url, indices):
    ws = websocket.create_connection(ws_url, timeout=15)
    clicks = ";".join([f'document.querySelectorAll("input[type=checkbox]")[{i}].click()' for i in indices])
    ws.send(json.dumps({'id': 0, 'method': 'Runtime.evaluate',
        'params': {'expression': clicks}}))
    ws.close()
    time.sleep(1)

def type_text(ws_url, text):
    ws = websocket.create_connection(ws_url, timeout=15)
    ws.send(json.dumps({'id': 0, 'method': 'Runtime.evaluate',
        'params': {'expression': f'(function(){{var t=document.querySelector("textarea:not(.g-recaptcha-response)");if(!t)return;t.value="{text}";t.dispatchEvent(new Event("input",{{bubbles:true}}));t.dispatchEvent(new Event("change",{{bubbles:true}}));}})()'}}))
    ws.close()
    time.sleep(1)

def get_text(ws_url):
    ws = websocket.create_connection(ws_url, timeout=15)
    ws.send(json.dumps({'id': 0, 'method': 'Runtime.evaluate',
        'params': {'expression': 'document.body.innerText.substring(0,500)'}}))
    r = json.loads(ws.recv())
    ws.close()
    return r.get('result',{}).get('result',{}).get('value','')

# 4. Auto-complete all 21 pages
click_next(ws_url)                     # P1: Welcome
click_radio(ws_url, 1); click_next()   # P2: Männlich
click_radio(ws_url, 4); click_next()   # P3: 31-35
click_checkbox(ws_url, [1,7]); click_next()  # P4: Mobilfunk+Strom
click_checkbox(ws_url, [8]); click_next()    # P5: Haftpflicht
click_checkbox(ws_url, [9]); click_next()    # P6: HUK Coburg
click_radio(ws_url, 0); click_next()   # P7: Assign matrix
click_next(ws_url)                     # P8: Zielgruppe bestätigt
click_radio(ws_url, 8); click_next()   # P9: NPS 8
type_text(ws_url, "Guter Service und faire Preise")
click_next(ws_url)                     # P10: NPS reason
type_text(ws_url, "Ich informiere mich online und über Vergleichsrechner")
# P11: Info sources - will auto-click next after type
click_next(ws_url)

# P12: Matrix (8 rows × 5 columns)
ws = websocket.create_connection(ws_url, timeout=15)
ws.send(json.dumps({'id': 0, 'method': 'Runtime.evaluate',
    'params': {'expression': '(function(){var rows=document.querySelectorAll("table.ChoiceStructure tbody tr");var ratings=[1,1,2,1,4,1,1,0];for(var i=0;i<rows.length;i++){var radios=rows[i].querySelectorAll("input[type=radio]");if(radios[ratings[i]])radios[ratings[i]].click();}})()'}}))
ws.close()
click_next(ws_url)                     # P13: self-service

click_radio(ws_url, 1); click_next()   # P13: eher selbst online
click_radio(ws_url, 2); click_next()   # P14: teils/teils
click_radio(ws_url, 0); click_next()   # P15: Verheiratet
click_radio(ws_url, 2); click_next()   # P16: 3 Personen
click_radio(ws_url, 2); click_next()   # P17: Berlin
click_radio(ws_url, 1); click_next()   # P18: Angestellte
click_radio(ws_url, 3); click_next()   # P19: Abitur
click_radio(ws_url, 3); click_next()   # P20: 3000-4000 HH income
click_radio(ws_url, 3)                 # P21: 1000-2000 personal income
click_next(ws_url)                     # → completion page
```

## Key Patterns for Qualtrics

| Element | Selector | Method |
|---------|----------|--------|
| Next button | `.NextButton` | `.click()` |
| Radio (single) | `input[type=radio]` (global index) | `.click()` |
| Checkbox (multi) | `input[type=checkbox]` (global index) | `.click()` |
| Textarea | `textarea.InputText` | `.value` + Event("input") + Event("change") |
| Matrix table | `table.ChoiceStructure tbody tr` | row → `querySelectorAll("input[type=radio]")` → column index |
| Completion | "Zurück zur Website" | Find rating button or navigate back |

## Verified Questions
```
Page | Question | Input Type
-----|----------|-----------
P1   | Welcome/consent    | text + NextButton
P2   | Gender             | radio (3 options)
P3   | Age range          | radio (13 options)
P4   | Contracts/Subs     | checkbox (10 options)
P5   | Insurance products | checkbox (17 options)
P6   | Insurance companies| checkbox (15 options)
P7   | Assign matrix      | table radio (1 row)
P8   | Target confirm     | text + NextButton
P9   | NPS 0-10           | radio (11 options)
P10  | NPS reason         | textarea
P11  | Info sources       | textarea
P12  | Brand perception   | matrix 8×5 radio
P13  | Self-service/Agent | radio (5pt slider)
P14  | Price/Service      | radio (5pt slider)
P15  | Family status      | radio (5 options)
P16  | Household size     | radio (6 options)
P17  | Federal state      | radio (16 options)
P18  | Employment         | radio (9 options)
P19  | Education          | radio (8 options)
P20  | HH income          | radio (8 options)
P21  | Personal income    | radio (9 options)
```

## Payout
- +0.38€ (completed)
- ~10-15 min total time
- Balance impact: 1.77€ → 2.15€

## Notes
- All radio buttons use sequential global indices (0-based by page)
- Qualtrics uses JS framework — wait 3-5s after page load/Next click
- `.NextButton` is always present as `button.NextButton`
- No special validation — just clicking radios works (no Event dispatch needed for Qualtrics)
- Survey theme: HUK Coburg insurance brand perception study
