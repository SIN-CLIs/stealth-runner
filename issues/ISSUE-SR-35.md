# ISSUE-SR-35: Chrome Lease Manager + Safety Layer

| Feld | Wert |
|------|------|
| **ID** | SR-35 |
| **Priority** | 🟡 P2 — Medium |
| **Status** | 📋 TODO |
| **Created** | 2026-05-06 |
| **Labels** | `safety`, `chrome`, `session`, `kill-guard` |
| **Plan** | `plan-sr-35-chrome-safety.md` |

## Problem
Der `SessionManager` (224 Zeilen) existiert, hat aber Lücken:
1. **KillGuard fehlt** — `pkill -f "heypiggy-bot"` killt ALLE Chrome-Instanzen (auch User-Chrome!)
2. **Kein Lease-System** — Kein Lock-Mechanismus damit nicht zwei Prozesse dasselbe Profil nutzen
3. **PID-Hardcoding** — AGENTS.md warnt davor, aber der Code könnte es trotzdem tun
4. **Keine Auto-Recovery** — Wenn Chrome crashed, kein automatischer Neustart

## Subissues

### SR-35.1 — KillGuard
- [ ] `KillGuard` Klasse: hookt in `subprocess.run` calls
- [ ] Blockiert: `pkill`, `killall`, `kill` mit Chrome-PID
- [ ] Pattern-Detection: `pkill -f "heypiggy-bot"` → BLOCK
- [ ] Pattern-Detection: `killall "Google Chrome"` → BLOCK
- [ ] Ausnahme: eigene PID vom `playstealth launch`
- [ ] Whitelist: `SessionManager.close_bot_only()`

### SR-35.2 — Lease System
- [ ] `~/.stealth/chrome_lease.json` — Lock-File
- [ ] `acquire_lease(profile_name)` → token oder None
- [ ] `release_lease(profile_name, token)` → ok
- [ ] Auto-Release nach Timeout (5 Minuten)
- [ ] Vor jedem `playstealth launch`: Lease prüfen

### SR-35.3 — PID Registry
- [ ] `~/.stealth/bot_pids.json` — aktuelle BOT-Chrome PIDs
- [ ] Jedes `playstealth launch` → PID registrieren
- [ ] `SessionManager.close_all()` → kill BOT-PIDs + leert Registry
- [ ] Health-Check: `ps aux | grep PID` → prüft ob Chrome noch lebt

### SR-35.4 — Auto-Recovery
- [ ] `ChromeHealthMonitor` — alle 30s checken
- [ ] Detect: Chrome-Prozess tot, CDP nicht erreichbar
- [ ] Recover: `playstealth launch --url '...'` → neuer Chrome
- [ ] Max 3 Recovery-Versuche, dann manueller Eingriff

## Acceptance Criteria
- [ ] `KillGuard` blockiert `pkill -f "heypiggy-bot"` und `killall "Google Chrome"`
- [ ] Lease-System verhindert Doppel-Nutzung eines Profils
- [ ] PID-Registry trackt alle BOT-Chrome Instanzen
- [ ] `SessionManager.close_all()` killt NUR BOT-Chrome, nie User-Chrome

## Betroffene Files
- `cli/modules/session_manager.py` → Upgrade
- `~/.stealth/chrome_lease.json` → NEU
- `~/.stealth/bot_pids.json` → NEU
