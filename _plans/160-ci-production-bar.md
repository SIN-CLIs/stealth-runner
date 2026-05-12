# SR-160 — CI Production Bar (coverage gate, real-chrome E2E, strict types, flaky-test guard)

## Context

Today's CI does ruff + pytest at default-strictness. That bar accepted PR #154 which had **3 latent bugs** (duplicate init block, broken imports in tests, broken imports in CLI). The bugs were only caught after-the-fact on user prompt — not by CI.

We need the bar to be high enough that landing buggy code is mechanically impossible.

## Goal

Five gates that must pass before any PR can merge:

1. **Coverage gate** — new code must lift overall coverage; floor at 85% for `survey-cli/survey/{daemon,captcha,reliability,network}/`
2. **mypy --strict gate** — fully typed, no `Any` leakage
3. **Real-Chrome E2E gate** — every PR runs a single smoke test that launches headless Chrome via mitmproxy, navigates to a fixture page, asserts proxy + fingerprint behavior
4. **Flaky-test guard** — pytest-rerunfailures; flaky tests block merge until stabilized
5. **Stricter ruff ruleset** — add S (bandit), SIM (simplification), B (bugbear), RUF (ruff-specific), TID (tidy imports)

## Files

### NEW (5)
- `.github/workflows/ci-production-bar.yml` — new workflow that runs after the existing `ci.yml`; required for merge
- `survey-cli/tests/e2e/test_real_chrome_smoke.py` — single E2E test (mitmproxy + Chrome + httpbin)
- `survey-cli/tests/e2e/conftest.py` — fixtures: `mitmproxy_server`, `chrome_via_proxy`, fixture HTML pages
- `scripts/coverage_diff.py` — Python tool that compares coverage on PR vs base; fails if PR coverage decreases
- `docs/CI_PRODUCTION_BAR.md` — describes each gate, how to debug failures locally

### MODIFY (4)
- `pyproject.toml`:
  - `[tool.coverage.report]` → `fail_under = 85`
  - `[tool.ruff.lint]` → add `S, SIM, B, RUF, TID` to select
  - `[tool.mypy]` → `strict = true` and `disallow_untyped_defs = true` (for `survey-cli/survey/`)
- `.github/workflows/ci.yml` — install `pytest-rerunfailures`, `mitmproxy`, `pytest-cov>=6.0`; mypy strict step
- `.pre-commit-config.yaml` — mirror new ruff rules locally
- `README.md` — "Local CI parity" section: how to run all gates locally

## Detail: Coverage Gate

Use `pytest --cov=survey --cov-report=xml --cov-fail-under=85`. Compare on PR via `scripts/coverage_diff.py`:

```python
# Compares coverage.xml (PR HEAD) vs coverage-base.xml (PR target merge-base).
# Fails if any module in survey/{daemon,captcha,reliability,network}/ drops by >0.5%.
# Allows drop in survey/legacy/ (TBD path) without fail.
```

## Detail: Real-Chrome E2E

```python
# survey-cli/tests/e2e/test_real_chrome_smoke.py
@pytest.mark.e2e
async def test_proxy_flag_actually_routes_through_proxy(mitmproxy_server, chrome_via_proxy):
    """SR-151's --proxy-server flag must actually route traffic through the proxy."""
    page_response = await chrome_via_proxy.fetch("http://httpbin.org/ip")
    intercepted = mitmproxy_server.get_intercepted_requests()
    assert any("httpbin.org/ip" in r.url for r in intercepted), \
        "Expected mitmproxy to see the httpbin request; got: " + str([r.url for r in intercepted])
```

Mitmproxy runs in-process via the `mitmproxy.tools.dump.DumpMaster` API. Chrome launches via the project's `BrowserDriver` / `BrowserManager`.

## Detail: Flaky-Test Guard

`pytest --reruns 1 --reruns-delay 2` for tests marked `@pytest.mark.may_flake`. Without the marker, tests must be deterministic; if they fail-then-pass on rerun, the run is marked `flaky` and blocks merge until stabilized.

