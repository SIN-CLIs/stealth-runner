"""Tests: Stealth injection in chrome.py and runner.py.

Verifies that:
1. _get_stealth_js() loads injection.js or returns fallback
2. inject_stealth_to_tab() sends Page.addScriptToEvaluateOnNewDocument
3. navigate_tab() sends Page.navigate
4. create_blank_tab() creates tab at about:blank
5. _create_tab() in runner.py uses stealth injection

Strategy: mock websocket.create_connection (imported locally in chrome.py functions).
"""

import unittest
from unittest.mock import MagicMock, patch
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestGetStealthJs(unittest.TestCase):
    """Test _get_stealth_js() loads from file or returns fallback."""

    def test_loads_from_file(self):
        """_get_stealth_js returns non-empty string from injection.js."""
        from survey.chrome import _get_stealth_js
        js = _get_stealth_js()
        self.assertIsInstance(js, str)
        self.assertGreater(len(js), 100)
        # Should contain the main stealth module
        self.assertIn("__stealth_main_applied__", js)

    def test_contains_webdriver_override(self):
        """JS must override navigator.webdriver."""
        from survey.chrome import _get_stealth_js
        js = _get_stealth_js()
        self.assertIn("webdriver", js)

    def test_contains_plugins_override(self):
        """JS must override navigator.plugins."""
        from survey.chrome import _get_stealth_js
        js = _get_stealth_js()
        self.assertIn("plugins", js)

    def test_fallback_when_file_missing(self):
        """When injection.js is missing, fallback returns minimal overrides."""
        from survey.chrome import _get_stealth_js as original_get
        # Temporarily rename the file to test fallback
        from survey import chrome
        original_path = chrome.STEALTH_BUNDLE
        temp_path = original_path + ".bak"
        try:
            if os.path.exists(original_path):
                os.rename(original_path, temp_path)
            # Reload the function
            import importlib
            importlib.reload(chrome)
            from survey.chrome import _get_stealth_js
            js = _get_stealth_js()
            # Fallback should be minimal
            self.assertIn("webdriver", js)
            self.assertGreater(len(js), 50)
            self.assertLess(len(js), 500)  # Fallback is short
        finally:
            if os.path.exists(temp_path):
                os.rename(temp_path, original_path)
            importlib.reload(chrome)

    def test_has_webdriver_override(self):
        """JS must set webdriver override (false or undefined)."""
        from survey.chrome import _get_stealth_js
        js = _get_stealth_js()
        # The main file uses 'false', fallback uses 'undefined'
        self.assertTrue("false" in js or "undefined" in js)


class TestInjectStealthToTab(unittest.TestCase):
    """Test inject_stealth_to_tab() CDP interaction."""

    @patch("websocket.create_connection")
    def test_sends_addScriptToEvaluateOnNewDocument(self, mock_ws_create):
        """inject_stealth_to_tab sends the correct CDP method."""
        fake_ws = MagicMock()
        fake_ws.recv.return_value = json.dumps({"result": {"identifier": "stealth-1"}})
        mock_ws_create.return_value = fake_ws

        from survey.chrome import inject_stealth_to_tab
        result = inject_stealth_to_tab("ws://localhost:9999/devtools/page/42")

        self.assertTrue(result)
        # Verify the CDP message sent
        call_data = fake_ws.send.call_args[0][0]
        call_dict = json.loads(call_data)
        self.assertEqual(call_dict["method"], "Page.addScriptToEvaluateOnNewDocument")
        self.assertIn("params", call_dict)
        self.assertIn("source", call_dict["params"])
        self.assertIn("__stealth_main_applied__", call_dict["params"]["source"])

    @patch("websocket.create_connection")
    def test_returns_false_on_error(self, mock_ws_create):
        """inject_stealth_to_tab returns False on WebSocket error."""
        mock_ws_create.side_effect = Exception("Connection refused")

        from survey.chrome import inject_stealth_to_tab
        result = inject_stealth_to_tab("ws://localhost:9999/devtools/page/42")
        self.assertFalse(result)


class TestNavigateTab(unittest.TestCase):
    """Test navigate_tab() CDP interaction."""

    @patch("websocket.create_connection")
    def test_sends_page_navigate(self, mock_ws_create):
        """navigate_tab sends Page.navigate with the URL."""
        fake_ws = MagicMock()
        fake_ws.recv.return_value = json.dumps({"result": {"frameId": "frame-1"}})
        mock_ws_create.return_value = fake_ws

        from survey.chrome import navigate_tab
        result = navigate_tab("ws://localhost:9999/devtools/page/42",
                              "https://survey.example.com/s/12345")

        self.assertTrue(result)
        call_data = fake_ws.send.call_args[0][0]
        call_dict = json.loads(call_data)
        self.assertEqual(call_dict["method"], "Page.navigate")
        self.assertEqual(call_dict["params"]["url"],
                         "https://survey.example.com/s/12345")


