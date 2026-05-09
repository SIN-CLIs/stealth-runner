

## ❌ FATAL: USER Chrome vs BOT Chrome NIEMALS VERWECHSELN — 2026-05-05
- **Regel:** NUR Chrome mit `--user-data-dir=/tmp/chrome-instance-B` ist BOT
- **BOT Chrome:** PID=DYNAMIC, `~/tmp/chrome-instance-B` → CUA-Interaktion ERLAUBT
- **USER Chrome:** PID=DYNAMIC → NIEMALS TOUCHEN, NIEMALS KILLEN
- **Check:** `ps aux | grep "user-data-dir"` um Boot vs User zu unterscheiden
- **Symptom:** Bei mehreren Chrome-Instanzen: IMMER prüfen ob user-data-dir `heypiggy-bot-` enthält

## ❌ CORE PROBLEM: Google OAuth Popup AX-Tree leer — 2026-05-05
- **Symptom:** WID 56475 hat 0 Web-Content im AX-Tree (nur Chrome UI)
- **Ursache:** Google OAuth iframe/popup exposed KEINE AXTextField/AXButton
- **Dashboard (WID 56451):** 675 elements → [56] AXLink (Google Login-Symbol) ✅
- **Login Popup (WID 56475):** 39 elements → NUR Chrome UI (Toolbar, MenuBar)
- **Lösung:** Nach Klick element 56 → 5s warten → list_windows → NEUE WID suchen
- **Alternative:** `playstealth launch --url 'https://accounts.google.com/'` direkt

## ✅ LOGIN FIX — 2026-05-05T13:17:12.476681

### Fehlerkette (was ALLES falsch war)
1. `list_windows` returns `{"windows": [...]}` nicht `[...]`
2. Windows haben `bounds` nicht `frame`
3. Kein `depth`-Feld in cua-driver Output
4. `playstealth launch` gibt mehrere JSON-Zeilen zurück
5. Google-Login-Button ist AXLink (nicht AXButton)
6. `click()` erwartet `" Performed "` aber cua-driver returned `"✅ Performed AXPress"`
7. Google-Login öffnet POPUP mit NEUER WID — alter Code blieb auf Heypiggy-WID
8. `type_text()` suchte `AXTextField` + "passwort" aber Mac-Keychain hat anderes Label
9. devjerro@gmail.com statt zukunftsorientierte.energie@gmail.com

### Fixes
1. Parse `windows.get("windows", [])`
2. Verwende `bounds` statt `frame`
3. Keine depth-Prüfung mehr
4. Parse alle JSON-Zeilen von playstealth
5. Suche AXButton + AXLink
6. Checke `r.get("stdout","") and " " in r.get("stdout","")` 
7. Nach Step 1: `_find_wid(["google","anmelden","sign","accounts"])`
8. Nach Step 5: `_find_wid(["heypiggy","dashboard","guthaben"])`
9. zukunftsorientierte.energie@gmail.com

### Tools die vergessen wurden
- **ax-graph** (SIN-CLIs) — Swift AX-Indexer, könnte WID-Findung beschleunigen
- **cua-touch MCP** — hat element_index Lookup

## ✅ CUA-ONLY LOGIN VOLLSTÄNDIG — 2026-05-05

### Funktionale Commands:
```bash
# Chrome starten
playstealth launch --url 'https://heypiggy.com/?page=dashboard'
# → PID=24378, profile=~/tmp/chrome-instance-B (Port 9224)

# Windows finden
cua-driver call list_windows
# → filter: height>100 + is_on_screen + "chrome" in app_name

# AX-Tree lesen
echo '{"pid": X, "window_id": Y}' | cua-driver call get_window_state > /tmp/tree.json

# Login Flow:
# 1. [54] AXLink (Google Login-Symbol) → Dashboard WID
# 2. [27] AXTextField (E-Mail oder Telefonnummer) → set_value
# 3. [37] AXButton "Weiter"
# 4. Keychain Auto-Fill → Konto-Auswahl "Jeremy Schulze"
# 5. [62] AXButton "Fortfahren"
# 6. [41] AXButton "Weiter"
# → Login complete, Dashboard zeigt "Umfragen" + "Auszahlung"
```

### Keychain Auto-Fill Discovery:
- Email eintragen → "Weiter" → Keychain füllt automatisch aus
- "Jeremy Schulze" Konto vorausgewählt → "Fortfahren" klicken
- → NUR NOCH EIN "Weiter" (element 41) → Login complete!
- KEIN PASSWORD FIELD nötig wenn Keychain aktiv

### NEUE AUTO-GOOGLE-LOGIN Datei erstellen:
- Path: cli/modules/auto_google_login.py (NEUER NAME!)
- 6-Step CUA-ONLY: launch → list_windows → click [54] → set_value [27] → click [37] → wait → click [62] → click [41]

## ✅ CUA-ONLY LOGIN COMPLETE — 2026-05-05 13:50+

