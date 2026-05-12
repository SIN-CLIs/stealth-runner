"""Tests for survey.auth package.

WARUM: Auth-Logik war 1700+ Zeilen Monolith. Jetzt ist sie modular.
Jedes Modul braucht eigene Tests.
"""

import unittest
from unittest.mock import MagicMock, patch
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from survey.auth.cua_adapter import CuaAdapter
from survey.auth.login_verifier import LoginVerifier
from survey.auth.google_oauth import GoogleOAuthFlow


class TestCuaAdapter(unittest.TestCase):
    """Test CuaAdapter low-level cua-driver wrapper."""

    def test_find_idx_returns_none_on_empty_tree(self):
        """Empty tree → None."""
        cua = CuaAdapter()
        result = cua.find_idx([], "weiter")
        self.assertIsNone(result)

    def test_find_idx_finds_button(self):
        """Find AXButton by keyword."""
        cua = CuaAdapter()
        tree = ['- [35] AXButton "Weiter" @(1095,706,91,40)']
        result = cua.find_idx(tree, "weiter")
        self.assertEqual(result, 35)

    def test_find_idx_finds_link(self):
        """Find AXLink by keyword."""
        cua = CuaAdapter()
        tree = ['- [54] AXLink "Google Login-Symbol" @(731,651,132,41)']
        result = cua.find_idx(tree, "google login-symbol", ["AXLink"])
        self.assertEqual(result, 54)

    def test_find_idx_case_insensitive(self):
        """Case-insensitive matching."""
        cua = CuaAdapter()
        tree = ['- [1] AXButton "WEITER" @(0,0,0,0)']
        result = cua.find_idx(tree, "weiter")
        self.assertEqual(result, 1)

    def test_click_returns_false_on_none_idx(self):
        """None index → False (no crash)."""
        cua = CuaAdapter()
        self.assertFalse(cua.click(123, 456, None))

    def test_type_returns_false_on_none_idx(self):
        """None index → False (no crash)."""
        cua = CuaAdapter()
        self.assertFalse(cua.type(123, 456, None, "text"))

    def test_find_bot_window_filters_by_height(self):
        """Skip windows with height < 100."""
        cua = CuaAdapter()
        with patch.object(
            cua,
            "list_windows",
            return_value=[
                {"bounds": {"height": 20}, "app_name": "Google Chrome"},
                {
                    "bounds": {"height": 800},
                    "app_name": "Google Chrome",
                    "pid": 123,
                    "window_id": 456,
                    "title": "HeyPiggy",
                },
            ],
        ):
            pid, wid = cua.find_bot_window()
            self.assertEqual(pid, 123)
            self.assertEqual(wid, 456)

    def test_find_bot_window_filters_by_keywords(self):
        """Find window matching keywords."""
        cua = CuaAdapter()
        with patch.object(
            cua,
            "list_windows",
            return_value=[
                {
                    "bounds": {"height": 800},
                    "app_name": "Google Chrome",
                    "pid": 1,
                    "window_id": 10,
                    "title": "OAuth",
                },
                {
                    "bounds": {"height": 800},
                    "app_name": "Google Chrome",
                    "pid": 2,
                    "window_id": 20,
                    "title": "HeyPiggy Dashboard",
                },
            ],
        ):
            pid, wid = cua.find_bot_window(["heypiggy"])
            self.assertEqual(pid, 2)
            self.assertEqual(wid, 20)


class TestLoginVerifier(unittest.TestCase):
    """Test LoginVerifier HeyPiggy logged-in detection."""

    def test_already_logged_in_by_title(self):
        """Title contains 'umfragen' → logged in."""
        mock_cua = MagicMock()
        mock_cua.list_windows.return_value = [
            {
                "bounds": {"height": 800},
                "app_name": "Google Chrome",
                "pid": 123,
                "window_id": 456,
                "title": "HeyPiggy – Umfragen",
                "z_index": 1,
            },
        ]
        verifier = LoginVerifier(mock_cua)
        pid, wid, logged = verifier.check()
        self.assertTrue(logged)
        self.assertEqual(pid, 123)
        self.assertEqual(wid, 456)

    def test_not_logged_in(self):
        """No matching windows → not logged in."""
        mock_cua = MagicMock()
        mock_cua.list_windows.return_value = []
        verifier = LoginVerifier(mock_cua)
        pid, wid, logged = verifier.check()
        self.assertFalse(logged)
        self.assertIsNone(pid)
        self.assertIsNone(wid)

    def test_ambiguous_title_checks_tree(self):
        """Title has 'heypiggy' but not login keywords → check tree."""
        mock_cua = MagicMock()
        mock_cua.list_windows.return_value = [
            {
                "bounds": {"height": 800},
                "app_name": "Google Chrome",
                "pid": 123,
                "window_id": 456,
                "title": "HeyPiggy – Verdienen",
                "z_index": 1,
            },
        ]
        mock_cua.get_tree.return_value = [
            '- [0] AXButton "Abmelden" @(0,0,0,0)',
        ]
        verifier = LoginVerifier(mock_cua)
        pid, wid, logged = verifier.check()
        self.assertTrue(logged)


