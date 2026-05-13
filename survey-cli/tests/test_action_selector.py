"""Tests for ActionSelector — fallback action generation without NIM.

WARUM: Jede Code-Datei braucht Tests. ActionSelector ist NEU.
"""

# === SR-63 #62 legacy-debt skip (do not delete without unskipping) ===
import pytest
# === END SR-63 skip ===

import unittest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from survey.action_selector import ActionSelector
from survey.snapshot import CompactSnapshot


class TestActionSelector(unittest.TestCase):
    """Test ActionSelector.select_actions() with various snapshot inputs."""

    def _make_snapshot(self, refs):
        return CompactSnapshot(refs=refs, url="", title="", provider="qualtrics",
                               semantic={"questions": [], "progress": "1/10"})

    def test_selects_preferred_persona_answer(self):
        snap = self._make_snapshot({
            "@e0": {"role": "radio", "text": "Berlin", "enabled": True},
            "@e1": {"role": "radio", "text": "Hamburg", "enabled": True},
            "@e2": {"role": "button", "text": "Weiter", "enabled": True},
        })
        actions = ActionSelector.select_actions(snap)
        self.assertEqual(actions[0], {"ref": "@e0", "action": "select"})

    def test_selects_first_radio_when_no_preferred(self):
        snap = self._make_snapshot({
            "@e0": {"role": "radio", "text": "Hamburg", "enabled": True},
            "@e1": {"role": "radio", "text": "München", "enabled": True},
            "@e2": {"role": "button", "text": "Weiter", "enabled": True},
        })
        actions = ActionSelector.select_actions(snap)
        self.assertEqual(actions[0], {"ref": "@e0", "action": "select"})

    def test_skips_disabled_elements(self):
        snap = self._make_snapshot({
            "@e0": {"role": "radio", "text": "Berlin", "enabled": False},
            "@e1": {"role": "radio", "text": "Hamburg", "enabled": True},
        })
        actions = ActionSelector.select_actions(snap)
        self.assertEqual(actions[0], {"ref": "@e1", "action": "select"})

    def test_finds_submit_button(self):
        snap = self._make_snapshot({
            "@e0": {"role": "radio", "text": "Ja", "enabled": True},
            "@e1": {"role": "button", "text": "Weiter", "enabled": True},
        })
        actions = ActionSelector.select_actions(snap)
        self.assertTrue(any(a.get("action") == "submit" for a in actions))

    def test_fills_textarea(self):
        snap = self._make_snapshot({
            "@e0": {"role": "textbox", "text": "", "enabled": True,
                     "placeholder": "Beschreiben Sie Ihr Hobby"},
        })
        actions = ActionSelector.select_actions(snap)
        self.assertEqual(actions[0]["action"], "fill")
        self.assertIn("Hobby", actions[0]["value"])

    def test_max_two_actions(self):
        snap = self._make_snapshot({
            "@e0": {"role": "radio", "text": "Berlin", "enabled": True},
            "@e1": {"role": "radio", "text": "Hamburg", "enabled": True},
            "@e2": {"role": "button", "text": "Weiter", "enabled": True},
            "@e3": {"role": "button", "text": "Zurück", "enabled": True},
        })
        actions = ActionSelector.select_actions(snap)
        self.assertLessEqual(len(actions), 2)

    def test_empty_snapshot(self):
        snap = self._make_snapshot({})
        actions = ActionSelector.select_actions(snap)
        self.assertEqual(actions, [])


if __name__ == "__main__":
    unittest.main()
