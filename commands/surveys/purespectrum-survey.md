# Purespectrum Survey Flow — DISCOVERED 2026-05-09

## Status
✅ VERIFIED 2026-05-09 — Survey opened via window.open interception, provider detected

## Survey URL Pattern
- `screener.purespectrum.com` (screener/pre-qualifier)
- `*.purespectrum.com` (main survey)

## Kompletter Ablauf

### Step 1: Survey öffnet sich (via window.open interception)
- Tab URL: `https://screener.purespectrum.com/?survey_id=...`
- Provider: `purespectrum`

### Step 2: Cookie Consent
```javascript
// cky-btn-accept = Cookiebot "Alle akzeptieren" button
document.querySelector('.cky-btn-accept')?.click()
```
- **DOM**: `.cky-btn-accept` class
- **Issue**: Cookie modal blockiert Survey-Content wenn nicht akzeptiert

### Step 3: ROBOT Captcha
```javascript
// ROBOT text field — hidden input near "confirm you have read the full terms" text
// Field ist visible aber `querySelector('input')` findet es nicht direkt
// Lösung: Suche nach input FELDERN die im gleichen div wie "ROBOT" text sind
document.querySelectorAll('input').forEach(inp => {
    const near = inp.closest('div,p')?.innerText || ''
    if (near.includes('ROBOT') || inp.placeholder?.toLowerCase().includes('robot')) {
        inp.value = 'ROBOT'
        inp.dispatchEvent(new Event('input', {bubbles: true}))
    }
})
```
- **Text on page**: "Enter the word 'ROBOT' in the field below to confirm..."
- **Field**: Hidden input oder inline text input
- **Pattern**: Suche nach input im DOM subtree unter dem ROBOT text paragraph

### Step 4: Role Model Textarea
```javascript
// Role model question: "Was sind die drei Dinge, die du an deinem Vorbild magst?"
// Minimum 5 Wörter required
var ta = document.querySelector('textarea[placeholder*="Antwort"]')
if (ta) {
    ta.value = 'Ich bewundere Ehrlichkeit, Entschlossenheit und die Fähigkeit andere zu inspirieren.'
    ta.dispatchEvent(new Event('input', {bubbles: true}))
}
```

### Step 5: Click "Nächste"
```javascript
document.querySelectorAll('button').forEach(b => {
    if (b.innerText.trim() === 'Nächste') { b.click(); return }
})
```

## DOM Struktur
```
.ps-root (main app)
├── .cky-consent-container (Cookiebot overlay) → .cky-btn-accept
├── .survey-container
│   ├── .question-title (heading: "Was sind die drei Dinge...")
│   ├── .question-description (min 5 words requirement)
│   ├── textarea (role model answer)
│   ├── input[type=text] (ROBOT captcha - hidden!)
│   ├── .btn "Nächste"
│   └── .font-size controls (A/A buttons)
└── footer (Datenschutzrichtlinie link)
```

## Provider Detection
```python
# In tool_open_survey.py PROVIDER_PATTERNS:
"purespectrum": ["purespectrum", "spectrum"]
```

## Test Results (2026-05-09)
- Survey ID: 67064749 → URL: `https://screener.purespectrum.com/?survey_id=49503255`
- Tab opened: YES (via window.open interception)
- Provider detected: purespectrum ✅
- Page loaded: cookie consent + ROBOT captcha + role model question ✅

## Commands
- Open: `survey-cli/tools/tool_open_survey.py` → `open_survey()` mit window.open interception
- Fill: CDP JS per Step 2-5

## History
- 2026-05-09: DISCOVERED via survey 67064749, window.open interception flow