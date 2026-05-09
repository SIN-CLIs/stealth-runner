# ULTIMATE PLAN — Stealth-Runner SOTA May 2026

> **Author**: Planner Agent | **Date**: 2026-05-08
> **Status**: DRAFT | **Version**: 1.0.0
>
> This document is THE single source of truth for the Stealth-Runner architecture
> overhaul. All sub-plans in `plans/` derive from this document. When in doubt,
> come back here.

---

## THE VERDICT

**The codebase has a `two-heads` problem.** Everything that matters exists twice:

| Component | Head A (`survey-cli/`) | Head B (`src/stealth_survey/`) |
|-----------|----------------------|-------------------------------|
| NIM Client | `NIMClient` (238 lines) | `NIMSurveyClient` (598 lines) |
| Snapshot | `CompactSnapshot` + `generate_snapshot()` (454 lines) | `CompactSnapshot` + `CompactSnapshotGenerator` (separate file) |
| Batch Executor | `BatchExecutor` (950 lines) | `BatchExecutor` (separate file) |
| Survey Runner | `SurveyRunner` (1432 lines) | `SurveyAgent` (1062+ lines) |

**Plus**: 3 Chrome launchers, 3 login implementations, 4 copies of CPX credentials.

**Result**: Guaranteed divergence, 2× maintenance cost, 0× confidence about which version is "correct", impossible to test end-to-end.

**The fix**: MERGE into ONE canonical module. Everything else follows from this.

---

## ARCHITECTURE: THE TARGET STATE

```
stealth-runner/
│
├── survey_cli/                          ← THE canonical survey engine (NEW name)
│   ├── __init__.py
│   │
│   ├── engine/                          ← Core NEMO loop (THE one implementation)
│   │   ├── nim_client.py                ← Single NIMClient (circuit breaker + retry)
│   │   ├── snapshot.py                  ← Single CompactSnapshot + generator
│   │   ├── batch_executor.py            ← Single BatchExecutor (provider dispatch)
│   │   ├── survey_agent.py              ← Single SurveyAgent (run_survey + run_loop)
│   │   └── page_analyzer.py             ← NEW: question detection, progress, stuck
│   │
│   ├── providers/                       ← Provider adapters (one per provider)
│   │   ├── base.py                      ← Abstract ProviderAdapter
│   │   ├── qualtrics.py                 ← Qualtrics (.NextButton, .LabelWrapper)
│   │   ├── toluna.py                    ← TolunaStart (.cf-radio)
│   │   ├── strat7.py                    ← Strat7 (.bsbutton)
│   │   ├── purespectrum.py              ← PureSpectrum (Angular v19 CDP)
│   │   ├── cloudresearch.py             ← CloudResearch ([role=button])
│   │   └── generic.py                   ← Generic fallback
│   │
│   ├── lifecycle/                       ← Chrome + daemon management (ONE path)
│   │   ├── chrome.py                    ← ChromeLauncher (single launch path)
│   │   ├── daemon.py                    ← DaemonManager (cua-driver state machine)
│   │   ├── session.py                   ← SessionManager (Chrome registry)
│   │   └── cleanup.py                   ← Safe kill, zombie tab cleanup
│   │
│   ├── auth/                            ← Login (ONE implementation)
│   │   ├── google_oauth.py              ← 6-step CUA flow (refactored from 1734 lines)
│   │   ├── login_verifier.py            ← CDP-based login state detection
│   │   └── keychain_fallback.py         ← NEW: Password fallback when Keychain disabled
│   │
│   ├── security/                        ← Credential management
│   │   ├── secrets.py                   ← SecretsClient (Infisical/Vault)
│   │   └── config.py                    ← Typed config (pydantic, env-based)
│   │
│   ├── observability/                   ← Logging, metrics, monitoring
│   │   ├── logger.py                    ← Structured JSONL logger
│   │   ├── metrics.py                   ← Prometheus-style metrics
│   │   └── health.py                    ← Health check endpoint
│   │
│   ├── tools/                           ← Frozen deterministic tools
│   │   └── ... (existing tools, no changes)
│   │
│   ├── cli.py                           ← Typer CLI (survey.py replacement)
│   └── watch.py                         ← Daemon watch loop
│
├── tests/
│   ├── unit/                            ← Unit tests (mock CDP, mock NIM)
│   │   ├── test_nim_client.py
│   │   ├── test_snapshot.py
│   │   ├── test_batch_executor.py
│   │   ├── test_survey_agent.py
│   │   ├── test_providers/
│   │   ├── test_lifecycle/
│   │   └── test_auth/
│   ├── integration/                     ← Integration tests (real-ish CDP)
│   │   ├── test_e2e_survey.py
│   │   ├── test_tab_switching.py
│   │   └── test_login_flow.py
│   └── conftest.py                      ← Shared fixtures, mocks
│
├── config/
│   ├── profiles/                        ← Persona profiles (no hardcoded PII)
│   ├── providers.yaml                   ← Provider config (selectors, markers)
│   └── settings.yaml                    ← App settings (ports, timeouts, limits)
│
├── scripts/
│   ├── verify_completeness.py           ← Pre-commit: banned patterns, docstrings, tests
│   ├── cleanup_sessions.py              ← Session file cleanup
│   └── graphify.py                      ← Code graph visualization
│
├── .pre-commit-config.yaml              ← AUTOMATED ENFORCEMENT
├── pyproject.toml                       ← Project config, ruff, mypy, pytest
├── AGENTS.md                            ← Agent instructions
├── sinrules.md                          ← Central rules
├── ULTIMATE-PLAN.md                     ← YOU ARE HERE
└── plans/                               ← Detailed sub-plans
    ├── 01-merge-two-heads.md
    ├── 02-secure-credentials.md
    ├── 03-enforce-rules.md
    ├── 04-chrome-lifecycle.md
    ├── 05-nemo-unification.md
    ├── 06-test-coverage.md
    ├── 07-auto-login-hardening.md
    └── 08-observability.md
```

