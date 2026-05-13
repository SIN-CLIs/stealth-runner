"""Tests for CompletionDetector — completion/screen-out detection logic.

WARUM: Jede Code-Datei braucht Tests (Archäologie-Tsunami Regel #6).
CompletionDetector ist ein NEUES Modul — ohne Tests würde der nächste
Agent es kaputt machen.

BANNED METHODS — NIEMALS VERWENDEN:
  ❌ playstealth launch
  ❌ webauto-nodriver — ABSOLUT BANNED
"""

import unittest
from unittest.mock import patch
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from survey.completion_detector import CompletionDetector


class TestDetect(unittest.TestCase):
    """Unit tests for CompletionDetector.detect() — pure text analysis."""

    def test_german_completion_detected(self):
        d = CompletionDetector()
        self.assertTrue(d.detect("Vielen Dank für Ihre Teilnahme!"))
        self.assertTrue(d.detect("Umfrage beendet. Guthaben wurde gutgeschrieben."))
        self.assertTrue(d.detect("Zurück zur Website"))

    def test_english_completion_detected(self):
        d = CompletionDetector()
        self.assertTrue(d.detect("Thank you for completing the survey"))
        self.assertTrue(d.detect("Your response has been recorded"))
        self.assertTrue(d.detect("Survey complete!"))

    def test_running_not_detected(self):
        d = CompletionDetector()
        self.assertFalse(d.detect("What is your age?"))
        self.assertFalse(d.detect("Please select an option"))
        self.assertFalse(d.detect("Loading..."))

    def test_case_insensitive(self):
        d = CompletionDetector()
        self.assertTrue(d.detect("THANK YOU FOR COMPLETING"))
        self.assertTrue(d.detect("Vielen Dank"))


class TestDetectWs(unittest.TestCase):
    """Tests for CompletionDetector.detect_ws() — reads page via BatchExecutor."""

    @patch("survey.completion_detector.BatchExecutor.read_page_text")
    def test_detects_completion_on_page(self, mock_read):
        mock_read.return_value = "Thank you for your participation"
        d = CompletionDetector()
        self.assertTrue(d.detect_ws("ws://test"))
        mock_read.assert_called_once_with("ws://test", 500)

    @patch("survey.completion_detector.BatchExecutor.read_page_text")
    def test_not_detected_on_running_page(self, mock_read):
        mock_read.return_value = "Question 3 of 10"
        d = CompletionDetector()
        self.assertFalse(d.detect_ws("ws://test"))

    @patch("survey.completion_detector.BatchExecutor.read_page_text")
    def test_exception_returns_false(self, mock_read):
        mock_read.side_effect = Exception("WS broken")
        d = CompletionDetector()
        self.assertFalse(d.detect_ws("ws://test"))


class TestScanAllTabs(unittest.TestCase):
    """Tests for CompletionDetector.scan_all_tabs() — cross-tab scan."""

    @patch("survey.completion_detector.chrome.find_bot_tabs")
    @patch("survey.completion_detector.BatchExecutor.read_page_text")
    def test_finds_completion_on_survey_tab(self, mock_read, mock_tabs):
        mock_tabs.return_value = [
            {"url": "https://heypiggy.com/dashboard", "webSocketDebuggerUrl": "ws://dash"},
            {"url": "https://survey.example.com/complete", "webSocketDebuggerUrl": "ws://survey"},
        ]
        mock_read.return_value = "Thank you for completing"
        d = CompletionDetector()
        self.assertTrue(d.scan_all_tabs())

    @patch("survey.completion_detector.chrome.find_bot_tabs")
    @patch("survey.completion_detector.BatchExecutor.read_page_text")
    def test_skips_dashboard_and_blank(self, mock_read, mock_tabs):
        mock_tabs.return_value = [
            {"url": "https://heypiggy.com/dashboard", "webSocketDebuggerUrl": "ws://dash"},
            {"url": "about:blank", "webSocketDebuggerUrl": "ws://blank"},
        ]
        d = CompletionDetector()
        self.assertFalse(d.scan_all_tabs())
        mock_read.assert_not_called()

    @patch("survey.completion_detector.chrome.find_bot_tabs")
    def test_exception_returns_false(self, mock_tabs):
        mock_tabs.side_effect = Exception("CDP down")
        d = CompletionDetector()
        self.assertFalse(d.scan_all_tabs())


if __name__ == "__main__":
    unittest.main()
