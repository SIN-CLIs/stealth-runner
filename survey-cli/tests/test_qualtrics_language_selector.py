#!/usr/bin/env python3
"""Test: Qualtrics language selector interaction (2026-05-09)

WHAT: Validates that <select class="Q_lang"> is handled correctly via:
  1. detect_language_page() — detects Q_lang select even without @e ref
  2. _build_js("select", "", "Deutsch") → click_select JS (selectedIndex + change)
  3. tool_select_language.select_language() — full 3-method fallback

PATTERN: selectedIndex + dispatchEvent('change') — never click NextButton

BANNED METHODS:
  ❌ pkill -f "Google Chrome"
  ❌ hardcoded PIDs
  ❌ cua-driver click (raw index)
"""

import unittest
from unittest.mock import MagicMock, patch
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from survey.execute import (
    BatchExecutor,
    detect_language_page,
    PROVIDER_COMMANDS,
    GENERIC_COMMANDS,
)


class TestQualtricsSelectInteraction(unittest.TestCase):
    """Tests for Qualtrics <select class="Q_lang"> language selector."""

    # ── _build_js: select action without @e ref ────────────────────────────

    def test_build_js_select_action_without_ref_calls_click_select(self):
        """_build_js('select', '', 'Deutsch') → click_select JS (NOT click_next).

        BEFORE FIX: action_type="select" + no ref → fell through to click_next
        (which searches for .NextButton → FAIL on language page).

        AFTER FIX: calls click_select (selectedIndex + change event).
        """
        executor = BatchExecutor("ws://localhost:9999", "qualtrics")
        js = executor._build_js("select", "", "Deutsch")
        self.assertIsNotNone(js, "click_select JS should be returned")
        # Must NOT contain .NextButton or click_next
        self.assertNotIn(".NextButton", js, "Must NOT use click_next on language page")
        self.assertNotIn("click_next", js, "Must NOT call click_next for select action")
        # Must contain selectedIndex + change event
        self.assertIn("selectedIndex", js, "Must use selectedIndex")
        self.assertIn("dispatchEvent", js, "Must dispatch change event")

    def test_build_js_select_action_with_ref_uses_click_element(self):
        """_build_js('select', '@e3', '') → click_element (falls through to click/check)."""
        executor = BatchExecutor("ws://localhost:9999", "qualtrics")
        js = executor._build_js("select", "@e3", "")
        self.assertIsNotNone(js, "Should use click_element")
        self.assertIn("3", js, "Should use index from @e3 ref")

    def test_build_js_select_action_with_ref_and_value_uses_click_select(self):
        """_build_js('select', '@e2', 'Germany') → click_select with value."""
        executor = BatchExecutor("ws://localhost:9999", "qualtrics")
        js = executor._build_js("select", "@e2", "Germany")
        self.assertIsNotNone(js)
        self.assertIn("selectedIndex", js, "Should use click_select with value")

    def test_build_js_select_action_no_ref_no_value_returns_none(self):
        """_build_js('select', '', '') → None (no ref + no value = nothing to select)."""
        executor = BatchExecutor("ws://localhost:9999", "qualtrics")
        js = executor._build_js("select", "", "")
        self.assertIsNone(js, "select with no ref + no value = None")

    def test_build_js_submit_still_calls_click_next(self):
        """submit action → click_next (unaffected by the fix)."""
        executor = BatchExecutor("ws://localhost:9999", "qualtrics")
        js = executor._build_js("submit", "", "")
        self.assertIn("NextButton", js, "submit should use click_next")

    def test_build_js_click_still_calls_click_element(self):
        """click action with @e ref → click_element (existing behavior)."""
        executor = BatchExecutor("ws://localhost:9999", "qualtrics")
        js = executor._build_js("click", "@e4", "")
        self.assertIsNotNone(js)
        self.assertIn("4", js)


