# PLAN: 24/7 Daemon Production — Cron-Job + Monitoring + Error Recovery

> **Quelle:** issues.md, `src/stealth_runner/autonomous_daemon.py`  
> **Abhängigkeiten:** survey-runner-complete (SR-14 — braucht fertigen Survey Runner)  
> **Priorität:** 🔴 KRITISCH  
> **Aufwand:** Mittel

---

## 🔍 Recherche-Ergebnisse

**Autonomous Daemon** (`src/stealth_runner/autonomous_daemon.py`) existiert bereits mit:
- ✅ Double-fork Daemonization (Hintergrund, kein TTY)
- ✅ PID Lock (keine doppelten Instanzen)
- ✅ Persistent Queue (`~/.stealth-runner/daemon-queue.json`)
- ✅ Persistent State (`~/.stealth-runner/daemon-state.json`)
- ✅ JSON Logs mit Rotation (10MB × 5)
- ✅ Human-like Pauses (30-90s zufällig)
- ✅ Exponential Backoff (30s → 3600s)
- ✅ Graceful SIGTERM Shutdown
- ✅ CLI: `start | stop | status | logs | stats | clear | add <url>`

**Fehlt:**
- ❌ LaunchD/Cron-Job für tägliche Ausführung
- ❌ EUR-Canary Benachrichtigung
- ❌ Health-Check Endpoint
- ❌ Slack/Telegram Alerting
- ❌ Integration mit fertigem Survey Runner (blockiert auf SR-14)

---

## 🎯 Ziel

Den autonomen Daemon produktionsreif machen: automatischer Start, tägliche Cron-Jobs, Monitoring und Error Recovery.

## 📋 Aktueller Stand

| Komponente | Status | Details |
|-----------|--------|---------|
| Autonomous Daemon | ✅ | `src/stealth_runner/autonomous_daemon.py` |
| PID Lock | ✅ | Verhindert doppelte Instanzen |
| Persistent Queue | ✅ | `~/.stealth-runner/daemon-queue.json` |
| State Tracking | ✅ | `~/.stealth-runner/daemon-state.json` |
| JSON Logs | ✅ | Rotation 10MB × 5 |
| Exponential Backoff | ✅ | 30s → 3600s |
| CLI: start/stop/status/logs/stats | ✅ | |

## ❌ Fehlende Features

| Feature | Status | Aufwand |
|---------|--------|---------|
| Cron-Job (täglich 9:00) | ❌ | Klein |
| EUR-Canary Benachrichtigung | ❌ | Klein |
| Health-Check Endpoint | ❌ | Klein |
| Slack/Telegram Alerting | ❌ | Mittel |
| Survey Runner Integration | ⚠️ Teilweise | Mittel |

## ✅ Sub-Tasks

### Phase 1: Cron-Job
- [ ] LaunchD/Cron-Job: `0 9 * * * cd ~/dev/stealth-runner && python3 -m cli.modules.survey_runner --auto`
- [ ] Logging nach `~/.stealth-runner/cron.log`
- [ ] Ergebnis in State-Datei persistieren

### Phase 2: Monitoring
- [ ] Health-Check: `daemon health` Befehl
- [ ] EUR-Tracking: Guthaben-Veränderung pro Tag
- [ ] Fehler-Rate pro Survey-Typ

### Phase 3: Alerting
- [ ] Bei kritischen Fehlern: macOS Notification
- [ ] Bei EUR-Verdienst: Tägliche Zusammenfassung
- [ ] Option: Telegram-Bot für Remote-Status

## 📂 Verwandte Dateien

| Datei | Rolle |
|-------|-------|
| `src/stealth_runner/autonomous_daemon.py` | Daemon (existiert) |
| `cli/modules/survey_runner.py` | Wird vom Daemon gestartet |
| `~/.stealth-runner/` | State + Logs |

## 🔗 Issue

[ISSUE-SR-17: 24/7 Daemon Production](../issues/ISSUE-SR-17.md)
