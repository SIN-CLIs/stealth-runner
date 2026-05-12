# -*- coding: utf-8 -*-
"""
test_learn_apply.py
====================

Test-Suite fuer SR-58 #57 — ``survey learn apply`` mit AST-Roundtrip.

Kategorien:
  TestAstRoundtrip   — AST-Splice mechanisch korrekt + idempotent + Regex
                       kompiliert post-splice.
  TestConfidenceGate — substring >= 0.7, llm >= 0.85, manual immer, sonst REJ.
  TestApplyInbox     — End-to-end: Inbox lesen, Gate, Modify, Audit-Log, Rollback.
  TestSafetyInvariants — _AUTO_APPLY bleibt False; Rollback bei pytest-Fail;
                         atomic write.

WICHTIG: skip_tests=True wird in den End-to-End-Tests genutzt, weil wir
KEIN ``pytest``-Subprocess innerhalb von ``pytest`` starten — das wuerde
endlos rekurrieren. Der pytest-Pfad selbst ist ueber Unit-Tests von
``_run_smoke_tests`` mit gemocktem subprocess.run abgedeckt.
"""

from __future__ import annotations

import io
import json
import os
import re
import sys
import tempfile
import textwrap
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
PARENT = os.path.dirname(HERE)
if PARENT not in sys.path:
    sys.path.insert(0, PARENT)

from survey.learn import (
    InboxEntry,
    apply_inbox,
    apply_keyword_to_family,
    compute_diff,
)
from survey.learn import apply as apply_mod


def _load_real_profile_loader() -> str:
    """Lese das ECHTE profile_loader.py aus dem Repo — keine Mocks fuer den
    AST-Roundtrip, das ist die produktive Datei."""
    path = os.path.join(PARENT, "survey", "profile_loader.py")
    with open(path) as f:
        return f.read()


# ────────────────────────────────────────────────────────────────────────────
# TestAstRoundtrip
# ────────────────────────────────────────────────────────────────────────────


class TestAstRoundtrip(unittest.TestCase):
    """AST-Splice mechanisch: family finden, Token splicen, Regex valid."""

    def setUp(self):
        self.src = _load_real_profile_loader()

    def test_single_line_family_email(self):
        new = apply_keyword_to_family(self.src, "email", "emailadresse")
        # Email entry sollte das neue Keyword vor dem schliessenden ) haben
        line = re.search(r'\("email", re\.compile\(.*?\)\)', new).group(0)
        self.assertIn("|emailadresse)", line)
        self.assertNotIn("|emailadresse)", self.src,
                         "test setup: keyword must not exist pre-splice")

    def test_multi_line_concat_family_phone(self):
        new = apply_keyword_to_family(self.src, "phone", "festnetz")
        # In der Multi-Line-Phone-Definition muss das neue Keyword auf der
        # LETZTEN Pattern-Zeile (die mit ``mobile|cell)``) erscheinen.
        self.assertIn("mobile|cell|festnetz)", new)

    def test_chained_applies_are_stable(self):
        s1 = apply_keyword_to_family(self.src, "phone", "festnetz")
        s2 = apply_keyword_to_family(s1, "phone", "vorwahl")
        self.assertIn("|festnetz|vorwahl)", s2)

    def test_unknown_family_raises(self):
        with self.assertRaisesRegex(ValueError, "lieblingsfarbe"):
            apply_keyword_to_family(self.src, "lieblingsfarbe", "rot")

    def test_empty_keyword_raises(self):
        with self.assertRaisesRegex(ValueError, "non-empty"):
            apply_keyword_to_family(self.src, "email", "")
        with self.assertRaisesRegex(ValueError, "non-empty"):
            apply_keyword_to_family(self.src, "email", "   ")

    def test_regex_special_chars_escaped(self):
        """Dots/braces/etc. werden via re.escape neutralisiert."""
        new = apply_keyword_to_family(self.src, "email", "mail.adr+test")
        line = re.search(r'\("email", re\.compile\(.*?\)\)', new).group(0)
        # Wenn re.escape arbeitet, sind ``.`` und ``+`` als ``\.`` / ``\+``
        # encoded.
        self.assertIn(r"mail\.adr\+test", line,
                      f"escape failed: {line!r}")

    def test_post_splice_module_importable_and_matches(self):
        """End-to-end: das modifizierte profile_loader.py importiert + die
        neue Pattern matched das hinzugefuegte Keyword."""
        new = apply_keyword_to_family(self.src, "phone", "festnetz")
        with tempfile.NamedTemporaryFile(
                "w", suffix=".py", delete=False) as f:
            f.write(new)
            tmp = f.name
        try:
            import importlib.util
            spec = importlib.util.spec_from_file_location("mod_under_test",
                                                          tmp)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            phone_re = next(p for k, p in mod.ProfileLoader.FIELD_PATTERNS
                            if k == "phone")
            self.assertTrue(phone_re.search("Festnetz-Anschluss"))
            self.assertTrue(phone_re.search("Telefon"))
            self.assertFalse(phone_re.search("Lieblingsfarbe"))
        finally:
            os.unlink(tmp)


