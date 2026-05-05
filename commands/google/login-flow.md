# GOOGLE LOGIN FLOW — VERIFIED ✅ (PASSKEY v2 — 2026-05-05)

## Status
**VERIFIED** — 2026-05-05, LIVE GETESTET mit PID=78708, 8 Steps, 0 Fehler

## Phasen
```
[1] playstealth launch → Chrome (PID)
[2] list_windows → Dashboard WID
[3] get_window_state → Google Login-Symbol [54]
[4] click [54] → OAuth Popup (NEUE WID)
[5] list_windows → OAuth WID
[6] get_window_state → Email [25] + Weiter [35]
[7] set_value [25] email
[8] click [35] Weiter
[9] get_window_state → Passkey Screen, Weiter [26]
[10] click [26] Weiter (PASSKEY!) ← NICHT "Andere Option"!
[11] get_window_state → Fortfahren [66]
[12] click [66] Fortfahren
[13] get_window_state → Consent, Weiter [41]
[14] click [41] Weiter
[15] ✅ EINGELOGGT → Dashboard mit "Abmelden"/"Umfragen"
```

---

## STEP-BY-STEP (Live Execution Trace, PID=78708)

### STEP 1: Chrome starten
```bash
playstealth launch --url 'https://heypiggy.com/?page=dashboard'
# → {"pid": 78708, "profile": "/tmp/heypiggy-bot-1777985655"}
```

### STEP 2: Dashboard WID finden
```bash
sleep 5 && cua-driver call list_windows | python3 -c "
import json, sys
d = json.load(sys.stdin)
for w in d.get('windows', []):
    t = (w.get('title') or '').lower()
    h = w.get('bounds',{}).get('height',0)
    if h > 100 and 'heypiggy' in t:
        print(f'WID={w[\"window_id\"]}')
"
# → WID=57128
```

### STEP 3: Google Login-Symbol finden + klicken (AXLink!)
```bash
echo '{"pid": 78708, "window_id": 57128}' | cua-driver call get_window_state
# → [54] AXLink (Google Login-Symbol) @(731,651,132,41)

echo '{"pid": 78708, "window_id": 57128, "element_index": 54}' | cua-driver call click
# → ✅ Performed AXPress on [54] AXLink
```

### STEP 4: OAuth WID finden
```bash
sleep 4 && cua-driver call list_windows | python3 -c "
import json, sys
d = json.load(sys.stdin)
for w in d.get('windows', []):
    t = (w.get('title') or '').lower()
    if 'anmelden' in t:
        print(f'WID={w[\"window_id\"]}')
"
# → WID=57141
```

### STEP 5: Email [25] + Weiter [35]
```bash
echo '{"pid": 78708, "window_id": 57141}' | cua-driver call get_window_state
# → [25] AXTextField (E-Mail oder Telefonnummer)
# → [35] AXButton "Weiter"

echo '{"pid": 78708, "window_id": 57141, "element_index": 25, "value": "zukunftsorientierte.energie@gmail.com"}' | cua-driver call set_value
# → ✅ Set AXValue on [25] AXTextField

sleep 1 && echo '{"pid": 78708, "window_id": 57141, "element_index": 35}' | cua-driver call click
# → ✅ Performed AXPress on [35] AXButton "Weiter"
```

### STEP 6: Passkey Screen → WEITER [26] ← KRITISCH!
```bash
sleep 5 && echo '{"pid": 78708, "window_id": 57141}' | cua-driver call get_window_state
# → [26] AXButton "Weiter" @(1095,753,91,41)
# → [31] AXButton "Andere Option wählen" ← DEGRADED! NIEMALS KLICKEN!

echo '{"pid": 78708, "window_id": 57141, "element_index": 26}' | cua-driver call click
# → ✅ macOS Passkey/TouchID Dialog triggert → Account erkannt
```

### STEP 7: Fortfahren [66]
```bash
echo '{"pid": 78708, "window_id": 57141}' | cua-driver call get_window_state
# → [66] AXButton "Fortfahren" @(1090,689,94,30)
# → [63],[64] AXRadioButton (Account-Auswahl)

echo '{"pid": 78708, "window_id": 57141, "element_index": 66}' | cua-driver call click
# → ✅ Account bestätigt
```

