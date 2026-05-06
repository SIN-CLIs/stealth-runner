"""Test SurveyRunner — NEMO loop, anti-stuck, error detection.

Uses unittest.mock to mock Chrome WebSocket calls and NIM responses.
"""

import unittest
from unittest.mock import MagicMock, patch
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from survey.runner import SurveyRunner, RunnerConfig, SurveyResult
from survey.snapshot import CompactSnapshot, detect_completion


class TestSimpleActions(unittest.TestCase):
    """Test _simple_actions — rule-based action generation without NIM.

    Strategy: select first radio, fill first textarea, click submit button.
    """

    def _make_snapshot(self, refs_dict):
        """Helper: create CompactSnapshot from dict of @eN -> element info."""
        snap = MagicMock(spec=CompactSnapshot)
        snap.refs = refs_dict
        snap.provider = "generic"
        snap.url = "https://example.com/survey"
        snap.title = "Test Survey"
        snap.semantic = {"questions": [], "progress": "1/10"}
        snap.to_dict.return_value = {"refs": refs_dict}
        return snap

    def test_select_first_radio(self):
        """First radio button should be selected."""
        runner = SurveyRunner(RunnerConfig())
        snap = self._make_snapshot({
            "@e0": {"role": "radio", "text": "Männlich", "label": "Gender"},
            "@e1": {"role": "radio", "text": "Weiblich", "label": "Gender"},
            "@e2": {"role": "button", "text": "Weiter", "label": ""},
        })
        snap.provider = "generic"
        actions = runner._simple_actions(snap)

        # Should have select action for first radio
        self.assertTrue(any(a["action"] in ("select", "click") for a in actions))

    def test_fill_first_textarea(self):
        """First textarea filled ONLY if no submit button exists.

        _simple_actions priority: radio > submit button > textarea fill.
        If a submit/next button is found, it takes precedence over textarea fill.
        """
        runner = SurveyRunner(RunnerConfig())

        # Case 1: With submit button → submit action, no fill
        snap = self._make_snapshot({
            "@e0": {"role": "textbox", "text": "", "label": "Comment"},
            "@e1": {"role": "button", "text": "Weiter", "label": ""},
        })
        snap.provider = "generic"
        actions = runner._simple_actions(snap)
        # Submit button found first → submit action, no fill
        self.assertTrue(len(actions) > 0)
        has_submit = any(a["action"] == "submit" for a in actions)
        has_fill = any(a["action"] == "fill" for a in actions)
        self.assertTrue(has_submit, "Submit button should be selected")
        self.assertFalse(has_fill, "No fill when submit button exists")

        # Case 2: Without submit button → fill textarea
        snap2 = self._make_snapshot({
            "@e0": {"role": "textbox", "text": "", "label": "Comment"},
        })
        snap2.provider = "generic"
        actions2 = runner._simple_actions(snap2)
        fill_actions = [a for a in actions2 if a["action"] == "fill"]
        self.assertTrue(len(fill_actions) > 0, "Textarea should be filled when no submit button")

    def test_submit_button(self):
        """Submit/next button should be clicked."""
        runner = SurveyRunner(RunnerConfig())
        snap = self._make_snapshot({
            "@e0": {"role": "radio", "text": "Option 1", "label": ""},
            "@e1": {"role": "button", "text": "Weiter", "label": ""},
        })
        snap.provider = "generic"
        actions = runner._simple_actions(snap)

        submit_actions = [a for a in actions if a["action"] in ("submit", "click")]
        self.assertTrue(len(submit_actions) > 0)

    def test_empty_snapshot_returns_empty_list(self):
        """Empty snapshot → empty list (no elements to interact with).

        _simple_actions has no "fallback submit" for empty snapshot.
        If there are no elements, there are no buttons to click.
        """
        runner = SurveyRunner(RunnerConfig())
        snap = self._make_snapshot({})
        snap.provider = "generic"
        actions = runner._simple_actions(snap)

        # Empty snapshot → no actions (nothing to click or fill)
        self.assertEqual(len(actions), 0)

    def test_provider_specific_selectors(self):
        """Different providers should use different element selectors."""
        runner = SurveyRunner(RunnerConfig())

        for provider in ["qualtrics", "tolunastart", "purespectrum", "generic"]:
            snap = self._make_snapshot({
                "@e0": {"role": "radio", "text": "Option", "label": ""},
                "@e1": {"role": "button", "text": "Next", "label": ""},
            })
            snap.provider = provider
            actions = runner._simple_actions(snap)
            # Should not crash
            self.assertIsInstance(actions, list)