# ────────────────────────────────────────────────────────────────────────────
# TestConfidenceGate
# ────────────────────────────────────────────────────────────────────────────


class TestConfidenceGate(unittest.TestCase):
    """Akzeptanz-Schwellen: substring 0.7, llm 0.85, manual immer."""

    def _entry(self, **kw) -> InboxEntry:
        defaults = dict(
            role="textbox", normalized_label="x", suggested_family="phone",
            confidence=1.0, source="substring",
        )
        defaults.update(kw)
        return InboxEntry(**defaults)

    def test_substring_below_threshold_rejected(self):
        e = self._entry(source="substring", confidence=0.65)
        ok, reason = apply_mod._gate_confidence(e)
        self.assertFalse(ok)
        self.assertIn("0.65", reason)
        self.assertIn("0.7", reason)

    def test_substring_at_threshold_accepted(self):
        e = self._entry(source="substring", confidence=0.7)
        ok, _ = apply_mod._gate_confidence(e)
        self.assertTrue(ok)

    def test_llm_below_threshold_rejected(self):
        e = self._entry(source="llm", confidence=0.80)
        ok, reason = apply_mod._gate_confidence(e)
        self.assertFalse(ok)
        self.assertIn("0.85", reason)

    def test_llm_at_threshold_accepted(self):
        e = self._entry(source="llm", confidence=0.85)
        ok, _ = apply_mod._gate_confidence(e)
        self.assertTrue(ok)

    def test_manual_source_always_accepted(self):
        e = self._entry(source="manual", confidence=0.0)
        ok, _ = apply_mod._gate_confidence(e)
        self.assertTrue(ok)

    def test_unknown_source_rejected(self):
        e = self._entry(source="oracle", confidence=1.0)
        ok, reason = apply_mod._gate_confidence(e)
        self.assertFalse(ok)
        self.assertIn("unknown source", reason)

    def test_no_suggested_family_rejected(self):
        e = self._entry(suggested_family=None, source="substring",
                        confidence=1.0)
        ok, reason = apply_mod._gate_confidence(e)
        self.assertFalse(ok)
        self.assertIn("new family", reason)


# ────────────────────────────────────────────────────────────────────────────
# TestApplyInbox (end-to-end orchestrator)
# ────────────────────────────────────────────────────────────────────────────


class _ApplyInboxFixture:
    """Helper: kopiert profile_loader.py in ein temp project + schreibt inbox."""

    def __init__(self, inbox_rows: list, profile_src: str = None):
        self.td = tempfile.mkdtemp(prefix="apply-test-")
        self.project_root = os.path.join(self.td, "project")
        self.survey_dir = os.path.join(self.project_root, "survey")
        self.logs_dir = os.path.join(self.td, "logs")
        os.makedirs(self.survey_dir)
        os.makedirs(self.logs_dir)
        self.target = os.path.join(self.survey_dir, "profile_loader.py")
        if profile_src is None:
            profile_src = _load_real_profile_loader()
        with open(self.target, "w") as f:
            f.write(profile_src)
        self.original_src = profile_src
        self.inbox = os.path.join(self.td, "accepted.jsonl")
        with open(self.inbox, "w") as f:
            for row in inbox_rows:
                f.write(json.dumps(row) + "\n")

    def cleanup(self):
        import shutil
        shutil.rmtree(self.td, ignore_errors=True)


