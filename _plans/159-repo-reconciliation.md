# SR-161 — Repo Path-Authority + Codebase Reconciliation

## Root Cause Diagnosis (data, not opinion)

Top-level directory listing of `main` shows **5 parallel Python codebases**:

| Path | Role | Status |
|---|---|---|
| `survey-cli/survey/` | Survey daemon + answer engine + captcha chain | **Authoritative** (95% of recent work lands here) |
| `agent-toolbox/` (hyphen!) | Legacy browser_manager.py + survey/* mirror | **Not importable as Python package** (hyphen) |
| `agent_toolbox/` (underscore) | Empty except `tests/` | Confusing siblings of `agent-toolbox` |
| `core/` (top-level) | analytics, config, langgraph_integration, security | Used by `cli/main.py` |
| `cli/main.py` | Top-level entry point | Imports from `core/` |

Result of this chaos:
- **Agent 11** (PR #154) built `agent-toolbox/core/network/` because that's where `BrowserManager` lives — but the *Plan* said `survey-cli/survey/network/`. Path-drift caused 3 real bugs (#155).
- **Tests don't run** in CI for PR #154 because imports like `from agent_toolbox.core.network` fail (hyphen vs underscore mismatch).
- **PR #153** and **#156** also have failing tests (need post-merge surgery).
- **No pre-commit guardrail** prevents future drift.

## Goal

Establish single source of truth and enforce it via tooling:

1. **Declare authority:** `survey-cli/survey/` is the canonical Python package. All other top-level Python dirs are either deprecated, archived, or marked legacy.
2. **Fix imports:** `cli/main.py` must import from `survey-cli.survey` (or from a re-export module that hides the path).
3. **Pre-commit hook:** Reject any PR that adds files outside `survey-cli/` (except docs, tests, _plans, .github).
4. **Move PR #154's files:** `agent-toolbox/core/network/` → `survey-cli/survey/network/` (preserves git history via `git mv`).
5. **Fix CI on PRs #153 + #156:** Diagnose + push fix commits so all 3 can merge.
6. **Update AGENTS.md** with binding path rules + linked AGENTS contract.

## Files

### NEW (3)
- `survey-cli/AGENTS.md` — binding path rules, naming convention, "single-source-of-truth" doctrine
- `.github/workflows/path-guard.yml` — CI job that fails when files appear outside allowed paths
- `scripts/repo_reconcile.py` — one-shot migration tool (idempotent): moves `agent-toolbox/core/network/` files to `survey-cli/survey/network/` with `git mv`, updates imports

### MODIFY (≥ 8)
- `.pre-commit-config.yaml` — add a hook calling `scripts/check_paths.sh` that fails on disallowed paths
- `cli/main.py` — change imports from `agent-toolbox.*` to `survey-cli.survey.*` (or to the installed `stealth-sync` package via pyproject's package map)
- `pyproject.toml` — explicit `tool.hatch.build.targets.wheel.packages = ["survey-cli/survey"]`; remove agent-toolbox refs
- `README.md` — top section "Where does code live?" with 5-line directive
- PRs #153 / #154 / #156 — push fix commits on the existing branches (CI green)

### DELETE / ARCHIVE (with caution, in same PR)
- `agent_toolbox/` (with underscore) → move `tests/` contents to `survey-cli/tests/` and remove the empty directory
- `agent-toolbox/` (hyphen) → if `core/browser_manager.py` is the ONLY active file, move it to `survey-cli/survey/browser_manager.py`. Otherwise mark `agent-toolbox/` as `# DEPRECATED` in its README and exclude from CI.

## Acceptance Criteria

### Reconciliation

- [ ] **One** Python package: `survey-cli/survey/` (installed as `survey` via pyproject)
- [ ] `cli/main.py` imports from `survey.*`, not `agent-toolbox.*`
- [ ] `agent-toolbox/core/network/` files moved to `survey-cli/survey/network/` (git history preserved)
- [ ] `agent_toolbox/` (underscore) deleted, tests merged into `survey-cli/tests/`
- [ ] PR #154 rebased on top of the move so it merges cleanly

### Path-Guard CI

- [ ] `.github/workflows/path-guard.yml` runs on every PR
- [ ] Fails when any `.py` file outside this allowlist appears:
  - `survey-cli/`, `cli/`, `scripts/`, `tests/`, `.github/`, `_plans/`
- [ ] Fails when a top-level Python dir is created (whitelist enforced)
- [ ] Pre-commit hook mirrors the same check for local dev

### Hanging PRs Fixed

- [ ] PR #153 — CI green after fix commit (diagnose first; likely import or test-fixture)
- [ ] PR #154 — rebased on reconciliation, CI green
- [ ] PR #156 — CI green after fix commit

### Documentation

- [ ] `survey-cli/AGENTS.md` includes:
  - Mandatory path table (where new files go)
  - Forbidden paths
  - "Plan-vs-Reality" doctrine: when plan path conflicts with repo state, **STOP** and open a follow-up issue (do not silently divert)
  - Pre-flight checklist for agents: read AGENTS.md, run `python scripts/check_paths.py`, then start work
- [ ] `README.md` top has 5-line "Where does code live?" pointer to AGENTS.md

### Quality
- [ ] ruff clean (E,W,F line-length 100, py312)
- [ ] mypy --strict clean for all moved files
- [ ] Closes #161 (and references #155 as resolved part)
- [ ] Branch: `feat/159-repo-reconciliation`

## Out of Scope

- New question types (SR-150 owns)
- Proxy / IP work (SR-151 owns)
- Reliability/DLQ (SR-152 owns)
- Observability (SR-161 owns)
- CI hardening beyond path-guard (SR-160 owns)

## Pre-flight Mandatory Steps (for the agent picking this up)

1. Read `survey-cli/AGENTS.md` (you'll be writing it; first inspect existing repo conventions: `survey-cli/survey/__init__.py`, `survey-cli/tests/conftest.py`)
2. Verify the assumed authority of `survey-cli/` by counting recent commits per top-level dir:
   ```
   git log --since=30.days --name-only | grep -E '^(survey-cli|agent-toolbox|agent_toolbox|core|cli)/' | sort | uniq -c | sort -rn
   ```
3. If verification contradicts the assumption, open a comment on this issue with the data and pause for direction.

## References

- Three hanging PRs:
  - https://github.com/SIN-CLIs/stealth-runner/pull/153
  - https://github.com/SIN-CLIs/stealth-runner/pull/154
  - https://github.com/SIN-CLIs/stealth-runner/pull/156
- Follow-up from Agent 10: https://github.com/SIN-CLIs/stealth-runner/issues/155
- pyproject.toml (top-level): https://raw.githubusercontent.com/SIN-CLIs/stealth-runner/main/pyproject.toml
- Existing pre-commit config: https://raw.githubusercontent.com/SIN-CLIs/stealth-runner/main/.pre-commit-config.yaml

## Parallel-Safety

**This track BLOCKS SR-160 and SR-161** until the path table is published in AGENTS.md (they need to know where to put their files). Run SR-161 first.
