"""Tests for CashOutTrigger — cua-driver cash-out navigation.

WARUM: Jede Code-Datei braucht Tests. CashOutTrigger ist NEU.

CEO-WAVE-1 / SR-237 added idempotency-ledger semantics on top of the
original tests. The ledger fixture isolates each test in its own tmp
STATE_DIR so concurrent test runs do not see each other's entries.
"""

import json
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class _IsolatedLedgerMixin:
    """Mixin: every test gets a fresh STATE_DIR -> fresh ledger."""

    def setUp(self):  # type: ignore[override]
        self._tmp = TemporaryDirectory()
        self._old_state_dir = os.environ.get("STATE_DIR")
        os.environ["STATE_DIR"] = self._tmp.name

    def tearDown(self):  # type: ignore[override]
        if self._old_state_dir is None:
            os.environ.pop("STATE_DIR", None)
        else:
            os.environ["STATE_DIR"] = self._old_state_dir
        self._tmp.cleanup()

    def _ledger_entries(self) -> list[dict]:
        path = Path(self._tmp.name) / "cash_out_ledger.jsonl"
        if not path.exists():
            return []
        return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


class TestCashOutTrigger(_IsolatedLedgerMixin, unittest.TestCase):
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

        # Ledger contract: exactly one success row for the canonical key.
        entries = self._ledger_entries()
        successes = [e for e in entries if e.get("status") == "success"]
        self.assertEqual(len(successes), 1)
        self.assertEqual(successes[0]["key"], "cash_out:5.00")

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

        # Ledger should record the failure, NOT a success.
        entries = self._ledger_entries()
        self.assertTrue(entries)
        self.assertEqual(entries[-1]["status"], "no-window")

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

        entries = self._ledger_entries()
        self.assertEqual(entries[-1]["status"], "no-target")

    @patch("survey.cash_out_trigger.subprocess.run")
    def test_trigger_subprocess_error(self, mock_run):
        from survey.cash_out_trigger import CashOutTrigger

        mock_run.side_effect = Exception("subprocess timeout")

        trigger = CashOutTrigger()
        result = trigger.trigger(balance_target=5.0)

        self.assertFalse(result)

        entries = self._ledger_entries()
        self.assertEqual(entries[-1]["status"], "error")
        self.assertIn("subprocess timeout", entries[-1].get("error", ""))

    @patch("survey.cash_out_trigger.subprocess.run")
    @patch("survey.cash_out_trigger.log_session")
    def test_trigger_json_decode_error(self, mock_log, mock_run):
        from survey.cash_out_trigger import CashOutTrigger

        mock_run.return_value = MagicMock(stdout="not valid json{{{")
        mock_run.side_effect = None

        trigger = CashOutTrigger()
        result = trigger.trigger(balance_target=5.0)

        self.assertFalse(result)