class TestApplyInbox(unittest.TestCase):

    def test_approve_all_writes_pattern_and_audit_log(self):
        fx = _ApplyInboxFixture([{
            "role": "textbox",
            "normalized_label": "mobilfunknummer",
            "suggested_family": "phone",
            "confidence": 0.85,
            "source": "substring",
        }])
        try:
            result = apply_inbox(
                inbox_path=fx.inbox, target_path=fx.target,
                mode="approve-all", skip_tests=True,
                audit_log_dir=fx.logs_dir,
            )
            self.assertEqual(result.accepted, 1)
            self.assertEqual(result.applied_keywords,
                             [("phone", "mobilfunknummer")])
            with open(fx.target) as f:
                modified = f.read()
            self.assertIn("|mobilfunknummer)", modified)
            self.assertIsNotNone(result.audit_log_path)
            self.assertTrue(os.path.exists(result.audit_log_path))
            with open(result.audit_log_path) as f:
                records = [json.loads(line) for line in f if line.strip()]
            self.assertEqual(records[0]["kind"], "header")
            self.assertIn("reviewer_hash", records[0])
            self.assertEqual(records[0]["issue"], "SR-58 #57")
            applied = [r for r in records[1:]
                       if r.get("decision") == "applied"]
            self.assertEqual(len(applied), 1)
            self.assertEqual(applied[0]["family"], "phone")
            self.assertEqual(applied[0]["keyword"], "mobilfunknummer")
        finally:
            fx.cleanup()

    def test_dry_run_no_writes_no_audit(self):
        fx = _ApplyInboxFixture([{
            "role": "textbox",
            "normalized_label": "festnetz",
            "suggested_family": "phone",
            "confidence": 0.9, "source": "substring",
        }])
        try:
            captured = io.StringIO()
            with mock.patch("sys.stdout", captured):
                result = apply_inbox(
                    inbox_path=fx.inbox, target_path=fx.target,
                    mode="dry-run", skip_tests=True,
                    audit_log_dir=fx.logs_dir,
                )
            # dry-run accepts in-memory (so the diff previews the apply),
            # but MUST NOT write the file or audit log.
            self.assertEqual(result.accepted, 1)
            self.assertEqual(len(result.applied_keywords), 1)
            self.assertIsNone(result.audit_log_path)
            with open(fx.target) as f:
                self.assertEqual(f.read(), fx.original_src,
                                 "dry-run must not write")
            # And the diff must be printed to stdout.
            self.assertIn("|festnetz)", captured.getvalue())
            # Logs-Dir leer
            self.assertEqual(
                [n for n in os.listdir(fx.logs_dir)
                 if n.startswith("learn-applied-")], [])
        finally:
            fx.cleanup()

    def test_confidence_gate_rejects_low_substring(self):
        fx = _ApplyInboxFixture([{
            "role": "textbox", "normalized_label": "x",
            "suggested_family": "phone", "confidence": 0.5,
            "source": "substring",
        }])
        try:
            result = apply_inbox(
                inbox_path=fx.inbox, target_path=fx.target,
                mode="approve-all", skip_tests=True,
                audit_log_dir=fx.logs_dir,
            )
            self.assertEqual(result.accepted, 0)
            self.assertEqual(result.rejected, 1)
            with open(fx.target) as f:
                self.assertEqual(f.read(), fx.original_src)
        finally:
            fx.cleanup()

    def test_unknown_family_rejected_by_ast(self):
        fx = _ApplyInboxFixture([{
            "role": "textbox", "normalized_label": "rot",
            "suggested_family": "lieblingsfarbe", "confidence": 0.95,
            "source": "substring",
        }])
        try:
            result = apply_inbox(
                inbox_path=fx.inbox, target_path=fx.target,
                mode="approve-all", skip_tests=True,
                audit_log_dir=fx.logs_dir,
            )
            self.assertEqual(result.accepted, 0)
            self.assertEqual(result.rejected, 1)
            with open(fx.target) as f:
                self.assertEqual(f.read(), fx.original_src)
        finally:
            fx.cleanup()

    def test_empty_inbox_returns_error(self):
        fx = _ApplyInboxFixture([])
        try:
            result = apply_inbox(
                inbox_path=fx.inbox, target_path=fx.target,
                mode="approve-all", skip_tests=True,
                audit_log_dir=fx.logs_dir,
            )
            self.assertIsNotNone(result.error)
            self.assertIn("empty", result.error)
        finally:
            fx.cleanup()

    def test_post_test_failure_triggers_rollback(self):
        """Wenn pytest-Subprocess Failure meldet, MUSS profile_loader.py
        auf den Vorzustand zurueckgerollt sein."""
        fx = _ApplyInboxFixture([{
            "role": "textbox", "normalized_label": "festnetz",
            "suggested_family": "phone", "confidence": 0.9,
            "source": "substring",
        }])
        try:
            call_count = {"n": 0}

            def fake_run_tests(project_root, test_paths):
                call_count["n"] += 1
                # 1st call (pre) succeeds, 2nd call (post) fails
                if call_count["n"] == 1:
                    return True, "pre OK"
                return False, "FAKE FAILURE: 1 test failed"

            with mock.patch.object(
                    apply_mod, "_run_smoke_tests", side_effect=fake_run_tests):
                result = apply_inbox(
                    inbox_path=fx.inbox, target_path=fx.target,
                    mode="approve-all", skip_tests=False,
                    audit_log_dir=fx.logs_dir,
                )
            self.assertTrue(result.rolled_back, f"result={result}")
            self.assertIn("FAKE FAILURE", result.error)
            with open(fx.target) as f:
                self.assertEqual(
                    f.read(), fx.original_src,
                    "rollback must restore byte-identical original",
                )
            # Audit-Log darf bei Rollback NICHT geschrieben sein
            self.assertEqual(
                [n for n in os.listdir(fx.logs_dir)
                 if n.startswith("learn-applied-")], [])
        finally:
            fx.cleanup()

    def test_pre_test_failure_aborts_without_changes(self):
        fx = _ApplyInboxFixture([{
            "role": "textbox", "normalized_label": "festnetz",
            "suggested_family": "phone", "confidence": 0.9,
            "source": "substring",
        }])
        try:
            with mock.patch.object(
                    apply_mod, "_run_smoke_tests",
                    return_value=(False, "FAKE PRE FAIL")):
                result = apply_inbox(
                    inbox_path=fx.inbox, target_path=fx.target,
                    mode="approve-all", skip_tests=False,
                    audit_log_dir=fx.logs_dir,
                )
            self.assertIn("pre-apply tests FAIL", result.error)
            self.assertFalse(result.rolled_back)  # nichts geschrieben
            with open(fx.target) as f:
                self.assertEqual(f.read(), fx.original_src)
        finally:
            fx.cleanup()


