# stealth-skill: google-login

> **Vollständiger Google OAuth Login/Logout — heypiggy.com + accounts.google.com**
> Alle Befehle, Element-Indizes, Fallbacks, Gotchas.

---

## ⚠️ Voraussetzung: Chrome Accessibility (EINMALIG)

```bash
osascript -e 'tell application "VoiceOver" to launch' && sleep 2
osascript -e 'tell application "VoiceOver" to quit'
```
Falls keine Web-Elemente: `chrome://accessibility` → "Suppress automatic" deaktivieren.

---

## 🚪 LOGOUT (3 Methoden)

### Methode 0: Manuell über heypiggy-UI (wie User es macht)
```bash
# 1. Klick auf Profil-Icon (rechts oben, ~x=1035 y=614)
# 2. Dropdown-Menü → "Ausloggen" oder "Abmelden"
# 3. Seite wechselt zu Login-Page
```

### Methode 1: Google-Konto abmelden (accounts.google.com)
```bash
# Direkt zur Google-Logout-Seite
open "https://accounts.google.com/Logout"
sleep 3
# Klick auf "Abmelden" oder Enter
```
**Ergebnis:** Vollständig von Google abgemeldet. Alle Sessions beendet.

### Methode 2: Incognito-Fenster (frisch, keine Cookies)
```bash
open -na "Google Chrome" --args --incognito "https://heypiggy.com/?page=dashboard"
```
**Ergebnis:** Keine Cookies, keine Session → Login-Seite.

### Methode 3: Neues Chrome-Profil
```bash
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
  --user-data-dir=/tmp/fresh-profile \
  "https://heypiggy.com/?page=dashboard" &
```
**Ergebnis:** Komplett frische Umgebung.

---

## 📋 LOGIN Flow: Google OAuth auf heypiggy.com

### Schritt 1: Login-Seite aufrufen
```bash
open -na "Google Chrome" --args --incognito "https://heypiggy.com/?page=dashboard"
sleep 5
PID=$(pgrep -f "Google Chrome.app/Contents/MacOS/Google Chrome$" | head -1)
```

### Schritt 2: Google Login Button klicken
```bash
GOOGLE_IDX=$(skylight-cli list-elements --pid $PID | \
  python3 -c "import json,sys; [print(e['index']) for e in json.load(sys.stdin)['elements'] if 'Google' in (e.get('label','')or'') and e['role']=='AXLink']")
skylight-cli click --pid $PID --element-index $GOOGLE_IDX
sleep 5
```

### Schritt 3: E-Mail tippen
```bash
EMAIL_IDX=$(skylight-cli list-elements --pid $PID | python3 -c "
import json,sys
for e in json.load(sys.stdin)['elements']:
    if e['role']=='AXTextField' and 'telefon' in (e.get('label','')or'').lower() and 'AXWebArea' in (e.get('path','')):
        print(e['index']); break
")
skylight-cli type --pid $PID --element-index $EMAIL_IDX --text "email@gmail.com"
sleep 3
```

### Schritt 4: Passwort tippen
```bash
PW_IDX=$(skylight-cli list-elements --pid $PID | python3 -c "
import json,sys
for e in json.load(sys.stdin)['elements']:
    if e['role']=='AXTextField' and 'verschlüsselt' in (e.get('label','')or''):
        print(e['index']); break
")
skylight-cli type --pid $PID --element-index $PW_IDX --text "passwort"
sleep 1
```

### Schritt 5: Weiter klicken
```bash
WEITER_IDX=$(skylight-cli list-elements --pid $PID | python3 -c "
import json,sys
for e in json.load(sys.stdin)['elements']:
    if e['role']=='AXButton' and 'weiter' in (e.get('label','')or'').lower() and 'AXWebArea' in (e.get('path','')):
        print(e['index']); break
")
skylight-cli click --pid $PID --element-index $WEITER_IDX
sleep 5
# ✅ Eingeloggt auf heypiggy.com via Google OAuth
```

---

## 🌐 LOGIN: Direkt auf accounts.google.com

```bash
# Google-Login-Seite öffnen
open "https://accounts.google.com/ServiceLogin"
sleep 5
PID=$(pgrep -f "Google Chrome.app/Contents/MacOS/Google Chrome$" | head -1)

# E-Mail-Feld (input[type="email"])
skylight-cli list-elements --pid $PID | python3 -c "
import json,sys
for e in json.load(sys.stdin)['elements']:
    if e['role']=='AXTextField' and 'AXWebArea' in (e.get('path','')):
        print(f'[{e[\"index\"]}] {e.get(\"label\",\"\")[:60]}')
"

# Type Email + Enter
skylight-cli type --pid $PID --element-index EMAIL_IDX --text "email@gmail.com"
sleep 3

# Type Password + Enter
skylight-cli type --pid $PID --element-index PW_IDX --text "passwort"
sleep 3

# ✅ Eingeloggt auf Google
```

---

## 🔁 VOLLSTÄNDIGER ZYKLUS: Logout → Login

```bash
# 1. Logout
open "https://accounts.google.com/Logout"
sleep 3
skylight-cli list-elements --pid $PID | \
  python3 -c "import json,sys; [print(f'[{e[\"index\"]}] {e[\"label\"]}') for e in json.load(sys.stdin)['elements'] if e['role']=='AXButton' and 'AXWebArea' in (e.get('path',''))]"

# 2. Verify Logout: heypiggy zeigt Login-Seite
open "https://heypiggy.com/?page=dashboard"
sleep 4
# → Google Login-Symbol muss sichtbar sein

# 3. Re-Login (Schritte 2-5 von oben)
# → Google Login klicken → Email → Passwort → Weiter
```

