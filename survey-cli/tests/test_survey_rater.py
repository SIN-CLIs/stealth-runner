"""Tests for SurveyRater — click rating button for +0.01€ bonus.

WARUM: Jede Code-Datei braucht Tests. SurveyRater ist NEU.
"""

import unittest
from unittest.mock import MagicMock, patch
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestSurveyRater(unittest.TestCase):
    """Test SurveyRater.rate() with mocked websocket and chrome."""

    @patch("survey.survey_rater.websocket")
    @patch("survey.survey_rater.chrome.find_bot_tabs")
    def test_rate_rating_tab_found(self, mock_tabs, mock_ws):
        from survey.survey_rater import SurveyRater

        mock_tabs.return_value = [
            {"url": "https://cpx-research.com/rating.php?survey=123", "webSocketDebuggerUrl": "ws://localhost:9223/devtools/page/1"},
        ]
        mock_conn = MagicMock()
        mock_conn.recv.return_value = '{"result": {"result": {"value": "clicked"}}}'
        mock_ws.create_connection.return_value = mock_conn

        rater = SurveyRater(cdp_port=9999, debug=True)
        result = rater.rate()

        self.assertTrue(result)
        mock_ws.create_connection.assert_called_once()

    @patch("survey.survey_rater.chrome.find_bot_tabs")
    def test_rate_no_rating_tab(self, mock_tabs):
        from survey.survey_rater import SurveyRater

        mock_tabs.return_value = [
            {"url": "https://heypiggy.com/dashboard", "webSocketDebuggerUrl": "ws://localhost:9223/devtools/page/1"},
        ]

        rater = SurveyRater(cdp_port=9999)
        result = rater.rate()

        self.assertFalse(result)

    @patch("survey.survey_rater.websocket")
    @patch("survey.survey_rater.chrome.find_bot_tabs")
    def test_rate_no_bot_tabs(self, mock_tabs, mock_ws):
        from survey.survey_rater import SurveyRater

        mock_tabs.return_value = []
        mock_ws.create_connection.return_value = MagicMock()

        rater = SurveyRater(cdp_port=9999)
        result = rater.rate()

        self.assertFalse(result)

    @patch("survey.survey_rater.websocket")
    @patch("survey.survey_rater.chrome.find_bot_tabs")
    def test_rate_cpx_research_url(self, mock_tabs, mock_ws):
        from survey.survey_rater import SurveyRater

        mock_tabs.return_value = [
            {"url": "https://www.cpx-research.com/survey/456/rate", "webSocketDebuggerUrl": "ws://localhost:9223/devtools/page/2"},
        ]
        mock_conn = MagicMock()
        mock_conn.recv.return_value = '{"result": {"result": {"value": null}}}'
        mock_ws.create_connection.return_value = mock_conn

        rater = SurveyRater(cdp_port=9999)
        result = rater.rate()

        self.assertTrue(result)

    @patch("survey.survey_rater.websocket")
    @patch("survey.survey_rater.chrome.find_bot_tabs")
    def test_rate_websocket_error(self, mock_tabs, mock_ws):
        from survey.survey_rater import SurveyRater

        mock_tabs.return_value = [
            {"url": "https://cpx-research.com/rating.php", "webSocketDebuggerUrl": "ws://localhost:9223/devtools/page/1"},
        ]
        mock_ws.create_connection.side_effect = Exception("connection refused")

        rater = SurveyRater(cdp_port=9999)
        result = rater.rate()

        self.assertFalse(result)

    @patch("survey.survey_rater.websocket")
    @patch("survey.survey_rater.chrome.find_bot_tabs")
    def test_rate_multiple_tabs_rating_last(self, mock_tabs, mock_ws):
        from survey.survey_rater import SurveyRater

        mock_tabs.return_value = [
            {"url": "https://heypiggy.com/dashboard", "webSocketDebuggerUrl": "ws://localhost:9223/devtools/page/1"},
            {"url": "https://cpx-research.com/rating.php", "webSocketDebuggerUrl": "ws://localhost:9223/devtools/page/2"},
        ]
        mock_conn = MagicMock()
        mock_conn.recv.return_value = '{"result": {"result": {"value": "done"}}}'
        mock_ws.create_connection.return_value = mock_conn

        rater = SurveyRater(cdp_port=9999)
        result = rater.rate()

        self.assertTrue(result)


if __name__ == "__main__":
    unittest.main()