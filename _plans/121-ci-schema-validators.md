# Plan: SR-121 — Wire schema validators into CI

Closes: #121
Branch: `feat/121-ci-schema-validators`
Assignee track: Agent-2 (hygiene / CI)
Min tests: 6

## Goal

Invoke `scripts/check_audit_log_schema.py` (from #114) and
`scripts/check_inbox_log_schema.py` (from #118) on every PR and push to
`main`. Fail the workflow on schema violations; upload the JSON
violation report as an artifact for 14 days.

## Acceptance Criteria

1. **New file** `.github/workflows/schema-guard.yml` exists. Triggers on
   `pull_request` and `push: branches: [main]`. Uses pinned action
   versions `actions/checkout@v5` and `actions/setup-python@v6`
   (AGENTS.md §13.8.4).
2. Job runs **both** validators with `--exit-non-zero-on-violation` and
   `--json` against `survey-cli/logs/` (the canonical log dir).
3. Job is **fast** — no `pip install -r requirements.txt`; both
   validators are stdlib-only. Setup-python step + raw `python` call only.
4. If logs dir is empty / missing (legitimate state on a fresh repo), the
   job MUST succeed quietly (no spurious failures).
5. JSON output captured to `audit-schema.json` and
   `inbox-schema.json`; both uploaded via `actions/upload-artifact@v4`
   (retention-days: 14) on `if: always()` so even failed runs leave
   forensics.
6. **New file** `scripts/tests/test_schema_guard_workflow.py` validates
   the YAML structure (parseable, has required jobs, uses pinned action
   versions, has `if: always()` upload). Pure YAML lint, no docker.

## File Boundaries

### MUST modify / create

- `.github/workflows/schema-guard.yml` (NEW)
- `scripts/tests/test_schema_guard_workflow.py` (NEW)

### MUST NOT touch

- `scripts/check_audit_log_schema.py`
- `scripts/check_inbox_log_schema.py`
- `scripts/tests/test_check_audit_log_schema.py`
- `scripts/tests/test_check_inbox_log_schema.py`
- `survey-cli/**` — completely out of scope
- `.github/workflows/ci.yml` — separate workflow, not a CI hook
- `.github/workflows/learn-suggester-eval.yml`

### Plan-file deletion (rule A4)

Delete `_plans/121-ci-schema-validators.md` in the same commit.

## Conflict Surface

- No conflicts with currently-open PRs (no other PR edits `.github/workflows/`
  newly).
- Verify by `git log --oneline main..HEAD -- .github/workflows/` before
  pushing — must be empty other than the new workflow.

## Test Minimum

6 tests in `scripts/tests/test_schema_guard_workflow.py`:

| # | What |
|---|------|
| T1 | YAML is parseable |
| T2 | Has `on.pull_request` and `on.push.branches == [main]` |
| T3 | Uses `actions/checkout@v5` (not @latest) |
| T4 | Uses `actions/setup-python@v6` (not @latest) |
| T5 | Both validator scripts are invoked with `--exit-non-zero-on-violation` |
| T6 | Has `if: always()` upload-artifact step with retention-days: 14 |

## Hand-off Notes for Agent-2

- Action versions are non-negotiable: AGENTS.md §13.8.4 forbids `@latest`
  and `@master`.
- Both validators are stdlib-only — DO NOT add `pip install` step.
- Treat empty/missing logs dir as success. Easiest implementation:
  `if [ -d survey-cli/logs ]; then python scripts/... ; else echo skip; fi`.
- Test the YAML with `python -c "import yaml; yaml.safe_load(open(...))"`
  during local iteration. PyYAML is available in standard test envs.

## Out of Scope

- Wiring `learn-suggester-eval.yml` to PRs (workflow_dispatch by design).
- Auto-fixing schema violations.
- Schema migration tooling.
