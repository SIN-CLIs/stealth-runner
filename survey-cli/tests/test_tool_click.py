#!/usr/bin/env python3
"""Test for tool_click.py — Click Tool with find + verify + retry.

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
from unittest.mock import patch, MagicMock
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

MOCK_MARKDOWN = """
- [42] AXButton ('Weiter')
- [43] AXButton ('Weitere Informationen')
- [10] AXTextField ('Email')
- [11] AXRadioButton ('Männlich')
"""


class TestClickCore(unittest.TestCase):
    """Test click() — element finding + cua-driver click + verify."""

    def setUp(self):
        self._run_patcher = patch("tools.tool_click.subprocess.run")
        self.mock_run = self._run_patcher.start()
        self._sleep_patcher = patch("tools.tool_click.time.sleep")
        self.mock_sleep = self._sleep_patcher.start()

    def tearDown(self):
        self._run_patcher.stop()
        self._sleep_patcher.stop()

    def _set_get_state(self, markdown=""):
        """Configure subprocess.run for get_window_state and click."""

        def _run_side_effect(cmd, **kwargs):
            result = MagicMock()
            result.returncode = 0
            result.stderr = ""
            cmd_str = " ".join(str(c) for c in cmd)
            if "get_window_state" in cmd_str:
                result.stdout = json.dumps({"tree_markdown": markdown or MOCK_MARKDOWN})
            elif "click" in cmd_str:
                result.stdout = "✓ Performed AXPress"
            elif "press_key" in cmd_str:
                result.stdout = "key pressed"
            elif "set_value" in cmd_str:
                result.stdout = "Set AXValue"
            return result

        self.mock_run.side_effect = _run_side_effect

    def test_click_by_index(self):
        """click() with element_index skips find_element."""
        self._set_get_state()
        from tools.tool_click import click

        result = click(pid=12345, wid=100, element_index=99, verify=False)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["element_index"], 99)

    def test_click_verify_enabled_checks_state(self):
        """click with verify=True resets AX-Tree after click."""
        from tools.tool_click import _verify_click

        result = _verify_click(
            pid=12345, wid=100, element_index=42, role="AXButton", label="Weiter"
        )
        self.assertIsInstance(result, bool)

    def test_click_verify_link_always_true(self):
        """AXLink verification always returns True."""
        self._set_get_state()
        from tools.tool_click import _verify_click

        result = _verify_click(pid=12345, wid=100, element_index=54, role="AXLink", label="Google")
        self.assertTrue(result)

    def test_click_raw_performed(self):
        """_click_raw returns True when cua-driver outputs 'Performed'."""
        result_mock = MagicMock()
        result_mock.stdout = "✓ Performed AXPress on [42] AXButton"
        result_mock.returncode = 0
        self.mock_run.return_value = result_mock
        from tools.tool_click import _click_raw

        self.assertTrue(_click_raw(12345, 100, 42))

    def test_click_raw_failure(self):
        """_click_raw returns False on failure."""
        result_mock = MagicMock()
        result_mock.stdout = "FAIL"
        result_mock.returncode = 1
        self.mock_run.return_value = result_mock
        from tools.tool_click import _click_raw

        self.assertFalse(_click_raw(12345, 100, 42))

    def test_click_raw_exception(self):
        """_click_raw returns False on exception."""
        self.mock_run.side_effect = RuntimeError("subprocess bomb")
        from tools.tool_click import _click_raw

        self.assertFalse(_click_raw(12345, 100, 42))

    def test_get_state_returns_markdown(self):
        """_get_state returns tree_markdown from cua-driver."""
        result_mock = MagicMock()
        result_mock.stdout = json.dumps({"tree_markdown": "- [1] AXButton ('Test')"})
        result_mock.returncode = 0
        self.mock_run.return_value = result_mock
        from tools.tool_click import _get_state

        md = _get_state(12345, 100)
        self.assertIn("AXButton", md)

    def test_get_state_failure_returns_empty(self):
        """_get_state returns empty string on failure."""
        result_mock = MagicMock()
        result_mock.returncode = 1
        self.mock_run.return_value = result_mock
        from tools.tool_click import _get_state

        self.assertEqual(_get_state(12345, 100), "")

    def test_press_key_success(self):
        """press_key() succeeds."""
        result_mock = MagicMock()
        result_mock.stdout = "key pressed"
        result_mock.returncode = 0
        self.mock_run.return_value = result_mock
        from tools.tool_click import press_key

        result = press_key(pid=12345, key="return")
        self.assertEqual(result["status"], "ok")

    def test_press_key_failure(self):
        """press_key() returns error on failure."""
        result_mock = MagicMock()
        result_mock.stdout = ""
        result_mock.stderr = "key error"
        result_mock.returncode = 1
        self.mock_run.return_value = result_mock
        from tools.tool_click import press_key

        result = press_key(pid=12345, key="return")
        self.assertEqual(result["status"], "error")

    def test_press_key_exception(self):
        """press_key() catches exceptions gracefully."""
        self.mock_run.side_effect = RuntimeError("subprocess bomb")
        from tools.tool_click import press_key

        result = press_key(pid=12345, key="return")
        self.assertEqual(result["status"], "error")


if __name__ == "__main__":
    unittest.main()