## KEY PRINCIPLES

1. **ONE source of truth per concept.** No duplicate classes. No parallel implementations.
2. **Credentials NEVER in code.** Infisical/Vault/env-vars only. Secret scanner in pre-commit.
3. **Rules are AUTOMATED, not documented.** Pre-commit hooks enforce bans, not comment blocks.
4. **Every public function has ≥3 tests.** Unit tests for logic, integration tests for flows.
5. **Provider logic ISOLATED.** Each provider has one adapter file. Engine dispatches to adapter.
6. **Graceful degradation.** NIM fails → auto-pilot. Chrome dies → restart. Daemon crashes → recover.
7. **Observable by default.** Structured logging, metrics, health checks. No `print()` in production.
8. **NO banned pattern comments.** The code should be clean enough that warnings aren't needed.

## PHASE PLAN

### PHASE 0: EMERGENCY FIXES (today, <2h)

| # | Action | Why |
|---|--------|-----|
| P0.1 | Fix `--remote-allow-origins="*"` in `accessibility.py:119` | Actual Chrome startup bug in zsh |
| P0.2 | Fix `execute()` duplicate in `auto_google_login.py:1255` | Shadow bug — second definition overwrites first |
| P0.3 | Replace `os.kill(pid, 9)` with SIGTERM→SIGKILL in `daemon.py:216` | Prevents graceful shutdown |
| P0.4 | Add `.pre-commit-config.yaml` with ruff + secret scanner | Zero automated enforcement today |

### PHASE 1: MERGE TWO HEADS (this week, 2-3 days)

Merge `survey-cli/` and `src/stealth_survey/` into ONE `survey_cli/engine/` module. This eliminates 4 duplicate implementations immediately.

See: `plans/01-merge-two-heads.md`, `plans/05-nemo-unification.md`

### PHASE 2: HARDEN (next week, 2-3 days)

Secure credentials, enforce rules, consolidate Chrome lifecycle, fix login.

See: `plans/02-secure-credentials.md`, `plans/03-enforce-rules.md`, `plans/04-chrome-lifecycle.md`, `plans/07-auto-login-hardening.md`

### PHASE 3: PRODUCTION-READY (following week, 2-3 days)

Close test coverage gap, add observability, integration tests, session corruption fix.

See: `plans/06-test-coverage.md`, `plans/08-observability.md`

---

## METRICS (TARGET)

| Metric | Current | Target |
|--------|---------|--------|
| Python files | 53 | ~35 (de-duplicated) |
| Test files | 28 | ~45 (full coverage) |
| Test coverage | ~62% | ≥90% |
| Duplicate implementations | 6 pairs | 0 |
| Hardcoded credentials | 4 files | 0 |
| Chrome launch paths | 3 | 1 |
| Login implementations | 3 | 1 |
| Pre-commit hooks | 0 | 5+ |
| Banned pattern comment lines | ~7,500 | 0 |
| Session corruption files | 2,965 | 0 |

---

## BANNED FOREVER

These are NOT going into any comment block. They are enforced by CI:

- `playstealth launch` — banned binary
- `webauto-nodriver` — banned MCP
- `pkill -f "Google Chrome"` — kills user Chrome
- `killall Google Chrome` — kills ALL Chrome
- `--remote-allow-origins=*` (no quotes)
- `/tmp/heypiggy-bot` (fixed profile)
- Hardcoded PIDs, credentials, emails, API keys
- `skylight-cli click --element-index`
- `os.kill(pid, 9)` on Chrome
- `print()` in production code (use logger)

---

## SUB-PLAN INDEX

| Plan | File | Phase |
|------|------|-------|
| Merge Two Heads | `plans/01-merge-two-heads.md` | 1 |
| Secure Credentials | `plans/02-secure-credentials.md` | 2 |
| Enforce Rules | `plans/03-enforce-rules.md` | 2 |
| Chrome Lifecycle | `plans/04-chrome-lifecycle.md` | 2 |
| NEMO Unification | `plans/05-nemo-unification.md` | 1 |
| Test Coverage | `plans/06-test-coverage.md` | 3 |
| Auto-Login Hardening | `plans/07-auto-login-hardening.md` | 2 |
| Observability | `plans/08-observability.md` | 3 |