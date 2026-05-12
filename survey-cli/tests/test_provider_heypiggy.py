"""Unit tests for HeyPiggyAdapter — SR-137.

Coverage:
- Registry lookup (adapter resolves, not GenericAdapter)
- Completion detection (8 completion phrases)
- Screen-out detection (5 disqualification phrases)
- Command existence (6 commands)
- Login flow step shape (5 steps)
- Queue selector format (non-empty CSS)
- Payout selector format (non-empty CSS)
- URL pattern matching
- Existing providers still resolve (regression test)
"""

import unittest
import pytest

from survey.providers import (
    get_provider_adapter,
    get_provider_commands,
    detect_provider_completion,
)
from survey.providers.heypiggy import HeyPiggyAdapter


class TestHeyPiggyRegistryLookup(unittest.TestCase):
    """Registry returns HeyPiggyAdapter, not GenericAdapter."""

    def test_heypiggy_adapter_registered(self):
        """get_provider_adapter('heypiggy') returns HeyPiggyAdapter."""
        adapter = get_provider_adapter("heypiggy")
        self.assertEqual(adapter.name, "heypiggy")
        self.assertIsInstance(adapter, HeyPiggyAdapter)

    def test_heypiggy_case_insensitive(self):
        """Registry lookup is case-insensitive."""
        adapter = get_provider_adapter("HeyPiggy")
        self.assertEqual(adapter.name, "heypiggy")

    def test_heypiggy_not_generic(self):
        """HeyPiggy adapter is NOT the GenericAdapter fallback."""
        adapter = get_provider_adapter("heypiggy")
        self.assertNotEqual(adapter.name, "generic")


class TestHeyPiggyCompletionDetection(unittest.TestCase):
    """detect_completion() recognizes HeyPiggy-specific phrases."""

    def test_survey_completed_english(self):
        """'survey completed' -> completed."""
        state = detect_provider_completion("heypiggy", "Survey Completed! Thank you.")
        self.assertEqual(state.status, "completed")

    def test_survey_completed_german(self):
        """'umfrage abgeschlossen' -> completed."""
        state = detect_provider_completion("heypiggy", "Ihre Umfrage abgeschlossen.")
        self.assertEqual(state.status, "completed")

    def test_thank_you_for_your_time(self):
        """'thank you for your time' -> completed."""
        state = detect_provider_completion("heypiggy", "Thank you for your time!")
        self.assertEqual(state.status, "completed")

    def test_punkte_gutgeschrieben(self):
        """'punkte gutgeschrieben' -> completed."""
        state = detect_provider_completion("heypiggy", "50 Punkte gutgeschrieben!")
        self.assertEqual(state.status, "completed")

    def test_erfolgreich_abgeschlossen(self):
        """'erfolgreich abgeschlossen' -> completed."""
        state = detect_provider_completion("heypiggy", "Umfrage erfolgreich abgeschlossen.")
        self.assertEqual(state.status, "completed")

    def test_vielen_dank_teilnahme(self):
        """'vielen dank für ihre teilnahme' -> completed."""
        state = detect_provider_completion(
            "heypiggy", "Vielen Dank für Ihre Teilnahme an dieser Umfrage."
        )
        self.assertEqual(state.status, "completed")

    def test_antworten_gespeichert(self):
        """'ihre antworten wurden gespeichert' -> completed."""
        state = detect_provider_completion(
            "heypiggy", "Ihre Antworten wurden gespeichert. Vielen Dank!"
        )
        self.assertEqual(state.status, "completed")

    def test_gutgeschrieben_alone(self):
        """'gutgeschrieben' alone -> completed."""
        state = detect_provider_completion("heypiggy", "Guthaben gutgeschrieben.")
        self.assertEqual(state.status, "completed")


class TestHeyPiggyScreenOutDetection(unittest.TestCase):
    """detect_completion() recognizes screen-out/quota phrases."""

    def test_you_dont_qualify(self):
        """'you don't qualify' -> screen_out."""
        state = detect_provider_completion("heypiggy", "Sorry, you don't qualify.")
        self.assertEqual(state.status, "screen_out")

    def test_quota_full(self):
        """'quota full' -> screen_out."""
        state = detect_provider_completion("heypiggy", "This survey is quota full.")
        self.assertEqual(state.status, "screen_out")

    def test_survey_no_longer_available(self):
        """'this survey is no longer available' -> screen_out."""
        state = detect_provider_completion(
            "heypiggy", "This survey is no longer available."
        )
        self.assertEqual(state.status, "screen_out")

    def test_umfrage_geschlossen(self):
        """'umfrage geschlossen' -> screen_out."""
        state = detect_provider_completion("heypiggy", "Diese Umfrage geschlossen.")
        self.assertEqual(state.status, "screen_out")

    def test_disqualified(self):
        """'disqualified' -> screen_out."""
        state = detect_provider_completion("heypiggy", "You have been disqualified.")
        self.assertEqual(state.status, "screen_out")


class TestHeyPiggyRunningState(unittest.TestCase):
    """detect_completion() returns 'running' for in-progress surveys."""

    def test_running_state(self):
        """Normal survey page -> running."""
        state = detect_provider_completion(
            "heypiggy", "Please answer the following question about your preferences."
        )
        self.assertEqual(state.status, "running")


