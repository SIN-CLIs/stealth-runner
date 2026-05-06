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

## ⚠️ WARNING: Missing Flags

**playstealth launch does NOT set `--force-renderer-accessibility`!**
Without this flag, cua-driver AX-Tree is EMPTY (0 children).

**playstealth launch does NOT guarantee `--remote-allow-origins=*`!**
Without this flag, CDP WebSocket connections get 403 Forbidden.

**If AX-Tree is empty or CDP is blocked**, launch Chrome manually:
```bash
open -a "Google Chrome" --args \
  --user-data-dir="/tmp/heypiggy-bot-XXXXX" \
  --remote-debugging-port=9999 \
  --remote-allow-origins=* \
  --force-renderer-accessibility \
  --no-first-run \
  'URL'
```

## Profile Pattern
`/tmp/heypiggy-bot-XXXXXXXX` → BOT Chrome (NIEMALS USER Chrome killen!)

## Warten
Nach launch: `sleep 5` warten bis Seite vollständig geladen.

## Test Log
- 2026-05-05: PID 75167, profile /tmp/heypiggy-bot-1777982953 ✅