---

## 🔑 Element-Index-Referenz

### heypiggy.com
| Element | Typ | Index (var.) | Label |
|---------|-----|-------------|-------|
| Google Login | AXLink | ~131 | "Google Login-Symbol" |
| Apple Login | AXLink | ~132 | "Apple Login-Symbol" |
| Facebook Login | AXLink | ~134 | "facebook Login-Symbol" |
| E-Mail Feld | AXTextField | ~140-150 | "E-Mail oder Telefonnummer" |
| Passwort Feld | AXTextField | variiert | "verschlüsseltes Textfeld" |
| Weiter Button | AXButton | ~99-180 | "Weiter" |
| heypiggy Logo | AXLink | ~52 | "heypiggy Logo" |
| Money Bag | AXLink | ~58 | "money bag 0.32 €" |

### accounts.google.com
| Element | Typ | Label |
|---------|-----|-------|
| E-Mail Feld | AXTextField | "E-Mail-Adresse oder Telefonnummer" |
| Passwort Feld | AXTextField | "Passwort eingeben" |
| Weiter | AXButton | "Weiter" |
| Abmelden | AXButton | "Abmelden" |

> **⚠️ Indizes ändern sich!** IMMER per `list-elements` + Label/Pfad suchen.

---

## 🛠️ Tools (NUR diese!)

| Tool | Befehl | Wofür |
|------|--------|-------|
| `skylight-cli` | `click --pid X --element-index N` | Klick (AXPress) |
| `skylight-cli` | `type --pid X --element-index N --text "..."` | Text (CGEvent Unicode) |
| `skylight-cli` | `list-elements --pid X` | Element-Tabelle |
| `skylight-cli` | `screenshot --pid X --mode raw --out f.png` | Screenshot |
| `skylight-cli` | `click --pid X --x -1 --y -1` | Primer (MUSS!) |

## ❌ NIEMALS
- `--x`/`--y` raten → Apple-Menü (0,0)
- `CGEventPostToPid` → Chrome 148 ignoriert
- `--force-renderer-accessibility` → Crasht Chrome
- `cua-driver` → ersetzt durch skylight-cli
- `osascript keystroke` → skylight-cli type ist besser
- Ohne Primer klicken

## 🧪 Fehler & Fixes
| Fehler | Ursache | Fix |
|--------|---------|-----|
| Popup schließt sofort | Zu schnell getippt | `sleep 3` nach type |
| "Konto erstellen" | Email kein Google-Konto | Andere Email |
| Keine Web-Elemente | VoiceOver fehlt | VoiceOver 1x starten/stoppen |
| type ins falsche Feld | Falscher Index | "E-Mail oder Telefonnummer" suchen |
| Klick macht nichts | Primer fehlt | `--x -1 --y -1` vor jedem Klick |

## 📁 Zusätzliche Dateien
- `states.md` — Zustandsautomat (IDLE→LOGOUT→LOGIN→DONE)
- `recovery.md` — Captcha/2FA/Timeout-Strategie
- `config.example.yaml` — Konfigurationsvorlage

## 🚨 NIE WIEDER: Die 3 eisernen Regeln

### Regel 1: NACH jedem Popup/Klick `list-elements` NEU abfragen
```bash
# ❌ FALSCH: Index von vor dem Popup verwenden
skylight-cli click --pid X --element-index 131  # Google klicken
skylight-cli type --pid X --element-index 140 --text "..."  # DIREKT tippen

# ✅ RICHTIG: Nach Popup neu scannen
skylight-cli click --pid X --element-index 131  # Google klicken
sleep 5  # ⏳ WICHTIG: Popup laden lassen!
skylight-cli list-elements --pid X  # 🔄 NEU SCANNEN
# JETZT erst den NEUEN Index für "E-Mail oder Telefonnummer" suchen
```

### Regel 2: Koordinaten-Prüfung (Apple-Menü-Schutz)
Jeder Klick MUSS `y > 30` sein. Alles darunter = Apple-Menüleiste.
```bash
# Im Agent IMMER vor Klick prüfen:
if [ $CLICK_Y -lt 30 ]; then
    echo "❌ APPLE-MENÜ! y=$CLICK_Y < 30 — NICHT klicken!" && exit 1
fi
```

### Regel 3: Element-Label exakt matchen
Google OAuth Feld heißt **"E-Mail oder Telefonnummer"** — NICHT "E-Mail" (das ist das HeyPiggy-Formular).
```python
# ❌ FALSCH: erstes "E-Mail"-Feld genommen → HeyPiggy-Formular
if 'mail' in label.lower():  # trifft beides!

# ✅ RICHTIG: exaktes Label für Google-Popup
if 'telefon' in label.lower():  # NUR Google-Feld
```

## 🧪 Test-Checkliste (vor jedem Login)
- [ ] `sleep 5` nach Google-Login-Klick (Popup braucht Zeit)
- [ ] `list-elements` NEU nach Popup
- [ ] "E-Mail oder Telefonnummer" suchen, nicht "E-Mail"
- [ ] `y > 30` prüfen (kein Apple-Menü)
- [ ] Primer `--x -1 --y -1` vor jedem Klick
