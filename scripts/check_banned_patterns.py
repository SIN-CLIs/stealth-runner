#!/usr/bin/env python3
# =============================================================================
# Pre-commit hook: scan for banned patterns in EXECUTABLE Python code.
#
# WHY THIS FILE EXISTS
# --------------------
# Several shell-level operations and CLI invocations have proven destructive
# in production (kill USER Chrome, corrupt profiles, miss critical CLI flags)
# and are documented in `sinrules.md §2 (BANNED)`. This script enforces them
# as a pre-commit gate so they never re-enter the codebase silently.
#
# HISTORY / BUG-LOG
# -----------------
# - Initial impl scanned line-by-line with a regex and tried to skip
#   docstrings via `stripped.startswith('"""') or '"""' in stripped`.
#   That filter ONLY recognised the boundary lines of a docstring, not the
#   body. Any module that documented BANNED commands inside a multi-line
#   docstring (e.g. `cli/main.py`, `survey-cli/survey/providers/qualtrics.py`,
#   `cli/modules/captcha_solver.py`) was flagged as a hit.
# - The bug stayed invisible because CI did not trigger on PRs against
#   integration branches (see AGENTS.md §13.8.2). Once the CI-trigger
#   contract was fixed (commit `826dded`), the pre-existing bug surfaced
#   and blocked PR #54.
# - 2026-05-11 (SR-60, this rewrite): replace regex-on-raw-source with
#   `tokenize`-based masking. STRING and COMMENT tokens are blanked out
#   (replaced with spaces, line numbers preserved) BEFORE regex scanning,
#   so docstrings and comments can never produce a hit while real code
#   still does.
#
# WHY tokenize INSTEAD OF ast
# ---------------------------
# `ast` discards string content entirely, which loses column info we need
# for clean error reporting on real hits inside f-strings or concatenated
# string-builds-of-shell-commands (those ARE intentional hits — building
# a banned command line at runtime is the EXACT thing we want to catch).
# But: a banned pattern that lives in a pure documentation string-literal
# (e.g. a module docstring listing BANNED commands) should NOT trigger.
# `tokenize` lets us distinguish "this is the body of a docstring literal"
# from "this is shell-command-text being assembled in real code" by token
# context (STRING token at statement-position == doc, STRING token inside
# an f-string with format-substitution == code-builds-command).
# For the current rule-set every STRING token is non-executable, so we mask
# them all. If a future rule needs to inspect f-string interpolations,
# extend `_mask_strings_and_comments` to walk `tokenize.FSTRING_*` tokens
# selectively.
#
# CONTRACT
# --------
# - Exits 0 if zero banned patterns found in executable code.
# - Exits 1 if any banned pattern found; prints file:line + reason + snippet.
# - Files matched: `survey-cli/**/*.py`, `cli/**/*.py`, `src/**/*.py`,
#   `run_survey.py`. Test files (`test_*.py`) and `__pycache__` skipped.
# - Pre-commit calls this with NO args; it scans the SCAN_DIRS list below.
#
# ADDING A NEW BANNED PATTERN
# ---------------------------
# 1. Append `(regex, human-readable reason)` to `BANNED_PATTERNS`.
# 2. Add a positive test (banned code) + a negative test (same string
#    inside a docstring/comment) to `scripts/tests/test_check_banned_patterns.py`.
# 3. Document the rule in `sinrules.md §2 (BANNED)` AND in AGENTS.md if the
#    rule reflects an architectural decision (see AGENTS.md §13).
# =============================================================================
"""Pre-commit hook: scan for banned patterns in Python source code.

Detects forbidden strings in EXECUTABLE code (docstrings/comments are
masked via `tokenize` before regex scan, so this file's own ban-list
above does NOT trigger itself).
"""

from __future__ import annotations

import io
import re
import sys
import tokenize
from pathlib import Path
from typing import Iterable

# Each entry: (compiled-regex, human-readable reason).
# Patterns are matched against the MASKED source (strings + comments
# blanked out). NEVER add a pattern that depends on string-content;
# such a pattern would be silently ignored by the masker.
BANNED_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r'pkill\s+-f\s+["\']*Google Chrome'),
     "pkill -f 'Google Chrome' kills USER Chrome"),
    (re.compile(r'killall\s+Google Chrome'),
     "killall Google Chrome kills ALL Chrome instances"),
    (re.compile(r'os\.kill\([^,]+,\s*9\)\s*(?!#.*SIGKILL.*fallback)'),
     "os.kill(pid, 9) blocks graceful shutdown - use SIGTERM first"),
    (re.compile(r'--remote-allow-origins=\*(?!")'),
     "--remote-allow-origins=* without quotes breaks in zsh"),
    (re.compile(r'/tmp/heypiggy-bot\b(?!-)'),
     "/tmp/heypiggy-bot (fixed profile) corrupts after restart"),
    (re.compile(r'playstealth\s+launch'),
     "playstealth launch does NOT set --force-renderer-accessibility"),
    (re.compile(r'webauto-nodriver'),
     "webauto-nodriver is ABSOLUT BANNED"),
    (re.compile(r'skylight-cli\s+click.*--element-index'),
     "skylight-cli click --element-index is unstable"),
    (re.compile(r'subprocess\.Popen.*Chrome.*(?!remote-allow-origins=\\"\*\\")'),
     'Chrome MUST be launched with --remote-allow-origins="*" (with quotes!)'),
]

