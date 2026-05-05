# Issues — Stealth Runner

> Alle Issues sind in `issues/ISSUE-SR-*.md`.

| Issue | Status | Priority | Titel |
|-------|--------|----------|-------|
| [SR-11](issues/ISSUE-SR-11.md) | ✅ COMPLETED | 🔴 Critical | CI/CD — GitHub Actions, Pre-Commit, Auto-Release |
| [SR-12](issues/ISSUE-SR-12.md) | ✅ COMPLETED | 🔴 Critical | Test Suite — Unit, Integration, E2E |
| [SR-13](issues/ISSUE-SR-13.md) | ✅ COMPLETED | 🟠 High | Survey Provider Adapter — Samplicio.us, Cint, Nfield |
| [SR-14](issues/ISSUE-SR-14.md) | ✅ COMPLETED | 🟠 High | Audio Capture Module — BlackHole + ffmpeg + Omni |
| [SR-15](issues/ISSUE-SR-15.md) | ✅ COMPLETED | 🟡 Medium | Captcha Solving — Simple, GeeTest v4, Lemin Puzzle |
| [SR-16](issues/ISSUE-SR-16.md) | ✅ COMPLETED | 🟡 Medium | Error Recovery — Disqualification, Modal Error, Timeout |
| [SR-17](issues/ISSUE-SR-17.md) | ✅ COMPLETED | 🔴 Critical | CUA-ONLY Migration — skylight-cli → cua-driver |
| [SR-18](issues/ISSUE-SR-18.md) | ✅ COMPLETED | 🔴 Critical | stealth-session — Warm Daemon für <50ms Command Execution |
| [SR-19](issues/ISSUE-SR-19.md) | ✅ COMPLETED | 🔴 Critical | stealth-axiom — 3-Tier Hierarchical Model Router |
| [SR-20](issues/ISSUE-SR-20.md) | ✅ COMPLETED | 🔴 Critical | RecursiveMAS — RecursiveLink + Survey MAS Pipeline |
| [SR-21](issues/ISSUE-SR-21.md) | ✅ COMPLETED | 🔴 Critical | stealth-sota — Chaos/Security/Healing/Observability/Determinism |
| [SR-22](issues/ISSUE-SR-22.md) | ✅ COMPLETED | 🔴 Critical | stealth-core + stealth-dynamic — Basis-Klassen + Dynamische Engine |
| [SR-23](issues/ISSUE-SR-23.md) | ✅ COMPLETED | 🔴 Critical | stealth-memory — Ewiges Gedächtnis (opencode.db Poller) | ✅ COMPLETED | 🔴 Critical | stealth-core + stealth-dynamic — Basis-Klassen + Dynamische Engine |

---

## 🔴 CRITICAL — orchestrator.py importiert gelöschte Datei — 2026-05-05

| Feld | Wert |
|------|------|
| Status | ✅ FIXED |
| Priority | 🔴 Critical |
| Gefunden | 2026-05-05 |
| Gefixt | 2026-05-05 |

### Problem
`heypiggy_login_box.py` gelöscht aber `orchestrator.py` (line 90) importiert noch davon:
```python
from cli.modules.heypiggy_login_box import heypiggy_login  # ImportError!
```

### Fix
`orchestrator.py` → `from cli.modules.auto_google_login import execute as auto_google_login`

### Betroffene Files
- `/Users/jeremy/dev/stealth-runner/app/core/orchestrator.py` → FIXED ✅
- `/Users/jeremy/dev/stealth-runner/AGENTS.md` → FIXED ✅

---

## 🟠 HIGH — BOT Chrome vs USER Chrome Verwechslung — 2026-05-05

| Feld | Wert |
|------|------|
| Status | ✅ DOCUMENTED |
| Priority | 🟠 High |
| Gefunden | 2026-05-05 |

### Problem
Bei mehreren Chrome-Instanzen: BOT Chrome (`heypiggy-bot-*`) von USER Chrome unterscheiden.

### Lösung
```bash
ps aux | grep "user-data-dir"
# BOT: /tmp/heypiggy-bot-XXXXXXXX
# USER: /Users/jeremy/Library/Application Support/Google/Chrome/...
```

### Regel
- NUR Chrome mit `heypiggy-bot-XXXXXXXX` in user-data-dir → INTERAGIEREN
- ALLE ANDEREN Chrome → IGNORIEREN
