# start-heypiggy — Chrome starten + HeyPiggy Dashboard (VERIFIED 2026-05-10)

## Status
✅ VERIFIED 2026-05-10 — Login funktioniert, 12 Surveys, Balance €2.75

## Command
```bash
python3 survey-cli/commands/start_heypiggy.py
```

## Workflow (5 Steps)
```
1. kill_bot_chrome() — killt NUR bot Chrome (Port 9999, /tmp/heypiggy profile)
2. cp -R "Profile 901 (Jeremy)" → /tmp/heypiggy-new-TIMESTAMP
3. Chrome starten (KEIN URL argument!)
4. Target.createTarget("about:blank") — neue Tab erstellen
5. Network.enable → Network.setCookies (7 HeyPiggy Cookies)
6. Page.navigate → HeyPiggy Dashboard
```

## Was funktioniert
- Profile 901 (Jeremy) Kopie → Chrome hat entschluesselte Session-Cookies
- Tab-Erstellung via CDP Target.createTarget (NICHT HTTP API)
- Network.setCookies auf about:blank Tab vor Navigation
- Dashboard zeigt "Abmelden" + Balance €2.75 + 12 Surveys

## Profile 901 vs Cookie-Injection
| Methode | Funktioniert? | Warum |
|---------|--------------|-------|
| Profile 901 Kopie (KEINE injection) | ✅ JA | Profile 901 hat entschluesselte Cookies |
| Frisches /tmp/ Profil (ohne Cookies) | ❌ NEIN | Keine Session → Login-page |
| Cookie-Injection auf about:blank | ⚠️ FAIL | Network.setCookies returns success=false |

**Fazit:** Profile 901 Kopie allein reicht. Keine separate Cookie-Injection noetig.

## KRITISCHE FLAGS (müssen IMMER gesetzt sein)
```bash
--remote-debugging-port=9999        # CDP Port
--remote-allow-origins=*            # MIT Quotes! Sonst 403
--force-renderer-accessibility      # Accessibility fuer CUA
--no-first-run                      # Kein First-Run Dialog
--user-data-dir=/tmp/heypiggy-new-*  # Profil-Kopie
```

## BANNED
❌ Chrome mit Dashboard URL als Argument starten (Cookies noch nicht injiziert)
❌ pkill -f "Google Chrome" (tötet USER Chrome!)
❌ playstealth launch (setzt nicht --force-renderer-accessibility)
❌ webauto-nodriver

## Return Value
```python
{
    "status": "ok" | "error",
    "tab_ws": "ws://127.0.0.1:9999/devtools/page/...",
    "target_id": "D427371491EFBA6BB55E...",
    "logged_in": True,
    "balance": 2.75,
    "profile_dir": "/tmp/heypiggy-new-1778405280"
}
```

## Integration in FastAPI
```python
from survey_cli.commands.start_heypiggy import main as start_heypiggy
result = start_heypiggy()
if result["status"] == "ok":
    dashboard_ws = result["tab_ws"]
    balance = result["balance"]
```

## History
- 2026-05-10: Erstellt + VERIFIED (1x Erfolg, 0x Fehler)
  - Login: YES
  - Balance: €2.75
  - Surveys: 12
  - Profile 901 Kopie allein reicht (keine Cookie-Injection noetig)