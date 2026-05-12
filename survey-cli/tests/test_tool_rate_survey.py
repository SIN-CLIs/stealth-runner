#!/usr/bin/env python3
"""Test for tool_rate_survey.py — Survey Rating Tool.

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


class TestRateSurvey(unittest.TestCase):
    """Test rate_survey() — rating completed surveys."""

    def setUp(self):
        self._urlopen_patcher = patch("tools.tool_rate_survey.urllib.request.urlopen")
        self.mock_urlopen = self._urlopen_patcher.start()
        self._sleep_patcher = patch("tools.tool_rate_survey.time.sleep")
        self.mock_sleep = self._sleep_patcher.start()

    def tearDown(self):
        self._urlopen_patcher.stop()
        self._sleep_patcher.stop()

    def _set_pages(self, pages):
        mock = MagicMock()
        mock.read.return_value = json.dumps(pages).encode()
        self.mock_urlopen.return_value = mock

    def test_rate_survey_not_found(self):
        """Returns 'not_found' when no rating page detected."""
        self._set_pages(
            [
                {"id": "tab1", "url": "https://heypiggy.com/dashboard", "type": "page"},
            ]
        )
        from tools.tool_rate_survey import rate_survey

        result = rate_survey()
        self.assertEqual(result["status"], "not_found")

    def test_rate_survey_no_ws_url_error(self):
        """Rating tab without WebSocket URL returns error."""
        self._set_pages(
            [
                {
                    "id": "tab2",
                    "url": "https://www.cpx-research.com/rating.php",
                    "type": "page",
                    "webSocketDebuggerUrl": None,
                },
            ]
        )
        from tools.tool_rate_survey import rate_survey

        result = rate_survey()
        self.assertEqual(result["status"], "error")
        self.assertIn("no WebSocket URL", result["reason"])

    def test_get_cdp_pages_failure_empty_list(self):
        """CDP HTTP failure returns empty list."""
        self.mock_urlopen.side_effect = ConnectionError("dead")
        from tools.tool_rate_survey import _get_cdp_pages

        pages = _get_cdp_pages()
        self.assertEqual(pages, [])
        from tools.tool_rate_survey import rate_survey

        result = rate_survey()
        self.assertEqual(result["status"], "not_found")

    def test_click_rating_button_success(self):
        """_click_rating_button returns True when WebSocket call succeeds."""
        mock_ws = MagicMock()
        mock_ws.recv.return_value = '{"result": {}}'
        mock_ws_mod = MagicMock()
        mock_ws_mod.create_connection.return_value = mock_ws
        with patch.dict("sys.modules", {"websocket": mock_ws_mod}):
            import tools.tool_rate_survey

            result = tools.tool_rate_survey._click_rating_button("ws://test/page")
            self.assertTrue(result)

    def test_click_rating_button_failure(self):
        """_click_rating_button returns False on error."""
        mock_ws_mod = MagicMock()
        mock_ws_mod.create_connection.side_effect = ConnectionError("nope")
        with patch.dict("sys.modules", {"websocket": mock_ws_mod}):
            import tools.tool_rate_survey

            result = tools.tool_rate_survey._click_rating_button("ws://test/page")
            self.assertFalse(result)

    def test_verify_rating_done_tab_closed(self):
        """_verify_rating_done returns True when tab closed."""
        self._set_pages([])
        from tools.tool_rate_survey import _verify_rating_done

        result = _verify_rating_done("missing_tab")
        self.assertTrue(result)

    def test_verify_rating_done_tab_still_rating(self):
        """_verify_rating_done returns False when tab still on rating page."""
        self._set_pages(
            [
                {"id": "tab2", "url": "https://www.cpx-research.com/rating.php", "type": "page"},
            ]
        )
        from tools.tool_rate_survey import _verify_rating_done

        result = _verify_rating_done("tab2")
        self.assertFalse(result)

    def test_rate_survey_returns_dict_always(self):
        """rate_survey always returns a dict."""
        self._set_pages([])
        from tools.tool_rate_survey import rate_survey

        result = rate_survey()
        self.assertIsInstance(result, dict)
        self.assertIn("status", result)


if __name__ == "__main__":
    unittest.main()
