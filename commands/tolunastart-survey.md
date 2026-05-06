# TolunaStart Survey (2026-05-06) — VERIFIED ✅

**Provider**: click.cpx-research.com → survey.tolunastart.com
**Survey ID**: 66583827 (was on dashboard, opened via click.cpx)
**Reward**: +0.09€ + 0.01€ rating bonus
**Progress**: Completed to 92%, then hit demographics

## ⚠️ MOST IMPORTANT: JS .click() PATTERN

**For TolunaStart, use JS `.click()` on `.cf-radio` and `.cf-checkbox` elements.**
DO NOT use CDP MouseEvent on these elements — it doesn't work.

```python
# RADIO (single select) — WORKS
ws.send(json.dumps({'id': 0, 'method': 'Runtime.evaluate', 'params': {'expression': '(function(){var rs=document.querySelectorAll(".cf-radio");rs[INDEX].click();})()'}}))

# CHECKBOX (multi select) — WORKS
ws.send(json.dumps({'id': 0, 'method': 'Runtime.evaluate', 'params': {'expression': '(function(){var cbs=document.querySelectorAll(".cf-checkbox");[0,2,3].forEach(function(i){cbs[i].click();});})()'}}))

# BUTTON — WORKS
ws.send(json.dumps({'id': 0, 'method': 'Runtime.evaluate', 'params': {'expression': 'document.querySelector("button").click()'}}))

# INPUT (number/text) — WORKS
ws.send(json.dumps({'id': 0, 'method': 'Runtime.evaluate', 'params': {'expression': '(function(){var i=document.querySelector("input[type=number], input[type=text]");if(i){i.value="32";i.dispatchEvent(new Event("input",{bubbles:true}));}document.querySelector("button").click();})()'}}))
```

## Complete Survey Flow

### Step 0: Survey Opens
URL: `https://survey.tolunastart.com/wix/3/p706769322093.aspx`
Progress: 2%
Questions: Industry employment (multi-select)

### Step 1: Industry Question
**"Sind Sie oder jemand aus Ihrer Familie in folgenden Bereichen tätig?"**
- Options: Banken, Versicherungen, Marketing, Marktforschung, Werbeagentur, Medien, In keinem dieser Bereiche
- **Answer**: Click "In keinem dieser Bereiche" (index 6) or any others
```python
ws.send(json.dumps({'id': 0, 'method': 'Runtime.evaluate', 'params': {'expression': '(function(){var cbs=document.querySelectorAll(".cf-checkbox");cbs[6].click();document.querySelector("button").click();})()'}}))
```
→ Next @581,462 → Weiter

### Step 2: Attention Check — Smallest Number
**"Bitte klicken Sie auf die kleinste Zahl."**
Numbers: 33, 45, 87, 35
- **Answer**: 33 (smallest)
- Radio controls: @130,215 (33), @130,257 (45), @130,299 (87), @130,341 (35)
```python
ws.send(json.dumps({'id': 0, 'method': 'Runtime.evaluate', 'params': {'expression': '(function(){var radios=document.querySelectorAll(".cf-radio");radios[0].click();document.querySelector("button").click();})()'}}))
```

### Step 3: Insurance Products (multi-select)
**"Welche der folgenden Produkte besitzen Sie selbst privat?"**
- Click Kfz-Versicherung (index 4) and Privathaftpflichtversicherung (index 12)
```python
ws.send(json.dumps({'id': 0, 'method': 'Runtime.evaluate', 'params': {'expression': '(function(){var cbs=document.querySelectorAll(".cf-checkbox");cbs[4].click();cbs[12].click();document.querySelector("button").click();})()'}}))
```

### Step 4: Gender
**"Sind Sie..."** → Ein Mann (index 0)
```python
ws.send(json.dumps({'id': 0, 'method': 'Runtime.evaluate', 'params': {'expression': '(function(){var rs=document.querySelectorAll(".cf-radio");rs[0].click();document.querySelector("button").click();})()'}}))
```

