# Test package marker.
# These tests cover `scripts/check_banned_patterns.py` and exist because
# the script is run as a pre-commit hook AND in CI (see
# `.github/workflows/ci.yml::Run banned patterns check`). Any regression
# here either lets a banned command slip into the codebase OR blocks
# every commit with false positives — see AGENTS.md §13.8.1 SR-60.
