"""Tests for SurveyOpener.

WARUM: SurveyOpener kapselt Tab-Lebenszyklus (open, close, refresh).
Ohne Tests kann die Integration in runner.py nicht sicher erfolgen.

ARCHITEKTUR: Unittest mit unittest.mock (MagicMock, patch).
chrome-Module und websocket werden gepatcht.
"""

# === SR-63 #62 legacy-debt skip (do not delete without unskipping) ===
import pytest
# === END SR-63 skip ===

import unittest
from unittest.mock import patch
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from survey.opener import SurveyOpener, SurveyTarget


class TestSurveyOpenerOpenNewTab(unittest.TestCase):
    """Opening a survey in a new browser tab."""

    @patch("survey.opener.chrome.create_blank_tab",
           return_value={"id": "tab-abc", "ws_url": "ws://tab"})
    @patch("survey.opener.chrome.inject_stealth_to_tab", return_value=True)
    @patch("survey.opener.chrome.navigate_tab", return_value=True)
    @patch("survey.opener.chrome.activate_tab")
    @patch("survey.opener.SurveyOpener._find_survey_tab_ws",
           return_value=("ws://survey", "https://survey.example.com"))
    def test_open_new_tab_returns_target(self, mock_find, mock_activate,
                                          mock_nav, mock_inj, mock_create):
        """open() returns a SurveyTarget with ws_url and tab_id."""
        opener = SurveyOpener(cdp_port=9999, debug=False)
        result = opener.open("s1", "qualtrics", "https://survey.example.com")
        self.assertIsNotNone(result.target)
        self.assertEqual(result.target.ws_url, "ws://survey")
        self.assertEqual(result.target.tab_id, "tab-abc")
        self.assertEqual(result.target.mode, "new_tab")
        self.assertEqual(result.target.actual_url, "https://survey.example.com")

    @patch("survey.opener.chrome.create_blank_tab", return_value=None)
    @patch("survey.opener.chrome.create_tab", return_value="tab-fallback")
    @patch("survey.opener.chrome.activate_tab")
    def test_create_blank_tab_fallback(self, mock_activate,
                                       mock_create_tab, mock_blank):
        """Fallback to chrome.create_tab when blank tab fails."""
        opener = SurveyOpener(cdp_port=9999, debug=False)
        with patch.object(opener, "_find_survey_tab_ws",
                          return_value=("ws://s", "https://s.com")):
            result = opener.open("s1", "qualtrics", "https://s.com")
        self.assertEqual(result.target.tab_id, "tab-fallback")


class TestSurveyOpenerOpenInPageModal(unittest.TestCase):
    """Opening a survey as an in-page modal."""

    @patch("survey.opener.chrome.find_bot_tabs", return_value=[])
    @patch("survey.opener.SurveyOpener._click_survey_card",
           return_value="ws://dashboard")
    @patch("survey.opener.SurveyOpener._pre_survey_cleanup", return_value=0)
    def test_open_in_page_returns_dashboard_ws(self, mock_cleanup,
                                                mock_click, mock_tabs):
        """In-page modal returns dashboard WS."""
        opener = SurveyOpener(cdp_port=9999, debug=False)
        result = opener.open("s1", "in_page_modal", "in-page://modal",
                             dashboard_ws="ws://dashboard")
        self.assertIsNotNone(result.target)
        self.assertEqual(result.target.ws_url, "ws://dashboard")
        self.assertEqual(result.target.mode, "in_page")

    @patch("survey.opener.chrome.find_bot_tabs",
           return_value=[{"id": "t1", "webSocketDebuggerUrl": "ws://dash"}])
    @patch("survey.opener.SurveyOpener._click_survey_card",
           return_value="ws://dash")
    @patch("survey.opener.SurveyOpener._find_new_tab_after_click",
           return_value="ws://new_tab")
    @patch("survey.opener.SurveyOpener._pre_survey_cleanup", return_value=0)
    def test_open_in_page_detects_new_tab(self, mock_cleanup, mock_new_tab,
                                           mock_click, mock_tabs):
        """If clickSurvey opens a new tab, mode becomes 'redirect'."""
        opener = SurveyOpener(cdp_port=9999, debug=False)
        result = opener.open("s1", "in_page_modal", "in-page://modal",
                             dashboard_ws="ws://dash")
        self.assertEqual(result.target.mode, "redirect")
        self.assertEqual(result.target.ws_url, "ws://new_tab")
        self.assertEqual(result.target.tab_id, "t1")


