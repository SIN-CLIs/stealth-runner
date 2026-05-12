#!/usr/bin/env python3
"""Test for tool_detect_completion.py — Survey Status Detection.

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


def _make_response(url="", title="", text=""):
    return json.dumps(
        {
            "result": {
                "result": {
                    "value": {
                        "url": url,
                        "title": title,
                        "text": text,
                    }
                }
            }
        }
    )


class TestDetectCompletion(unittest.TestCase):
    """Test detect() — survey completion detection via mocked CDP."""

    def setUp(self):
        self.ws_url = "ws://127.0.0.1:9999/devtools/page/mockSurvey"
        self._ws_patcher = patch("tools.tool_detect_completion.websocket.create_connection")
        self.mock_create = self._ws_patcher.start()

    def tearDown(self):
        self._ws_patcher.stop()

    def _set_response(self, url="", title="", text=""):
        mock_ws = MagicMock()
        mock_ws.recv.return_value = _make_response(url, title, text)
        self.mock_create.return_value = mock_ws

    def test_detect_completed_danke(self):
        """German 'Vielen Dank' page returns 'completed'."""
        self._set_response(
            url="https://survey.qualtrics.com/complete",
            title="vielen dank",
            text="vielen dank für ihre teilnahme sie können das fenster schließen",
        )
        from tools.tool_detect_completion import detect

        self.assertEqual(detect(self.ws_url), "completed")

    def test_detect_screen_out(self):
        """'leider nicht qualifiziert' returns 'screen_out'."""
        self._set_response(
            url="https://survey.example.com/redirect",
            title="umfrage beendet",
            text="leider qualifizieren sie sich nicht für diese umfrage",
        )
        from tools.tool_detect_completion import detect

        self.assertEqual(detect(self.ws_url), "screen_out")

    def test_detect_running_with_interactivity(self):
        """Page with interaction markers returns 'running'."""
        self._set_response(
            url="https://survey.example.com/question/3",
            title="frage 3 von 10",
            text="weiter  nächste  ihre antwort eingeben",
        )
        from tools.tool_detect_completion import detect

        self.assertEqual(detect(self.ws_url), "running")

    def test_detect_running_single_marker(self):
        """Single 'Weiter' marker alone does NOT force 'running' (needs 2+)."""
        self._set_response(
            url="https://site.com/thankyou",
            title="danke",
            text="weiter zum panel vielen dank für ihre teilnahme",
        )
        from tools.tool_detect_completion import detect

        self.assertEqual(detect(self.ws_url), "completed")

    def test_detect_dashboard_redirect(self):
        """Prolific redirect returns 'completed'."""
        self._set_response(
            url="https://app.prolific.co/submissions/complete?cc=xyz", title="prolific", text=""
        )
        from tools.tool_detect_completion import detect

        self.assertEqual(detect(self.ws_url), "completed")

    def test_detect_url_complete_keyword(self):
        """URL containing 'complete' returns 'completed'."""
        self._set_response(url="https://example.com/survey/complete?id=123", title="", text="danke")
        from tools.tool_detect_completion import detect

        self.assertEqual(detect(self.ws_url), "completed")

    def test_detect_ws_failure_returns_running(self):
        """WebSocket failure conservative: returns 'running'."""
        self.mock_create.side_effect = ConnectionError("CDP dead")
        from tools.tool_detect_completion import detect

        self.assertEqual(detect(self.ws_url), "running")

    def test_detect_english_thank_you(self):
        """English 'thank you for completing' returns 'completed'."""
        self._set_response(
            url="https://survey.example.com/end",
            title="survey end",
            text="thank you for completing our survey",
        )
        from tools.tool_detect_completion import detect

        self.assertEqual(detect(self.ws_url), "completed")

    def test_detect_quota_full(self):
        """'quota full' returns 'screen_out'."""
        self._set_response(
            url="https://survey.example.com/out",
            title="",
            text="unfortunately the quota full for this survey",
        )
        from tools.tool_detect_completion import detect

        self.assertEqual(detect(self.ws_url), "screen_out")

    def test_detect_generic_page_running(self):
        """Unknown page with no markers returns 'running'."""
        self._set_response(
            url="https://survey.example.com/q4",
            title="Question 4",
            text="Please select your preference.",
        )
        from tools.tool_detect_completion import detect

        self.assertEqual(detect(self.ws_url), "running")

    def test_detect_returns_string(self):
        """Always returns a str."""
        self._set_response()
        from tools.tool_detect_completion import detect

        result = detect(self.ws_url)
        self.assertIsInstance(result, str)
        self.assertIn(result, ["completed", "screen_out", "running"])


if __name__ == "__main__":
    unittest.main()