class TestCashOutIdempotency(_IsolatedLedgerMixin, unittest.TestCase):
    """SR-237: idempotency contract for the cash-out side effect."""

    def _stub_success(self) -> list[MagicMock]:
        return [
            MagicMock(
                stdout='{"windows": [{"pid": 71234, "window_id": 5, '
                '"title": "HeyPiggy Dashboard"}]}'
            ),
            MagicMock(
                stdout='{"tree_markdown": "[3] AXLink Auszahlung\\n"}'
            ),
            MagicMock(stdout="Performed AXPress on [3]"),
        ]

    @patch("survey.cash_out_trigger.subprocess.run")
    @patch("survey.cash_out_trigger.log_session")
    def test_second_call_with_same_key_is_replay_skip(self, mock_log, mock_run):
        from survey.cash_out_trigger import CashOutTrigger

        # First call: actual side effect. Three subprocess calls.
        mock_run.side_effect = self._stub_success()
        first = CashOutTrigger().trigger(balance_target=5.0)
        self.assertTrue(first)
        self.assertEqual(mock_run.call_count, 3)

        # Second call with the SAME key: short-circuit BEFORE any
        # subprocess.run. Returns True (idempotency contract: caller saw
        # success the first time, must see success again).
        mock_run.reset_mock()
        mock_run.side_effect = self._stub_success()  # would be used if it ran
        second = CashOutTrigger().trigger(balance_target=5.0)
        self.assertTrue(second)
        self.assertEqual(
            mock_run.call_count, 0,
            "second trigger() with the same key MUST NOT call cua-driver again",
        )

        # Ledger contract: one 'success', one 'replay-skip'.
        entries = self._ledger_entries()
        statuses = [e["status"] for e in entries]
        self.assertEqual(statuses.count("success"), 1)
        self.assertEqual(statuses.count("replay-skip"), 1)

        # log_session was called for the first trigger (triggered) and
        # the second trigger (replay-skip).
        actions = [c.args[1] for c in mock_log.call_args_list]
        self.assertIn("triggered", actions)
        self.assertIn("replay-skip", actions)

    @patch("survey.cash_out_trigger.subprocess.run")
    def test_failure_does_not_block_future_attempts(self, mock_run):
        from survey.cash_out_trigger import CashOutTrigger

        # First call fails (no HeyPiggy window).
        mock_run.return_value = MagicMock(
            stdout='{"windows": [{"pid": 99, "window_id": 1, "title": "Other"}]}'
        )
        first = CashOutTrigger().trigger(balance_target=5.0)
        self.assertFalse(first)

        # Second call must NOT short-circuit — failures don't lock the
        # key. Stub a success this time.
        mock_run.reset_mock()
        mock_run.side_effect = [
            MagicMock(
                stdout='{"windows": [{"pid": 71234, "window_id": 5, '
                '"title": "HeyPiggy Dashboard"}]}'
            ),
            MagicMock(stdout='{"tree_markdown": "[3] AXLink Auszahlung\\n"}'),
            MagicMock(stdout="Performed AXPress on [3]"),
        ]
        second = CashOutTrigger().trigger(balance_target=5.0)
        self.assertTrue(second)
        self.assertEqual(mock_run.call_count, 3)

    @patch("survey.cash_out_trigger.subprocess.run")
    def test_explicit_idempotency_key_overrides_default(self, mock_run):
        from survey.cash_out_trigger import CashOutTrigger

        # Run once with a custom key, succeed.
        mock_run.side_effect = self._stub_success()
        ok = CashOutTrigger().trigger(
            balance_target=5.0, idempotency_key="custom-key-A"
        )
        self.assertTrue(ok)

        # Second call with the SAME custom key short-circuits.
        mock_run.reset_mock()
        mock_run.side_effect = self._stub_success()
        replayed = CashOutTrigger().trigger(
            balance_target=5.0, idempotency_key="custom-key-A"
        )
        self.assertTrue(replayed)
        self.assertEqual(mock_run.call_count, 0)

        # A different custom key with the same balance_target must NOT
        # short-circuit — keys are the dedup boundary, not the target.
        mock_run.reset_mock()
        mock_run.side_effect = self._stub_success()
        other = CashOutTrigger().trigger(
            balance_target=5.0, idempotency_key="custom-key-B"
        )
        self.assertTrue(other)
        self.assertEqual(mock_run.call_count, 3)

    @patch("survey.cash_out_trigger.subprocess.run")
    def test_account_namespacing_separates_keys(self, mock_run):
        from survey.cash_out_trigger import CashOutTrigger

        mock_run.side_effect = self._stub_success()
        a1 = CashOutTrigger().trigger(balance_target=5.0, account="user-a")
        self.assertTrue(a1)

        # Same target, different account → different key, no short-circuit.
        mock_run.reset_mock()
        mock_run.side_effect = self._stub_success()
        b1 = CashOutTrigger().trigger(balance_target=5.0, account="user-b")
        self.assertTrue(b1)
        self.assertEqual(mock_run.call_count, 3)

        # Same account again → short-circuit.
        mock_run.reset_mock()
        a2 = CashOutTrigger().trigger(balance_target=5.0, account="user-a")
        self.assertTrue(a2)
        self.assertEqual(mock_run.call_count, 0)

    def test_corrupt_ledger_line_does_not_block_attempts(self):
        """A garbled line on disk must not be a foot-gun: the next
        attempt should run, not refuse."""
        from survey.cash_out_trigger import _has_successful_attempt, _ledger_path

        path = _ledger_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            'this is not json\n'
            '{"key": "cash_out:5.00", "status": "error"}\n'
        )

        # No success row → must report False even with a corrupt line.
        self.assertFalse(_has_successful_attempt("cash_out:5.00"))

    def test_default_key_is_balance_rounded_to_two_decimals(self):
        from survey.cash_out_trigger import _default_idempotency_key

        # Two equivalent representations of the same target collapse.
        self.assertEqual(
            _default_idempotency_key(5.00),
            _default_idempotency_key(5.0),
        )
        self.assertEqual(
            _default_idempotency_key(5.005),
            "cash_out:5.00",
        )
        self.assertEqual(
            _default_idempotency_key(5.0, account="acc-1"),
            "acc-1:cash_out:5.00",
        )


if __name__ == "__main__":
    unittest.main()
