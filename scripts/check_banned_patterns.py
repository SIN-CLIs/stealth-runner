#!/usr/bin/env python3
"""Pre-commit hook: scan for banned patterns in Python source code.

Detects forbidden strings in executable code (not docstrings/comments).
Exits with non-zero if ANY banned pattern is found.
"""

import re
import sys
from pathlib import Path

BANNED_PATTERNS = [
    (r'pkill\s+-f\s+["\']*Google Chrome', "pkill -f 'Google Chrome' kills USER Chrome"),
    (r'killall\s+Google Chrome', "killall Google Chrome kills ALL Chrome instances"),
    (r'os\.kill\([^,]+,\s*9\)\s*(?!#.*SIGKILL.*fallback)', "os.kill(pid, 9) blocks graceful shutdown — use SIGTERM first"),
    (r'--remote-allow-origins=\*(?!")', "--remote-allow-origins=* without quotes breaks in zsh"),
    (r'/tmp/heypiggy-bot\b(?!-)', "/tmp/heypiggy-bot (fixed profile) corrupts after restart"),
    (r'playstealth\s+launch', "playstealth launch does NOT set --force-renderer-accessibility"),
    (r'webauto-nodriver', "webauto-nodriver is ABSOLUT BANNED"),
    (r'skylight-cli\s+click.*--element-index', "skylight-cli click --element-index is unstable"),
    (r'subprocess\.Popen.*Chrome.*(?!remote-allow-origins=\\"\*\\")',
     "Chrome MUST be launched with --remote-allow-origins=\"*\" (with quotes!)"),
]

ROOT = Path(__file__).resolve().parent.parent
SCAN_DIRS = ["survey-cli", "src", "cli", "run_survey.py"]

found = 0

for scan_path in SCAN_DIRS:
    path = ROOT / scan_path
    if not path.exists():
        continue
    files = Path(path).rglob("*.py") if Path(path).is_dir() else [Path(path)]
    for py_file in files:
        if "test_" in str(py_file) or "__pycache__" in str(py_file):
            continue
        try:
            content = py_file.read_text()
            lines = content.split("\n")
        except Exception:
            continue

        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped.startswith("#") or stripped.startswith('"""') or '"""' in stripped:
                continue  # skip comments and docstrings

            for pattern, reason in BANNED_PATTERNS:
                if re.search(pattern, line):
                    print(f"  {py_file}:{i}: BANNED: {reason}")
                    print(f"    -> {stripped[:120]}")
                    found += 1

if found:
    print(f"\n{f'='*60}")
    print(f"  {found} BANNED pattern(s) found. Commit blocked.")
    print(f"  These patterns are documented in sinrules.md §2 (BANNED).")
    print(f"  Fix the code or explain WHY this is an exception.")
    print(f"{'='*60}\n")
    sys.exit(1)

print("  No banned patterns found.")
sys.exit(0)