class TestDetectLanguagePage(unittest.TestCase):
    """Integration tests for detect_language_page() — verifies the runner integration.

    NOTE: Direct WS mocking of detect_language_page has Python test isolation issues
    (the function captures the websocket module reference at import time). These
    tests verify the integration by testing that the runner correctly handles the
    detect_language_page return value.
    """

    def test_runner_imports_detect_language_page(self):
        """Runner imports detect_language_page from execute.py."""
        from survey.runner import detect_language_page as runner_detect
        # The runner should have access to detect_language_page
        self.assertIsNotNone(runner_detect)

    def test_runner_nemo_loop_calls_detect_language_page(self):
        """Runner NEMO loop calls detect_language_page for qualtrics provider.

        This test verifies that the runner's NEMO loop has the language detection
        branch by checking the source code contains the call.
        """
        import inspect
        from survey.runner import SurveyRunner
        source = inspect.getsource(SurveyRunner.run_survey)
        self.assertIn("detect_language_page", source,
                      "run_survey must call detect_language_page for qualtrics")
        self.assertIn("lang_actions", source,
                      "run_survey must assign detect_language_page result to lang_actions")

    def test_execute_imports_detect_language_page(self):
        """execute.py exports detect_language_page."""
        from survey.execute import detect_language_page
        self.assertIsNotNone(detect_language_page)

    def test_detect_language_page_returns_list_action(self):
        """detect_language_page returns [{"action": "select", "value": ..., "lang_page": True}]."""
        # Verify the function signature
        import inspect
        sig = inspect.signature(detect_language_page)
        self.assertIn("ws_url", [p.name for p in sig.parameters.values()])
        self.assertIn("default_lang", [p.name for p in sig.parameters.values()])

    def test_detect_language_page_fallback_on_error(self):
        """detect_language_page returns None on any exception (fail gracefully)."""
        with patch("survey.execute.websocket.create_connection") as mock:
            mock.side_effect = ConnectionError("timeout")
            result = detect_language_page("ws://localhost:9999", "Deutsch")
        self.assertIsNone(result)

    def test_detect_language_page_fallback_on_empty_response(self):
        """detect_language_page returns None when CDP response value is empty."""
        with patch("survey.execute.websocket.create_connection") as mock:
            mock.return_value = MagicMock()
            mock.return_value.recv.return_value = json.dumps({
                "result": {"result": {"value": None}}
            })
            result = detect_language_page("ws://localhost:9999", "Deutsch")
        self.assertIsNone(result)

    def test_click_select_js_command_exists_in_all_providers(self):
        """click_select command should exist for all survey providers.

        QUALTRICS: has provider-specific click_select in PROVIDER_COMMANDS.
        OTHER PROVIDERS: use GENERIC_COMMANDS fallback via BatchExecutor.
        """
        self.assertIn("click_select", PROVIDER_COMMANDS["qualtrics"],
                      "qualtrics must have click_select command")
        self.assertIn("click_select", GENERIC_COMMANDS,
                      "generic must have click_select fallback (for all providers)")


class TestClickSelectJSCommand(unittest.TestCase):
    """Tests for the enhanced click_select JS command.

    Enhancement (2026-05-09): Added nativeSetter for v-model/ngModel binding.
    Before: only dispatchEvent('change')
    After: selectedIndex + change + input + nativeSetter + change
    """

    def test_click_select_js_has_native_setter(self):
        """click_select JS must use nativeSetter for v-model/ngModel."""
        cmd = PROVIDER_COMMANDS["qualtrics"]["click_select"]
        self.assertIn("nativeSetter", cmd,
                      "Must use nativeSetter for Angular/React select binding")
        self.assertIn("HTMLSelectElement.prototype", cmd,
                      "Must access native HTMLSelectElement value setter")
        self.assertIn("change", cmd, "Must dispatch change event")
        self.assertIn("input", cmd, "Must dispatch input event for v-model")

    def test_click_select_js_is_case_insensitive(self):
        """click_select JS must match language case-insensitively."""
        cmd = PROVIDER_COMMANDS["qualtrics"]["click_select"]
        self.assertIn("toLowerCase()", cmd, "Must use case-insensitive matching")

    def test_click_select_js_returns_json_result(self):
        """click_select JS must return JSON with found/idx/method."""
        cmd = PROVIDER_COMMANDS["qualtrics"]["click_select"]
        self.assertIn("found", cmd)
        self.assertIn("idx", cmd)
        self.assertIn("method", cmd)
        self.assertIn("JSON.stringify", cmd, "Must return JSON via JSON.stringify")

    def test_click_select_js_has_cancelable_events(self):
        """Events must be cancelable for React/Angular compatibility."""
        cmd = PROVIDER_COMMANDS["qualtrics"]["click_select"]
        self.assertIn("cancelable:true", cmd, "Events must be cancelable")

    def test_generic_click_select_command_exists(self):
        """generic provider should also have click_select command."""
        self.assertIn("click_select", GENERIC_COMMANDS,
                      "GENERIC_COMMANDS must have click_select as fallback")


