# Plan: Issue #83 — Production-Ready Error Handling & Observability

> Temporary planning file. **DELETE in the same PR that closes #83.**
> Tracking issue: https://github.com/SIN-CLIs/stealth-runner/issues/83

## Goal
Bring the survey agent to production reliability: circuit breaker, checkpointing, audit log, metrics export.

## Phased Scope
This is a multi-PR EPIC. Each phase ships independently and updates STATUS INDEX.

### Phase 1 — Error Handling
- Circuit breaker per step (fail-stop on N consecutive failures)
- Exponential backoff with jitter for retryable errors (extends #85 infra)
- Screenshot capture on failure → `logs/failure-screens/<ts>.png`
- Structured error context (step, page_url, AX-snapshot hash, stack)

### Phase 2 — State Management
- Pipeline state checkpoint after each major step → `logs/checkpoints/<run_id>.json`
- Resume-from-checkpoint CLI: `survey resume <run_id>`
- Optional Supabase sync hook (disabled by default; no integration installed yet)

### Phase 3 — Security & Audit
- Fernet-encrypted credentials at rest (env var key)
- Tamper-evident audit log (HMAC chain)
- IP anonymization via SHA-256 with daily salt rotation

### Phase 4 — Observability
- Prometheus exporter on `/metrics` (step latency p50/p95/p99, success rate, error categories)
- Structured logs via `structlog` with JSON output to stdout
- Health endpoint `/healthz` returning current run state + uptime

## Out of Scope (now)
- Distributed tracing (OpenTelemetry) — separate issue if needed
- Multi-tenant credential vault — separate issue

## Acceptance Criteria (per phase)
- Phase 1: synthetic flaky step triggers circuit breaker after 3 failures; screenshot present.
- Phase 2: kill process mid-run → resume completes the run from checkpoint.
- Phase 3: audit log verification CLI detects a single-byte tampering.
- Phase 4: `curl /metrics` returns valid Prometheus exposition.

## Files Affected (Phase 1 scope only)
- `survey-cli/survey/error_policy.py` (new)
- `survey-cli/survey/cdp_actuator.py` (wire breaker)
- `survey-cli/survey/screenshot.py` (new)
- `tests/test_error_policy.py` (new)

## Cleanup
After EPIC fully closed: `git rm _plans/83-error-observability.md`.