class TestSurveyOpenerErrorHandling(unittest.TestCase):
    """Error handling for stuck loading and expired surveys."""

    @patch("survey.opener.chrome.create_blank_tab",
           return_value={"id": "tab-x", "ws_url": "ws://t"})
    @patch("survey.opener.chrome.inject_stealth_to_tab", return_value=True)
    @patch("survey.opener.chrome.navigate_tab", return_value=True)
    @patch("survey.opener.chrome.activate_tab")
    @patch("survey.opener.SurveyOpener._find_survey_tab_ws",
           return_value=("ws://t", "https://s.com"))
    @patch("survey.opener.SurveyOpener._read_page_text",
           return_value="still loading just getting things ready please wait")
    @patch("survey.opener.SurveyOpener._close_tab")
    def test_stuck_loading_returns_screen_out(self, mock_close, mock_text,
                                              mock_find, mock_activate,
                                              mock_nav, mock_inj, mock_create):
        """Stuck loading page → screen_out with specific error."""
        opener = SurveyOpener(cdp_port=9999, debug=False)
        result = opener.open("s1", "qualtrics", "https://s.com")
        self.assertIsNone(result.target)
        self.assertEqual(result.status, "screen_out")
        self.assertIn("loading", result.error.lower())
        mock_close.assert_called_once_with("tab-x")

    @patch("survey.opener.chrome.create_blank_tab",
           return_value={"id": "tab-x", "ws_url": "ws://t"})
    @patch("survey.opener.chrome.inject_stealth_to_tab", return_value=True)
    @patch("survey.opener.chrome.navigate_tab", return_value=True)
    @patch("survey.opener.chrome.activate_tab")
    @patch("survey.opener.SurveyOpener._find_survey_tab_ws",
           return_value=("ws://t", "https://s.com"))
    @patch("survey.opener.SurveyOpener._read_page_text",
           return_value="survey not available — error occurred")
    @patch("survey.opener.SurveyOpener._close_tab")
    def test_expired_survey_returns_screen_out(self, mock_close, mock_text,
                                               mock_find, mock_activate,
                                               mock_nav, mock_inj, mock_create):
        """Expired/error page → screen_out with specific error."""
        opener = SurveyOpener(cdp_port=9999, debug=False)
        result = opener.open("s1", "qualtrics", "https://s.com")
        self.assertIsNone(result.target)
        self.assertEqual(result.status, "screen_out")
        self.assertIn("expired", result.error.lower())


class TestSurveyOpenerCloseAndRefresh(unittest.TestCase):
    """close() and refresh_ws() behaviors."""

    @patch("survey.opener.chrome.find_bot_tabs", return_value=[])
    def test_close_noop_for_in_page(self, mock_tabs):
        """close() is a no-op for in-page modal."""
        opener = SurveyOpener(cdp_port=9999, debug=False)
        target = SurveyTarget(survey_id="s1", provider="in_page_modal",
                              ws_url="ws://dash", mode="in_page")
        opener.close(target)  # should not raise

    @patch("survey.opener.chrome.activate_tab")
    @patch("survey.opener.chrome.get_ws_for_tab", return_value="ws://fresh")
    @patch("survey.opener.SurveyOpener._refresh_tab_ws",
           return_value="ws://fresh")
    def test_refresh_ws_returns_fresh_url(self, mock_refresh, mock_get,
                                          mock_activate):
        """refresh_ws returns new WS URL when tab navigated."""
        opener = SurveyOpener(cdp_port=9999, debug=False)
        target = SurveyTarget(survey_id="s1", provider="qualtrics",
                              ws_url="ws://old", tab_id="tab-x")
        fresh = opener.refresh_ws(target)
        self.assertEqual(fresh, "ws://fresh")


if __name__ == "__main__":
    unittest.main()
