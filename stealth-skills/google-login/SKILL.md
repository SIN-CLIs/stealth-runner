# stealth-skill: google-login

> **Vollständiger Google OAuth Login — heypiggy.com via skylight-cli + playstealth**
> NUR skylight-cli. KEIN **skylight-cli**. KEIN osascript. KEIN Nutzer-Chrome.

---

## 🚀 Chrome starten (isoliert, KEIN Nutzer-Chrome)
```bash
playstealth launch --url 'https://heypiggy.com/?page=dashboard'
# → {"pid": 97228, "status": "ok"}
PID=97228
```

## 📋 LOGIN Flow

### Schritt 1: Google Login Button klicken
```bash
GOOGLE_IDX=$(skylight-cli list-elements --pid $PID | \
  python3 -c "import json,sys; [print(e['index']) for e in json.load(sys.stdin)['elements'] if 'google' in (e.get('label','')or'').lower() and e['role']=='AXLink']")
skylight-cli click --pid $PID --element-index $GOOGLE_IDX
sleep 5
```

### Schritt 2: E-Mail eingeben
```bash
EMAIL_IDX=$(skylight-cli list-elements --pid $PID | python3 -c "
import json,sys
for e in json.load(sys.stdin)['elements']:
    if e['role']=='AXTextField' and 'telefon' in (e.get('label','')or'').lower():
        print(e['index']); break
")
skylight-cli type --pid $PID --element-index $EMAIL_IDX --text "EMAIL (ENTFERNT – siehe profiles/)"
sleep 3
```

### Schritt 3: Weiter klicken
```bash
WEITER=$(skylight-cli list-elements --pid $PID | python3 -c "
import json,sys
for e in json.load(sys.stdin)['elements']:
    if e['role']=='AXButton' and 'weiter' in (e.get('label','')or'').lower():
        print(e['index']); break
")
skylight-cli click --pid $PID --element-index $WEITER
sleep 5
```

### Schritt 4: Passwort eingeben
```bash
PW_IDX=$(skylight-cli list-elements --pid $PID | python3 -c "
import json,sys
for e in json.load(sys.stdin)['elements']:
    label = (e.get('label','')or'').lower()
    if e['role']=='AXTextField' and any(k in label for k in ['passwort','password','verschlüsselt']):
        print(e['index']); break
")
skylight-cli type --pid $PID --element-index $PW_IDX --text "ZOE.jerry2024"
sleep 1
```

### Schritt 5: Weiter nach Passwort
```bash
PW_WEITER=$(skylight-cli list-elements --pid $PID | python3 -c "
import json,sys
for e in json.load(sys.stdin)['elements']:
    if e['role']=='AXButton' and 'weiter' in (e.get('label','')or'').lower():
        print(e['index']); break
")
skylight-cli click --pid $PID --element-index $PW_WEITER
sleep 5
```

## 🛠️ Tools (NUR diese!)
| Tool | Befehl |
|------|--------|
| skylight-cli | `click --pid X --element-index N` |
| skylight-cli | `type --pid X --element-index N --text "..."` |
| skylight-cli | `list-elements --pid X` |
| skylight-cli | `screenshot --pid X --mode som --out f.png` |
| playstealth | `launch --url 'URL'` |

## ❌ NIEMALS
- **skylight-cli** MCP → BANNED
- `--x`/`--y` raten → Apple-Menü (0,0)
- `osascript` oder `open` → manipuliert Nutzer-Chrome
- `**playstealth launch (isolierte PID)**"` → könnte Nutzer-PID greifen
- Ohne `sleep 5` nach Popup-Klick

## 🚨 Die 3 eisernen Regeln
1. **NACH jedem Popup `list-elements` NEU abfragen** (Indizes ändern sich!)
2. **Koordinaten-Prüfung**: y > 30 (kein Apple-Menü)
3. **Label exakt matchen**: "E-Mail oder Telefonnummer" NICHT nur "E-Mail"