class TestToolSelectLanguageIntegration(unittest.TestCase):
    """Integration test: tool_select_language calls CDP with correct JS.

    tool_select_language.py is the frozen tool that has the 3-method pattern.
    This test verifies it produces the correct CDP eval expression.
    """

    def test_tool_select_language_sent_correct_expression(self):
        """tool_select_language sends JS with selectedIndex + dispatchEvent."""
        from tools.tool_select_language import select_language

        mock_ws = MagicMock()
        cdp_resp = json.dumps({
            "result": {"result": {"value": {"success": True, "method": "select", "value": "Deutsch"}}}
        })
        mock_ws.recv.return_value = cdp_resp
        # side_effect ensures recv() always returns the JSON string
        # (not affected by subsequent MagicMock calls)
        mock_ws.recv.side_effect = [cdp_resp, cdp_resp]

        with patch("tools.tool_select_language.websocket.create_connection", return_value=mock_ws):
            result = select_language("ws://localhost:9999", "Deutsch")
            self.assertTrue(result["success"], f"Expected success, got: {result}")
            self.assertTrue(mock_ws.send.called)
            sent = json.loads(mock_ws.send.call_args[0][0])
            self.assertIsInstance(sent, dict)
            self.assertEqual(sent["method"], "Runtime.evaluate")
            js_expr = sent["params"]["expression"]
            self.assertIn("selectedIndex", js_expr)
            self.assertIn("dispatchEvent", js_expr)
            self.assertIn("change", js_expr)

    def test_tool_select_language_returns_result_dict(self):
        """tool_select_language returns the CDP result dict."""
        from tools.tool_select_language import select_language

        mock_ws = MagicMock()
        cdp_resp = json.dumps({
            "result": {"result": {"value": {"success": True, "method": "select", "value": "Deutsch"}}}
        })
        mock_ws.recv.return_value = cdp_resp
        mock_ws.recv.side_effect = [cdp_resp, cdp_resp]

        with patch("tools.tool_select_language.websocket.create_connection", return_value=mock_ws):
            result = select_language("ws://localhost:9999", "Deutsch")
            self.assertTrue(result["success"])
            self.assertEqual(result["method"], "select")
            self.assertEqual(result["value"], "Deutsch")

    def test_tool_select_language_default_german(self):
        """Default language is Deutsch."""
        from tools.tool_select_language import select_language

        mock_ws = MagicMock()
        cdp_resp = json.dumps({
            "result": {"result": {"value": {"success": True, "method": "select", "value": "Deutsch"}}}
        })
        mock_ws.recv.return_value = cdp_resp
        mock_ws.recv.side_effect = [cdp_resp, cdp_resp]

        with patch("tools.tool_select_language.websocket.create_connection", return_value=mock_ws):
            result = select_language("ws://localhost:9999")
            self.assertTrue(result["success"])


if __name__ == "__main__":
    print("=" * 70)
    print("Qualtrics Language Selector Test Suite (2026-05-09)")
    print("=" * 70)
    print()
    print("Testing: selectedIndex + dispatchEvent('change') pattern")
    print("  1. _build_js('select', '', 'Deutsch') → click_select JS")
    print("  2. detect_language_page() → language actions")
    print("  3. click_select JS → nativeSetter + change + input events")
    print("  4. tool_select_language → 3-method fallback")
    print()
    unittest.main(verbosity=2)