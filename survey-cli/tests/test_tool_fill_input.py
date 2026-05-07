#!/usr/bin/env python3
"""Test for tool_fill_input.py — Input Field Filler with Validation Retry.

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


def _make_response(value):
    return json.dumps({"result": {"result": {"value": value}}})


class TestFillInput(unittest.TestCase):
    """Test fill() — input filling with validation retry via mocked WebSocket."""

    def setUp(self):
        self.ws_url = "ws://127.0.0.1:9999/devtools/page/mockInput"
        self._ws_patcher = patch(
            "tools.tool_fill_input.websocket.create_connection"
        )
        self.mock_create = self._ws_patcher.start()

    def tearDown(self):
        self._ws_patcher.stop()

    def _set_response(self, value):
        mock_ws = MagicMock()
        mock_ws.recv.return_value = _make_response(value)
        self.mock_create.return_value = mock_ws

    def test_fill_by_idx_success(self):
        """fill via idx returns success with value."""
        self._set_response({"success": True, "value": "25"})
        from tools.tool_fill_input import fill
        result = fill(self.ws_url, value="25", idx=0)
        self.assertTrue(result["success"])
        self.assertEqual(result["value"], "25")

    def test_fill_no_args_returns_error(self):
        """fill without idx or selector returns error."""
        from tools.tool_fill_input import fill
        result = fill(self.ws_url, value="25")
        self.assertFalse(result["success"])
        self.assertIn("required", result["error"])

    def test_fill_validation_retry_with_hint(self):
        """Validation failure with hint triggers retry with corrected value."""
        calls = []
        def recv_fn():
            calls.append(1)
            if len(calls) == 1:
                return json.dumps({"result": {"result": {"value": {
                    "error": "validation",
                    "validationMessage": "Bitte Zahl zwischen 18-65",
                    "hint": "25",
                }}}})
            else:
                return json.dumps({"result": {"result": {"value": {
                    "success": True, "value": "25",
                }}}})
        mock_ws = MagicMock()
        mock_ws.recv.side_effect = recv_fn
        self.mock_create.return_value = mock_ws
        from tools.tool_fill_input import fill
        result = fill(self.ws_url, value="3", idx=0)
        self.assertTrue(result["success"])
        self.assertEqual(result["method"], "hint_retry")

    def test_fill_by_selector_success(self):
        """fill via CSS selector returns success."""
        self._set_response({"success": True, "value": "Berlin"})
        from tools.tool_fill_input import fill
        result = fill(self.ws_url, value="Berlin", selector="#city")
        self.assertTrue(result["success"])

    def test_fill_ws_failure_returns_error(self):
        """WebSocket failure returns error dict."""
        self.mock_create.side_effect = ConnectionError("no port")
        from tools.tool_fill_input import fill
        result = fill(self.ws_url, value="test", selector="#field")
        self.assertFalse(result["success"])
        self.assertIn("no port", result["error"])

    def test_fill_no_result_returns_error(self):
        """Empty CDP response returns error."""
        # When CDP returns value=None, the code catches the .get() error
        # and returns the dict with the error message
        self._set_response(None)
        from tools.tool_fill_input import fill
        result = fill(self.ws_url, value="test", idx=0)
        self.assertFalse(result["success"])
        # Error could be the exception message or "No result"
        self.assertIn("error", result)

    def test_fill_validation_no_hint_no_retry(self):
        """Validation without hint does not trigger retry."""
        self._set_response({
            "success": False,
            "error": "validation",
            "validationMessage": "Bitte auswählen",
            "hint": None,
        })
        from tools.tool_fill_input import fill
        result = fill(self.ws_url, value="test", idx=0)
        self.assertFalse(result["success"])
        self.assertIsNone(result.get("method"))


if __name__ == "__main__":
    unittest.main()