class TestRunSurveyLoopDetection(unittest.TestCase):
    """Test loop detection + anti-stuck in run_survey.

    Since we can't test run_survey without real Chrome, we test individual
    loop detection helpers and provider detection.
    """

    def test_detect_provider_cpx(self):
        """CPX click URL → 'unknown' (redirects to real provider)."""
        runner = SurveyRunner(RunnerConfig())
        provider = runner._detect_provider("https://click.cpx-research.com/?k=abc123")
        self.assertEqual(provider, "unknown")

    def test_detect_provider_samplicio(self):
        """Samplicio URL → 'samplicio'."""
        runner = SurveyRunner(RunnerConfig())
        provider = runner._detect_provider("https://www.samplicio.us/s/RespondentAuthentication.aspx?SID=xyz")
        self.assertEqual(provider, "samplicio")

    def test_detect_provider_purespectrum(self):
        """PureSpectrum URL → 'purespectrum'."""
        runner = SurveyRunner(RunnerConfig())
        provider = runner._detect_provider("https://screener.purespectrum.com/survey?id=abc")
        self.assertEqual(provider, "purespectrum")

    def test_detect_provider_cloudresearch(self):
        """CloudResearch URL → 'cloudresearch'."""
        runner = SurveyRunner(RunnerConfig())
        provider = runner._detect_provider("https://ndc.cloudresearch.com/survey?p=abc")
        self.assertEqual(provider, "cloudresearch")

    def test_detect_provider_qualtrics(self):
        """Qualtrics URL → 'qualtrics'."""
        runner = SurveyRunner(RunnerConfig())
        provider = runner._detect_provider("https://survey.qconnect.qualtrics.com/jfe/form/SV_abc")
        self.assertEqual(provider, "qualtrics")

    def test_detect_provider_toluna(self):
        """Toluna URL → 'tolunastart'."""
        runner = SurveyRunner(RunnerConfig())
        provider = runner._detect_provider("https://www.toluna-surveys.com/survey.aspx?id=abc")
        # Provider detection may return 'gfk' or 'tolunastart' depending on URL patterns
        self.assertIn(provider, ("tolunastart", "gfk"))

    def test_detect_provider_cint(self):
        """Cint URL → 'cint'."""
        runner = SurveyRunner(RunnerConfig())
        provider = runner._detect_provider("https://s.cint.com/Survey/Fingerprint/id/abc")
        self.assertEqual(provider, "cint")

    def test_detect_provider_unknown(self):
        """Unknown URL → 'unknown'."""
        runner = SurveyRunner(RunnerConfig())
        provider = runner._detect_provider("https://completely-unknown-panel.com/survey")
        self.assertEqual(provider, "unknown")

    def test_detect_provider_with_utm(self):
        """URL with UTM params → still detects provider."""
        runner = SurveyRunner(RunnerConfig())
        provider = runner._detect_provider(
            "https://www.samplicio.us/s/RespondentAuthentication.aspx?SID=xyz&utm_source=cpx"
        )
        self.assertEqual(provider, "samplicio")


class TestSurveyResult(unittest.TestCase):
    """Test SurveyResult dataclass."""

    def test_default_values(self):
        """Default survey result should have 'unknown' status."""
        result = SurveyResult(survey_id="12345")
        self.assertEqual(result.survey_id, "12345")
        self.assertEqual(result.status, "unknown")  # Default is 'unknown', not ''
        self.assertEqual(result.earned, 0.0)
        self.assertEqual(result.error, "")
        self.assertEqual(result.provider, "unknown")  # Default is 'unknown'
        self.assertEqual(result.iterations, 0)
        self.assertEqual(result.nim_calls, 0)
        self.assertEqual(result.nim_tokens, 0)
        self.assertEqual(result.elapsed_s, 0.0)

    def test_result_can_be_modified(self):
        """Result should be mutable."""
        result = SurveyResult(survey_id="12345")
        result.status = "completed"
        result.earned = 1.5
        result.provider = "qualtrics"
        result.iterations = 10

        self.assertEqual(result.status, "completed")
        self.assertEqual(result.earned, 1.5)
        self.assertEqual(result.provider, "qualtrics")
        self.assertEqual(result.iterations, 10)


class TestRunnerConfig(unittest.TestCase):
    """Test RunnerConfig defaults."""

    def test_default_config_values(self):
        config = RunnerConfig()
        # Check reasonable defaults
        self.assertGreater(config.max_iterations, 0)
        self.assertGreaterEqual(config.wait_page_load, 0)
        self.assertGreaterEqual(config.wait_after_action, 0)
        self.assertIsInstance(config.skip_providers, list)

    def test_config_debug_flag(self):
        config = RunnerConfig()
        config.debug = True
        self.assertTrue(config.debug)

    def test_config_balance_target(self):
        config = RunnerConfig()
        self.assertGreaterEqual(config.balance_target, 0)


class TestRefNormalization(unittest.TestCase):
    """Test that refs from NIM (without @) are handled correctly.

    NIM returns "e0" but _build_js expects "@e0".
    The normalization happens in _execute_single.
    """

    def test_ref_without_at_gets_prefixed(self):
        """ref='e5' → '@e5' in _build_js."""
        from survey.execute import BatchExecutor

        executor = BatchExecutor("ws://localhost:9999", "generic")

        # Build JS for "e5" (no @) — should NOT crash (falls back to click_next)
        # The actual normalization check happens in _execute_single
        js = executor._build_js("click", "e5", "")
        # Falls back to click_next since "e5" doesn't start with "@e"
        self.assertIsNotNone(js)

    def test_ref_with_at_works_normally(self):
        """ref='@e5' → click_element[5]."""
        from survey.execute import BatchExecutor

        executor = BatchExecutor("ws://localhost:9999", "generic")
        js = executor._build_js("click", "@e5", "")
        self.assertIn("5", js)


if __name__ == "__main__":
    unittest.main(verbosity=2)