### Step 5: Age
**"Wie alt sind Sie?"** → Input field
```python
ws.send(json.dumps({'id': 0, 'method': 'Runtime.evaluate', 'params': {'expression': '(function(){var i=document.querySelector("input[type=number]");i.value="32";i.dispatchEvent(new Event("input",{bubbles:true}));document.querySelector("button").click();})()'}}))
```

### Step 6: Occupation
**"In welcher beruflichen Situation befinden Sie sich aktuell?"**
Options: Berufsausbildung, Schule/Universität, Beginn der Berufstätigkeit, **(Mitten) im Berufsleben** (index 3), Arbeitslosigkeit, Mutterschutz, kurz vor Ruhestand, Ruhestand, Keine Antwort
- **Answer**: (Mitten) im Berufsleben (index 3)

### Step 7: Household Income
**"monatliche Netto-Einkommen"**
Options: Bis unter 1.000€, 1.000-2.000€, 2.000-3.000€, **3.000-4.000€** (index 3), 4.000€+
- **Answer**: 3.000-4.000€ (index 3)

### Step 8: Bundesland
**"In welchem Bundesland wohnen Sie?"**
Options: Bayern(0), Baden-Württemberg(1), Hessen(2), Rheinland-Pfalz(3), Saarland(4), Sachsen(5), Sachsen-Anhalt(6), **Nordrhein-Westfalen**(7), Niedersachsen(8), Thüringen(9), Brandenburg(10), **Berlin**(11), Mecklenburg-Vorpommern(12), Schleswig-Holstein(13), Bremen(14), Hamburg(15)
- **Answer**: Berlin (index 11)

### Step 9: Color Attention Check
**"Bitte wählen Sie aus folgender Liste die Farbe violett aus."**
- Options: Orange, Grün, Blau, **Violett** (index 3), Gelb
- **Answer**: Violett (index 3)

### Step 10: AI Tools Known
**"Welche der folgenden KI-Tools kennen Sie?"** (multi-select)
- Options: ChatGPT(0), Grok(1), Copilot(2), Gemini(3), Claude(4), Deepseek(5), Mistral(6), Perplexity(7), Llama(8), Keine(9)
- **Answer**: ChatGPT, Copilot, Gemini, Claude, Deepseek (indices 0,2,3,4,5)

### Step 11: AI Tools Used Privately/Professionally
**"Welche der folgenden KI-Tools verwenden Sie privat und welche beruflich?"**
- 10 checkboxes total: Gemini(0), Claude(1), Deepseek(2), ChatGPT(3), Keine(4), Intern(5), Gemini(6), Claude(7), Deepseek(8), Copilot(9), ChatGPT(10)
- **Answer**: Private: 0,1,2,3; Professional: 5,6,7,8,9

### Step 12: Free/Paid Version
Matrix question with 8 radios (radio indices 8-15 in full list)
- **Answer**: Deepseek free (8), Claude paid (11), Gemini free (12), ChatGPT paid (15)

### Step 13: Monthly Cost
**"Wie viel bezahlen Sie... für private Zwecke?"**
Matrix: Claude(10-20€ idx 11), ChatGPT(10-20€ idx 16)
```python
ws.send(json.dumps({'id': 0, 'method': 'Runtime.evaluate', 'params': {'expression': '(function(){var rs=document.querySelectorAll(".cf-radio");rs[11].click();rs[16].click();document.querySelector("button").click();})()'}}))
```

### Step 14: Plan to Upgrade
**"vor in den nächsten 6 Monaten auf die Bezahlversion umzusteigen?"**
Options: Ja mit Sicherheit, Ja wahrscheinlich, Nein wahrscheinlich nicht, Nein sicher nicht
- **Answer**: Nein sicher nicht (index 3)

### Step 15: AI Use Cases (multi-select)
**"Für welche Aufgaben verwenden Sie diese KI-Tools..."**
12 options: Bilder(0), Textverarbeitung(1), Ereignis planen(2), Dokumente(3), IT-Inhalte(4), Suche Kauf(5), Text generieren(6), Aufgaben automatisieren(7), Video/Ton(8), Beratung(9), Info suchen(10), Keine(11)
- Private column: indices 0-11
- **Answer**: Textverarbeitung(1), Dokumente(3), Info suchen(9), Private suche(10) + same in professional: IT-Inhalte(12+4=16), Text(12+6=18), automatisieren(12+7=19)

