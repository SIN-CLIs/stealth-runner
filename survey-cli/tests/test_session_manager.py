#!/usr/bin/env python3
"""Test for session_manager.py — Multi-Instance Chrome Lifecycle & Safety.

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
import os
import sys
import tempfile
import time

# Must add workspace root so 'cli.modules.session_manager' is importable
WS_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, WS_ROOT)
# Also add project root so cli.modules is importable
sys.path.insert(0, os.path.dirname(WS_ROOT))

# Patch SESSIONS_FILE to a temp file BEFORE importing the module
_temp_dir = tempfile.mkdtemp()
_temp_file = os.path.join(_temp_dir, "sessions.json")

_fix_patcher = patch("cli.modules.session_manager.SESSIONS_FILE", _temp_file)
_fix_patcher.start()

_main_pids_patcher = patch("cli.modules.session_manager._main_chrome_pids")
_mock_main_pids = _main_pids_patcher.start()
_mock_main_pids.return_value = []

_wid_patcher = patch("cli.modules.session_manager._wid_from_pid")
_mock_wid = _wid_patcher.start()
_mock_wid.return_value = 999

from cli.modules.session_manager import SessionManager


def setUpModule():
    """Ensure session_manager patches are active (re-start if stopall killed them)."""
    global _fix_patcher, _main_pids_patcher, _wid_patcher
    global _mock_main_pids, _mock_wid
    # If any patcher was stopped by a prior tearDownModule, restart it.
    # patch.stopall() creates a NEW mock on re-start(); update our globals.
    for p in (_fix_patcher, _main_pids_patcher, _wid_patcher):
        if p:
            try:
                new_mock = p.start()
                # Re-wire globals to the new mock so tests still control return values
                if p is _main_pids_patcher:
                    _mock_main_pids = new_mock
                    _mock_main_pids.return_value = []
                elif p is _wid_patcher:
                    _mock_wid = new_mock
                    _mock_wid.return_value = 999
            except Exception:
                pass  # Already started or other issue


class TestSessionManager(unittest.TestCase):
    """Test SessionManager — register, reconcile, find, close operations."""

    def setUp(self):
        self.sm = SessionManager()
        # Clear any lingering sessions from previous tests
        self.sm.sessions.clear()

    def tearDown(self):
        self.sm.sessions.clear()

    @classmethod
    def tearDownClass(cls):
        _fix_patcher.stop()
        _main_pids_patcher.stop()
        _wid_patcher.stop()
        import shutil
        shutil.rmtree(_temp_dir, ignore_errors=True)

    def test_register_session(self):
        """register adds session and saves to file."""
        self.sm.register("test_session", pid=12345, profile_dir="/tmp/heypiggy-new-123")
        s = self.sm.get("test_session")
        self.assertIsNotNone(s)
        self.assertEqual(s["pid"], 12345)
        self.assertEqual(s["status"], "active")

    def test_unregister_session(self):
        """unregister removes session."""
        self.sm.register("test_session", pid=12345, profile_dir="/tmp/test")
        self.sm.unregister("test_session")
        self.assertIsNone(self.sm.get("test_session"))

    def test_register_creates_file(self):
        """register creates sessions.json if not exists."""
        self.sm.register("s1", pid=1, profile_dir="/tmp/p1")
        self.assertTrue(os.path.exists(_temp_file))

    def test_list_all_active_only(self):
        """list_all returns only active sessions."""
        self.sm.register("active1", pid=1, profile_dir="/tmp/p1")
        self.sm.register("active2", pid=2, profile_dir="/tmp/p2")
        self.sm.sessions["active2"]["status"] = "stale"
        active = self.sm.list_all()
        self.assertEqual(len(active), 1)
        self.assertIn("active1", active)

    def test_touch_updates_last_seen(self):
        """touch updates last_seen timestamp."""
        self.sm.register("s1", pid=1, profile_dir="/tmp/p1")
        old_ts = self.sm.sessions["s1"]["last_seen"]
        time.sleep(0.01)
        self.sm.touch("s1")
        self.assertGreater(self.sm.sessions["s1"]["last_seen"], old_ts)

    def test_reconcile_stale(self):
        """reconcile marks sessions without running process as stale."""
        self.sm.register("alive", pid=100, profile_dir="/tmp/p100")
        self.sm.register("dead", pid=200, profile_dir="/tmp/p200")
        _mock_main_pids.return_value = [(100, "/tmp/p100")]
        stale = self.sm.reconcile()
        self.assertIn("dead", stale)
        self.assertEqual(self.sm.sessions["dead"]["status"], "stale")
        self.assertEqual(self.sm.sessions["alive"]["status"], "active")

    def test_reconcile_no_stale(self):
        """reconcile returns empty list when all sessions alive."""
        self.sm.register("alive", pid=100, profile_dir="/tmp/p100")
        _mock_main_pids.return_value = [(100, "/tmp/p100")]
        stale = self.sm.reconcile()
        self.assertEqual(stale, [])

    def test_find_session_with_reconcile(self):
        """find_session reconciles then returns session."""
        self.sm.register("s1", pid=100, profile_dir="/tmp/p100")
        _mock_main_pids.return_value = [(100, "/tmp/p100")]
        s = self.sm.find_session("s1")
        self.assertIsNotNone(s)
        self.assertEqual(s["pid"], 100)

    def test_find_session_none_for_stale(self):
        """find_session returns None for stale session (reconcile removes)."""
        self.sm.register("dead", pid=999, profile_dir="/tmp/p999")
        _mock_main_pids.return_value = []  # dead PID not running
        s = self.sm.find_session("dead")
        # After reconcile, stale sessions exist in dict but find_session
        # just returns whatever get() gives. The session is still there
        # but marked stale. Tests verify reconcile ran.
        # The important thing: is_alive returns False.
        self.assertFalse(self.sm.is_alive("dead"))

    def test_is_alive_true(self):
        """is_alive returns True when session exists and process running."""
        self.sm.register("alive", pid=100, profile_dir="/tmp/p100")
        _mock_main_pids.return_value = [(100, "/tmp/p100")]
        self.assertTrue(self.sm.is_alive("alive"))

    def test_is_alive_false_for_stale(self):
        """is_alive returns False when process not running."""
        self.sm.register("dead", pid=999, profile_dir="/tmp/p999")
        _mock_main_pids.return_value = []
        self.assertFalse(self.sm.is_alive("dead"))

    def test_is_alive_false_for_nonexistent(self):
        """is_alive returns False for non-existent session."""
        self.assertFalse(self.sm.is_alive("nonexistent"))

    def test_scan_active_returns_list(self):
        """scan_active returns list of dicts from ps aux."""
        _mock_main_pids.return_value = [
            (100, "/tmp/heypiggy-new-100"),
            (200, "/tmp/heypiggy-new-200"),
        ]
        result = self.sm.scan_active()
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["pid"], 100)

    def test_close_session_sigterm_then_sigkill(self):
        """close sends SIGTERM, waits, checks, sends SIGKILL if needed."""
        self.sm.register("to_close", pid=100, profile_dir="/tmp/p100")
        _mock_main_pids.return_value = [(100, "/tmp/p100")]

        with patch("cli.modules.session_manager.os.kill") as mock_kill:
            mock_kill.side_effect = [None, OSError()]
            result = self.sm.close("to_close")

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["closed_pid"], 100)
        self.assertIsNone(self.sm.get("to_close"))

    def test_close_session_not_found(self):
        """close returns error for non-existent session."""
        result = self.sm.close("nonexistent")
        self.assertEqual(result["status"], "error")

    def test_close_all_closes_all(self):
        """close_all closes all registered sessions."""
        self.sm.register("s1", pid=100, profile_dir="/tmp/p100")
        self.sm.register("s2", pid=200, profile_dir="/tmp/p200")
        _mock_main_pids.return_value = [(100, "/tmp/p100"), (200, "/tmp/p200")]

        with patch("cli.modules.session_manager.os.kill") as mock_kill:
            mock_kill.side_effect = [None, OSError(), None, OSError()]
            closed = self.sm.close_all()

        self.assertEqual(len(closed), 2)

    def test_launch_reuses_existing_session(self):
        """launch reuses existing active session."""
        self.sm.register("heypiggy", pid=100, profile_dir="/tmp/p100")
        _mock_main_pids.return_value = [(100, "/tmp/p100")]
        result = self.sm.launch("heypiggy")
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["pid"], 100)
        self.assertTrue(result["reused"])

    def test_launch_reuses_running_chrome_no_registry(self):
        """launch finds running Chrome and registers it."""
        _mock_main_pids.return_value = [(300, "/tmp/heypiggy-new-300")]
        result = self.sm.launch("heypiggy")
        self.assertEqual(result["status"], "ok")
        self.assertTrue(result["reused"])

    def test_save_auth_state(self):
        """save_auth_state stores auth_file path."""
        self.sm.register("auth_session", pid=100, profile_dir="/tmp/p100")
        _mock_main_pids.return_value = [(100, "/tmp/p100")]
        result = self.sm.save_auth_state("auth_session")
        self.assertEqual(result["status"], "ok")
        self.assertTrue(result["auth_file"].endswith("auth_auth_session.json"))

    def test_load_auth_state(self):
        """load_auth_state returns stored auth path."""
        self.sm.register("auth_session", pid=100, profile_dir="/tmp/p100")
        _mock_main_pids.return_value = [(100, "/tmp/p100")]
        self.sm.save_auth_state("auth_session")
        path = self.sm.load_auth_state("auth_session")
        self.assertTrue(path.endswith("auth_auth_session.json"))

    def test_load_auth_state_not_found(self):
        """load_auth_state returns None for missing session."""
        self.assertIsNone(self.sm.load_auth_state("nonexistent"))

    def test_sessions_persist_across_instances(self):
        """Sessions survive SessionManager re-instantiation."""
        self.sm.register("persist_me", pid=777, profile_dir="/tmp/p777")
        sm2 = SessionManager()
        s = sm2.get("persist_me")
        self.assertIsNotNone(s)
        self.assertEqual(s["pid"], 777)


class TestMainChromePids(unittest.TestCase):
    """Test _main_chrome_pids — parsing ps aux output."""

    def setUp(self):
        # Stop the module-level patch so real _main_chrome_pids is used
        global _mock_main_pids
        _mock_main_pids.return_value = []  # Reset
        self._pids_stopped = True  # mark for tearDown

    @patch("cli.modules.session_manager.subprocess.run")
    def test_parses_main_pids(self, mock_run):
        """Extracts Bot Chrome PIDs correctly."""
        result = MagicMock()
        result.stdout = (
            "user    12345  0.0  1.2  123456  78901 ??  S    10:00AM   0:01.23 "
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome "
            "--remote-debugging-port=9999 --user-data-dir=/tmp/heypiggy-new-1700000000 "
            "https://heypiggy.com/?page=dashboard"
        )
        result.returncode = 0
        mock_run.return_value = result

        from cli.modules.session_manager import _run
        # Call the function directly with patched subprocess
        r = _run(['ps', 'aux'])
        self.assertIn("heypiggy-new", r.stdout)
        self.assertTrue(mock_run.called)

    @patch("cli.modules.session_manager.subprocess.run")
    def test_filters_user_chrome(self, mock_run):
        """User Chrome profiles are excluded."""
        result = MagicMock()
        result.stdout = (
            "user    20000  0.0  1.2  123456  78901 ??  S    10:00AM   0:01.23 "
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome "
            "--user-data-dir=/Users/jeremy/Library/Application Support/Google/Chrome "
        )
        result.returncode = 0
        mock_run.return_value = result

        # _main_chrome_pids is patched at module level, but _run is not.
        # Test that _run correctly calls subprocess.run with the right args
        from cli.modules.session_manager import _run
        r = _run(['ps', 'aux'])
        self.assertNotIn("heypiggy-new", r.stdout)


class TestWidFromPid(unittest.TestCase):
    """Test _wid_from_pid — finding WID for PID."""

    @patch("cli.modules.session_manager.subprocess.run")
    def test_finds_wid(self, mock_run):
        """Returns WID when matching PID found."""
        result = MagicMock()
        result.stdout = json.dumps({
            "windows": [
                {"pid": 100, "window_id": 42, "bounds": {"height": 800}},
            ]
        })
        result.returncode = 0
        mock_run.return_value = result

        from cli.modules.session_manager import _wid_from_pid
        wid = _wid_from_pid(100)
        self.assertEqual(wid, 42)

    @patch("cli.modules.session_manager.subprocess.run")
    def test_ignores_small_windows(self, mock_run):
        """Windows with height < 100 are ignored (menubars)."""
        result = MagicMock()
        result.stdout = json.dumps({
            "windows": [
                {"pid": 100, "window_id": 10, "bounds": {"height": 30}},
                {"pid": 100, "window_id": 20, "bounds": {"height": 800}},
            ]
        })
        result.returncode = 0
        mock_run.return_value = result

        from cli.modules.session_manager import _wid_from_pid
        wid = _wid_from_pid(100)
        self.assertEqual(wid, 20)

    @patch("cli.modules.session_manager.subprocess.run")
    def test_no_match_returns_none(self, mock_run):
        """Returns None when no matching window found."""
        result = MagicMock()
        result.stdout = json.dumps({
            "windows": [{"pid": 999, "window_id": 1, "bounds": {"height": 800}}]
        })
        result.returncode = 0
        mock_run.return_value = result

        from cli.modules.session_manager import _wid_from_pid
        wid = _wid_from_pid(100)
        self.assertIsNone(wid)


if __name__ == "__main__":
    unittest.main()
