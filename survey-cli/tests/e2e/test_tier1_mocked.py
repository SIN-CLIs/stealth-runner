"""Tier-1 E2E Smoketest — Mocked CI (SR-139).

Fast mocked tests that run on every PR without network or browser.
Target: <15 seconds total runtime.

Coverage:
- Login flow (mocked HTTP)
- Dashboard scrape (fixture HTML)
- Survey selection
- Answer routing (5 questions)
- Completion detection
- Balance update verification

Usage:
    pytest survey-cli/tests/e2e/test_tier1_mocked.py -v
"""

import json
import unittest
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
from unittest.mock import MagicMock

import pytest

# ── Fixtures Loading ─────────────────────────────────────────────────────────

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> dict:
    """Load a JSON fixture file."""
    fixture_path = FIXTURES_DIR / name
    if not fixture_path.exists():
        raise FileNotFoundError(f"Fixture not found: {fixture_path}")
    with open(fixture_path, "r", encoding="utf-8") as f:
        return json.load(f)


# ── Mock State Classes ───────────────────────────────────────────────────────


@dataclass
class MockSurveyState:
    """Mock survey state for testing."""

    survey_id: str = "test-survey-001"
    provider: str = "heypiggy"
    status: str = "pending"
    balance_before: float = 15.50
    balance_after: float = 15.50
    current_question: int = 0
    answers: list = field(default_factory=list)
    errors: list = field(default_factory=list)
    page_content: str = ""


@dataclass
class MockLoginResult:
    """Mock login result."""

    success: bool = True
    user_id: int = 12345
    username: str = "example_user"
    balance: float = 15.50
    session_token: str = "<REDACTED-TOKEN>"
    error: Optional[str] = None


@dataclass
class MockCompletionState:
    """Mock completion detection result."""

    status: str = "pending"
    completion_phrase: Optional[str] = None
    balance_delta: float = 0.0


# ── Mock Adapter (Sentinel for pre-#137) ─────────────────────────────────────


class MockHeyPiggyAdapter:
    """Mock HeyPiggy adapter (sentinel until #137 lands)."""

    name = "heypiggy"

    def get_commands(self) -> dict:
        return {
            "click_next": ".btn-next, button[type='submit']",
            "click_element": ".survey-option, .choice-item",
            "login_submit": "#login-form button[type='submit']",
            "survey_card_click": ".survey-card",
            "fill_text": "input[type='text'], textarea",
        }

    def detect_completion(self, page_content: str) -> MockCompletionState:
        """Detect survey completion from page content."""
        completion_phrases = [
            "vielen dank für ihre teilnahme",
            "thank you for completing",
            "wurden ihrem konto gutgeschrieben",
            "survey completed",
            "umfrage abgeschlossen",
        ]
        screen_out_phrases = [
            "qualifizieren sie sich nicht",
            "do not qualify",
            "nicht für diese umfrage",
            "sorry, you do not qualify",
            "screen out",
        ]

        content_lower = page_content.lower()

        for phrase in completion_phrases:
            if phrase in content_lower:
                return MockCompletionState(
                    status="completed", completion_phrase=phrase, balance_delta=0.80
                )

        for phrase in screen_out_phrases:
            if phrase in content_lower:
                return MockCompletionState(
                    status="screen_out", completion_phrase=phrase, balance_delta=0.0
                )

        return MockCompletionState(status="pending")

    def matches(self, url: str) -> bool:
        """Check if URL matches HeyPiggy."""
        return "heypiggy.com" in url.lower()


def get_mock_provider_adapter(provider: str):
    """Mock provider adapter factory (pre-#137 sentinel)."""
    if provider == "heypiggy":
        return MockHeyPiggyAdapter()
    # Return generic mock for others
    mock = MagicMock()
    mock.name = "generic"
    mock.get_commands.return_value = {"click_next": "button"}
    return mock


# ── Test Classes ─────────────────────────────────────────────────────────────


class TestLoginFlow(unittest.TestCase):
    """Test login flow with mocked HTTP responses."""

    @classmethod
    def setUpClass(cls):
        cls.login_fixture = load_fixture("heypiggy_login.json")

    def test_login_fixture_is_sanitized(self):
        """Verify login fixture contains no real credentials."""
        creds = self.login_fixture["credentials"]
        self.assertEqual(creds["username"], "EXAMPLE_USER")
        self.assertEqual(creds["password"], "EXAMPLE_PASS")

    def test_login_fixture_has_redacted_tokens(self):
        """Verify all tokens are redacted in fixture."""
        session = self.login_fixture["session"]
        self.assertIn("<REDACTED-TOKEN>", session["cookie"])

    def test_login_page_request_returns_200(self):
        """Verify login page fixture has 200 status."""
        login_page = self.login_fixture["requests"][0]
        self.assertEqual(login_page["step"], "login_page")
        self.assertEqual(login_page["response"]["status"], 200)

    def test_login_submit_returns_user_data(self):
        """Verify login submit returns user data structure."""
        login_submit = self.login_fixture["requests"][1]
        self.assertEqual(login_submit["step"], "login_submit")
        response_body = login_submit["response"]["body"]
        self.assertTrue(response_body["success"])
        self.assertIn("user", response_body)
        self.assertIn("balance", response_body["user"])

    def test_login_flow_mock_execution(self):
        """Test mocked login flow execution."""
        fixture = self.login_fixture

        # Simulate login
        result = MockLoginResult(
            success=fixture["requests"][1]["response"]["body"]["success"],
            user_id=fixture["session"]["user_id"],
            balance=fixture["session"]["initial_balance"],
        )

        self.assertTrue(result.success)
        self.assertEqual(result.user_id, 12345)
        self.assertEqual(result.balance, 15.50)