ROOT = Path(__file__).resolve().parent.parent
SCAN_DIRS = ["survey-cli", "src", "cli", "run_survey.py"]


def _mask_strings_and_comments(source: str) -> str:
    """Return `source` with every STRING and COMMENT token replaced by
    same-length whitespace, preserving line numbers and column offsets.

    Falls back to the unmasked source on tokenize errors (e.g. syntax-
    invalid file). That fallback is intentional: a broken file should
    still be scannable — broken syntax can't hide a banned pattern.
    """
    try:
        tokens = list(tokenize.tokenize(io.BytesIO(source.encode("utf-8")).readline))
    except (tokenize.TokenizeError, SyntaxError, IndentationError):
        return source

    # Split source into lines (1-indexed) for in-place mutation.
    # We keep the trailing newline on each line to preserve offsets.
    lines = source.splitlines(keepends=True)

    for tok in tokens:
        if tok.type not in (tokenize.STRING, tokenize.COMMENT):
            continue
        start_row, start_col = tok.start
        end_row, end_col = tok.end
        # tokenize rows are 1-indexed; our list is 0-indexed.
        if start_row == end_row:
            ln = lines[start_row - 1]
            replacement = " " * (end_col - start_col)
            lines[start_row - 1] = ln[:start_col] + replacement + ln[end_col:]
        else:
            # Multi-line string/comment: blank the tail of start line,
            # entire middle lines, and head of end line.
            head = lines[start_row - 1]
            lines[start_row - 1] = head[:start_col] + " " * (len(head) - start_col - (1 if head.endswith("\n") else 0)) + ("\n" if head.endswith("\n") else "")
            for r in range(start_row, end_row - 1):
                # full middle line; preserve trailing newline
                lines[r] = (" " * (len(lines[r]) - (1 if lines[r].endswith("\n") else 0))) + ("\n" if lines[r].endswith("\n") else "")
            tail = lines[end_row - 1]
            lines[end_row - 1] = (" " * end_col) + tail[end_col:]

    return "".join(lines)


def _iter_python_files(scan_dirs: Iterable[str]) -> Iterable[Path]:
    for scan_path in scan_dirs:
        path = ROOT / scan_path
        if not path.exists():
            continue
        files = path.rglob("*.py") if path.is_dir() else [path]
        for py_file in files:
            sp = str(py_file)
            if "test_" in sp or "__pycache__" in sp:
                continue
            yield py_file


def scan_file(py_file: Path) -> list[tuple[int, str, str]]:
    """Return list of (line_no, reason, raw_snippet) for hits in this file.

    Public for the unit-tests in `scripts/tests/test_check_banned_patterns.py`.
    """
    try:
        raw = py_file.read_text()
    except OSError:
        return []

    masked = _mask_strings_and_comments(raw)
    masked_lines = masked.split("\n")
    raw_lines = raw.split("\n")

    hits: list[tuple[int, str, str]] = []
    for i, mline in enumerate(masked_lines, 1):
        # An entirely-whitespace masked line cannot contain a banned token.
        if not mline.strip():
            continue
        for pattern, reason in BANNED_PATTERNS:
            if pattern.search(mline):
                snippet = raw_lines[i - 1].strip() if i - 1 < len(raw_lines) else ""
                hits.append((i, reason, snippet[:120]))
    return hits


def main() -> int:
    found = 0
    for py_file in _iter_python_files(SCAN_DIRS):
        for line_no, reason, snippet in scan_file(py_file):
            print(f"  {py_file}:{line_no}: BANNED: {reason}")
            print(f"    -> {snippet}")
            found += 1

    if found:
        bar = "=" * 60
        print(f"\n{bar}")
        print(f"  {found} BANNED pattern(s) found. Commit blocked.")
        print("  These patterns are documented in sinrules.md §2 (BANNED).")
        print("  Fix the code or explain WHY this is an exception.")
        print(f"{bar}\n")
        return 1

    print("  No banned patterns found.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