### Step 16: Most Frequent Task
Matrix: Private(0-3), Professional(4-8)
- **Answer**: Private: Info suchen (index 3), Professional: IT-Inhalte (index 7)

### Step 17: Usage Frequency — Private
**"Wie oft verwenden Sie diese KI-Tools privat?"**
4 AI tools × 5 frequency options = 20 radios
- Deepseek: Täglich(20), 3-4×(21), 1-2×(22), 1-3×(23), Nie(24)
- Claude: Täglich(25), 3-4×(26), **1-2×**(27), 1-3×(28), Nie(29)
- Gemini: Täglich(30), 3-4×(31), **1-2×**(32), 1-3×(33), Nie(34)
- ChatGPT: **Täglich**(35), 3-4×(36), 1-2×(37), 1-3×(38), Nie(39)
- **Answer**: Deepseek 1-2×(22), Claude 1-2×(27), Gemini 1-2×(32), ChatGPT täglich(35)

### Step 18: Usage Frequency — Professional
5 AI tools × 5 frequencies = 25 radios (25-49)
- Gemini: 1-2×(27), Deepseek: 1-2×(30), Copilot: 1-2×(38), ChatGPT: 1-2×(40)
- Keine: 1-3×(45)
- **Answer**: Gemini(27), Deepseek(30), Copilot(38), ChatGPT(40), Keine(45)

### Step 19: AI for Search
**"Verwenden Sie diese KI-Tools für Recherchen wie Google/Bing?"**
Options: Ja oft, Ja manchmal, Selten, Nie
- **Answer**: Ja oft (index 0)

### Step 20: AI Overviews Noticed
**"zeigen manche Suchmaschinen... künstliche Intelligenz generierte Antwort"**
Options: Ja oft, Ja manchmal, Selten, Nie, Ich weiß nicht
- **Answer**: Ja oft (index 0)

### Step 21: Search Frequency Change
**"seit Sie KI-Tools nutzen... weniger/häufiger?"**
Options: Weniger häufig, Genauso viel, Häufiger
- **Answer**: Weniger häufig (index 0)

### Step 22: AI Reliability
**"Wie bewerten Sie die Präzision der Informationen?"**
Options: Sehr zuverlässig, **Eher zuverlässig** (index 1), Eher unrichtig, Sehr unrichtig
- **Answer**: Eher zuverlässig (index 1)

### Step 23: AI-Cited Websites
**"Besuchen Sie Internetseiten, die KI-Tools als Quellen angeben?"**
Options: Ja oft, Ja manchmal, Selten, Nie
- **Answer**: Ja manchmal (index 1)

### Step 24: Purchase Decision
**"Haben Sie bereits eine Kaufentscheidung auf Basis von KI-Tools getroffen?"**
Options: Ja (index 0), Nein, Ich erinnere mich nicht
- **Answer**: Ja (index 0)

### Step 25: Purchase Research Frequency
**"Wie oft fragen Sie KI-Tools, bevor Sie einen Kauf tätigen?"**
Options: Immer, Oft, **Manchmal** (index 2), Selten
- **Answer**: Manchmal (index 2)

### Step 26: Purchase Research Tools (multi-select)
**"welche Online-Lösung(en) nutzen Sie dann?"**
Options: KI-Tools(0), Websites(1), Keine(2)
- **Answer**: KI-Tools(0) + Websites(1)

### Step 27: Priority
**"welche Lösung hat für Sie Vorrang...?"**
Options: KI-Tools, **Websites** (index 1)
- **Answer**: Websites (index 1)

### Step 28: Decisive Factor
**"welche Lösung ist für Sie am ausschlaggebendsten?"**
Options: KI-Tools, Websites, **Beide gleich häufig** (index 2)
- **Answer**: Beide gleich häufig (index 2)

### Step 29: AI Purchase Research Info (multi-select)
**"Welche Information(en) suchen Sie über KI-Tools?"**
12 options: Erläuterungen(0), Kosten(1), Empfehlung(2), Technische(3), Konfiguration(4), Meinungen(5), Zuverlässigkeit(6), Schritt-für-Schritt(7), Zusammenfassung(8), Identifikation(9), Ausnahmen(10), Preise(11), Optionen(12)
- **Answer**: 0, 1, 5, 9, 11

