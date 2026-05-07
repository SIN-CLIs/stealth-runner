"""Tests for CDPConnection — retry, reconnect, ID routing, backoff.

WARUM: CDPConnection ist das Herzstück der Browser-Kommunikation.
Verbindungsabbrüche, Timeout-Handling und ID-Routing müssen robust sein,
sonst bricht der gesamte Survey-Loop ab.

ARCHITEKTUR: Unittest mit unittest.mock (MagicMock, patch, call).
websocket.create_connection und recv/send werden gepatcht.
Es werden Retry-Logik, Reconnect, exponentieller Backoff und
Fehlerbehandlung getestet — kein echter WebSocket.

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
from unittest.mock import MagicMock, patch, call
import json
import websocket

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from survey.cdp_client import CDPConnection, CDPError, CDPConnectionError


# ── Helpers ────────────────────────────────────────────────────

def _make_ws_with_responses(responses: list[str]):
    """Create a fake WebSocket that returns responses in sequence."""
    ws = MagicMock()
    ws.recv.side_effect = responses
    return ws


def _make_cdp_response(msg_id: int, result: dict | None = None) -> str:
    """Create a CDP response JSON string."""
    return json.dumps({"id": msg_id, "result": result or {}})


def _make_cdp_error(msg_id: int, message: str) -> str:
    """Create a CDP error response JSON string."""
    return json.dumps({
        "id": msg_id,
        "error": {"code": -32000, "message": message}
    })


# ── Tests ──────────────────────────────────────────────────────


class TestCDPConnectionBasic(unittest.TestCase):
    """Basic send/receive with ID routing."""

    @patch("survey.cdp_client.websocket.create_connection")
    def test_simple_call_returns_result(self, mock_create):
        """call() sends CDP message and returns parsed response."""
        ws = _make_ws_with_responses([_make_cdp_response(1, {"value": 42})])
        mock_create.return_value = ws

        with CDPConnection("ws://localhost:9999/page/1") as cdp:
            result = cdp.call("Runtime.evaluate", {"expression": "42"})

        self.assertEqual(result["id"], 1)
        self.assertEqual(result["result"]["value"], 42)

        # Verify correct CDP message format
        sent_json = ws.send.call_args[0][0]
        sent = json.loads(sent_json)
        self.assertEqual(sent["method"], "Runtime.evaluate")
        self.assertEqual(sent["params"]["expression"], "42")

    @patch("survey.cdp_client.websocket.create_connection")
    def test_call_result_returns_result_dict(self, mock_create):
        """call_result() extracts the 'result' key."""
        ws = _make_ws_with_responses([_make_cdp_response(1, {"status": "ok"})])
        mock_create.return_value = ws

        with CDPConnection("ws://localhost:9999/page/1") as cdp:
            result = cdp.call_result("Page.enable")

        self.assertEqual(result, {"status": "ok"})

    @patch("survey.cdp_client.websocket.create_connection")
    def test_id_increments_correctly(self, mock_create):
        """Each call gets a unique ID."""
        responses = [
            _make_cdp_response(1, {"a": 1}),
            _make_cdp_response(2, {"b": 2}),
            _make_cdp_response(3, {"c": 3}),
        ]
        ws = _make_ws_with_responses(responses)
        mock_create.return_value = ws

        with CDPConnection("ws://localhost:9999/page/1") as cdp:
            r1 = cdp.call("Method1")
            r2 = cdp.call("Method2")
            r3 = cdp.call("Method3")

        self.assertEqual(r1["id"], 1)
        self.assertEqual(r2["id"], 2)
        self.assertEqual(r3["id"], 3)

    @patch("survey.cdp_client.websocket.create_connection")
    def test_skips_event_messages(self, mock_create):
        """recv_until_id skips messages without 'id' (events)."""
        responses = [
            json.dumps({"method": "Page.loadEventFired", "params": {}}),  # event
            _make_cdp_response(1, {"value": "done"}),
        ]
        ws = _make_ws_with_responses(responses)
        mock_create.return_value = ws

        with CDPConnection("ws://localhost:9999/page/1") as cdp:
            result = cdp.call("Runtime.evaluate")

        self.assertEqual(result["result"]["value"], "done")
        self.assertEqual(ws.recv.call_count, 2)  # event + response

    @patch("survey.cdp_client.websocket.create_connection")
    def test_skips_responses_for_other_ids(self, mock_create):
        """recv_until_id skips responses with non-matching IDs."""
        responses = [
            _make_cdp_response(99, {"x": "other"}),  # wrong ID
            _make_cdp_response(1, {"x": "mine"}),
        ]
        ws = _make_ws_with_responses(responses)
        mock_create.return_value = ws

        with CDPConnection("ws://localhost:9999/page/1") as cdp:
            result = cdp.call("GetMine")

        self.assertEqual(result["result"]["x"], "mine")


class TestCDPConnectionError(unittest.TestCase):
    """CDP command errors and connection failures."""

    @patch("survey.cdp_client.websocket.create_connection")
    def test_raises_cdp_error_on_server_error(self, mock_create):
        """CDP server error → CDPError raised."""
        ws = _make_ws_with_responses([_make_cdp_error(1, "Target not found")])
        mock_create.return_value = ws

        with CDPConnection("ws://localhost:9999/page/1") as cdp:
            with self.assertRaises(CDPError):
                cdp.call("BadMethod")

    @patch("survey.cdp_client.websocket.create_connection")
    def test_raises_connection_error_on_connect_failure(self, mock_create):
        """connect() fails → CDPConnectionError after retries."""
        mock_create.side_effect = OSError("Connection refused")

        with self.assertRaises(CDPConnectionError):
            cdp = CDPConnection("ws://bad", max_retries=3)
            cdp.connect()


class TestCDPConnectionRetry(unittest.TestCase):
    """Retry logic with exponential backoff."""

    @patch("time.sleep", return_value=None)
    @patch("survey.cdp_client.websocket.create_connection")
    def test_retries_on_send_failure(self, mock_create, mock_sleep):
        """Retries on WebSocket send/recv failure."""
        # First attempt: WebSocket exception on send
        # Second attempt: success
        ws1 = MagicMock()
        ws1.send.side_effect = websocket.WebSocketException("Broken pipe")

        from survey.cdp_client import websocket as ws_mod
        ws2 = _make_ws_with_responses([_make_cdp_response(1, {"ok": True})])

        mock_create.side_effect = [ws1, ws2]

        # connect() uses the first WS
        cdp = CDPConnection("ws://localhost:9999/page/1", max_retries=3)
        cdp.connect()

        # call() fails on ws1, reconnects with ws2
        result = cdp.call("Runtime.evaluate")
        self.assertEqual(result["result"]["ok"], True)
        self.assertEqual(mock_create.call_count, 2)  # initial + retry
        mock_sleep.assert_called()  # Backoff was applied

    @patch("time.sleep", return_value=None)
    @patch("survey.cdp_client.websocket.create_connection")
    def test_no_such_target_triggers_reconnect(self, mock_create, mock_sleep):
        """'No such target id' → reconnects with new URL."""
        # First WS: connection OK but call raises WebSocketException.
        ws1 = MagicMock()
        ws1.send.side_effect = websocket.WebSocketException("No such target id: 42")
        ws1.recv.return_value = _make_cdp_response(1, {"ok": True})

        ws2 = _make_ws_with_responses([_make_cdp_response(1, {"ok": True})])

        mock_create.side_effect = [ws1, ws2]

        reconnect_url = "ws://localhost:9999/page/new_tab"
        cdp = CDPConnection(
            "ws://localhost:9999/page/old_tab",
            max_retries=3,
            reconnect_url_fn=lambda: reconnect_url,
        )
        cdp.connect()

        result = cdp.call("Runtime.evaluate")
        self.assertEqual(result["result"]["ok"], True)
        self.assertEqual(cdp.ws_url, reconnect_url)  # URL was updated

    @patch("time.sleep", return_value=None)
    @patch("survey.cdp_client.websocket.create_connection")
    def test_max_retries_exceeded_raises(self, mock_create, mock_sleep):
        """After max_retries failed attempts → CDPConnectionError."""
        ws = MagicMock()
        ws.send.side_effect = websocket.WebSocketException("Fail")
        mock_create.return_value = ws

        cdp = CDPConnection("ws://localhost:9999/page/1", max_retries=3)
        cdp.connect()

        with self.assertRaises(CDPConnectionError):
            cdp.call("Runtime.evaluate")

        self.assertEqual(mock_create.call_count, 3)  # initial + 2 retries

    @patch("time.sleep", return_value=None)
    @patch("survey.cdp_client.websocket.create_connection")
    def test_disable_retry_with_flag(self, mock_create, mock_sleep):
        """retry=False disables retry — fails immediately."""
        ws = MagicMock()
        ws.send.side_effect = websocket.WebSocketException("Fail")
        mock_create.return_value = ws

        cdp = CDPConnection("ws://localhost:9999/page/1", max_retries=3)
        cdp.connect()

        with self.assertRaises(CDPConnectionError):
            cdp.call("Runtime.evaluate", retry=False)

        self.assertEqual(mock_create.call_count, 1)  # No retry


class TestCDPConnectionClose(unittest.TestCase):
    """Connection close and cleanup."""

    @patch("survey.cdp_client.websocket.create_connection")
    def test_context_manager_closes_connection(self, mock_create):
        """__exit__ closes the connection."""
        ws = _make_ws_with_responses([_make_cdp_response(1, {})])
        mock_create.return_value = ws

        with CDPConnection("ws://localhost:9999/page/1") as cdp:
            cdp.call("Test")

        ws.close.assert_called_once()

    @patch("survey.cdp_client.websocket.create_connection")
    def test_close_is_idempotent(self, mock_create):
        """Multiple close calls don't crash."""
        ws = MagicMock()
        mock_create.return_value = ws

        cdp = CDPConnection("ws://localhost:9999/page/1")
        cdp.connect()
        cdp.close()
        cdp.close()  # Should not raise

    @patch("survey.cdp_client.websocket.create_connection")
    def test_close_tolerates_ws_error(self, mock_create):
        """close() handles WebSocket errors gracefully."""
        ws = MagicMock()
        ws.close.side_effect = websocket.WebSocketException("Already closed")
        mock_create.return_value = ws

        cdp = CDPConnection("ws://localhost:9999/page/1")
        cdp.connect()
        cdp.close()  # Should not raise