# ────────────────────────────────────────────────────────────────────────────
# TestSafetyInvariants
# ────────────────────────────────────────────────────────────────────────────


class TestSafetyInvariants(unittest.TestCase):

    def test_auto_apply_is_false(self):
        """SICHERHEITSGURT: ``_AUTO_APPLY`` MUSS False bleiben."""
        self.assertFalse(apply_mod._AUTO_APPLY,
                         "_AUTO_APPLY must remain False — see AGENTS.md §12")

    def test_confidence_thresholds_match_spec(self):
        self.assertEqual(apply_mod._SUBSTRING_MIN_CONFIDENCE, 0.7)
        self.assertEqual(apply_mod._LLM_MIN_CONFIDENCE, 0.85)

    def test_atomic_write_no_partial_on_crash(self):
        """``_atomic_write`` benutzt tempfile + os.replace — bei Crash bleibt
        die Ziel-Datei unberuehrt."""
        with tempfile.TemporaryDirectory() as td:
            target = os.path.join(td, "x.py")
            with open(target, "w") as f:
                f.write("original")
            # Simuliere Crash mitten im Write durch Mocking von os.replace
            with mock.patch("os.replace",
                            side_effect=OSError("disk full")):
                with self.assertRaises(OSError):
                    apply_mod._atomic_write(target, "new content")
            # Original unbeschaedigt + keine Temp-Datei uebrig
            with open(target) as f:
                self.assertEqual(f.read(), "original")
            leftover = [n for n in os.listdir(td) if n.startswith(".apply-")]
            self.assertEqual(leftover, [],
                             f"temp files leaked: {leftover}")

    def test_compute_diff_returns_unified_format(self):
        before = "a\nb\nc\n"
        after = "a\nB\nc\n"
        diff = compute_diff(before, after, path="x.py")
        self.assertIn("--- a/x.py", diff)
        self.assertIn("+++ b/x.py", diff)
        self.assertIn("-b", diff)
        self.assertIn("+B", diff)


if __name__ == "__main__":
    unittest.main(verbosity=2)
