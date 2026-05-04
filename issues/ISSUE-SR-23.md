# SR-23: stealth-memory — Ewiges Gedächtnis (opencode.db Poller)

- **Status:** ✅ COMPLETED (2026-05-04)
- **Priority:** 🔴 Critical
- **Repo:** [`SIN-CLIs/stealth-memory`](https://github.com/SIN-CLIs/stealth-memory)

## Description

Memory Daemon der opencode.db pollt, Fehler/Erfolge extrahiert und append-only in learn.md/brain.md schreibt. Löst das Kernproblem: Der Agent vergisst ALLES zwischen Sessions.

## Deliverables

- [x] `db_poller.py` — 5s Polling der opencode.db via SQLite
- [x] `extractor.py` — 9 Error-Patterns + 4 Success-Patterns (Regex)
- [x] `writer.py` — Append-only mit fcntl File-Lock
- [x] `daemon.py` — Haupt-Loop mit Signal-Handling + Checkpoint

## Patterns

**Errors erkannt:**
- wrong_pid, ax_missing, fixed_sleep, overwrite_md, cdp_js_forbidden
- login_failed, import_path, wid_stale, engine_error

**Successes erkannt:**
- login_ok, survey_started, survey_done, daemon_ok
