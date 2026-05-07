#!/usr/bin/env python3
"""Test for tool_anti_stuck.py — Stuck loop detector.

BANNED METHODS — NIEMALS VERWENDEN:
❌ playstealth launch
❌ webauto-nodriver — ABSOLUT BANNED
❌ cua-driver click (raw index)
❌ --remote-allow-origins=* (ohne Quotes)
❌ /tmp/heypiggy-bot (fixed profile)
❌ Hardcoded PIDs
❌ pkill -f "Google Chrome"
❌ killall Google Chrome
❌ skylight-cli click --element-index
"""

import unittest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools.tool_anti_stuck import AntiStuck, check_stuck


class TestAntiStuck(unittest.TestCase):
    """Test the AntiStuck class — DOM-hash repeat detection."""

    def test_is_stuck_3x_same_hash(self):
        """After 3 identical hashes, is_stuck returns True."""
        checker = AntiStuck(threshold=3)
        self.assertFalse(checker.is_stuck("abc"))
        self.assertFalse(checker.is_stuck("abc"))
        self.assertTrue(checker.is_stuck("abc"))

    def test_not_stuck_different_hashes(self):
        """Different hashes never trigger stuck."""
        checker = AntiStuck(threshold=3)
        self.assertFalse(checker.is_stuck("abc"))
        self.assertFalse(checker.is_stuck("def"))
        self.assertFalse(checker.is_stuck("abc"))
        self.assertFalse(checker.is_stuck("def"))

    def test_reset_clears_history(self):
        """reset() clears all hash history."""
        checker = AntiStuck(threshold=3)
        checker.is_stuck("abc")
        checker.is_stuck("abc")
        checker.reset()
        self.assertFalse(checker.is_stuck("abc"))
        self.assertFalse(checker.is_stuck("abc"))
        self.assertTrue(checker.is_stuck("abc"))

    def test_count_property(self):
        """count returns consecutive identical hash count."""
        checker = AntiStuck(threshold=3)
        self.assertEqual(checker.count, 0)
        checker.is_stuck("x")
        self.assertEqual(checker.count, 1)
        checker.is_stuck("x")
        self.assertEqual(checker.count, 2)
        checker.is_stuck("x")
        self.assertEqual(checker.count, 3)

    def test_count_changes_with_different_hash(self):
        """count resets to 1 when hash changes."""
        checker = AntiStuck(threshold=3)
        checker.is_stuck("x")
        checker.is_stuck("x")
        checker.is_stuck("y")
        self.assertEqual(checker.count, 1)

    def test_threshold_5(self):
        """Custom threshold=5 needs 5 identical hashes."""
        checker = AntiStuck(threshold=5)
        for _ in range(4):
            self.assertFalse(checker.is_stuck("a"))
        self.assertTrue(checker.is_stuck("a"))

    def test_history_grows_with_hashes(self):
        """History grows for each is_stuck call (no limit enforced)."""
        checker = AntiStuck(threshold=3)
        for i in range(50):
            checker.is_stuck(f"hash{i}")
        self.assertEqual(len(checker.history), 50)


class TestCheckStuckStateless(unittest.TestCase):
    """Test the stateless check_stuck function."""

    def test_check_stuck_with_enough_history(self):
        """Stuck detected when history + current meet threshold."""
        self.assertTrue(check_stuck(["a", "a"], "a", threshold=3))

    def test_check_stuck_insufficient_history(self):
        """Not stuck when not enough history entries."""
        self.assertFalse(check_stuck(["a"], "a", threshold=3))
        self.assertFalse(check_stuck([], "a", threshold=3))

    def test_check_stuck_different_current(self):
        """Not stuck when current differs from history."""
        self.assertFalse(check_stuck(["a", "a"], "b", threshold=3))

    def test_check_stuck_custom_threshold(self):
        """Custom threshold works as expected."""
        self.assertTrue(check_stuck(["a", "a", "a", "a"], "a", threshold=5))
        self.assertFalse(check_stuck(["a", "a", "a"], "a", threshold=5))

    def test_check_stuck_returns_bool(self):
        """Always returns a bool."""
        self.assertIsInstance(check_stuck([], "x"), bool)
        self.assertIsInstance(check_stuck(["x", "x"], "x"), bool)


if __name__ == "__main__":
    unittest.main()
