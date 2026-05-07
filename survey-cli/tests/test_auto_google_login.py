#!/usr/bin/env python3
"""Test for auto_google_login.py — CUA-ONLY 6-Step Login.

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
from unittest.mock import patch, MagicMock
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestAutoGoogleLogin(unittest.TestCase):
    """Test helpers and execute flow with mocked external deps."""

    def test_find_idx_matches_keyword(self):
        """_find_idx finds element by keyword in tree."""
        mock_sm = MagicMock()
        with patch.dict("sys.modules", {"cli.modules.session_manager": MagicMock()}):
            import cli.modules.auto_google_login as login_mod
            login_mod._SessionManager = mock_sm

        tree = [
            "- [10] AXRadioButton ('Männlich')",
            "- [54] AXLink ('Google Login-Symbol')",
            "- [200] AXButton ('Weiter')",
        ]
        idx = login_mod._find_idx(tree, "google login-symbol", ["AXLink"])
        self.assertEqual(idx, 54)

    def test_find_idx_no_match(self):
        """_find_idx returns None when keyword not found."""
        mock_sm = MagicMock()
        with patch.dict("sys.modules", {"cli.modules.session_manager": MagicMock()}):
            import cli.modules.auto_google_login as login_mod
            login_mod._SessionManager = mock_sm

        tree = ["- [10] AXRadioButton ('Männlich')"]
        idx = login_mod._find_idx(tree, "nonexistent", ["AXButton"])
        self.assertIsNone(idx)

    def test_find_idx_case_insensitive(self):
        """_find_idx matches case-insensitively."""
        mock_sm = MagicMock()
        with patch.dict("sys.modules", {"cli.modules.session_manager": MagicMock()}):
            import cli.modules.auto_google_login as login_mod
            login_mod._SessionManager = mock_sm

        tree = ["- [200] AXButton ('WEITER')"]
        idx = login_mod._find_idx(tree, "weiter", ["AXButton"])
        self.assertEqual(idx, 200)

    @patch("cli.modules.auto_google_login.subprocess.run")
    @patch("cli.modules.auto_google_login.time.sleep")
    def test_execute_already_logged_in(self, mock_sleep, mock_run):
        """When HeyPiggy already logged in, returns ok immediately."""
        mock_sm = MagicMock()
        with patch.dict("sys.modules", {"cli.modules.session_manager": MagicMock()}):
            from cli.modules import auto_google_login as login_mod
            login_mod._SessionManager = mock_sm

        def _run_side(cmd, **kw):
            res = MagicMock()
            res.stdout = json.dumps({"windows": [{
                "pid": 12345, "window_id": 100,
                "title": "HeyPiggy – Verdienen – Abmelden",
                "app_name": "Google Chrome",
                "bounds": {"height": 800, "x": 0, "y": 0}
            }]})
            res.returncode = 0
            res.stderr = ""
            return res
        mock_run.side_effect = _run_side

        result = login_mod.execute(pid=12345)
        self.assertEqual(result["status"], "ok")
        self.assertIn(result["pid"], [12345])

    @patch("cli.modules.auto_google_login.subprocess.run")
    @patch("cli.modules.auto_google_login.time.sleep")
    def test_execute_returns_dict(self, mock_sleep, mock_run):
        """execute always returns a dict."""
        mock_sm = MagicMock()
        mock_sm.launch.return_value = {"status": "ok", "pid": 55555, "wid": None}
        with patch.dict("sys.modules", {"cli.modules.session_manager": MagicMock()}):
            from cli.modules import auto_google_login as login_mod
            login_mod._SessionManager = mock_sm

        def _run_side(cmd, **kw):
            res = MagicMock()
            res.stdout = json.dumps({"windows": []})
            res.returncode = 0
            res.stderr = ""
            return res
        mock_run.side_effect = _run_side

        result = login_mod.execute()
        self.assertIsInstance(result, dict)
        self.assertIn("status", result)

    @patch("cli.modules.auto_google_login.subprocess.run")
    @patch("cli.modules.auto_google_login.time.sleep")
    def test_execute_session_manager_failure(self, mock_sleep, mock_run):
        """When SessionManager.launch fails, returns error."""
        mock_sm = MagicMock()
        mock_sm.launch.return_value = {"status": "error", "reason": "chrome_launch_failed"}
        with patch.dict("sys.modules", {"cli.modules.session_manager": MagicMock()}):
            from cli.modules import auto_google_login as login_mod
            login_mod._SessionManager = mock_sm

        def _run_side(cmd, **kw):
            res = MagicMock()
            res.stdout = json.dumps({"windows": []})
            res.returncode = 0
            res.stderr = ""
            return res
        mock_run.side_effect = _run_side

        result = login_mod.execute()
        self.assertEqual(result["status"], "error")

    @patch("cli.modules.auto_google_login.subprocess.run")
    @patch("cli.modules.auto_google_login.time.sleep")
    def test_execute_session_manager_called(self, mock_sleep, mock_run):
        """When no already-logged-in found, session_manager.launch is called."""
        mock_sm = MagicMock()
        mock_sm.launch.return_value = {"status": "ok", "pid": 777, "wid": None}
        with patch.dict("sys.modules", {"cli.modules.session_manager": MagicMock()}):
            from cli.modules import auto_google_login as login_mod
            login_mod._SessionManager = mock_sm

        def _run_side(cmd, **kw):
            res = MagicMock()
            res.stdout = json.dumps({"windows": []})
            res.returncode = 0
            res.stderr = ""
            return res
        mock_run.side_effect = _run_side

        login_mod.execute()
        mock_sm.launch.assert_called()

    def test_windows_parses_correctly(self):
        """_windows returns list from dict response."""
        mock_sm = MagicMock()
        with patch.dict("sys.modules", {"cli.modules.session_manager": MagicMock()}):
            import cli.modules.auto_google_login as login_mod
            login_mod._SessionManager = mock_sm
            login_mod._run = MagicMock()

        mock_result = MagicMock()
        mock_result.stdout = json.dumps({"windows": [
            {"pid": 1, "window_id": 2, "bounds": {"height": 500}}
        ]})
        login_mod._run.return_value = mock_result
        windows = login_mod._windows()
        self.assertIsInstance(windows, list)
        self.assertEqual(len(windows), 1)


if __name__ == "__main__":
    unittest.main()
