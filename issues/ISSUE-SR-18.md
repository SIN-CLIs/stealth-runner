# SR-18: stealth-session — Warm Daemon für <50ms Command Execution

- **Status:** ✅ COMPLETED (2026-05-04)
- **Priority:** 🔴 Critical
- **Repo:** [`SIN-CLIs/stealth-session`](https://github.com/SIN-CLIs/stealth-session)

## Description

Warm daemon that keeps Chrome, CDP, AX-tree, and login session hot. LLM agent controls each step via `stealth-exec`, execution is <50ms per command instead of 5-15s via raw shell.

## Deliverables

- [x] `daemon.py` — Unix-Socket-Server, Chrome-Start, Auto-Login, Signal-Handling
- [x] `executor.py` — WarmExecutor mit Verify-Box und WindowManager-Integration
- [x] `window_manager.py` — CDP Target-Domain Echtzeit-Tracking aller Fenster/Popups
- [x] `idiot_proof.py` — 8 Schutzmuster (PID/WID, CDP-JS, Sleep, Verify, etc.)
- [x] `ax_cache.py` — AX-Tree Cache mit TTL
- [x] `cache.py` — PID, CDP-Port, Window-ID Key-Value-Cache
- [x] `client.py` — `stealth-exec` CLI mit --verify Flag
- [x] `watchdog.py` — Chrome mit --force-renderer-accessibility, Auto-Port-Detection
- [x] `setup.py` — pip installable, entry_points für beide CLIs

## Known Issues

- Chrome Port Auto-Detection: Watchdog findet existierende Chrome-Instanzen per CDP-Port-Abfrage

## Files

- `SIN-CLIs/stealth-session` — komplettes Repo
- `stealth-runner/commands.md` — stealth-exec Befehle dokumentiert
- `stealth-runner/AGENTS.md` — Verify-Box Regel
- `stealth-runner/brain.md` — Architektur-Diagramm
- `stealth-runner/sinrules.md` — §7 Regeln
- `stealth-runner/architecture.md` — Architektur
