# KILL BOT CHROME — VERIFIED ✅

## Status
**VERIFIED** — 2026-05-05

## Was es tut
Killt NUR die heypiggy-bot Chrome-Main-Prozesse. Child-Prozesse (Renderer, Helper) werden vom OS automatisch aufgeräumt. USER Chrome bleibt unberührt.

## Wann nutzen
- Neue Survey-Session starten (vorher killen)
- Registry ist inkonsistent
- Chrome hängt/antwortet nicht mehr

## Command (Python)
```python
import subprocess, re, time

r = subprocess.run(['ps', 'aux'], capture_output=True, text=True)
bot_main_pids = []
for line in r.stdout.split('\n'):
    if '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' not in line:
        continue
    if '/tmp/heypiggy-bot-' in line:
        parts = line.split()
        if len(parts) >= 2:
            try:
                bot_main_pids.append(int(parts[1]))
            except:
                pass

for pid in bot_main_pids:
    subprocess.run(['kill', str(pid)], timeout=5)

time.sleep(2)
```

## Verification
```bash
# Nach Kill: 0 heypiggy-bot main processes
ps aux | grep "/tmp/heypiggy-bot-" | grep "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" | wc -l
# → 0 (gut!)

# Registry leeren
rm -f ~/.stealth/sessions.json
```

## Banned Alternativen
- ❌ `pkill -f "heypiggy-bot"` — killt ALLE Chrome-Instanzen
- ❌ `killall Google Chrome` — killt ALLE Chrome (USER + BOT!)
- ❌ `kill <hardcoded_pid>` — PIDs ändern sich!

## SOTA Alternative
```python
from cli.modules.session_manager import SessionManager
sm = SessionManager()
sm.close_all()  # Killt + Registry geleert
```

## Test Log
- 2026-05-05: PID 74483, 74351, 74299 gekillt → 0 remaining ✅
- Registry geleert → launch() startet neues Chrome mit reused=False ✅