# SR-22: stealth-core + stealth-dynamic — Basis-Klassen + Dynamische Survey-Engine

- **Status:** ✅ COMPLETED (2026-05-04)
- **Priority:** 🔴 Critical
- **Repos:** [`SIN-CLIs/stealth-core`](https://github.com/SIN-CLIs/stealth-core), [`SIN-CLIs/stealth-dynamic`](https://github.com/SIN-CLIs/stealth-dynamic)

## Description

Anti-Kollaps-Schicht: Basis-Klassen für Retry/CircuitBreaker/GracefulDegradation + dynamische Survey-Engine.

## Deliverables

**stealth-core (6 Module):**
- [x] `constants.py` — Timeouts, Rollen
- [x] `exceptions.py` — 6 Fehlerklassen
- [x] `retry.py` — Decorator mit Exponential Backoff
- [x] `circuit_breaker.py` — CircuitBreaker (Closed/Open/Half-Open)
- [x] `graceful_degradation.py` — 5 Status: Healthy→Blacklisted
- [x] `process_guardian.py` — Prozess-Überwachung
- [x] `health_check.py` — CDP + OpenCode DB Check
- [x] `logging_config.py` — JSON-Structured Logging

**stealth-dynamic (4 Module):**
- [x] `classifier.py` — 11 Seitentypen (consent→unknown)
- [x] `resolver.py` — Persona-basierte Strategie pro Fragetyp
- [x] `flow_state.py` — Zustandsmaschine (nie Kontextverlust)
- [x] `engine.py` — DynamicSurveyEngine (Handle Page + Weiter-Polling)

**Integration:**
- [x] `stealth-session/daemon.py` — DynamicSurveyEngine + AxiomRouter im Daemon
- [x] `stealth-exec cua-touch --action survey_loop` — Ein Befehl für gesamte Umfrage

## Files

- `SIN-CLIs/stealth-core` — 8 Dateien
- `SIN-CLIs/stealth-dynamic` — 6 Dateien
- `stealth-runner/issues/ISSUE-SR-22.md`