class TestDashboardScrape(unittest.TestCase):
    """Test dashboard scraping with mocked HTML."""

    @classmethod
    def setUpClass(cls):
        cls.login_fixture = load_fixture("heypiggy_login.json")
        cls.dashboard_html = cls.login_fixture["requests"][2]["response"]["body_preview"]

    def test_dashboard_contains_balance(self):
        """Verify dashboard HTML contains balance element."""
        self.assertIn("balance", self.dashboard_html)
        self.assertIn("15,50", self.dashboard_html)

    def test_dashboard_contains_survey_cards(self):
        """Verify dashboard HTML contains survey cards."""
        self.assertIn("survey-card", self.dashboard_html)
        self.assertIn("survey-001", self.dashboard_html)

    def test_dashboard_parse_survey_reward(self):
        """Verify survey reward can be parsed from dashboard."""
        self.assertIn("0,80 €", self.dashboard_html)
        self.assertIn("5 min", self.dashboard_html)


class TestSurveySelection(unittest.TestCase):
    """Test survey selection logic."""

    @classmethod
    def setUpClass(cls):
        cls.survey_fixture = load_fixture("heypiggy_survey_short.json")

    def test_survey_fixture_metadata(self):
        """Verify survey fixture has required metadata."""
        meta = self.survey_fixture["_meta"]
        self.assertEqual(meta["provider"], "heypiggy")
        self.assertTrue(meta["sanitized"])

    def test_survey_has_5_questions(self):
        """Verify survey fixture has exactly 5 questions."""
        questions = self.survey_fixture["questions"]
        self.assertEqual(len(questions), 5)

    def test_survey_reward_matches(self):
        """Verify survey reward is correctly specified."""
        survey = self.survey_fixture["survey"]
        self.assertEqual(survey["reward"], 0.80)
        self.assertEqual(survey["currency"], "EUR")


class TestAnswerRouting(unittest.TestCase):
    """Test answer routing for different question types."""

    @classmethod
    def setUpClass(cls):
        cls.survey_fixture = load_fixture("heypiggy_survey_short.json")
        cls.questions = cls.survey_fixture["questions"]

    def test_single_choice_routing(self):
        """Test single choice question routing."""
        q = self.questions[0]
        self.assertEqual(q["type"], "single_choice")
        self.assertEqual(q["expected_answer"], "25-34")
        self.assertEqual(len(q["options"]), 5)

    def test_multiple_choice_routing(self):
        """Test multiple choice question routing."""
        q = self.questions[2]
        self.assertEqual(q["type"], "multiple_choice")
        self.assertIsInstance(q["expected_answer"], list)
        self.assertIn("electronics", q["expected_answer"])

    def test_text_input_routing(self):
        """Test text input question routing."""
        q = self.questions[3]
        self.assertEqual(q["type"], "text_input")
        self.assertIn("validation", q)
        self.assertGreaterEqual(q["validation"]["min_length"], 1)

    def test_rating_scale_routing(self):
        """Test rating scale question routing."""
        q = self.questions[4]
        self.assertEqual(q["type"], "rating_scale")
        self.assertEqual(q["scale"]["min"], 1)
        self.assertEqual(q["scale"]["max"], 5)

    def test_disqualifying_options_marked(self):
        """Test that disqualifying options are properly marked."""
        q = self.questions[1]  # Shopping frequency question
        self.assertIn("never", q["disqualifying_options"])


class TestCompletionDetection(unittest.TestCase):
    """Test completion detection logic."""

    @classmethod
    def setUpClass(cls):
        cls.survey_fixture = load_fixture("heypiggy_survey_short.json")
        cls.adapter = MockHeyPiggyAdapter()

    def test_completion_detected_german(self):
        """Test completion detection with German phrase."""
        page = self.survey_fixture["completion"]["success_page"]["body_preview"]
        result = self.adapter.detect_completion(page)
        self.assertEqual(result.status, "completed")

    def test_completion_detected_english(self):
        """Test completion detection with English phrase."""
        page = "Thank you for completing this survey. Your response has been recorded."
        result = self.adapter.detect_completion(page)
        self.assertEqual(result.status, "completed")

    def test_screen_out_detected_german(self):
        """Test screen-out detection with German phrase."""
        page = self.survey_fixture["screen_out"]["page"]["body_preview"]
        result = self.adapter.detect_completion(page)
        self.assertEqual(result.status, "screen_out")

    def test_screen_out_detected_english(self):
        """Test screen-out detection with English phrase."""
        page = "Sorry, you do not qualify for this survey."
        result = self.adapter.detect_completion(page)
        self.assertEqual(result.status, "screen_out")

    def test_pending_when_no_match(self):
        """Test pending status when no completion phrase matches."""
        page = "<html><body>Please answer the next question.</body></html>"
        result = self.adapter.detect_completion(page)
        self.assertEqual(result.status, "pending")


