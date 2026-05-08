"""Tests for CashOutTrigger — cua-driver cash-out navigation.

WARUM: Jede Code-Datei braucht Tests. CashOutTrigger ist NEU.
"""

import unittest
from unittest.mock import MagicMock, patch
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestCashOutTrigger(unittest.TestCase):
    """Test CashOutTrigger.trigger() with mocked cua-driver."""

    @patch("survey.cash_out_trigger.subprocess.run")
    @patch("survey.cash_out_trigger.log_session")
    def test_trigger_success_finds_hey_piggy_window(self, mock_log, mock_run):
        from survey.cash_out_trigger import CashOutTrigger

        mock_run.side_effect = [
            MagicMock(
                stdout='{"windows": [{"pid": 71234, "window_id": 5, '
                '"title": "HeyPiggy Dashboard"}]}'
            ),
            MagicMock(
                stdout='{"tree_markdown": "[3] AXLink Auszahlung\\n[4] AXLink '
                'Umfragen\\n"}'
            ),
            MagicMock(stdout="Performed AXPress on [3]"),
        ]

        trigger = CashOutTrigger()
        result = trigger.trigger(balance_target=5.0)

        self.assertTrue(result)
        mock_log.assert_called_once_with(
            "cash_out", "triggered", {"balance_target": 5.0}
        )
        self.assertEqual(mock_run.call_count, 3)

    @patch("survey.cash_out_trigger.subprocess.run")
    def test_trigger_no_hey_piggy_window(self, mock_run):
        from survey.cash_out_trigger import CashOutTrigger

        mock_run.return_value = MagicMock(
            stdout='{"windows": [{"pid": 99999, "window_id": 1, "title": "Other App"}]}'
        )

        trigger = CashOutTrigger()
        result = trigger.trigger(balance_target=5.0)

        self.assertFalse(result)
        self.assertEqual(mock_run.call_count, 1)

    @patch("survey.cash_out_trigger.subprocess.run")
    def test_trigger_ax_tree_no_auszahlung(self, mock_run):
        from survey.cash_out_trigger import CashOutTrigger

        mock_run.side_effect = [
            MagicMock(
                stdout='{"windows": [{"pid": 71234, "window_id": 5, '
                '"title": "HeyPiggy Dashboard"}]}'
            ),
            MagicMock(
                stdout='{"tree_markdown": "[3] AXLink Einstellungen\\n[4] AXLink Profil\\n"}'
            ),
        ]

        trigger = CashOutTrigger()
        result = trigger.trigger(balance_target=5.0)

        self.assertFalse(result)
        self.assertEqual(mock_run.call_count, 2)

    @patch("survey.cash_out_trigger.subprocess.run")
    def test_trigger_subprocess_error(self, mock_run):
        from survey.cash_out_trigger import CashOutTrigger

        mock_run.side_effect = Exception("subprocess timeout")

        trigger = CashOutTrigger()
        result = trigger.trigger(balance_target=5.0)

        self.assertFalse(result)

    @patch("survey.cash_out_trigger.subprocess.run")
    @patch("survey.cash_out_trigger.log_session")
    def test_trigger_json_decode_error(self, mock_log, mock_run):
        from survey.cash_out_trigger import CashOutTrigger

        mock_run.return_value = MagicMock(stdout="not valid json{{{")
        mock_run.side_effect = None

        trigger = CashOutTrigger()
        result = trigger.trigger(balance_target=5.0)

        self.assertFalse(result)


if __name__ == "__main__":
    unittest.main()