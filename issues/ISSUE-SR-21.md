# SR-21: stealth-sota — SOTA-Erweiterungen (Chaos/Security/Healing/Observability)

- **Status:** ✅ COMPLETED (2026-05-04)
- **Priority:** 🔴 Critical
- **Repo:** [`SIN-CLIs/stealth-sota`](https://github.com/SIN-CLIs/stealth-sota)

## Description

Sechs kritische SOTA-Bausteine für echte Google/Netflix-Robustheit:
1. **Chaos Engineering** — ChaosMonkey mit 5 aktiven Attacken
2. **Security Hardening** — InputSanitizer + RateLimiter + AuditChain
3. **Self-Healing Daemon** — DaemonSupervisor mit max 5 Restarts
4. **Prometheus Observability** — Command-Latenz, Survey-Counts, Error-Rate
5. **Determinismus & Seeding** — Reproduzierbare Umfragen aus Survey-ID
6. **Performance Regression Tests** — Micro <100ms, Mid <500ms, MAS <2000ms

## Deliverables

- [x] `chaos_engine.py` — ChaosMonkey (5 Attacks: kill_chrome, kill_daemon, fill_disk, corrupt_cache, high_cpu)
- [x] `security_hardening.py` — InputSanitizer, RateLimiter, AuditChain (SHA256-verkettet)
- [x] `self_healing.py` — DaemonSupervisor (5s Polling, max 5 Restarts)
- [x] `observability.py` — Prometheus-Metriken (Counter/Histogram/Gauge) + Graceful Fallback
- [x] `determinism.py` — Seeder (SHA256-SurveyID → Seed)
- [x] `tests/test_chaos.py` — 3 Tests
- [x] `tests/test_security.py` — 9 Tests
- [x] `tests/test_self_healing.py` — 2 Tests
- [x] `tests/test_performance.py` — 3 Tests (inkl. MAS <2000ms)
- [x] `setup.py` — v1.0.0, psutil + [test] deps
- [x] `README.md` — Dokumentation

## Performance

| Test | Erwartet | Gemessen |
|------|----------|----------|
| Router Micro-Tier | <100ms | ✅ passed |
| Router Mid-Tier | <500ms | ✅ passed |
| Survey MAS Pipeline | <2000ms | ✅ passed |
| Audit Chain Verify | korrekt | ✅ 8/8 |
| Security Blocked Patterns | 4/4 | ✅ |

## Files

- `SIN-CLIs/stealth-sota` — komplettes Repo (10 Dateien)
- `stealth-runner/issues/ISSUE-SR-21.md` — dies hier
- `stealth-runner/issues.md` — Issue-Tabelle
