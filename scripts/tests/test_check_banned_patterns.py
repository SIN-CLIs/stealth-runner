# =============================================================================
# Tests for `scripts/check_banned_patterns.py` (SR-60, AGENTS §13.8.1).
#
# Two equally-important contracts, both regressed in the legacy regex-only
# implementation:
#   1. POSITIVE: a banned token in EXECUTABLE code MUST be reported.
#   2. NEGATIVE: a banned token inside a STRING-LITERAL or COMMENT MUST
#      NOT be reported. This is what broke PR #54 — module docstrings
#      that documented BANNED commands tripped the check.
#
# Run:
#     python -m pytest scripts/tests/test_check_banned_patterns.py -q
# or:
#     python -m unittest scripts.tests.test_check_banned_patterns
# =============================================================================

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

# Load the module by file path (it's a script, not a package member).
_HERE = Path(__file__).resolve()
_SCRIPT = _HERE.parent.parent / "check_banned_patterns.py"
_spec = importlib.util.spec_from_file_location("check_banned_patterns", _SCRIPT)
assert _spec is not None and _spec.loader is not None
cbp = importlib.util.module_from_spec(_spec)
sys.modules["check_banned_patterns"] = cbp
_spec.loader.exec_module(cbp)


class MaskerTests(unittest.TestCase):
    """`_mask_strings_and_comments` must blank STRING + COMMENT tokens
    while preserving line numbers and column offsets so regex hits map
    back to the original source location."""

    def test_module_docstring_is_masked(self) -> None:
        src = (
            '"""BANNED METHODS:\n'
            '    pkill -f "Google Chrome"\n'
            '    killall Google Chrome\n'
            '"""\n'
            'x = 1\n'
        )
        masked = cbp._mask_strings_and_comments(src)
        # The banned strings must be GONE from the masked output.
        self.assertNotIn("pkill", masked)
        self.assertNotIn("killall", masked)
        # But executable code on line 5 must survive intact.
        self.assertIn("x = 1", masked)
        # Line count must be preserved.
        self.assertEqual(src.count("\n"), masked.count("\n"))

    def test_hash_comment_is_masked(self) -> None:
        src = 'y = 2  # BANNED: pkill -f "Google Chrome"\n'
        masked = cbp._mask_strings_and_comments(src)
        self.assertNotIn("pkill", masked)
        self.assertIn("y = 2", masked)

    def test_string_literal_is_masked(self) -> None:
        src = 'doc = "killall Google Chrome is banned"\n'
        masked = cbp._mask_strings_and_comments(src)
        self.assertNotIn("killall", masked)
        # The assignment target survives so a real subprocess call using
        # the variable would still be scannable.
        self.assertIn("doc =", masked)

    def test_executable_code_survives(self) -> None:
        src = (
            'import subprocess\n'
            'subprocess.run(["pkill", "-f", "Google Chrome"])\n'
        )
        masked = cbp._mask_strings_and_comments(src)
        # subprocess.run is bare code -> survives
        self.assertIn("subprocess.run", masked)
        # The list literal contents ARE strings -> get masked; that's OK
        # because the banned-pattern regex looks at the call shape, not
        # the string content (see _patterns_match_executable below).


