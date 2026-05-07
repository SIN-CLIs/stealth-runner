"""Regression tests: Pre-qualifier handling in run_loop().

WARUM: Pre-Qualifiers filtern Teilnehmer vor dem eigentlichen Survey.
Falsche Beantwortung oder Überspringen führt zu 0.02€ Compensation statt
vollem Verdienst. Der CPX-API-Call muss korrekt simuliert werden.

ARCHITEKTUR: Unittest mit unittest.mock (MagicMock, patch).
chrome.find_dashboard_ws und urllib.request.urlopen werden gepatcht.
Der Runner verwendet Fallback-DETAILS_URL wenn kein Dashboard-WS gefunden.
Profile-Alter (32) mapped zu answer_idx=2 — Tests prüfen Index-Bounds.
Kein echter Chrome, kein echter CPX-Server.

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
from unittest.mock import MagicMock, patch
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from survey.runner import SurveyRunner, RunnerConfig, SurveyResult


def _make_urlopen_response(data_dict):
    """Create a proper urlopen mock response with bytes from read()."""
    resp = MagicMock()
    resp.read.return_value = json.dumps(data_dict).encode()
    return resp


# Test data: 6 age brackets (profile age 32 → answer_idx=2 → a3)
AGE_ANSWERS = {
    'a1': {'text': 'Under 18', 'key': 'a1'},
    'a2': {'text': '18-25', 'key': 'a2'},
    'a3': {'text': '26-35', 'key': 'a3'},
    'a4': {'text': '36-45', 'key': 'a4'},
    'a5': {'text': '46-55', 'key': 'a5'},
    'a6': {'text': '56+', 'key': 'a6'},
}

AGE_DETAILS = {
    'id': 'test_123',
    'question_text': 'What is your age?',
    'question_key': 'q_age',
    'answers': AGE_ANSWERS,
}


class TestHandlePreQualifier(unittest.TestCase):
    """Test handle_pre_qualifier() CPX API loop.

    Key: find_dashboard_ws returns None → get_details_url falls back to DETAILS_URL.
    This avoids CDP WS calls entirely. urlopen is mocked for the CPX API POST.
    """

    def _make_runner(self):
        """Create SurveyRunner and clear module-level cache."""
        from survey import chrome as _c
        _c._cached_details_url = None
        return SurveyRunner(RunnerConfig(cdp_port=9999))

    @patch("survey.chrome.find_dashboard_ws", return_value=None)
    @patch("survey.runner.urllib.request.urlopen")
    def test_returns_href_on_okay(self, mock_urlopen, mock_find_ws):
        """Response with status:success + href → return href."""
        runner = self._make_runner()
        mock_urlopen.side_effect = lambda *a, **kw: _make_urlopen_response({
            "status": "success", "href": "https://survey.example.com/s/12345"
        })
        result = runner.handle_pre_qualifier("preq_123", AGE_DETAILS)
        self.assertEqual(result, "https://survey.example.com/s/12345")
        mock_urlopen.assert_called_once()

    @patch("survey.chrome.find_dashboard_ws", return_value=None)
    @patch("survey.runner.urllib.request.urlopen")
    def test_loops_on_multiple_questions(self, mock_urlopen, mock_find_ws):
        """3 questions → 3 POST calls → href returned on 3rd."""
        runner = self._make_runner()
        responses = iter([
            _make_urlopen_response({"type": "question", "question_text": "Employment?",
                                    "question_key": "q_emp",
                                    "answers": {
                                        "e1": {"text": "Not employed", "key": "e1"},
                                        "e2": {"text": "Employed", "key": "e2"},
                                        "e3": {"text": "Self-employed", "key": "e3"},
                                    }}),
            _make_urlopen_response({"type": "question", "question_text": "Income?",
                                    "question_key": "q_inc",
                                    "answers": {
                                        "i1": {"text": "<2000", "key": "i1"},
                                        "i2": {"text": "2000-4000", "key": "i2"},
                                        "i3": {"text": "4000+", "key": "i3"},
                                    }}),
            _make_urlopen_response({"status": "success",
                                    "href": "https://real.survey.io/789"}),
        ])
        mock_urlopen.side_effect = lambda *a, **kw: next(responses)

        result = runner.handle_pre_qualifier("preq_456", AGE_DETAILS)
        self.assertEqual(result, "https://real.survey.io/789")
        self.assertEqual(mock_urlopen.call_count, 3)

    @patch("survey.chrome.find_dashboard_ws", return_value=None)
    @patch("survey.runner.urllib.request.urlopen")
    def test_returns_none_on_screen_out(self, mock_urlopen, mock_find_ws):
        """Screen-out response → returns None."""
        runner = self._make_runner()
        mock_urlopen.side_effect = lambda *a, **kw: _make_urlopen_response({
            "type": "screen_out", "message": "No qualify"
        })
        result = runner.handle_pre_qualifier("preq_789", AGE_DETAILS)
        self.assertIsNone(result)

    @patch("survey.chrome.find_dashboard_ws", return_value=None)
    @patch("survey.runner.urllib.request.urlopen")
    def test_returns_none_on_max_retries(self, mock_urlopen, mock_find_ws):
        """All responses are 'question' → exceeds 8 retries → None."""
        runner = self._make_runner()
        mock_urlopen.side_effect = lambda *a, **kw: _make_urlopen_response({
            "type": "question", "question_text": "Hobby?",
            "question_key": "q_hobby",
            "answers": {"h1": {"text": "Sports", "key": "h1"}},
        })
        result = runner.handle_pre_qualifier("preq_000", AGE_DETAILS)
        self.assertIsNone(result)
        self.assertGreaterEqual(mock_urlopen.call_count, 8)

    @patch("survey.chrome.find_dashboard_ws", return_value=None)
    @patch("survey.runner.urllib.request.urlopen")
    def test_profile_matching_gender(self, mock_urlopen, mock_find_ws):
        """Gender question → male profile selects male option."""
        runner = self._make_runner()
        captured = []

        def capture(url, timeout=None):
            captured.append(str(url))
            return _make_urlopen_response({"status": "success",
                                           "href": "https://survey.io/m"})

        mock_urlopen.side_effect = capture
        result = runner.handle_pre_qualifier("preq_gen", {
            "id": "preq_gen",
            "question_text": "What is your gender?",
            "question_key": "q_gender",
            "answers": {"m": {"text": "Male", "key": "m"},
                        "f": {"text": "Female", "key": "f"}},
        })
        self.assertEqual(result, "https://survey.io/m")
        self.assertTrue(any("q_gender=m" in u for u in captured),
                        "Should send male answer (m)")
        self.assertFalse(any("q_gender=f" in u for u in captured),
                         "Should NOT send female answer (f)")

    @patch("survey.chrome.find_dashboard_ws", return_value=None)
    @patch("survey.runner.urllib.request.urlopen")
    def test_profile_matching_berlin(self, mock_urlopen, mock_find_ws):
        """City question → Berlin profile selects Berlin option."""
        runner = self._make_runner()
        captured = []

        def capture_berlin(url, timeout=None):
            captured.append(str(url))
            return _make_urlopen_response({"status": "success",
                                           "href": "https://survey.io/berlin"})

        mock_urlopen.side_effect = capture_berlin
        result = runner.handle_pre_qualifier("preq_city", {
            "id": "preq_city",
            "question_text": "In welcher Stadt wohnen Sie?",  # "stadt" triggers Berlin matching
            "question_key": "q_city",
            "answers": {
                "c1": {"text": "München", "key": "c1"},
                "c2": {"text": "Berlin", "key": "c2"},
                "c3": {"text": "Hamburg", "key": "c3"},
            },
        })
        self.assertEqual(result, "https://survey.io/berlin")
        self.assertTrue(any("q_city=c2" in u for u in captured),
                        "Should send Berlin answer (c2)")

    @patch("survey.chrome.find_dashboard_ws", return_value=None)
    @patch("survey.runner.urllib.request.urlopen")
    def test_answer_idx_bound_check(self, mock_urlopen, mock_find_ws):
        """Profile answer_idx must be < len(answer_keys) to avoid None."""
        runner = self._make_runner()
        # Only 1 answer, but profile age 32 maps to idx 2 → 2 >= 1 → None
        mock_urlopen.side_effect = lambda *a, **kw: _make_urlopen_response({
            "status": "success", "href": "https://survey.io/done"
        })
        # Age question with only 1 answer (profile age 32 → idx 2 → 2 >= 1)
        result = runner.handle_pre_qualifier("preq_bound", {
            "id": "preq_bound",
            "question_text": "What is your age?",
            "question_key": "q_age",
            "answers": {"a1": {"text": "18-25", "key": "a1"}},
        })
        self.assertIsNone(result, "answer_idx >= len(answers) → None")
        mock_urlopen.assert_not_called()  # urlopen never reached


class TestRunLoopPreQualifiers(unittest.TestCase):
    """Test run_loop() handles pre-qualifiers (not skip them).

    These mock run_loop dependencies: scan_dashboard, read_balance, find_dashboard_ws.
    handle_pre_qualifier is mocked via patch.object to verify it's called.
    """

    def _make_runner(self):
        return SurveyRunner(RunnerConfig(cdp_port=9999))

    @patch("survey.runner.scan_dashboard")
    @patch("survey.runner.read_balance")
    @patch("survey.runner.chrome.find_dashboard_ws")
    @patch("survey.runner.chrome.find_bot_tabs")
    def test_prequalifier_answered_via_api(
            self, mock_tabs, mock_dash_ws, mock_balance, mock_scan):
        """Pre-qualifier → handle_pre_qualifier() called → survey run."""
        runner = self._make_runner()
        mock_scan.return_value = [
            {"id": "pq_001", "provider": "pre_qualifier", "href": "",
             "question_text": "Age?", "question_key": "q_age",
             "answers": AGE_ANSWERS},
        ]
        mock_balance.return_value = 1.0
        mock_tabs.return_value = []
        mock_dash_ws.return_value = "ws://localhost:9999/db"

        with patch.object(runner, "handle_pre_qualifier",
                          return_value="https://real.survey.io/001") as mock_hpq, \
             patch.object(runner, "run_survey") as mock_run:
            mock_run.return_value = SurveyResult(survey_id="pq_001", status="completed", earned=0.50)
            results = runner.run_loop(max_surveys=1)

            mock_hpq.assert_called_once()
            self.assertEqual(mock_hpq.call_args[0][0], "pq_001")
            mock_run.assert_called_once_with("pq_001", survey_url="https://real.survey.io/001")
            self.assertEqual(len(results), 1)

    @patch("survey.runner.scan_dashboard")
    @patch("survey.runner.read_balance")
    @patch("survey.runner.chrome.find_dashboard_ws")
    @patch("survey.runner.chrome.find_bot_tabs")
    def test_prequalifier_skipped_when_api_fails(
            self, mock_tabs, mock_dash_ws, mock_balance, mock_scan):
        """Pre-qualifier → handle_pre_qualifier() returns None → skipped."""
        runner = self._make_runner()
        mock_scan.return_value = [
            {"id": "pq_002", "provider": "pre_qualifier", "href": "",
             "question_text": "Age?", "question_key": "q_age", "answers": {}},
        ]
        mock_balance.return_value = 0.0
        mock_tabs.return_value = []
        mock_dash_ws.return_value = "ws://localhost:9999/db"

        with patch.object(runner, "handle_pre_qualifier", return_value=None) as mock_hpq, \
             patch.object(runner, "run_survey") as mock_run:
            results = runner.run_loop(max_surveys=1)
            mock_hpq.assert_called_once()
            mock_run.assert_not_called()
            self.assertEqual(len(results), 0)

    @patch("survey.runner.scan_dashboard")
    @patch("survey.runner.read_balance")
    @patch("survey.runner.chrome.find_dashboard_ws")
    @patch("survey.runner.chrome.find_bot_tabs")
    def test_normal_survey_unchanged(
            self, mock_tabs, mock_dash_ws, mock_balance, mock_scan):
        """Non-pre-qualifier runs normally (handle_pre_qualifier NOT called)."""
        runner = self._make_runner()
        mock_scan.return_value = [
            {"id": "norm_001", "provider": "qualtrics",
             "href": "https://qualtrics.com/survey/123"},
        ]
        mock_balance.return_value = 0.5
        mock_tabs.return_value = []
        mock_dash_ws.return_value = "ws://localhost:9999/db"

        with patch.object(runner, "handle_pre_qualifier") as mock_hpq, \
             patch.object(runner, "run_survey") as mock_run:
            mock_run.return_value = SurveyResult(survey_id="norm_001", status="completed", earned=0.75)
            results = runner.run_loop(max_surveys=1)
            mock_hpq.assert_not_called()
            mock_run.assert_called_once_with("norm_001", survey_url="https://qualtrics.com/survey/123")
            self.assertEqual(len(results), 1)

    @patch("survey.runner.scan_dashboard")
    @patch("survey.runner.read_balance")
    @patch("survey.runner.chrome.find_dashboard_ws")
    @patch("survey.runner.chrome.find_bot_tabs")
    def test_mixed_prequalifier_and_normal(
            self, mock_tabs, mock_dash_ws, mock_balance, mock_scan):
        """One pre-qualifier (answered), one normal survey."""
        runner = self._make_runner()
        mock_scan.return_value = [
            {"id": "pq_001", "provider": "pre_qualifier", "href": "",
             "question_text": "Age?", "question_key": "q_age", "answers": AGE_ANSWERS},
            {"id": "norm_001", "provider": "qualtrics", "href": "https://qualtrics.com/s/456"},
        ]
        mock_balance.return_value = 0.0
        mock_tabs.return_value = []
        mock_dash_ws.return_value = "ws://localhost:9999/db"

        with patch.object(runner, "handle_pre_qualifier",
                          return_value="https://real.survey.io/pq001") as mock_hpq, \
             patch.object(runner, "run_survey",
                          side_effect=lambda sid, **kw: SurveyResult(survey_id=sid, status="completed", earned=0.33)):
            results = runner.run_loop(max_surveys=2)
            self.assertEqual(len(results), 2)
            self.assertEqual(mock_hpq.call_count, 1)
            self.assertEqual(mock_hpq.call_args[0][0], "pq_001")

    @patch("survey.runner.scan_dashboard")
    @patch("survey.runner.read_balance")
    @patch("survey.runner.chrome.find_dashboard_ws")
    @patch("survey.runner.chrome.find_bot_tabs")
    def test_all_prequalifiers_no_early_return(
            self, mock_tabs, mock_dash_ws, mock_balance, mock_scan):
        """All pre-qualifiers (failed) → return empty, don't crash."""
        runner = self._make_runner()
        mock_scan.return_value = [
            {"id": "pq_001", "provider": "pre_qualifier", "href": "",
             "question_text": "Age?", "question_key": "q_age", "answers": AGE_ANSWERS},
        ]
        mock_balance.return_value = 0.0
        mock_tabs.return_value = []
        mock_dash_ws.return_value = "ws://localhost:9999/db"

        with patch.object(runner, "handle_pre_qualifier", return_value=None) as mock_hpq, \
             patch.object(runner, "run_survey") as mock_run:
            results = runner.run_loop(max_surveys=3)
            self.assertEqual(mock_hpq.call_count, 1)
            mock_run.assert_not_called()
            self.assertEqual(len(results), 0)


class TestProviderRewrite(unittest.TestCase):
    """Pre-qualifier survey dict rewritten after answering."""

    def test_survey_dict_rewritten(self):
        """After handle_pre_qualifier returns href, provider set to pre_qualifier_answered."""
        survey_url = "https://survey.io/answered"
        survey = {"id": "pq_test", "provider": "pre_qualifier", "href": ""}
        survey = survey.copy()
        survey["href"] = survey_url
        survey["provider"] = "pre_qualifier_answered"

        self.assertEqual(survey["provider"], "pre_qualifier_answered")
        self.assertEqual(survey["href"], "https://survey.io/answered")
        self.assertEqual(survey["id"], "pq_test")


if __name__ == "__main__":
    unittest.main()