## Detail: Ruff Extended Ruleset

| Code | What | Why now |
|---|---|---|
| `S` | bandit security checks | catches `subprocess.run(shell=True)`, hardcoded secrets |
| `SIM` | simplification | reject `if x: return True; else: return False` |
| `B` | bugbear | catches `except:` bare, `mutable default args` |
| `RUF` | ruff-specific | f-string consistency, useless `noqa` |
| `TID` | tidy imports | bans relative imports above 2 levels, banned-imports list |

Suppress overrides in `pyproject.toml` if any current code violates them — but log each suppression with `# TODO(SR-NNN): fix and remove suppression`.

## Acceptance Criteria

### Coverage Gate
- [ ] `pytest --cov=survey --cov-fail-under=85` runs in CI
- [ ] `scripts/coverage_diff.py` runs on every PR and blocks merge on regression
- [ ] Local command `make coverage` produces the same report as CI

### mypy --strict Gate
- [ ] `mypy --strict survey-cli/survey/` returns 0 errors on `main`
- [ ] CI fails when new code adds untyped functions
- [ ] Strict applies only to `survey-cli/survey/` (NOT to tests; tests use `--no-strict-optional`)

### Real-Chrome E2E Gate
- [ ] `.github/workflows/ci-production-bar.yml` includes a job that:
  - Installs mitmproxy + Chrome (headless)
  - Runs `pytest -m e2e survey-cli/tests/e2e/ -v --reruns 1`
  - Job timeout: 5 minutes
- [ ] Test passes on a clean checkout
- [ ] Test fails meaningfully when proxy flag is removed from Chrome args (regression detection)

### Flaky-Test Guard
- [ ] `pytest-rerunfailures` is a dev dependency
- [ ] Tests without `@pytest.mark.may_flake` that fail-then-pass cause the CI job to fail
- [ ] The flaky-test report is uploaded as an artifact

### Stricter Ruff
- [ ] `[tool.ruff.lint.select]` includes `E, W, F, S, SIM, B, RUF, TID` in pyproject.toml
- [ ] Every suppression has a `# noqa: <code> — <reason>` or a TODO with issue link
- [ ] `ruff check survey-cli/` on `main` returns 0 errors

### Documentation
- [ ] `docs/CI_PRODUCTION_BAR.md` exists and explains each gate
- [ ] `README.md` "Local CI parity" section: `make ci-local` runs all gates locally
- [ ] `Makefile` has `make coverage`, `make typecheck`, `make e2e`, `make ci-local` targets

### Quality
- [ ] Branch: `feat/160-ci-production-bar`
- [ ] Closes #160 in commit + PR body
- [ ] ruff clean (with the new extended ruleset)
- [ ] mypy --strict clean

## Out of Scope

- Adding new tests for existing features (separate SR)
- Migrating to `uv` (separate SR — current pyproject uses hatchling)
- Refactoring tests for higher coverage (this issue raises the bar; individual tracks pay the bill)
- Repo-reconciliation (SR-161 owns)
- Observability (SR-161 owns)

## Dependencies

- **Blocks on SR-161.** Path-Authority must exist before coverage gate makes sense (which paths count?).

## References

- mitmproxy in-process: https://docs.mitmproxy.org/stable/addons-scripting/
- pytest-rerunfailures: https://github.com/pytest-dev/pytest-rerunfailures
- coverage.py XML report: https://coverage.readthedocs.io/en/latest/cmd.html#xml-reporting
- Existing CI: https://raw.githubusercontent.com/SIN-CLIs/stealth-runner/main/.github/workflows/ci.yml
- Existing pyproject: https://raw.githubusercontent.com/SIN-CLIs/stealth-runner/main/pyproject.toml
- The 3 latent bugs in PR #154 (Agent 11 self-review): https://github.com/SIN-CLIs/stealth-runner/pull/154

## Parallel-Safety

Touches `pyproject.toml`, `.github/workflows/`, `Makefile`, `README.md`, `docs/`. Zero overlap with SR-161.
**Must run AFTER SR-161.**
