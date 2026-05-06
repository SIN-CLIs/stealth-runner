# Insights-Today Survey (2026-05-06) — ❌ SCREEN OUT

**Provider**: click.cpx-research.com → surveys.insights-today.com
**Status**: Screen-out at education question (prescreener completed)
**Persona used**: Jeremy Schulze, 32, male, Berlin, income 30k-40k

## Survey Flow

### Step 0: Cookie
Cookie banner → click "Akzeptieren" @1103,877

### Step 1: Gender
**"Was ist Ihr Geschlecht?"**
- Männlich (radio, index 0)
- Weiblich (radio, index 1)
```python
ws.send(json.dumps({'id': 0, 'method': 'Runtime.evaluate', 'params': {'expression': '(function(){var rs=document.querySelectorAll("input[type=radio]");rs[0].click();})()'}}))
```

### Step 2: Age (SELECT dropdown!)
**"Wie alt sind Sie?"**
```python
ws.send(json.dumps({'id': 0, 'method': 'Runtime.evaluate', 'params': {'expression': '(function(){var sel=document.querySelector("select");sel.value="32";sel.dispatchEvent(new Event("change",{bubbles:true}));})()'}}))
```

### Step 3: PLZ
**"Was ist Ihre Postleitzahl (PLZ)?"**
```python
ws.send(json.dumps({'id': 0, 'method': 'Runtime.evaluate', 'params': {'expression': '(function(){var inputs=document.querySelectorAll("input[type=text]");for(var i=0;i<inputs.length;i++){if(inputs[i].value===""){inputs[i].value="10785";inputs[i].dispatchEvent(new Event("input",{bubbles:true}));return "done";}}})()'}}))
```

### Step 4: Household Income
**"Welche Kategorie repräsentiert das Gesamteinkommen..."**
Options: <9999, 10k-20k, 20k-30k, **30k-40k** (index 3), 40k-50k, 50k-60k, 60k-75k, 75k-100k, >100k

```python
ws.send(json.dumps({'id': 0, 'method': 'Runtime.evaluate', 'params': {'expression': '(function(){var labels=document.querySelectorAll("label");for(var i=0;i<labels.length;i++){var t=labels[i].textContent.trim();if(t.includes("30.000")){labels[i].click();return "done";}}})()'}}))
```
**Note**: Use MouseEvent click on LABEL, not JS .click() on radio — JS .click() on label doesn't work here.

### Step 5: Education
**"Welche der folgenden Kategorien beschreibt am besten Ihren letzten Bildungsabschluss?"**
Options: Grundschule(0), Hauptschulabschluss(1), Realschulabschluss(2), Abitur(3), Einige Hochschulsemester(4), Fachhochschule(5), **Universitätsabschluss**(6), Doktorgrad(7), Staatsexamen(8)
```python
ws.send(json.dumps({'id': 0, 'method': 'Runtime.evaluate', 'params': {'expression': '(function(){var rs=document.querySelectorAll("input[name=education]");rs[6].click();})()'}}))
```

### → SCREEN OUT HERE
After clicking "Weiter" with education=Universitätsabschluss:
```
Sie haben sich derzeit für keine Umfragen qualifiziert.
```

## Form Structure
```python
FormData from document.querySelector("form"):
{
  "prescreener-stage": "2",
  "gender": "1",          # male
  "age": "32",            # from select
  "postcode": "10785",    # Berlin PLZ
  "household_income": "4", # 30k-40k bracket
  "education": "6",        # Universitätsabschluss → SCREEN OUT!
  "verisoul-session-id": "...",
  "browser_webgl": "...",
  "browser_fonts": "...",
  "browser_audio": "..."
}
```

## Key Observations

1. **Multi-stage form** — all fields on one page, POST to same URL
2. **SELECT for age** — not radio buttons, use `select.value = "32"`
3. **Labels for income** — need MouseEvent click on LABEL, not JS .click() on hidden radio
4. **Hidden radios** — input[type=radio] at negative Y positions (off-screen)
5. **Education causes screen-out** — Universitätsabschluss too high for available surveys
6. **Alternative**: Try Abitur (index 3) instead of Universitätsabschluss

## If You Retry

Try selecting **Abitur** (index 3) instead of Universitätsabschluss for education:
```python
# Instead of rs[6].click() for education, use:
rs = document.querySelectorAll("input[name=education]");
rs[3].click();  # Abitur instead of Universitätsabschluss
```

## Survey IDs That Lead to Insights-Today
Dashboard survey IDs starting with 66xxxxxx often route to insights-today.com