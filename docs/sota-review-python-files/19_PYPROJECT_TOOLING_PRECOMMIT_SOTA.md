# 🛠️ pyproject.toml, Tooling & Pre-Commit SOTA

## SOTA-Tooling-Stack
- `uv` für Dependency-Resolution & Lockfile
- `ruff` als Linter + Formatter (E/F/W/I/N/UP/B/A/C4/SIM)
- `mypy --strict` für Typsicherheit
- `bandit` für Security-Scans
- `pre-commit` Quality-Gate vor jedem Commit
- `pytest-asyncio` + `--cov-fail-under=80` in CI
- `pyproject.toml` als Single-Source-of-Truth (PEP 621)

## Pre-Commit Hooks
- ruff (fix + format), mypy, bandit, trailing-whitespace, end-of-file-fixer, check-yaml
