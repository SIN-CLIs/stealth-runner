"""Contract tests for ProviderAdapter registry."""

import unittest

from survey.providers import get_provider_adapter, get_provider_commands, detect_provider_completion


class TestProviderRegistry(unittest.TestCase):
    """Provider registry returns deep adapters, not scattered dicts."""

    def test_unknown_provider_uses_generic(self):
        adapter = get_provider_adapter("unknown-new-provider")
        self.assertEqual(adapter.name, "generic")
        self.assertIn("click_next", adapter.get_commands())

    def test_qualtrics_adapter_commands_include_nextbutton(self):
        commands = get_provider_commands("qualtrics")
        self.assertIn("click_next", commands)
        self.assertIn("NextButton", commands["click_next"])
        self.assertIn("LabelWrapper", commands["click_element"])

    def test_toluna_adapter_commands_include_cf_radio(self):
        commands = get_provider_commands("tolunastart")
        self.assertIn("cf-radio", commands["click_element"])

    def test_strat7_adapter_commands_include_bsbutton(self):
        commands = get_provider_commands("strat7")
        self.assertIn("bsbutton", commands["click_next"])

    def test_purespectrum_adapter_uses_cdp_marker(self):
        commands = get_provider_commands("purespectrum")
        self.assertTrue(commands["click_next"].startswith("__CDP_CLICK_BUTTON__"))

    def test_provider_completion_detects_completed(self):
        state = detect_provider_completion(
            "qualtrics",
            "Thank you for completing this survey. Your response has been recorded.",
        )
        self.assertEqual(state.status, "completed")

    def test_provider_completion_detects_screen_out(self):
        state = detect_provider_completion("generic", "Sorry, you do not qualify for this survey")
        self.assertEqual(state.status, "screen_out")


if __name__ == "__main__":
    unittest.main()
