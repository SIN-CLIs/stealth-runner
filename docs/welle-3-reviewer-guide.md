# Welle-3 Reviewer Guide

> **Audience:** humans (and agents) reviewing the 7 Welle-3 primitive PRs (#245 – #252).
> **Goal:** answer "in what order do I review/merge these, and what do I look at first in each?".
> **Constraint:** Welle-1 (#234 – #241) and Welle-2 (#242 → #243 → #244) are reviewed in their own threads — this guide is scoped strictly to Welle-3.

This document was written 2026-05-17 alongside SR-256 and reflects state at that point. PR titles + branch names below are the canonical references; if a number drifts, trust the branch name.

---

## TL;DR — recommended review order

1. **Doc-only first** — #248 (`docs/wave-3-audit-section-sr-249`) is pure markdown. Merge sets the audit trail before code lands.
2. **Quick-win primitives** — #249 (log redaction), #250 (TokenBucket), #251 (CircuitBreaker), #252 (env-check) — all four are pure-Python, fully unit-tested, no I/O, no banned patterns. Reviewable in ~10 min each. Order doesn't matter; merge in parallel as bandwidth allows.
3. **Reliability composition** — #245 (full_stability) depends conceptually on SR-169 (already on `main`) + SR-174 (already on `main`); merge any time after #248.
4. **Storage-shape change** — #246 (persona-quarantine TTL) bumps the on-disk JSON schema 1→2. Backward-compatible by construction (old schema-1 files load with `ttl_seconds=None`), but worth a slightly closer read of the backward-compat tests.
5. **Operator visibility** — #247 (DLQ health) is read-only over existing `DLQRecord`. No risk to the live path.

**All 7 PRs can technically be merged in any order — there are no inter-PR dependencies inside Welle-3.** The order above is the lowest-risk-first sequence.

---

## Per-PR review hints

For each PR, the table gives:
- **What to look at first** — the single concept the rest of the diff hangs on.
- **What to test** — the specific assertion that, if it passes, the PR is safe.
- **Wireup-Folge-PR** — what happens *after* merge. Reviewers don't need to evaluate this here; the listed scope is for context only.

### #245 — SR-246 — `feat/full-stability-composition-sr-246`

| Field | Detail |
|---|---|
| **What to look at first** | The DOM-first ordering decision in the module docstring. The short-circuit on `dom_timeout` (network skipped) is the load-bearing claim. |
| **What to test** | `test_dom_timeout_short_circuits_network_call` — it asserts `tracker.activity_calls == 0` when DOM never converges. |
| **Wireup-Folge-PR** | One hook in `safe_executor.py` after the click-path DOM verifier. ~5 LoC. |
| **Risk** | None on `main` (additive, pure facade). |

### #246 — SR-247 — `feat/persona-quarantine-ttl-sr-247`

| Field | Detail |
|---|---|
| **What to look at first** | Schema bump 1→2 in `_SCHEMA_VERSION`. The `from_dict` migration path: schema-1 JSONs (no `ttl_seconds`) load with `ttl_seconds=None` → unchanged behaviour. |
| **What to test** | `test_schema1_file_without_ttl_loads_as_no_ttl` + `test_schema1_file_survives_sweep` — these prove old data is not auto-released. |
| **Wireup-Folge-PR** | Daemon startup adds one `sweep_expired()` cron call. |
| **Risk** | Storage-shape change. Mitigation: explicit schema-1 load test, and `is_active()` (legacy method) is preserved for audit tools. |

### #247 — SR-248 — `feat/dlq-health-observability-sr-248`

| Field | Detail |
|---|---|
| **What to look at first** | `aggregate_health()` is a pure function over `DLQRecord` lists. It does NOT mutate the DLQ. |
| **What to test** | `test_clock_skew_negative_age_clamped_to_zero` + `test_unparseable_timestamp_does_not_crash` — defensive paths. |
| **Wireup-Folge-PR** | Add a `/doctor` JSON endpoint emitting `aggregate_health(dlq.list_all()).to_dict()`. |
| **Risk** | None on `main` (read-only observability). |

### #248 — SR-249 + SR-252 + SR-255 — `docs/wave-3-audit-section-sr-249`

| Field | Detail |
|---|---|
| **What to look at first** | This is a single PR that grew three commits — Sections 16, 17, and 18 of `AGENTS.md`. Each section closes one round. |
| **What to test** | `git log --oneline` shows three commits; `head -1 AGENTS.md` shows `# AGENTS.md — Das Brain`. |
| **Wireup-Folge-PR** | None. |
| **Risk** | None — pure docs. Merge first to set the audit trail. |

### #249 — SR-250 — `feat/log-redaction-util-sr-250`

| Field | Detail |
|---|---|
| **What to look at first** | The two pattern lists at the top of the file: `DEFAULT_SECRET_KEY_PATTERNS` (key-name) and `DEFAULT_VALUE_PATTERNS` (value-substring). These are the policy. |
| **What to test** | `test_log_event_shape` — realistic structlog event with persona PII + bearer token + sk-key, asserts host stays in URL but session token is scrubbed. |
| **Wireup-Folge-PR** | Add `redact()` as a structlog processor in `observability/logger.py`. |
| **Risk** | None on `main` (the module isn't called yet). Wireup PR introduces the only behavioural change. |

### #250 — SR-251 — `feat/token-bucket-rate-limiter-sr-251`

| Field | Detail |
|---|---|
| **What to look at first** | The `acquire()` blocking path uses `time_until()` to compute sleep duration — no busy-poll. Caller-injectable `sleep_fn`/`now_fn`. |
| **What to test** | `test_concurrent_try_acquire_never_oversells` — 100 threads x 5 acquires, asserts exactly `capacity` successes (no over-acquisition). |
| **Wireup-Folge-PR** | Four small wireups: DLQ replay, LangGraph resume, sweep_expired throttle, OpenAI Vision cost cap. |
| **Risk** | None on `main` (pure primitive). |

### #251 — SR-253 — `feat/circuit-breaker-sr-253`

| Field | Detail |
|---|---|
| **What to look at first** | The state machine (CLOSED -> OPEN -> HALF_OPEN -> CLOSED). `_maybe_transition_to_half_open_locked()` is called on every state read so cooldown elapse is observable without a background thread. |
| **What to test** | `test_provider_outage_recovers` — full lifecycle smoke incl. five short-circuits during outage and a successful recovery probe. |
| **Wireup-Folge-PR** | Four wireups: NIM, captcha solvers, OpenAI Vision, Heypiggy login. Each wraps the existing call site with `breaker.call(...)` and classifies `CircuitOpenError` as `FATAL` in the matching `RetryPolicy.classify_fn`. |
| **Risk** | None on `main` (pure primitive). |

### #252 — SR-254 — `feat/env-presence-check-sr-254`

| Field | Detail |
|---|---|
| **What to look at first** | `format_human_report()` — the secret-leak regression guard. Test: `test_report_redacts_present_values` asserts the value `sk-proj-very-secret` is NOT echoed back. |
| **What to test** | `test_default_lists_are_evaluable` — both default requirement lists (`REQUIRED_FOR_DAEMON`, `REQUIRED_FOR_LIVE_RUN`) evaluate cleanly on a totally-empty env without crashing. |
| **Wireup-Folge-PR** | One trip-wire line at the top of `daemon/cli.py`: `result = check_env(REQUIRED_FOR_DAEMON); sys.exit(2) if not result.is_ok else continue`. |
| **Risk** | None on `main` (module is unreferenced until the wireup PR). |

---

## Cross-cutting checks

When reviewing any Welle-3 PR, verify the five session disciplines:

1. **No edit to a file touched by an open PR.** Run `git diff main...<branch> --name-only` and cross-check against the file lists of #234 - #244. Welle-3 was deliberately built to be conflict-free.
2. **No new top-level directory.** All new modules live under `survey/reliability/` or `survey/observability/` — same parent dirs as their Welle-1/2 siblings.
3. **No new dependencies.** `requirements.txt` and `pyproject.toml` are untouched in every Welle-3 PR.
4. **`scripts/check_banned_patterns.py` clean.** This was run before every commit; CI runs it again.
5. **Tests are unittest-only.** No `pytest` import. The sandbox these were built in had no pytest.

If a PR violates any of the above, treat as a regression.

---

## What this guide deliberately does NOT do

- It does **not** rank the merge value of Welle-1+2. Those PRs have their own context in `incidents/CRITIC-AUDIT-2026-05-13.md` and the prior session summaries in `AGENTS.md` section 15.
- It does **not** open the wireup PRs. By design, every primitive is shipped without integration so that Welle-1+2 stack conflicts remain at zero.
- It is **not** a substitute for the per-PR description. Each PR body has the canonical acceptance criteria, test counts, and links.

---

## Audit footer

| Item | Value |
|---|---|
| Welle-3 primitives delivered | 7 |
| Tests added | 153 (52 + 58 + 43 across three rounds) |
| Direct pushes to `main` during Welle-3 | 0 |
| Files mutated in any open Welle-1+2 PR | 0 |
| New top-level directories | 0 |
| New dependencies | 0 |

Generated 2026-05-17 alongside SR-256.
