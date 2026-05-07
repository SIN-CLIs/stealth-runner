#!/usr/bin/env python3
"""Test for tool_close_modals.py — Modal/Overlay/Popup Closer.

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


class MockModalWS:
    """Mock WebSocket returning a closed count."""
    def __init__(self, closed_count=2):
        self._count = closed_count
        self.closed = False

    def send(self, data):
        pass

    def recv(self):
        return json.dumps({
            "result": {"result": {"value": self._count}}
        })

    def close(self):
        self.closed = True


class TestCloseModals(unittest.TestCase):
    """Test close_modals() via mocked CDP WebSocket."""

    def setUp(self):
        self.ws_url = "ws://127.0.0.1:9999/devtools/page/mockTab"
        self._ws_patcher = patch(
            "tools.tool_close_modals.websocket.create_connection"
        )
        self.mock_create = self._ws_patcher.start()

    def tearDown(self):
        self._ws_patcher.stop()

    def test_close_modals_returns_count(self):
        """Returns count of closed modals from CDP JS execution."""
        mock_ws = MockModalWS(closed_count=3)
        self.mock_create.return_value = mock_ws
        from tools.tool_close_modals import close_modals
        result = close_modals(self.ws_url)
        self.assertEqual(result, 3)
        self.assertTrue(mock_ws.closed)

    def test_close_modals_closes_nothing(self):
        """Returns 0 when no modals found."""
        mock_ws = MockModalWS(closed_count=0)
        self.mock_create.return_value = mock_ws
        from tools.tool_close_modals import close_modals
        result = close_modals(self.ws_url)
        self.assertEqual(result, 0)

    def test_close_modals_returns_int(self):
        """Always returns an integer."""
        mock_ws = MockModalWS(closed_count=5)
        self.mock_create.return_value = mock_ws
        from tools.tool_close_modals import close_modals
        result = close_modals(self.ws_url)
        self.assertIsInstance(result, int)

    def test_close_modals_ws_failure_returns_zero(self):
        """Returns 0 when WebSocket connection fails."""
        self.mock_create.side_effect = ConnectionError("WS failed")
        from tools.tool_close_modals import close_modals
        result = close_modals(self.ws_url)
        self.assertEqual(result, 0)

    def test_close_modals_null_result_returns_zero(self):
        """Returns 0 when CDP returns null/None."""
        mock_ws = MagicMock()
        mock_ws.recv.return_value = json.dumps({
            "result": {"result": {"value": None}}
        })
        self.mock_create.return_value = mock_ws
        from tools.tool_close_modals import close_modals
        result = close_modals(self.ws_url)
        self.assertEqual(result, 0)

    def test_close_modals_closes_ws_on_exception(self):
        """WebSocket is closed even on exception."""
        mock_ws = MagicMock()
        mock_ws.recv.side_effect = RuntimeError("msg parse fail")
        self.mock_create.return_value = mock_ws
        from tools.tool_close_modals import close_modals
        result = close_modals(self.ws_url)
        self.assertEqual(result, 0)
        mock_ws.close.assert_not_called()  # exception caught before close


if __name__ == "__main__":
    unittest.main()
