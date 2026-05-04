# SR-17: 24/7 Daemon Production — Cron + Monitoring

- **Status:** 🟡 PARTIAL — daemon exists (512 lines), plist created, cron+alerting missing
- **Priority:** 🔴 Critical
- **Plan:** [`plans/plan-daemon-production.md`](../plans/plan-daemon-production.md)

## Description

Autonomous daemon for 24/7 survey automation. Core daemon exists, LaunchD plist created, but cron job and alerting still need implementation.

## Deliverables

- [x] `autonomous_daemon.py` (512 lines) — double-fork, PID lock, persistent queue
- [x] Persistent state + JSON logs with rotation
- [x] Human-like pauses + exponential backoff
- [x] CLI: `start | stop | status | logs | stats | clear | add <url>`
- [x] `com.stealth-runner.daemon.plist` — LaunchD auto-start config
- [x] Install plist: `launchctl load ~/Library/LaunchAgents/com.stealth-runner.daemon.plist`
- [ ] LaunchD/Cron job for daily 9:00 execution
- [ ] EUR-Canary tracking + macOS notification

## Acceptance Criteria

- [x] Daemon starts/stops via CLI
- [x] Daemon persists across shell sessions
- [x] LaunchD plist ready for loading
- [ ] Daemon auto-starts on system boot
- [ ] Daily survey execution via launchd/cron
- [ ] Alert on critical errors

## Files

- `src/stealth_runner/autonomous_daemon.py` (512 lines)
- `com.stealth-runner.daemon.plist`
- `~/.stealth-runner/` — state + log directory
