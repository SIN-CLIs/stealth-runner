# HeyPiggy Surveyrouter — Pre-Qualifier Flow (2026-05-09)

## Status
🔄 LEARNING — Survey ID 66919948, 67063392 getestet

## Provider
- **Name:** surveyrouter (heypiggy internal)
- **Erkennung:** URL = heypiggy.com, kein externer Link, modal overlay
- **Flow:** Click → Modal (kein new tab) → Pre-Q Fragen → "Umfrage starten"

## DOM Struktur

### Survey Cards auf Dashboard
```javascript
// Find all survey cards
document.querySelectorAll("[onclick*=clickSurvey]")
// → onclick="clickSurvey('ID')"
// → text = "0.49 €\n\n4 Min\n32\n🔥21"

// Click survey card
document.querySelectorAll("[onclick*=clickSurvey]")[0].click()
```

### Modal Overlay (nach clickSurvey)
```javascript
// Modals found: 22 total, ~1-2 visible
document.querySelectorAll(".modal.show")
// → Active: class="modal long-animation show" (disqualification)
// → Active: class="modal show" (pre-qualifier question)

// MODAL STRUKTUR:
// .modal-content-wrapper
//   .modal-content
//     h2: Frage-Text
//     .input-content-wrapper
//       LABEL + INPUT[type=radio] × 5 (Single Choice)
//       LABEL: "Ich bevorzuge, diese Frage nicht zu beantworten." (refusal)
//       LABEL: "Diese Frage kann / will ich nicht beantworten." (refusal)
//     BUTTON.modal-button-positive: "Nächste" (submit)
```

### Pre-Qualifier Fragen (ENTDECKT):
1. "Verwenden/Tragen Sie eine Brille oder Kontaktlinsen?" — 5 options (radio)
2. "Welche der folgenden Optionen beschreibt am besten die Umgebung..." — 4 options (radio)

### Antworten auswählen (CDP JS)
```javascript
// Radio auswählen (index 0-4)
var rad = document.querySelectorAll(".modal.show input[type=radio]");
rad[0].checked = true;
rad[0].click();  // fire change event

// "Nächste" button klicken
var btns = document.querySelectorAll(".modal.show .modal-button-positive");
for (var b of btns) {
    if (b.innerText.trim() === "Nächste") {
        b.click();
        break;
    }
}
```

### "Umfrage starten" (nach Pre-Q bestanden)
```javascript
// Button klicken (nach Pre-Q qualifiziert)
var btns = document.querySelectorAll(".modal.show .modal-button-positive");
for (var b of btns) {
    if (b.innerText.trim() === "Umfrage starten") {
        b.click();
        break;
    }
}
```

### Disqualification Modal
```javascript
// "Schließen" button
for (var b of document.querySelectorAll("button")) {
    if (b.innerText.trim() === "Schließen") { b.click(); }
}
```

## Surveyrouter Flow (VOLLSTÄNDIG)

```
1. Dashboard: Survey Cards mit onclick="clickSurvey('ID')"
   ↓ click card
2. Modal Overlay auf Dashboard (KEIN new tab!)
   → Pre-Qualifier Frage(n) oder "Umfrage starten"
   ↓ 2-5 Pre-Q Fragen (radio, single choice)
   ↓ "Nächste" nach jeder Antwort
3. "Du kannst jetzt die Umfrage beginnen. Viel Erfolg!"
   → "Umfrage starten" Button erscheint
   ↓ click "Umfrage starten"
4. ENTWEDER:
   a) New Tab mit externer Survey URL (CPX flow)
   b) In-Page Survey (weiter in modal)
   c) DISQUALIFIED ("Umfrage passt nicht") — slots full oder profile mismatch
5. Survey beendet → Tab schließt → zurück zum Dashboard
```

## Selector Mapping

| Element | CSS Selector | CDP JS |
|---------|-------------|--------|
| Survey Card | `[onclick*="clickSurvey"]` | querySelectorAll |
| Modal (aktiv) | `.modal.show` | querySelectorAll |
| Radio Button | `.modal.show input[type=radio]` | querySelectorAll |
| Radio Label | `.modal.show label` | querySelectorAll |
| Nächste Button | `.modal.show .modal-button-positive` (text="Nächste") | for-loop |
| Umfrage starten | `.modal.show .modal-button-positive` (text="Umfrage starten") | for-loop |
| Schließen | `button` (text="Schließen") | for-loop |
| Disqualification Modal | `.modal.long-animation.show` | querySelector |

## Question Types (ENTDECKT)

| Q-Type | Erkennung | DOM | Interaktion |
|--------|-----------|-----|-------------|
| Single Choice Radio | 5 LABEL + 5 INPUT[radio] | `input[type=radio]` + `label` | click radio + Nächste |
| Refusal Option | Label mit "nicht beantworten" | `label` | click radio |

## Known Survey IDs (2026-05-09)

| ID | Reward | Flow | Status |
|----|--------|------|--------|
| 67027382 | 1.82€ | Ipsos Landing → Consent → redirect | DISQUALIFIED (type=out) |
| 66919948 | 0.49€ | surveyrouter modal → 2 Pre-Q → DISQUALIFIED | no slot after qual |
| 67063392 | 0.64€ | surveyrouter modal → "Umfrage starten" → nothing | broken |
| 67023114 | 0.23€ | — | nicht getestet |
| 66947768 | 0.28€ | — | nicht getestet |

## Anti-Learnings (WICHTIG!)

❌ survey 67063392: "Umfrage starten" clicked but nothing happened → survey removed
❌ survey 66919948: Pre-Q passed but survey disqualified (slots full during answering)
❌ 1.82€ Ipsos: Landing consent passed but redirect showed "Umfrage passt nicht"
❌ Survey slots can fill up while answering pre-qualifier questions!

## Chrome Session State

- Chrome 9999 mit 7 HeyPiggy-Cookies aus Backup
- 12 Surveys auf Dashboard, balance 2.65€
- Survey 66919948 (0.49€) und 67063392 (0.64€) aus Liste entfernt
- Ipsos Tab geschlossen

## Next Steps

1. Chrome restart mit frischen Cookies für bessere Session
2. Survey mit kurzer Zeit (4 Min) testen
3. Antworten schneller geben (weniger delay)
4. Ipsos Survey 1.82€ mit neuem Tab versuchen (consent passiert)
5. Survey 67023114 (0.23€) testen