### STEP 8: Consent Weiter [41]
```bash
echo '{"pid": 78708, "window_id": 57141}' | cua-driver call get_window_state
# → [16] zukunftsorientierte.energie@gmail.com ausgewählt
# → [41] AXButton "Weiter" @(966,753,220,40)

echo '{"pid": 78708, "window_id": 57141, "element_index": 41}' | cua-driver call click
# → ✅ LOGIN COMPLETE!
```

---

## 🔥 DEGRADIERUNG: Was FALSCH war (Session PID=75167)

### ❌ DEGRADED #1: "Andere Option wählen" beim Passkey-Screen
```bash
# FALSCH (PID=75167, WID=56885):
echo '{"pid": 75167, "window_id": 56885, "element_index": 31}' | cua-driver call click
# → "Andere Option wählen" → Keychain Popover → "Passwort eingeben"
# → Manuelles Passwort-Feld → 2FA → BLOCKIERT
# → BRICHT Passkey-Flow → 30 Minuten verschwendet!

# RICHTIG (PID=78708, WID=57141):
echo '{"pid": 78708, "window_id": 57141, "element_index": 26}' | cua-driver call click
# → "Weiter" → macOS Keychain/TouchID → Account bestätigt
# → KEIN Passwort! KEINE 2FA! 0 Fehler!
```
**Lektion**: Passkey "Weiter" = Login. "Andere Option" = ABBRUCH!

### ❌ DEGRADED #2: ZOE.jeremy2024
```
Dieses Passwort EXISTIERT NICHT! Erfunden/Halluziniert.
Richtig: ZOE.jerry2024 (wird bei Passkey gar nicht benötigt).
```

### ❌ DEGRADED #3: Keychain Auto-Fill Annahme (veraltet)
```
ALT (2026-05-04): Email → Weiter → Keychain auto-fill → Fortfahren
NEU (2026-05-05): Email → Weiter → Passkey "Weiter" → TouchID → Fortfahren
Keychain nicht nötig. Passkey ersetzt Keychain im Bot-Profil.
```

### ❌ DEGRADED #4: 2FA Block (PID=75167)
```
Session expired + falscher Flow ("Andere Option") → 2FA-Abfrage
Google will Handy-Bestätigung → manuelle Intervention nötig
RICHTIG: Passkey "Weiter" triggert KEINE 2FA!
```

---

## Element Indices (variieren → IMMER scannen!)
| Screen | Element | Index | AXRole |
|--------|---------|-------|--------|
| Dashboard | Google Login-Symbol | 54 | AXLink |
| OAuth Email | E-Mail-Feld | 25 | AXTextField |
| OAuth Email | Weiter | 35 | AXButton |
| Passkey | **Weiter** ✅ | 26 | AXButton |
| Passkey | ~~Andere Option~~ ❌ | ~~31~~ | ~~AXButton~~ |
| Account | Fortfahren | 66 | AXButton |
| Consent | Weiter | 41 | AXButton |

## /commands Referenz
| File | Typ |
|------|-----|
| `playstealth-launch.md` | Chrome Launch |
| `cua-driver-list-windows.md` | Fenster finden |
| `cua-driver-get-window-state.md` | AX-Tree lesen |
| `cua-driver-click.md` | Element klicken |
| `cua-driver-set-value.md` | Text eintragen |
| `cua-driver-find-element-index.md` | Element-Index extrahieren |
| `cua-driver-find-pid-wid.md` | PID & WID finden |
| `google-login-flow.md` | DIESE DATEI |
| `heypiggy-credentials.md` | Login Credentials |
| `kill-bot-chrome.md` | BOT Chrome killen |

## Test Log
- ✅ 2026-05-05 14:54: PID=78708 → 8 Steps, 0 Fehler, Passkey Flow
- ❌ 2026-05-05 14:50: PID=75167 → "Andere Option" → 2FA Block DEGRADED
- ✅ 2026-05-05 14:20: PASSKEY Discovery → "Weiter" statt "Andere Option"