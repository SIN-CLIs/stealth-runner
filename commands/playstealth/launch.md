# PLAYSTEALTH LAUNCH — VERIFIED ✅

## Status
**VERIFIED** — 2026-05-05

## Was es tut
Startet isolierte Chrome-Instanz mit eigenem Profil für HeyPiggy Bot.

## Command
```bash
playstealth launch --url 'https://heypiggy.com/?page=dashboard'
```

## Output (JSON multiline)
```json
{"pid": 75167, "url": "https://heypiggy.com/?page=dashboard", "status": "ok", "cdp_port": 58651, "profile": "/tmp/heypiggy-bot-1777982953"}
```

## Parse Output
```python
import subprocess, json
r = subprocess.run(["playstealth", "launch", "--url", url], capture_output=True, text=True)
for line in r.stdout.strip().split("\n"):
    try:
        d = json.loads(line)
        if d.get("pid"):
            pid = d["pid"]
            profile = d.get("profile", "")
            break
    except:
        pass
```

## Profile Pattern
`/tmp/heypiggy-bot-XXXXXXXX` → BOT Chrome (NIEMALS USER Chrome killen!)

## Warten
Nach launch: `sleep 5` warten bis Seite vollständig geladen.

## Test Log
- 2026-05-05: PID 75167, profile /tmp/heypiggy-bot-1777982953 ✅