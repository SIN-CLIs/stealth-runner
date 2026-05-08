"""Tests for BalanceTracker — balance reading + earnings calculation.

WARUM: Jede Code-Datei braucht Tests (Archäologie-Tsunami Regel #6).
BalanceTracker ist ein NEUES Modul — ohne Tests würde der nächste
Agent es kaputt machen.

BANNED METHODS — NIEMALS VERWENDEN:
  ❌ playstealth launch
  ❌ webauto-nodriver — ABSOLUT BANNED
"""

import unittest
from unittest.mock import patch
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from survey.balance_tracker import BalanceTracker


class TestReadBalance(unittest.TestCase):
    """Tests for BalanceTracker.read_balance() — delegates to scanner."""

    @patch("survey.balance_tracker.read_balance_with_backoff")
    def test_reads_balance(self, mock_read):
        mock_read.return_value = 3.45
        tracker = BalanceTracker(cdp_port=9999)
        self.assertEqual(tracker.read_balance(), 3.45)
        mock_read.assert_called_once_with(9999)

    @patch("survey.balance_tracker.read_balance_with_backoff")
    def test_read_failure_returns_zero(self, mock_read):
        mock_read.side_effect = Exception("CDP down")
        tracker = BalanceTracker(debug=False)
        self.assertEqual(tracker.read_balance(), 0.0)

    @patch("survey.balance_tracker.read_balance_with_backoff")
    def test_debug_prints(self, mock_read):
        mock_read.return_value = 2.00
        tracker = BalanceTracker(debug=True)
        # Should not raise
        tracker.read_balance()


class TestCalculateEarned(unittest.TestCase):
    """Tests for BalanceTracker.calculate_earned() — pure math."""

    def test_positive_earnings(self):
        self.assertEqual(BalanceTracker.calculate_earned(2.00, 3.50), 1.50)

    def test_zero_earnings(self):
        self.assertEqual(BalanceTracker.calculate_earned(5.00, 5.00), 0.0)

    def test_negative_clamped_to_zero(self):
        self.assertEqual(BalanceTracker.calculate_earned(5.00, 4.00), 0.0)

    def test_rounding(self):
        self.assertEqual(BalanceTracker.calculate_earned(1.111, 2.222), 1.11)


if __name__ == "__main__":
    unittest.main()
