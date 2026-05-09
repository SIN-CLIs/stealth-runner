# Plan 03: ENFORCE RULES

> **Parent**: ULTIMATE-PLAN.md | **Phase**: 2 | **Priority**: P0
> **Effort**: 1 day | **Risk**: LOW

---

## PROBLEM

The codebase has ~7,500 lines of banned-pattern warnings in comments. **Zero automated enforcement.** Every rule is honor-system only.

## WHAT BREAKS

- Agent can check in `pkill -f "Google Chrome"` and no CI stops it
- Hardcoded PID commit → no pre-commit blocks it
- Missing docstring → unknown until human review
- The ban list is maintained in comments, not in a script that checks

## PLAN

### Step 1: Create `.pre-commit-config.yaml`

```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.12.0
    hooks:
      - id: ruff
      - id: ruff-format
        args: [--check]

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.14.0
    hooks:
      - id: mypy
        args: [--strict, --ignore-missing-imports]

  - repo: https://github.com/Yelp/detect-secrets
    rev: v1.5.0
    hooks:
      - id: detect-secrets

  - repo: local
    hooks:
      - id: verify-completeness
        name: verify completeness
        entry: python scripts/verify_completeness.py
        language: python
        types: [python]
        pass_filenames: true

      - id: banned-patterns
        name: banned patterns
        entry: python scripts/check_banned_patterns.py
        language: python
        types: [python]
        pass_filenames: true
```

### Step 2: Create `scripts/check_banned_patterns.py`

Scans all `.py` files for forbidden strings in executable code (not comments):

```python
BANNED_PATTERNS = [
    r'pkill\s+-f\s+["\']*Google Chrome',
    r'killall\s+Google Chrome',
    r'os\.kill\([^,]+,\s*9\)',  # SIGKILL on Chrome
    r'--remote-allow-origins=\*',  # no quotes
    r'/tmp/heypiggy-bot\b',  # fixed profile
    r'playstealth\s+launch',
    r'webauto-nodriver',
    r'skylight-cli\s+click.*--element-index',
    r'pid\s*=\s*\d{4,5}(?!\s*\#)',  # hardcoded PID in code
]
```

### Step 3: Create `scripts/verify_completeness.py`

Checks every Python file for:

```python
CHECKS = {
    "has_banned_header": "File must start with BANNED warning (until migration removes them)",
    "all_functions_have_docstring": "Every def must have a docstring",
    "all_constants_have_warum": "Every constant needs WARUM comment",
    "public_functions_have_tests": "≥3 tests per public function (checks test files)",
    "no_hardcoded_credentials": "No emails, API keys, hashes",
}
```

### Step 4: Remove banned-pattern comment blocks

After pre-commit enforcement is active, remove the ~7,500 lines of redundant banned-pattern comments from all files. The rule is now enforced by CI, not by comment blocks.

### Step 5: Add CI gate

```yaml
# .github/workflows/ci.yml
- name: Pre-commit checks
  run: pre-commit run --all-files

- name: Test suite
  run: pytest tests/ -v
```

## DELIVERABLES

- [ ] `.pre-commit-config.yaml` created
- [ ] `scripts/check_banned_patterns.py` created
- [ ] `scripts/verify_completeness.py` created
- [ ] `ruff configuration` in `pyproject.toml`
- [ ] `mypy configuration` in `pyproject.toml`
- [ ] Banned-pattern comment blocks removed from files
- [ ] CI workflow active

## VERIFICATION

```bash
# Pre-commit passes on all files
pre-commit run --all-files

# No banned patterns in code
python scripts/check_banned_patterns.py survey_cli/ cli/ run_survey.py

# Completeness check passes
python scripts/verify_completeness.py
```