class TestGoogleOAuthFlow(unittest.TestCase):
    """Test GoogleOAuthFlow 6-step login."""

    def test_already_logged_in_short_circuit(self):
        """If already logged in → immediate success."""
        mock_cua = MagicMock()
        mock_verifier = MagicMock()
        mock_verifier.check.return_value = (123, 456, True)

        flow = GoogleOAuthFlow(mock_cua, mock_verifier)
        result = flow.execute()

        self.assertEqual(result.status, "already_logged_in")
        self.assertEqual(result.pid, 123)
        self.assertEqual(result.wid, 456)

    def test_missing_pid_error(self):
        """No pid provided and not logged in → error."""
        mock_cua = MagicMock()
        mock_verifier = MagicMock()
        mock_verifier.check.return_value = (None, None, False)

        flow = GoogleOAuthFlow(mock_cua, mock_verifier)
        result = flow.execute(pid=None)

        self.assertEqual(result.status, "error")
        self.assertEqual(result.reason, "chrome_not_started")

    def test_no_dashboard_window_error(self):
        """Dashboard window not found → error."""
        mock_cua = MagicMock()
        mock_cua.find_bot_window.return_value = (None, None)
        mock_verifier = MagicMock()
        mock_verifier.check.return_value = (None, None, False)

        flow = GoogleOAuthFlow(mock_cua, mock_verifier)
        result = flow.execute(pid=123)

        self.assertEqual(result.status, "error")
        self.assertEqual(result.reason, "no_dashboard_window")

    def test_login_button_not_found_error(self):
        """Google login button not in AX-Tree → error."""
        mock_cua = MagicMock()
        mock_cua.find_bot_window.return_value = (123, 456)
        mock_cua.get_tree.return_value = []
        mock_cua.find_idx.return_value = None
        mock_verifier = MagicMock()
        mock_verifier.check.return_value = (None, None, False)

        flow = GoogleOAuthFlow(mock_cua, mock_verifier)
        result = flow.execute(pid=123)

        self.assertEqual(result.status, "error")
        self.assertEqual(result.reason, "google_login_button_not_found")

    def test_successful_login_flow(self):
        """Complete successful 6-step login flow."""
        mock_cua = MagicMock()
        mock_cua.find_bot_window.side_effect = [
            (123, 456),  # Dashboard
            (123, 789),  # OAuth
            (123, 790),  # Keychain
            (123, 791),  # Final
        ]
        mock_cua.get_tree.return_value = [
            '- [54] AXLink "Google Login-Symbol" @(0,0,0,0)',
            '- [25] AXTextField "E-Mail" @(0,0,0,0)',
            '- [35] AXButton "Weiter" @(0,0,0,0)',
            '- [62] AXButton "Fortfahren" @(0,0,0,0)',
        ]
        mock_cua.find_idx.side_effect = [54, 25, 35, 62, 35]
        mock_cua.click.return_value = True
        mock_cua.type.return_value = True

        mock_verifier = MagicMock()
        mock_verifier.check.side_effect = [
            (None, None, False),  # Initial check
            (123, 456, True),  # Final verify
        ]

        with patch.dict(os.environ, {"GOOGLE_EMAIL": "test@example.com"}):
            flow = GoogleOAuthFlow(mock_cua, mock_verifier)
            result = flow.execute(pid=123)

        self.assertEqual(result.status, "ok")
        self.assertEqual(result.pid, 123)
        self.assertEqual(result.wid, 456)


if __name__ == "__main__":
    unittest.main()
