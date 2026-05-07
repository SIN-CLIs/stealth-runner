# Issue #1: Login-Loop Failure — 0 Surveys seit Tagen (P0-Kritisch)

> **Status**: OPEN  
> **Severity**: 🔴 P0 — Blockiert ALLE Survey-Runs  
> **Reporter**: Automated Analysis (STATE.md)  
> **Erstellt**: 2026-05-08 00:20 UTC  
> **Betroffene Dateien**: `survey-cli/survey.py`, `cli/modules/auto_google_login.py`, `src/stealth_survey/survey_agent.py`

---

## Problem-Beschreibung

**Symptom**: Watch-Loop (`cmd_watch()` in `survey-cli/survey.py`) wiederholt endlos:
```
NEUE TAB! Aber NICHT eingeloggt! Login first:
```

**Impact**: `surveys_completed: 0` in `daemon_state.json` seit 07. Mai 06:53.

**Daten** (aus `~/.stealth/intents.jsonl`, letzte 20 Einträge):
```json
{"type": "intent_start", "intent_id": "88b023317b9a", "goal": "\n\n\nNEUE TAB! Aber NICHT eingeloggt! Login first:\n\n", "status": "pending"}
{"type": "intent_resolved", "intent_id": "88b023317b9a", "verdict": "failed", "exit_code": 1, "success": false}
```
→ **100% Failure Rate**, identisches Pattern.

---

## Root-Cause-Analyse

### Hypothese 1: Chrome Accessibility nicht aktiv
**Beweis**: `ensure_accessibility()` in `cmd_watch()` gibt Warnung aus aber fährt fort.
```python
if not ensure_accessibility(port=args.port):
    print("[WATCH] Accessibility not available — cua-driver login will fail")
    print("[WATCH] Continuing with CDP-only mode...")  # ❌ Fährt trotzdem fort!
```
**Impact**: cua-driver findet keine Elemente → Login schlägt fehl.

### Hypothese 2: cua-driver Daemon nicht laufend
**Beweis**: `start_cua_daemon()` wird aufgerufen aber nicht verifiziert ob Daemon läuft.
```python
from survey.accessibility import ensure_accessibility, start_cua_daemon
start_cua_daemon()  # ❌ Kein Check ob erfolgreich!
```

### Hypothese 3: Google OAuth Popup nicht erkannt
**Beweis**: `find_dashboard_ws()` sucht Dashboard-Tab, aber OAuth-Tab ist "Anmelden - Google".
→ `find_dashboard_ws` findet NICHTS oder falschen Tab.

### Hypothese 4: Keychain Auto-Fill nicht aktiv
**Beweis**: `auto_google_login.py` erwartet Keychain Auto-Fill ("Fortfahren" Button).
→ Wenn Keychain deaktiviert oder neu, gibt es KEIN "Fortfahren" sondern Passwort-Feld.
→ `_find_idx(tree, "fortfahren", ["AXButton"])` gibt None zurück.

---

## Reproduktionsschritte

1. `python3 survey-cli/survey.py watch --max 1`
2. Beobachte Output:
   ```
   [WATCH] Checking login state...
   [WATCH] Not logged in — running cua-driver Google OAuth login...
   [WATCH] ❌ Login failed: google_login_button_not_found — retrying later
   ```
3. Oder: Login scheint zu funktionieren aber Dashboard zeigt "Nicht eingeloggt"

---

## Akzeptanzkriterien (Definition of Done)

- [ ] Login-Flow schlägt nicht mehr fehl (5/5 erfolgreiche Logins in Tests)
- [ ] Wenn Chrome nicht läuft: Automatischer Start mit korrekten Flags
- [ ] Wenn Accessibility fehlt: Fehlermeldung + STOP (nicht "Continuing...")
- [ ] Wenn Daemon nicht läuft: Automatischer Start + Verifikation
- [ ] OAuth Popup wird korrekt erkannt (neuer Tab, nicht Dashboard)
- [ ] Keychain und Non-Keychain Path beide unterstützt
- [ ] Integrationstest: `test_watch_login_success` muss passen

---

## Vorgeschlagener Fix

### Fix 1: Hard-Stop bei fehlender Accessibility
```python
if not ensure_accessibility(port=args.port):
    print("[WATCH] ❌ CRITICAL: Accessibility not available")
    print("[WATCH] Chrome MUST be started with --force-renderer-accessibility")
    log_session("watch_stop", "error", {"reason": "accessibility_unavailable"})
    return  # ❌ STOP, nicht weiterfahren!
```

### Fix 2: Daemon Health-Check
```python
if not start_cua_daemon():
    print("[WATCH] ❌ CRITICAL: cua-driver Daemon failed to start")
    log_session("watch_stop", "error", {"reason": "daemon_start_failed"})
    return
```

### Fix 3: OAuth Tab Detection
```python
# Nicht nur Dashboard suchen, sondern auch OAuth Tabs
oauth_ws = find_oauth_ws(args.port)  # Sucht "Anmelden", "Google", "accounts"
if oauth_ws:
    # OAuth läuft bereits → Fortfahren statt neu starten
```

### Fix 4: Keychain Fallback
```python
fortsetzen_idx = _find_idx(tree, "fortfahren", ["AXButton"])
if fortsetzen_idx is None:
    # Fallback: Passwort-Feld (wenn Keychain NICHT aktiv)
    passwort_idx = _find_idx(tree, "passwort", ["AXTextField"])
    if passwort_idx:
        _type(pid, wid, passwort_idx, os.getenv("GOOGLE_PASSWORD"))
        weiter_idx = _find_idx(tree, "weiter", ["AXButton"])
        _click(pid, wid, weiter_idx)
```

---

## Zusammenhängende Issues
- #2: Daemon State Management
- #3: Chrome Startup Flags
- #4: Session File Corruption (2 Byte Files)

---

**Nächster Schritt**: Fix implementieren + Integrationstest schreiben.

*Letzte Aktualisierung: 2026-05-08 00:20 UTC*
