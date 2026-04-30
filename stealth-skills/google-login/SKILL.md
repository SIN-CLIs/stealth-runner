# stealth-skill: google-login

> **Vollständiger Google OAuth Login/Logout über heypiggy.com**
> Alle Befehle, Element-Indizes, Fallbacks, Gotchas.

---

## ⚠️ Voraussetzung: Chrome Accessibility (EINMALIG)

```bash
# VoiceOver kurz starten → Chrome aktiviert AX-Tree
osascript -e 'tell application "VoiceOver" to launch' && sleep 2
osascript -e 'tell application "VoiceOver" to quit'
# Danach: Web-Elemente dauerhaft im AX-Tree
```

Falls keine Web-Elemente: `chrome://accessibility` → "Suppress automatic" deaktivieren.

---

## 📋 Login Flow: Google OAuth auf heypiggy.com

### Schritt 1: Browser starten (mit Accessibility)

```bash
# Wichtig: KEIN --force-renderer-accessibility (crasht Chrome auf macOS 26)
playstealth-cli launch --url "https://heypiggy.com/?page=dashboard"
# ODER manuell:
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
  "https://heypiggy.com/?page=dashboard" &
```

### Schritt 2: Google Login Button klicken

```bash
PID=$(pgrep -f "Google Chrome.app/Contents/MacOS/Google Chrome$" | head -1)

# Google Login-Symbol finden (AXLink mit "Google" im Label)
GOOGLE_IDX=$(skylight-cli list-elements --pid $PID | \
  python3 -c "import json,sys; [print(e['index']) for e in json.load(sys.stdin)['elements'] if 'Google' in (e.get('label','')or'') and e['role']=='AXLink']")

# Klick (AXPress via Accessibility API)
skylight-cli click --pid $PID --element-index $GOOGLE_IDX
sleep 5  # Warten auf Google OAuth Popup
```

### Schritt 3: E-Mail-Feld finden + tippen

```bash
# Google OAuth Feld: "E-Mail oder Telefonnummer" (AXTextField)
EMAIL_IDX=$(skylight-cli list-elements --pid $PID | python3 -c "
import json,sys
for e in json.load(sys.stdin)['elements']:
    if e['role']=='AXTextField' and 'telefon' in (e.get('label','')or'').lower() and 'AXWebArea' in (e.get('path','')):
        print(e['index']); break
")

# Type Befehl (CGEvent Keyboard, Unicode, human-speed 30-150ms)
skylight-cli type --pid $PID --element-index $EMAIL_IDX --text "email@gmail.com"
sleep 3  # Google verarbeitet E-Mail (Auto-Advance)
```

### Schritt 4: Passwort-Feld finden + tippen

```bash
# Nach Google-Auto-Advance: Passwort-Feld "verschlüsseltes Textfeld"
PW_IDX=$(skylight-cli list-elements --pid $PID | python3 -c "
import json,sys
for e in json.load(sys.stdin)['elements']:
    if e['role']=='AXTextField' and 'verschlüsselt' in (e.get('label','')or''):
        print(e['index']); break
")

skylight-cli type --pid $PID --element-index $PW_IDX --text "passwort123"
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
# ✅ Eingeloggt!
```

---

## 🔑 Element-Index-Referenz (heypiggy.com)

| Element | Typ | Typischer Index | Label |
|---------|-----|-----------------|-------|
| Google Login | AXLink | ~131 | "Google Login-Symbol" |
| Apple Login | AXLink | ~132 | "Apple Login-Symbol" |
| Facebook Login | AXLink | ~134 | "facebook Login-Symbol" |
| E-Mail Feld | AXTextField | ~140-150 | "E-Mail oder Telefonnummer" |
| Passwort Feld | AXTextField | variiert | "verschlüsseltes Textfeld" |
| Weiter Button | AXButton | ~99-180 | "Weiter" |
| heypiggy Logo | AXLink | ~52 | "heypiggy Logo" |
| Money Bag | AXLink | ~58 | "money bag 0.32 €" |
| Konto erstellen | AXButton | ~168 | "Konto erstellen" |

> **⚠️ Indizes ändern sich!** IMMER per `list-elements` + Label/Pfad suchen. Nie Indizes hartcodieren.

---

## 🚪 Logout Flow

```bash
# Methode 1: Incognito-Fenster (sicherste)
open -na "Google Chrome" --args --incognito "https://heypiggy.com/?page=dashboard"

# Methode 2: Cookies löschen
osascript -e 'tell application "Google Chrome" to tell window 1 to set URL of active tab to "javascript:document.cookie.split(\";\").forEach(function(c){document.cookie=c.replace(/^ +/,\"\").replace(/=.*/,\"=;expires=\"+new Date().toUTCString()+\";path=/\");});void(0);"'

# Methode 3: Neues Chrome-Profil
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
  --user-data-dir=/tmp/fresh-profile \
  "https://heypiggy.com/?page=dashboard" &
```

---

## 🛠️ Verwendete Tools (NUR diese!)

| Tool | Befehl | Wofür |
|------|--------|-------|
| `skylight-cli` | `click --pid X --element-index N` | Klick (AXPress) |
| `skylight-cli` | `type --pid X --element-index N --text "..."` | Text (CGEvent Unicode) |
| `skylight-cli` | `list-elements --pid X` | Element-Tabelle |
| `skylight-cli` | `screenshot --pid X --mode raw --out file.png` | Screenshot |
| `skylight-cli` | `get-window-state --pid X` | Fenster-Titel |
| `skylight-cli` | `click --pid X --x -1 --y -1` | Primer (MUSS vor jedem Klick!) |

---

## ❌ NIEMALS

- `--x`/`--y` Koordinaten raten → Apple-Menü (0,0)
- `CGEventPostToPid` → Chrome 148 ignoriert
- `--force-renderer-accessibility` → Crasht Chrome auf macOS 26
- `cua-driver` → Ersetzt durch skylight-cli
- `osascript keystroke` → skylight-cli type ist besser
- Ohne Primer-Klick klicken → User-Activation-Gate

---

## 🧪 Bekannte Fehler & Fixes

| Fehler | Ursache | Fix |
|--------|---------|-----|
| Google-Popup schließt sofort | Email zu schnell getippt | `sleep 3` nach type, Google braucht Zeit |
| "Konto erstellen" statt Passwort | Email ist kein Google-Konto | Andere Email verwenden |
| Keine Web-Elemente | VoiceOver-Trick fehlt | VoiceOver 1x starten/stoppen |
| type geht ins falsche Feld | Falscher Index | Label "E-Mail oder Telefonnummer" suchen, nicht "E-Mail" |
| Klick macht nichts | Primer fehlt | `--x -1 --y -1` vor jedem Klick |

---

## 🔗 Abhängigkeiten in der Stealth Quad

```
playstealth-cli (Browser starten)
    ↓
skylight-cli (Klick + Type)
    ↓
unmask-cli (Stealth prüfen)
    ↓
stealth-runner (Orchestriert alles)
```
