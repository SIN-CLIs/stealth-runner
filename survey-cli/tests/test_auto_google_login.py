#!/usr/bin/env python3
"""Test for auto_google_login.py — Backward-compatible wrapper.

WARUM: auto_google_login.py ist jetzt ein dünner Wrapper um survey.auth.
Die echte Logik wird in test_auth.py getestet. Diese Tests prüfen nur,
dass der Wrapper korrekt delegiert.
"""

import unittest
from unittest.mock import patch, MagicMock
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestAutoGoogleLoginWrapper(unittest.TestCase):
    """Test backward-compatible wrapper functions."""

    @patch("cli.modules.auto_google_login.GoogleOAuthFlow")
    def test_execute_delegates_to_google_oauth_flow(self, mock_flow_cls):
        """execute() creates GoogleOAuthFlow and returns result."""
        mock_flow = MagicMock()
        mock_flow.execute.return_value = MagicMock(
            status="ok", pid=12345, wid=67890, reason=None
        )
        mock_flow_cls.return_value = mock_flow

        from cli.modules.auto_google_login import execute
        result = execute(pid=12345)

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["pid"], 12345)
        self.assertEqual(result["wid"], 67890)
        mock_flow.execute.assert_called_once_with(pid=12345)

    @patch("cli.modules.auto_google_login.GoogleOAuthFlow")
    def test_execute_error_result(self, mock_flow_cls):
        """execute() returns error dict on failure."""
        mock_flow = MagicMock()
        mock_flow.execute.return_value = MagicMock(
            status="error", pid=None, wid=None, reason="chrome_not_started"
        )
        mock_flow_cls.return_value = mock_flow

        from cli.modules.auto_google_login import execute
        result = execute()

        self.assertEqual(result["status"], "error")
        self.assertEqual(result["reason"], "chrome_not_started")

    @patch("cli.modules.auto_google_login.GoogleOAuthFlow")
    def test_execute_already_logged_in(self, mock_flow_cls):
        """execute() returns ok for already_logged_in status."""
        mock_flow = MagicMock()
        mock_flow.execute.return_value = MagicMock(
            status="already_logged_in", pid=123, wid=456, reason=None
        )
        mock_flow_cls.return_value = mock_flow

        from cli.modules.auto_google_login import execute
        result = execute()

        self.assertEqual(result["status"], "ok")

    def test_deprecated_aliases_exist(self):
        """Backward-compatible aliases are importable."""
        from cli.modules.auto_google_login import (
            _find_idx, _click, _type, _tree, _find_bot_wid,
            _find_logged_in_heypiggy
        )
        # Just verify they exist and are callable
        self.assertTrue(callable(_find_idx))
        self.assertTrue(callable(_click))
        self.assertTrue(callable(_type))
        self.assertTrue(callable(_tree))
        self.assertTrue(callable(_find_bot_wid))
        self.assertTrue(callable(_find_logged_in_heypiggy))


if __name__ == "__main__":
    unittest.main()