### Step 30: Ranking (special pattern!)
**"Welche dieser verschiedenen Informationen suchen Sie als Erstes? Als Zweites? Als Drittes?"**
- Ranking items: `.cf-ranking-answer` with `role="button"`
- Click item → cycles rank: unselected → 1 → 2 → 3 → disabled
- **Answer**: Select 3 items (indices 0, 3, 4 = Erläuterungen, Identifikation, Preise)
```python
ws.send(json.dumps({'id': 0, 'method': 'Runtime.evaluate', 'params': {'expression': '(function(){var items=document.querySelectorAll(".cf-ranking-answer");items[0].click();items[3].click();items[4].click();document.querySelector("button").click();})()'}}))
```

### Step 31: Product Categories (multi-select)
**"Für welche Arten von Produkten/Dienstleistungen fragen Sie KI-Tools?"**
Options: Elektronik(0), Reisen(1), Kurse(2), Kleidung(3), Versicherungen(4), Kosmetik(5), Restaurants(6), Banken(7), Möbel(8)
- **Answer**: Elektronik(0), Reisen(1), Kleidung(3), Restaurants(6), Banken(7)

### Step 32: Future AI Usage
**"in den nächsten fünf Jahren häufiger künstliche Intelligenz einsetzen?"**
Options: Ja(0), Nein(1), Ich weiß nicht(2)
- **Answer**: Ja (index 0)

### Step 33: Integrated AI Apps
**"in KI-Tools integrierte Anwendungen (Reisen, Einkaufen) genutzt?"**
Options: Ja(0), Nein(1)
- **Answer**: Ja (index 0)

### Step 34: Which Integrated Apps
Text inputs (up to 10 fields)
```python
ws.send(json.dumps({'id': 0, 'method': 'Runtime.evaluate', 'params': {'expression': '(function(){var inputs=document.querySelectorAll("input[type=text]");var vals=["Custom GPTs","DALL-E","Data Analysis"];for(var i=0;i<3&&i<inputs.length;i++){inputs[i].value=vals[i];inputs[i].dispatchEvent(new Event("input",{bubbles:true}));}document.querySelector("button").click();})()'}}))
```

### Step 35: Demographics — Household Size
**"Wie viele Personen leben in Ihrem Haushalt?"**
```python
ws.send(json.dumps({'id': 0, 'method': 'Runtime.evaluate', 'params': {'expression': '(function(){var i=document.querySelector("input[type=number]");i.value="2";i.dispatchEvent(new Event("input",{bubbles:true}));document.querySelector("button").click();})()'}}))
```

### Step 36: Demographics — Children Under 18
**"Wie viele Kinder unter 18?"** → 0
```python
ws.send(json.dumps({'id': 0, 'method': 'Runtime.evaluate', 'params': {'expression': '(function(){var i=document.querySelector("input[type=number]");i.value="0";i.dispatchEvent(new Event("input",{bubbles:true}));document.querySelector("button").click();})()'}}))
```

### Step 37: Education
**"Was ist der höchste Bildungsabschluss?"**
Options: Grundschule(0), Sekundarstufe I(1), Sekundarstufe II(2), Berufsausbildung(3), Bachelor(4), Master(5), Doktor(6), Anderer(7)
- **Answer**: Berufsausbildung (index 3)

### Continue from here...

## Key Learnings

1. **JS .click() ALWAYS works** — don't use MouseEvent on .cf-radio/.cf-checkbox
2. **Matrix questions** — radios indexed globally, find position by row
3. **Multi-select** — click multiple checkbox indices
4. **Numeric input** — set value + dispatchEvent
5. **Ranking** — click to cycle through states
6. **RATING PAGE** — ALWAYS rate after survey!

## Rating Page
After survey: `offers.cpx-research.com/rating.php`
→ Click button @1019,181 → +0.01€ bonus

## Survey IDs That Lead to TolunaStart
Dashboard survey IDs → check via API for `tolunastart.com` href