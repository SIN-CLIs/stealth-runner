# SESSION MANAGER LAUNCH — VERIFIED ✅

## Status
**VERIFIED** — 2026-05-05

## Was es tut
Startet oder reused Chrome-Session via SessionManager Registry.
- Registry leer + kein Chrome → launcht NEUES Chrome
- Registry hat Session + Chrome läuft → REUSE (kein neuer Start)
- Kein Registry aber Chrome läuft → findet laufendes Chrome via Process-Scan

## Command
```python
from cli.modules.session_manager import SessionManager

sm = SessionManager()
result = sm.launch("heypiggy", "https://heypiggy.com/?page=dashboard")
# Returns: {"status": "ok", "pid": X, "wid": Y, "reused": bool}
```

## Return Values
| status | reused | Bedeutung |
|--------|--------|-----------|
| ok | false | Neues Chrome gestartet |
| ok | true | Existierendes Chrome reused |
| error | - | Launch fehlgeschlagen |

## SOTA REUSE LOGIC (3-Step)
```
1. Registry check  → wenn session active + pid alive → REUSE
2. Process scan    → finde heypiggy-bot-* Chrome → REUSE
3. Kein existiert  → playstealth launch → NEW
```

## Warum SOTA
- **Vorher**: Immer `playstealth launch` → neue Chrome-Instanz → Element-Indizes ändern
- **Jetzt**: SessionManager prüft Registry + Process-Scan → reused bestehendes Chrome
- **Vorteil**: Kein neues Fenster, Login-State bleibt erhalten, schneller

## Registry File
`~/.stealth/sessions.json`
```json
{
  "heypiggy": {
    "pid": 74483,
    "profile_dir": "/tmp/heypiggy-bot-1777982535",
    "wid": 56728,
    "url": "https://heypiggy.com/?page=dashboard",
    "status": "active",
    "created_at": 1746...,
    "last_seen": 1746...
  }
}
```

## CLI Usage
```bash
python3 cli/modules/session_manager.py scan      # Show running processes
python3 cli/modules/session_manager.py list      # Show registry
python3 cli/modules/session_manager.py reconcile # Remove stale entries
python3 cli/modules/session_manager.py close-all # Kill all + clear registry
python3 cli/modules/session_manager.py launch heypiggy "https://..."
```

## Test Log
- 2026-05-05: Fresh launch → reused=False, PID 74483, profile frisch ✅
- 2026-05-05: Second call → reused=True, PID 74483 from registry ✅
- 2026-05-05: Close → PID 74483 killed, registry cleared ✅