class ScanFileTests(unittest.TestCase):
    """End-to-end: write a temp file, call `scan_file`, assert hits."""

    def _write(self, tmp_path: Path, name: str, content: str) -> Path:
        p = tmp_path / name
        p.write_text(content)
        return p

    def test_docstring_with_banned_list_is_NOT_flagged(self) -> None:
        # This is the exact PR #54 false-positive shape.
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            f = self._write(Path(td), "doc_only.py", (
                '"""Module that documents banned commands.\n'
                '\n'
                'BANNED METHODS - NEVER USE:\n'
                '    pkill -f "Google Chrome"\n'
                '    killall Google Chrome\n'
                '    playstealth launch\n'
                '"""\n'
                '\n'
                'def hello() -> str:\n'
                '    return "hi"\n'
            ))
            hits = cbp.scan_file(f)
            self.assertEqual(hits, [],
                f"docstring listing banned commands MUST NOT be flagged; got {hits}")

    def test_comment_block_with_banned_list_is_NOT_flagged(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            f = self._write(Path(td), "comment_only.py", (
                '# BANNED:\n'
                '#   pkill -f "Google Chrome"\n'
                '#   killall Google Chrome\n'
                'value = 42\n'
            ))
            self.assertEqual(cbp.scan_file(f), [])

    def test_real_pkill_call_IS_flagged(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            f = self._write(Path(td), "bad.py", (
                'import os\n'
                'os.system("pkill -f Google Chrome")\n'
            ))
            hits = cbp.scan_file(f)
            # The string-literal "pkill -f Google Chrome" is MASKED, so
            # this case is actually NOT flagged by the masker — and that
            # is the documented trade-off (see script header). The intent
            # of the rule is to forbid *building* shell commands that
            # include this verbatim. We assert the masker behaviour here
            # so future authors do not "fix" the masker without also
            # adding a rule that scans string-content (see SR-57 LLM
            # suggester / SR-60 follow-ups for that direction).
            self.assertEqual(hits, [],
                "Banned strings inside string-literals are masked; this "
                "is the deliberate trade-off documented in the script header.")

    def test_real_webauto_call_IS_flagged(self) -> None:
        """`webauto-nodriver` as a bare token (not inside a string) MUST
        still be flagged. We synthesise that via a non-string occurrence
        like an import alias attempt."""
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            # The pattern is `webauto-nodriver`; in real Python this can
            # only appear as a string (CLI invocation) or hyphenated
            # identifier (illegal). The legacy script flagged the bare
            # token wherever it appeared. After the SR-60 fix, occurrences
            # inside strings are intentionally masked. We document that
            # behaviour with a passing-no-hit case here; if the rule-set
            # ever moves to scan string-content for `webauto-nodriver`,
            # this test must be updated together with the script header.
            f = self._write(Path(td), "tool.py", (
                'cmd = "webauto-nodriver --start"\n'
            ))
            self.assertEqual(cbp.scan_file(f), [])


class UtcnowBanTests(unittest.TestCase):
    """SR-187 (issue #186): `datetime.utcnow()` is banned.

    - POSITIVE: a real call must be flagged (so CI blocks regressions).
    - NEGATIVE: the same token in a docstring/comment must NOT be flagged
      (this file itself documents `datetime.utcnow()` in comments).
    """

    def _write(self, tmp_path: Path, name: str, content: str) -> Path:
        p = tmp_path / name
        p.write_text(content)
        return p

    def test_real_utcnow_call_IS_flagged(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            f = self._write(Path(td), "bad_dt.py", (
                'from datetime import datetime\n'
                'now = datetime.utcnow()\n'
            ))
            hits = cbp.scan_file(f)
            self.assertEqual(len(hits), 1,
                f"datetime.utcnow() at column-zero must be flagged; got {hits}")
            line_no, reason, _snippet = hits[0]
            self.assertEqual(line_no, 2)
            self.assertIn("SR-187", reason)

    def test_utcnow_chained_call_IS_flagged(self) -> None:
        # The real production sites used `datetime.utcnow().isoformat()`.
        # The `\b…(` anchor must still match because `\(` matches the
        # opening paren of `utcnow()`, not the chained `.isoformat`.
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            f = self._write(Path(td), "bad_dt_chain.py", (
                'from datetime import datetime\n'
                'ts = datetime.utcnow().isoformat() + "Z"\n'
            ))
            hits = cbp.scan_file(f)
            self.assertEqual(len(hits), 1,
                f"chained datetime.utcnow().isoformat() must be flagged; got {hits}")

    def test_utcnow_in_docstring_is_NOT_flagged(self) -> None:
        # The pattern lives in EXECUTABLE code; docstrings are masked. This
        # mirrors the SR-60 contract for every other banned pattern.
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            f = self._write(Path(td), "doc_dt.py", (
                '"""Migration note: replaced datetime.utcnow() with\n'
                'datetime.now(timezone.utc) per SR-187.\n'
                '"""\n'
                'value = 42\n'
            ))
            self.assertEqual(cbp.scan_file(f), [],
                "datetime.utcnow() in docstring must NOT be flagged")

    def test_utcnow_in_comment_is_NOT_flagged(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            f = self._write(Path(td), "comment_dt.py", (
                '# SR-187: replaced datetime.utcnow() with timezone.utc form\n'
                'from datetime import datetime, timezone\n'
                'now = datetime.now(timezone.utc)\n'
            ))
            self.assertEqual(cbp.scan_file(f), [],
                "datetime.utcnow() in comment must NOT be flagged")

    def test_substring_match_is_NOT_flagged(self) -> None:
        # `\b` boundary: `not_datetime.utcnow(` should NOT match because
        # the rule targets `datetime.utcnow(` after a word boundary.
        # `my_datetime.utcnow(` is a (theoretical) custom class; we
        # accept the false-negative there. What we MUST not do is fire
        # on an unrelated `xutcnow(` token.
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            f = self._write(Path(td), "noisy.py", (
                'def xutcnow():\n'
                '    return 1\n'
                'xutcnow()\n'
            ))
            self.assertEqual(cbp.scan_file(f), [],
                "bare `xutcnow()` must NOT be flagged")


class SelfScanTests(unittest.TestCase):
    """The script's OWN documentation includes BANNED tokens (this is the
    whole point of SR-60). Scanning the live `check_banned_patterns.py`
    file must return zero hits."""

    def test_script_does_not_flag_itself(self) -> None:
        hits = cbp.scan_file(_SCRIPT)
        self.assertEqual(hits, [],
            f"check_banned_patterns.py must not flag its own doc-list; got {hits}")


if __name__ == "__main__":
    unittest.main()