### Login Flow (LIVE GETESTET, PID=24378 (aktuell)):
```bash
# Shell Commands exakt in dieser Reihenfolge:

# STEP 1: Chrome starten
playstealth launch --url 'https://heypiggy.com/?page=dashboard'
→ PID=24378 (aktuell), profile=~/tmp/chrome-instance-B

# STEP 2: Dashboard WID finden
cua-driver call list_windows | python3 -c "..."
→ WID=DYNAMIC PID=DYNAMIC, Title=HeyPiggy Dashboard

# STEP 3: get_window_state → Google Login-Symbol finden
echo '{"pid": 24378, "window_id": DYNAMIC}' | cua-driver call get_window_state > /tmp/bot_tree.json
→ [54] AXLink (Google Login-Symbol) @(731,651,132,41)

# STEP 4: Google Login klicken
echo '{"pid": 24378, "window_id": DYNAMIC, "element_index": 54}' | cua-driver call click
→ ✅ Performed AXPress on [54] AXLink

# STEP 5: Wait 5s → list_windows → NEUE WID
sleep 5 && cua-driver call list_windows
→ WID=DYNAMIC PID=DYNAMIC, Title="Anmelden – Google Konten"

# STEP 6: get_window_state → Email-Feld finden
echo '{"pid": 24378, "window_id": 56658}' | cua-driver call get_window_state
→ [25] AXTextField (E-Mail oder Telefonnummer) @(735,549,450,54)
→ [35] AXButton "Weiter" @(1095,706,91,40)

# STEP 7: Email eintragen
echo '{"pid": 24378, "window_id": 56658, "element_index": 25, "value": "zukunftsorientierte.energie@gmail.com"}' | cua-driver call set_value
→ ✅ Set AXValue on [25] AXTextField

# STEP 8: Weiter klicken
echo '{"pid": 24378, "window_id": 56658, "element_index": 35}' | cua-driver call click
→ ✅ Performed AXPress on [35] AXButton "Weiter"

# STEP 9: Wait 5s → Keychain Auto-Fill → Konto-Auswahl
sleep 5 && cua-driver call list_windows
→ WID=DYNAMIC PID=DYNAMIC, Title="Jeremy Schulze" (Keychain!)

# STEP 10: get_window_state → Fortfahren finden
echo '{"pid": 24378, "window_id": 56658}' | cua-driver call get_window_state
→ [62] AXButton "Fortfahren" @(1090,689,94,30)

# STEP 11: Fortfahren klicken
echo '{"pid": 24378, "window_id": 56658, "element_index": 62}' | cua-driver call click
→ ✅ Performed AXPress on [62]

# STEP 12: Wait 5s → list_windows → Final Weiter
sleep 5 && cua-driver call list_windows
→ WID=DYNAMIC PID=DYNAMIC, Title="Anmelden – Google Konten"

# STEP 13: get_window_state → Final Weiter finden
echo '{"pid": 24378, "window_id": 56658}' | cua-driver call get_window_state
→ [41] AXButton "Weiter" @(966,786,220,40)

# STEP 14: Final Weiter klicken
echo '{"pid": 24378, "window_id": 56658, "element_index": 41}' | cua-driver call click
→ ✅ Performed AXPress on [41]

# STEP 15: Wait 5s → Login Complete!
sleep 5 && cua-driver call list_windows
→ WID=56658 GESCHWUNDEN!
→ WID=DYNAMIC PID=DYNAMIC Dashboard zeigt EINGELOGGT:
   [49] AXLink (Umfragen)
   [52] AXLink (Auszahlung)
   [61] AXLink (Abmelden)
```

### Neue Dateien:
- cli/modules/auto_google_login.py → 6-Step CUA-ONLY Login (ERSETZT heypiggy_login_box.py!)
- app/flows/learning/survey_heypiggy.py → Survey Flow mit auto_google_login Import

### Keychain Auto-Fill Discovery:
- Nach Email + "Weiter" → Keychain füllt automatisch aus
- KEIN Passwort nötig wenn Keychain Credentials gespeichert
- → "Fortfahren" klicken + final "Weiter" = Login Complete

### Element-Index Map (PID=24378 (aktuell)):
| Step | Element | Index | AXRole |
|------|---------|-------|--------|
| 3 | Google Login-Symbol | 54 | AXLink |
| 6 | Email-Feld | 25 | AXTextField |
| 6 | Weiter | 35 | AXButton |
| 10 | Fortfahren | 62 | AXButton |
| 13 | Weiter (Final) | 41 | AXButton |

### BOT Chrome PIDs (LIVE):
| PID | Profile | Status |
|-----|---------|--------|
| 24378 | ~/tmp/chrome-instance-B (Profil 902) | AKTUELL ✅ (Port 9224) |
| — | — | Alte Instanzen gelöscht |
| — | — | Alte Instanzen gelöscht |

### REGELN (NIEMALS BRECHEN):
1. list_windows → {"windows": [...]} NICHT Array!
2. bounds NICHT frame
3. Google Login = AXLink NICHT AXButton
4. click() → "performed" in response
5. OAuth öffnet NEUE WID → nach Klick neu suchen
6. Keychain Auto-Fill → "Fortfahren" + final "Weiter"
7. NUR heypiggy-bot-* Profile → USER Chrome NIEMALS TOUCHEN
