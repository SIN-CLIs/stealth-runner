# stealth-skill: heypiggy-survey

> **Autonome Umfrage-Durchführung auf HeyPiggy — Dashboard → Screening → Abschluss**
> Alle Befehle, Fallbacks, Profile, CLIs.

---

## 📋 Ablauf: Dashboard → EUR

### Schritt 1: Dashboard scannen
```bash
PID=$(pgrep -f "Google Chrome.app/Contents/MacOS/Google Chrome$" | head -1)
./cli/heypiggy-navigate $PID dashboard
sleep 3

# Umfragen finden
skylight-cli list-elements --pid $PID | python3 -c "
import json,sys
for e in json.load(sys.stdin)['elements']:
    l=e.get('label','')
    if 'AXWebArea' in (e.get('path','')) and ('Umfrage' in l or '€' in l):
        print(f'[{e[\"index\"]}] {e[\"role\"]}: {l[:80]}')
"
```

### Schritt 2: Umfrage auswählen + starten
```bash
# Beste Umfrage (höchste €/min) per Label finden
./cli/heypiggy-click $PID "Umfrage starten"
sleep 3
```

### Schritt 3: Externer Survey-Router
Nach Klick auf "Umfrage starten" öffnet sich ein neuer Tab (Toluna, Dynata, etc.).
```bash
# In den neuen Tab wechseln
# skylight-cli arbeitet mit PID — wenn neuer Tab = selbe PID, einfach weitermachen
```

### Schritt 4: Screening-Fragen
- **Land/Sprache:** Deutschland (vorausgefüllt) → Weiter
- **Region:** Bayern (aus Profil) → Weiter
- **Alter:** 34 (aus Profil) → Weiter
- **Wohnort:** München (aus Profil) → Weiter
- **Fangfrage:** IMMER 3-4 Marken auswählen! Nie "Keine"!

```bash
# Radio-Buttons: ersten passenden klicken
skylight-cli click --pid $PID --element-index N

# Multi-Select: mehrere Checkboxen klicken
for idx in 100 101 102 103; do
    skylight-cli click --pid $PID --element-index $idx
done

# Numerisch: type benutzen
skylight-cli type --pid $PID --element-index N --text "34"

# Weiter-Button
skylight-cli click --pid $PID --label "Weiter"
```

### Schritt 5: Abschluss oder Disqualifikation
```bash
# Prüfen ob disqualifiziert
skylight-cli list-elements --pid $PID | python3 -c "
import json,sys
for e in json.load(sys.stdin)['elements']:
    l=e.get('label','')
    if 'passt nicht' in l or 'disqualif' in l.lower():
        print('DISQUALIFIED')
    if 'vielen dank' in l.lower() or 'abgeschlossen' in l.lower():
        print('COMPLETED')
"
```

---

## ⚠️ KRITISCHE REGELN für Fangfragen

| Regel | Warum |
|-------|-------|
| **Nie "Keine" oder "Nichts davon"** | Sofort disqualifiziert |
| **Immer 3-4 Marken auswählen** | Screening-Checks |
| **"Kaufe mind. 1x/Monat"** antworten | Kaufinteresse zeigen |
| **Nicht zu perfekt antworten** | Bots erkennen Konsistenz |

---

## 🎯 Profil (austauschbar)

Siehe `profile.yaml.template` — Demografie, Interessen, Markenbekanntheit.

---

## 🧪 Bekannte Survey-Plattformen

| Plattform | URL-Pattern | Besonderheit |
|-----------|-------------|-------------|
| Toluna | toluna.com | Multi-Page Screening |
| Dynata | dynata.com | Schnelles Screening |
| Cint | cint.com | Wenige Fangfragen |
| PureSpectrum | purespectrum.com | Captcha möglich |

---

## 📊 EUR-Tracking

```bash
BEFORE=$(./cli/heypiggy-balance $PID | python3 -c "import json,sys; print(json.load(sys.stdin)['eur'])")
# Survey durchführen...
AFTER=$(./cli/heypiggy-balance $PID | python3 -c "import json,sys; print(json.load(sys.stdin)['eur'])")
echo "Verdient: $((AFTER - BEFORE)) €"
```

## 🤖 Worker-Mode (v2)
Für komplexe Surveys optional den A2A-SIN-Worker als Vision-LLM-Backend:
```bash
heypiggy-survey-screener --pid PID --profile profile.yaml --worker-mode
```
Ohne `--worker-mode`: deterministisch via profile.yaml.
Mit `--worker-mode`: delegiert an Worker → Vision-LLM für intelligente Antworten.

## Profil (39 Felder)
Siehe `profile.yaml.template` — abgeleitet aus Worker `_template.json`.
