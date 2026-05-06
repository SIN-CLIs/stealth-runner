| 2026-05-05 | CaptchaSolver: Slide-Captcha 8/8 via cua-driver drag | [cli/modules/captcha_solver.py](cli/modules/captcha_solver.py) |
| 2026-05-05 | Koordinaten-Bug: dynamisch statt hardcoded Window-Position | [commands/captcha/solve-slide.md](commands/captcha/solve-slide.md) |
| 2026-05-05 | pixtral-large: Text-Captcha QXem34 korrekt gelesen | [commands/captcha/solve-text.md](commands/captcha/solve-text.md) |

# successful.md – Erfolgreich implementierte Features & Fixes

## ✅ 2026-05-03 – Word-Boundary Label Fix

**Erfolg**: `find_by_label` nutzt jetzt `\b` word-boundary regex statt Substring.
"Weiter" matched nicht mehr "Weitere Informationen" → Google Chrome-Hilfe Redirect verhindert.

**Betroffene Module:** `skylight_main.find_by_label()`, `consent_screen._find_element()`, `google_email._find_in_elements()`, `cua_touch.wait_for_element()`

---

## ✅ 2026-05-02 – cua-driver Popup-Interaktion (DURCHBRUCH!)
**Erfolg**: Google OAuth Login VOLLSTÄNDIG automatisiert via `cua-driver` Popup-Steuerung.
DYNAMIC_PID, Checkboxen, Radio-Buttons, Textfelder.

## ✅ 2026-05-01 – Pre-existing Bugfixes (5 Stück)
- `Path` Import in `skylight.py`
- `asyncio.get_event_loop()` → `new_event_loop()` Python 3.14
- `playstealth --json` Argument-Reihenfolge
- `screenshot()` Aufruf in `stealth_executor.py`
- `step.py` ModuleNotFoundError (__init__.py fehlte)

---

## ✅ 2026-05-05 — CUA-ONLY GOOGLE LOGIN VOLLSTÄNDIG (DYNAMIC_PID)

**Erfolg**: Vollständiger 6-Step Login via `cua-driver` CLI — `playstealth launch` → Dashboard eingeloggt!

### Flow dokumentiert:
```bash
Manueller Chrome-Launch --remote-debugging-port=9999 → PID=DYNAMIC, WID 56640
click [54] Google Login-Symbol → WID 56658 Google OAuth
set_value [25] Email → click [35] Weiter
→ Keychain Auto-Fill! → "Jeremy Schulze" Konto
click [62] Fortfahren → click [41] Weiter
→ Login Complete! Dashboard zeigt "Umfragen", "Auszahlung", "Abmelden"
```

### Keychain Auto-Fill Discovery:
- Nach Email + "Weiter" → Keychain füllt Credentials automatisch aus
- KEIN Passwort-Feld nötig wenn Keychain aktiv
- → NUR "Fortfahren" + final "Weiter" klicken

### Neue Dateien (MIT EXTENSIVEN KOMMENTAREN):
- `cli/modules/auto_google_login.py` → 463 Zeilen, 6-Step CUA-ONLY
- `app/flows/learning/survey_heypiggy.py` → 416 Zeilen, auto_google_login Import
- `run_survey.py` → 110 Zeilen, Single Entry Point

### Gelöscht:
- `cli/modules/heypiggy_login_box.py` → ersetzt durch auto_google_login.py

### BOT Chrome PIDs (LIVE):
| PID | Profile | Status |
|-----|---------|--------|
| 71104 | heypiggy-bot-1777981361 | AKTUELL |
| 70293 | heypiggy-bot-1777981087 | geschlossen |
| 68317 | heypiggy-bot-1777979455 | geschlossen |