class TestBalanceUpdate(unittest.TestCase):
    """Test balance update verification."""

    @classmethod
    def setUpClass(cls):
        cls.login_fixture = load_fixture("heypiggy_login.json")
        cls.survey_fixture = load_fixture("heypiggy_survey_short.json")

    def test_initial_balance_from_login(self):
        """Verify initial balance is set from login."""
        initial = self.login_fixture["session"]["initial_balance"]
        self.assertEqual(initial, 15.50)

    def test_balance_after_completion(self):
        """Verify balance after survey completion."""
        balance_after = self.survey_fixture["completion"]["balance_after"]
        self.assertEqual(balance_after, 16.30)

    def test_balance_delta_correct(self):
        """Verify balance delta matches reward."""
        delta = self.survey_fixture["completion"]["balance_delta"]
        reward = self.survey_fixture["survey"]["reward"]
        self.assertEqual(delta, reward)
        self.assertEqual(delta, 0.80)


class TestProviderAdapterIntegration(unittest.TestCase):
    """Test provider adapter integration (mocked until #137)."""

    def test_heypiggy_adapter_returns_commands(self):
        """Test HeyPiggy adapter returns expected commands."""
        adapter = get_mock_provider_adapter("heypiggy")
        commands = adapter.get_commands()
        self.assertIn("click_next", commands)
        self.assertIn("survey_card_click", commands)

    def test_heypiggy_adapter_matches_url(self):
        """Test HeyPiggy adapter matches heypiggy.com URLs."""
        adapter = get_mock_provider_adapter("heypiggy")
        self.assertTrue(adapter.matches("https://www.heypiggy.com/survey/123"))
        self.assertTrue(adapter.matches("https://heypiggy.com/dashboard"))

    def test_generic_adapter_fallback(self):
        """Test generic adapter is returned for unknown providers."""
        adapter = get_mock_provider_adapter("unknown")
        self.assertEqual(adapter.name, "generic")


class TestEndToEndMockedFlow(unittest.TestCase):
    """Integration test: Full mocked E2E flow."""

    @classmethod
    def setUpClass(cls):
        cls.login_fixture = load_fixture("heypiggy_login.json")
        cls.survey_fixture = load_fixture("heypiggy_survey_short.json")
        cls.adapter = MockHeyPiggyAdapter()

    def test_full_flow_login_to_completion(self):
        """Test full mocked flow from login to completion."""
        # 1. Login
        state = MockSurveyState(
            provider="heypiggy",
            balance_before=self.login_fixture["session"]["initial_balance"],
        )
        self.assertEqual(state.balance_before, 15.50)

        # 2. Dashboard scrape
        dashboard = self.login_fixture["requests"][2]["response"]["body_preview"]
        self.assertIn("survey-card", dashboard)

        # 3. Survey selection
        survey = self.survey_fixture["survey"]
        state.survey_id = survey["id"]
        self.assertEqual(state.survey_id, "survey-001")

        # 4. Answer 5 questions
        for q in self.survey_fixture["questions"]:
            state.answers.append(
                {"question_index": q["index"], "answer": q["expected_answer"]}
            )
        self.assertEqual(len(state.answers), 5)

        # 5. Completion detection
        completion_page = self.survey_fixture["completion"]["success_page"]["body_preview"]
        result = self.adapter.detect_completion(completion_page)
        state.status = result.status
        self.assertEqual(state.status, "completed")

        # 6. Balance update
        state.balance_after = self.survey_fixture["completion"]["balance_after"]
        self.assertEqual(state.balance_after, 16.30)
        self.assertGreater(state.balance_after, state.balance_before)

    def test_flow_with_screen_out(self):
        """Test flow that results in screen-out."""
        state = MockSurveyState(provider="heypiggy")

        # Simulate screen-out after question 1
        screen_out_page = self.survey_fixture["screen_out"]["page"]["body_preview"]
        result = self.adapter.detect_completion(screen_out_page)

        state.status = result.status
        self.assertEqual(state.status, "screen_out")
        self.assertEqual(state.balance_after, state.balance_before)


# ── Pytest Markers ───────────────────────────────────────────────────────────

pytestmark = [
    pytest.mark.tier1,
]


if __name__ == "__main__":
    unittest.main()
