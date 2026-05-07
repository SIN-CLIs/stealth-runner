#!/usr/bin/env python3
"""Test for tool_select_language.py — Language Selector.

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


class TestSelectLanguage(unittest.TestCase):
    """Test select_language() via mocked CDP WebSocket."""

    def setUp(self):
        self.ws_url = "ws://127.0.0.1:9999/devtools/page/mockLang"
        self._ws_patcher = patch(
            "tools.tool_select_language.websocket.create_connection"
        )
        self.mock_create = self._ws_patcher.start()

    def tearDown(self):
        self._ws_patcher.stop()

    def _set_response(self, value):
        mock_ws = MagicMock()
        mock_ws.recv.return_value = json.dumps({
            "result": {"result": {"value": value}}
        })
        self.mock_create.return_value = mock_ws

    def test_select_language_select_method(self):
        """Dropdown <select> method returns success."""
        self._set_response({
            "success": True,
            "method": "select",
            "value": "Deutsch"
        })
        from tools.tool_select_language import select_language
        result = select_language(self.ws_url, "Deutsch")
        self.assertTrue(result["success"])
        self.assertEqual(result["method"], "select")

    def test_select_language_radio_method(self):
        """Radio button method returns success."""
        self._set_response({
            "success": True,
            "method": "radio",
            "value": "deutsch"
        })
        from tools.tool_select_language import select_language
        result = select_language(self.ws_url, "Deutsch")
        self.assertTrue(result["success"])
        self.assertEqual(result["method"], "radio")

    def test_select_language_text_match_method(self):
        """Text-match fallback returns success."""
        self._set_response({
            "success": True,
            "method": "text_match",
            "value": "deutsch"
        })
        from tools.tool_select_language import select_language
        result = select_language(self.ws_url, "DEUTSCH")
        self.assertTrue(result["success"])
        self.assertEqual(result["method"], "text_match")

    def test_select_language_not_found(self):
        """Language not found returns error."""
        self._set_response({
            "success": False,
            "error": "Language not found: english"
        })
        from tools.tool_select_language import select_language
        result = select_language(self.ws_url, "English")
        self.assertFalse(result["success"])
        self.assertIn("not found", result["error"])

    def test_select_language_ws_failure(self):
        """WebSocket failure returns error."""
        self.mock_create.side_effect = ConnectionError("no")
        from tools.tool_select_language import select_language
        result = select_language(self.ws_url, "Deutsch")
        self.assertFalse(result["success"])
        self.assertIn("no", result["error"])

    def test_select_language_no_result(self):
        """Empty CDP response returns error."""
        mock_ws = MagicMock()
        mock_ws.recv.return_value = json.dumps({
            "result": {"result": {"value": None}}
        })
        self.mock_create.return_value = mock_ws
        from tools.tool_select_language import select_language
        result = select_language(self.ws_url, "Deutsch")
        self.assertFalse(result["success"])
        self.assertIn("No result", result["error"])

    def test_select_language_ws_closed_after_call(self):
        """WebSocket is closed after successful call."""
        mock_ws = MagicMock()
        mock_ws.recv.return_value = json.dumps({
            "result": {"result": {"value": {
                "success": True, "method": "select", "value": "Deutsch"
            }}}
        })
        self.mock_create.return_value = mock_ws
        from tools.tool_select_language import select_language
        select_language(self.ws_url)
        mock_ws.close.assert_called()

    def test_select_language_default_german(self):
        """Default language is Deutsch."""
        self._set_response({
            "success": True, "method": "select", "value": "Deutsch"
        })
        from tools.tool_select_language import select_language
        result = select_language(self.ws_url)
        self.assertTrue(result["success"])

    def test_select_language_returns_dict(self):
        """Always returns a dict."""
        self._set_response({"success": True, "method": "select", "value": "test"})
        from tools.tool_select_language import select_language
        result = select_language(self.ws_url, "Test")
        self.assertIsInstance(result, dict)
        self.assertIn("success", result)


if __name__ == "__main__":
    unittest.main()