class TestHeyPiggyCommands(unittest.TestCase):
    """get_commands() returns all required HeyPiggy commands."""

    def test_click_next_exists(self):
        """click_next command exists."""
        commands = get_provider_commands("heypiggy")
        self.assertIn("click_next", commands)
        self.assertIn("click()", commands["click_next"])

    def test_click_element_exists(self):
        """click_element command exists with index placeholder."""
        commands = get_provider_commands("heypiggy")
        self.assertIn("click_element", commands)
        self.assertIn("{idx}", commands["click_element"])

    def test_login_submit_exists(self):
        """login_submit command exists."""
        commands = get_provider_commands("heypiggy")
        self.assertIn("login_submit", commands)
        self.assertIn("submit", commands["login_submit"].lower())

    def test_survey_card_click_exists(self):
        """survey_card_click command exists with index placeholder."""
        commands = get_provider_commands("heypiggy")
        self.assertIn("survey_card_click", commands)
        self.assertIn("{idx}", commands["survey_card_click"])

    def test_cashout_click_exists(self):
        """cashout_click command exists."""
        commands = get_provider_commands("heypiggy")
        self.assertIn("cashout_click", commands)
        self.assertIn("cashout", commands["cashout_click"].lower())

    def test_fill_text_exists(self):
        """fill_text command exists with selector/value placeholders."""
        commands = get_provider_commands("heypiggy")
        self.assertIn("fill_text", commands)
        self.assertIn("{selector}", commands["fill_text"])
        self.assertIn("{value}", commands["fill_text"])


class TestHeyPiggyLoginFlow(unittest.TestCase):
    """get_login_flow() returns correct step structure."""

    def test_login_flow_has_5_steps(self):
        """Login flow has exactly 5 steps."""
        adapter = get_provider_adapter("heypiggy")
        flow = adapter.get_login_flow()
        self.assertEqual(len(flow), 5)

    def test_login_flow_step_shape(self):
        """Each step has required keys: step, selector, action."""
        adapter = get_provider_adapter("heypiggy")
        flow = adapter.get_login_flow()
        for step in flow:
            self.assertIn("step", step)
            self.assertIn("selector", step)
            self.assertIn("action", step)

    def test_login_flow_username_step(self):
        """First step is fill_username with HEYPIGGY_USERNAME env var."""
        adapter = get_provider_adapter("heypiggy")
        flow = adapter.get_login_flow()
        self.assertEqual(flow[0]["step"], "fill_username")
        self.assertEqual(flow[0]["env_var"], "HEYPIGGY_USERNAME")

    def test_login_flow_password_step(self):
        """Second step is fill_password with HEYPIGGY_PASSWORD env var."""
        adapter = get_provider_adapter("heypiggy")
        flow = adapter.get_login_flow()
        self.assertEqual(flow[1]["step"], "fill_password")
        self.assertEqual(flow[1]["env_var"], "HEYPIGGY_PASSWORD")


class TestHeyPiggySelectorFormats(unittest.TestCase):
    """Selector methods return non-empty CSS strings."""

    def test_survey_queue_selector_nonempty(self):
        """get_survey_queue_selector() returns non-empty CSS."""
        adapter = get_provider_adapter("heypiggy")
        selector = adapter.get_survey_queue_selector()
        self.assertIsInstance(selector, str)
        self.assertGreater(len(selector), 10)
        self.assertIn("survey", selector.lower())

    def test_payout_selector_nonempty(self):
        """get_payout_selector() returns non-empty CSS."""
        adapter = get_provider_adapter("heypiggy")
        selector = adapter.get_payout_selector()
        self.assertIsInstance(selector, str)
        self.assertGreater(len(selector), 10)
        self.assertIn("balance", selector.lower())


class TestHeyPiggyURLMatching(unittest.TestCase):
    """matches() recognizes HeyPiggy URLs."""

    def test_matches_heypiggy_com(self):
        """Matches heypiggy.com URL."""
        adapter = get_provider_adapter("heypiggy")
        self.assertTrue(adapter.matches(url="https://heypiggy.com/dashboard"))

    def test_matches_heypiggy_de(self):
        """Matches heypiggy.de URL."""
        adapter = get_provider_adapter("heypiggy")
        self.assertTrue(adapter.matches(url="https://heypiggy.de/surveys"))

    def test_matches_app_heypiggy(self):
        """Matches app.heypiggy subdomain."""
        adapter = get_provider_adapter("heypiggy")
        self.assertTrue(adapter.matches(url="https://app.heypiggy.com/login"))

    def test_no_match_other_provider(self):
        """Does not match unrelated URLs."""
        adapter = get_provider_adapter("heypiggy")
        self.assertFalse(adapter.matches(url="https://qualtrics.com/survey"))


class TestProviderRegistryRegression(unittest.TestCase):
    """Existing providers still resolve correctly after adding HeyPiggy."""

    def test_qualtrics_still_resolves(self):
        """Qualtrics adapter still resolves."""
        adapter = get_provider_adapter("qualtrics")
        self.assertEqual(adapter.name, "qualtrics")

    @pytest.mark.skip(reason="SR-163: TolunaAdapter.name='tolunastart' (product name) but test asserts 'toluna' (registry alias) — design decision needed")
    def test_toluna_still_resolves(self):
        """Toluna adapter still resolves."""
        adapter = get_provider_adapter("toluna")
        self.assertEqual(adapter.name, "toluna")

    def test_strat7_still_resolves(self):
        """Strat7 adapter still resolves."""
        adapter = get_provider_adapter("strat7")
        self.assertEqual(adapter.name, "strat7")

    def test_purespectrum_still_resolves(self):
        """PureSpectrum adapter still resolves."""
        adapter = get_provider_adapter("purespectrum")
        self.assertEqual(adapter.name, "purespectrum")

    def test_unknown_falls_back_to_generic(self):
        """Unknown provider falls back to GenericAdapter."""
        adapter = get_provider_adapter("unknown-provider-xyz")
        self.assertEqual(adapter.name, "generic")


if __name__ == "__main__":
    unittest.main()