class TestCDPConnectionBackoff(unittest.TestCase):
    """Exponential backoff timing."""

    @patch("survey.cdp_client.websocket.create_connection")
    def test_exponential_backoff_respected(self, mock_create):
        """Backoff: 0.3 → 0.6 → 1.2 → 2.4 → 5.0 (max)."""
        ws = MagicMock()
        ws.send.side_effect = websocket.WebSocketException("Fail")
        mock_create.return_value = ws

        cdp = CDPConnection(
            "ws://localhost:9999/page/1",
            max_retries=6,
            backoff_base=0.3,
            backoff_max=5.0,
        )
        cdp.connect()

        with patch("time.sleep") as mock_sleep:
            with self.assertRaises(CDPConnectionError):
                cdp.call("Runtime.evaluate")

        # Check sleep durations (5 retries → 5 sleeps)
        expected_waits = [0.3, 0.6, 1.2, 2.4, 4.8]  # 0.3 * 2^4 = 4.8 (capped)
        actual_waits = [c[0][0] for c in mock_sleep.call_args_list]

        # The first sleep might include 0 for the connection attempt
        # Filter to only the retry sleeps
        retry_waits = [w for w in actual_waits if w > 0]
        self.assertEqual(len(retry_waits), 5)
        for expected, actual in zip(expected_waits, retry_waits):
            self.assertAlmostEqual(expected, actual, delta=0.01)


if __name__ == "__main__":
    unittest.main()