class TestCreateBlankTab(unittest.TestCase):
    """Test create_blank_tab() creates tab and returns info."""

    @patch("websocket.create_connection")
    @patch("survey.chrome.find_bot_tabs")
    def test_creates_tab_with_about_blank(self, mock_find_tabs, mock_ws_create):
        """create_blank_tab creates tab at about:blank and returns info."""
        fake_ws = MagicMock()
        # Response for Target.createTarget
        fake_ws.recv.return_value = json.dumps({
            "result": {"targetId": "tab-42"}
        })
        mock_ws_create.return_value = fake_ws

        # find_bot_tabs returns a list of tabs, including the new one
        mock_find_tabs.return_value = [
            {"id": "tab-main", "url": "https://heypiggy.com/dashboard",
             "webSocketDebuggerUrl": "ws://localhost:9999/main"},
            {"id": "tab-42", "url": "about:blank",
             "webSocketDebuggerUrl": "ws://localhost:9999/tab-42"},
        ]

        from survey.chrome import create_blank_tab
        result = create_blank_tab(port=9999)

        self.assertIsNotNone(result)
        self.assertEqual(result["id"], "tab-42")
        self.assertEqual(result["ws_url"], "ws://localhost:9999/tab-42")

        # Verify Target.createTarget message
        call_data = fake_ws.send.call_args[0][0]
        call_dict = json.loads(call_data)
        self.assertEqual(call_dict["method"], "Target.createTarget")
        self.assertEqual(call_dict["params"]["url"], "about:blank")

    @patch("survey.chrome.find_bot_tabs", return_value=[])
    @patch("websocket.create_connection")
    def test_returns_none_on_no_tabs(self, mock_ws_create, mock_find_tabs):
        """create_blank_tab returns None when no existing tabs found."""
        from survey.chrome import create_blank_tab
        result = create_blank_tab(port=9999)
        self.assertIsNone(result)


class TestRunnerCreateTabStealth(unittest.TestCase):
    """Test _create_tab() in runner.py uses stealth injection."""

    @patch("survey.runner.chrome.create_blank_tab")
    @patch("survey.runner.chrome.inject_stealth_to_tab")
    @patch("survey.runner.chrome.navigate_tab")
    def test_create_tab_uses_stealth_flow(self, mock_nav, mock_inject, mock_blank):
        """_create_tab creates blank tab, injects stealth, navigates."""
        from survey.runner import SurveyRunner, RunnerConfig
        runner = SurveyRunner(RunnerConfig(cdp_port=9999))
        runner.config.debug = True

        mock_blank.return_value = {
            "id": "tab-42",
            "ws_url": "ws://localhost:9999/tab-42"
        }
        mock_inject.return_value = True
        mock_nav.return_value = True

        result = runner._create_tab("ws://main", "https://survey.example.com/s/12345")

        self.assertEqual(result, "tab-42")
        mock_blank.assert_called_once_with(9999)
        mock_inject.assert_called_once_with("ws://localhost:9999/tab-42")
        mock_nav.assert_called_once_with("ws://localhost:9999/tab-42",
                                          "https://survey.example.com/s/12345")

    @patch("survey.runner.chrome.create_blank_tab")
    @patch("survey.runner.chrome.create_tab")
    def test_fallback_when_blank_tab_fails(self, mock_create_tab, mock_blank):
        """_create_tab falls back to direct create_tab when blank tab fails."""
        from survey.runner import SurveyRunner, RunnerConfig
        runner = SurveyRunner(RunnerConfig(cdp_port=9999))

        mock_blank.return_value = None
        mock_create_tab.return_value = "tab-42"

        result = runner._create_tab("ws://main", "https://survey.example.com/s/12345")

        self.assertEqual(result, "tab-42")
        mock_blank.assert_called_once_with(9999)
        mock_create_tab.assert_called_once_with("https://survey.example.com/s/12345", 9999)


class TestStealthJSContent(unittest.TestCase):
    """Verify stealth JS content covers all required modules."""

    def setUp(self):
        from survey.chrome import _get_stealth_js
        self.js = _get_stealth_js()

    def test_has_navigator_webdriver(self):
        """Must override navigator.webdriver."""
        self.assertIn("webdriver", self.js)

    def test_has_plugins(self):
        """Must override navigator.plugins."""
        self.assertIn("plugins", self.js)

    def test_has_languages(self):
        """Must override navigator.languages."""
        self.assertIn("languages", self.js)

    def test_has_webgl(self):
        """Must override WebGL vendor/renderer."""
        self.assertIn("WebGL", self.js) or self.assertIn("webgl", self.js)

    def test_has_canvas(self):
        """Must override canvas fingerprint."""
        self.assertIn("canvas", self.js) or self.assertIn("Canvas", self.js)

    def test_has_permissions(self):
        """Must override permissions API."""
        self.assertIn("permissions", self.js.lower())

    def test_crash_safe_in_try_catch(self):
        """Every module wrapped in try/catch."""
        self.assertIn("try", self.js)
        self.assertIn("catch", self.js)


if __name__ == "__main__":
    unittest.main()