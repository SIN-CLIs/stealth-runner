# FIND BOT PIDS — VERIFIED ✅

## Status
**VERIFIED** — 2026-05-05

## Was es tut
Findet alle heypiggy-bot Chrome-Main-Prozesse (NICHT Children/Helpers) mit Profil-Pfad.

## Command (Python)
```python
import subprocess, re

r = subprocess.run(['ps', 'aux'], capture_output=True, text=True)
for line in r.stdout.split('\n'):
    if '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' not in line:
        continue
    if '/tmp/heypiggy-bot-' in line:
        parts = line.split()
        if len(parts) >= 2:
            try:
                pid = int(parts[1])
            except:
                continue
        m = re.search(r'--user-data-dir=([^\s]+)', line)
        profile_dir = m.group(1) if m else None
        print(f"PID={pid} profile={profile_dir}")
```

## Command (Bash)
```bash
ps aux | grep "/tmp/heypiggy-bot-" | grep "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
```

## Output
```
simoneschulze 74483 ... /Applications/Google Chrome.app/Contents/MacOS/Google Chrome --user-data-dir=/tmp/heypiggy-bot-1777982535
simoneschulze 74351 ... /Applications/Google Chrome.app/Contents/MacOS/Google Chrome --user-data-dir=/tmp/heypiggy-bot-1777982093
```

## Filter-Logik
| Pattern | Matched | NOT Matched |
|---------|---------|-------------|
| `/Contents/MacOS/Google Chrome` | Main-Prozess | Helper/Renderer |
| `/tmp/heypiggy-bot-` | BOT Chrome | USER Chrome |

## Test Log
- 2026-05-05: 1 BOT gefunden (PID 74483, profile heypiggy-bot-1777982535) ✅
- 2026-05-05: 3 BOT gefunden (PID 71104, 72721, 72639) ✅