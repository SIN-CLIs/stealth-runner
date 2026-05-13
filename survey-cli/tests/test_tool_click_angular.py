#!/usr/bin/env python3
"""Test for tool_click_angular.py — CDP Mouse Events.

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
from unittest.mock import patch
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class MockWebSocket:
    """Mock CDP WebSocket that returns shaped responses."""
    def __init__(self, coords=None, error=None):
        self.coords = coords or {"x": 100.0, "y": 200.0, "tag": "BUTTON"}
        self.error = error
        self.sent = []
        self.closed = False

    def send(self, data):
        self.sent.append(json.loads(data))

    def recv(self):
        msg_id = self.sent[-1]["id"] if self.sent else 1
        if msg_id == 1:
            if self.error:
                resp = {"result": {"result": {"value": None}}}
            else:
                resp = {"result": {"result": {"value": self.coords}}}
        else:
            resp = {"result": {}}
        return json.dumps(resp)

    def close(self):
        self.closed = True


class TestClickAngular(unittest.TestCase):
    """Test CDP mouse event click via mocked WebSocket."""

    def setUp(self):
        self.ws_url = "ws://127.0.0.1:9999/devtools/page/mock123"
        self._ws_patcher = patch(
            "tools.tool_click_angular.websocket.create_connection"
        )
        self.mock_create = self._ws_patcher.start()

    def tearDown(self):
        self._ws_patcher.stop()

    def test_click_by_idx_success(self):
        """"click via idx returns success with coords."""
        mock_ws = MockWebSocket()
        self.mock_create.return_value = mock_ws
        from tools.tool_click_angular import click
        result = click(self.ws_url, idx=5)
        self.assertTrue(result["success"])
        self.assertEqual(result["method"], "cdp_mouse")
        self.assertEqual(result["coords"], [100.0, 200.0])
        self.assertTrue(mock_ws.closed)

    def test_click_by_selector_success(self):
        """click via CSS selector returns success."""
        mock_ws = MockWebSocket(coords={"x": 50.0, "y": 60.0, "tag": "A"})
        self.mock_create.return_value = mock_ws
        from tools.tool_click_angular import click
        result = click(self.ws_url, selector=".NextButton")
        self.assertTrue(result["success"])
        self.assertEqual(result["coords"], [50.0, 60.0])

    def test_click_by_text_success(self):
        """click via text matching returns success."""
        mock_ws = MockWebSocket()
        self.mock_create.return_value = mock_ws
        from tools.tool_click_angular import click
        result = click(self.ws_url, text="Weiter")
        self.assertTrue(result["success"])

    def test_click_no_args_returns_error(self):
        """click without idx/selector/text returns error."""
        mock_ws = MockWebSocket()
        self.mock_create.return_value = mock_ws
        from tools.tool_click_angular import click
        result = click(self.ws_url)
        self.assertFalse(result["success"])
        self.assertIn("required", result["error"])

    def test_click_element_not_found(self):
        """click returns error when element not in DOM."""
        mock_ws = MockWebSocket(error=True)
        self.mock_create.return_value = mock_ws
        from tools.tool_click_angular import click
        result = click(self.ws_url, idx=999)
        self.assertFalse(result["success"])
        self.assertIn("not found", result["error"])

    def test_click_ws_connection_failure(self):
        """click handles WebSocket connection failure gracefully."""
        self.mock_create.side_effect = ConnectionRefusedError("port dead")
        from tools.tool_click_angular import click
        result = click(self.ws_url, selector=".btn")
        self.assertFalse(result["success"])
        self.assertIn("port dead", result["error"])

    def test_click_sends_correct_mouse_events(self):
        """Three CDP mouse events dispatched: move, press, release."""
        mock_ws = MockWebSocket()
        self.mock_create.return_value = mock_ws
        from tools.tool_click_angular import click
        click(self.ws_url, idx=0)
        methods = [s["method"] for s in mock_ws.sent]
        self.assertIn("Runtime.evaluate", methods)
        self.assertIn("Input.dispatchMouseEvent", methods)
        self.assertEqual(methods.count("Input.dispatchMouseEvent"), 3)


if __name__ == "__main__":
    unittest.main()
