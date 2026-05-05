# BANNED: Hardcoded PIDs ❌

## Status
**BANNED** — 2026-05-05

## Warum verboten
PIDs sind **IMMER dynamisch** — sie ändern sich bei jedem Chrome-Start.

## Warum es kaputt ist
Beispiel aus alter Doku:
```
PID 71104 = heypiggy-bot-1777981361 (AKTUELLER BOT)
PID 70293 = heypiggy-bot-1777981087 (geschlossen)
PID 68317 = heypiggy-bot-1777979455 (geschlossen)
```

Beim nächsten `playstealth launch`:
- PID 71104 → existiert NICHT mehr
- Neues PID = ZUFÄLLIG (z.B. 74483, 75201, etc.)

Hardcoded PIDs in Code/Doku → **verwaiste References**, Code-Checks die ins Leere greifen.

## Korrekte Alternative
→ `/commands/find-bot-pids.md` — dynamisches Scannen via `ps aux | grep heypiggy-bot`

```python
import subprocess, re

r = subprocess.run(['ps', 'aux'], capture_output=True, text=True)
for line in r.stdout.split('\n'):
    if '/tmp/heypiggy-bot-' in line:
        m = re.search(r'--user-data-dir=([^\s]+)', line)
        profile_dir = m.group(1) if m else None
        pid = int(line.split()[1])
        print(f"PID={pid} profile={profile_dir}")
```

## REGEL
- ❌ Niemals PIDs hardcodieren
- ❌ Niemals `kill 71104` schreiben
- ✅ Immer via Process-Scan dynamisch finden
- ✅ SessionManager Registry nutzen