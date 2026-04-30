# AGENTS.md — Agent Operating Manual for stealth-runner

> **Read this file COMPLETELY before executing any action.**
> Every violation makes the survey immediately detectable.

## 1. What Is The stealth-runner?
The `stealth-runner` controls a masked Chrome browser **exclusively** through three CLI tools:

| Tool | Purpose |
|------|---------|
| `playstealth-cli` | Launch browser, mask fingerprint, rotate profiles |
| `skylight-cli` | Screenshots (SoM), invisible clicks, text input, scroll, drag |
| `unmask-cli` | Stealth verification after every action |

## 2. State Machine
```
IDLE → LAUNCH_BROWSER → WAIT_READY → CAPTURE → VISION → EXECUTE → VERIFY → (loop) → DONE
```

## 3. How To Start
```bash
python main.py "https://heypiggy.com/?page=dashboard"
```

## 4. Crash / Resume
Runner saves checkpoint after every VERIFY. Crash → re-run same command → auto-resumes.

## 5. ABSOLUTELY FORBIDDEN
- ❌ `cua-driver` · ❌ `open -na Chrome` · ❌ Clicking `AXStaticText`
- ❌ Blind clicking without Vision · ❌ CDP/DOM/JavaScript
- ❌ Chrome Extensions · ❌ Cursor stealing · ❌ `.env` with real secrets
