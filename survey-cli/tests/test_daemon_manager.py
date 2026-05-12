"""Test DaemonManager — cua-driver state machine, health checks, auto-recovery.

WARUM: Issue #13 — Daemon state not tracked, no auto-recovery on crash.
Tests cover: state transitions, process detection, health check, restart logic.
"""

import unittest
from unittest.mock import MagicMock, patch
import json
import subprocess
import sys
import os
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestDaemonManagerStates(unittest.TestCase):
    def setUp(self):
        patcher = patch("survey.daemon.CUA_DAEMON_STATE_FILE", new_callable=MagicMock)
        self.mock_state_file = patcher.start()
        self.addCleanup(patcher.stop)
        type(self.mock_state_file).__truediv__ = MagicMock(
            return_value=Path("/tmp/_test_cua_daemon_state.json")
        )
        self._state_data = {}

    def _setup_state(self, state="STOPPED", failures=0):
        self._state_data = {
            "state": state,
            "consecutive_failures": failures,
            "updated_at": "2026-01-01T00:00:00",
        }
        with patch(
            "builtins.open",
            new_callable=unittest.mock.mock_open,
            read_data=json.dumps(self._state_data),
        ):
            from survey.daemon import DaemonManager

            return DaemonManager()

    @patch("survey.daemon.DaemonManager._load_state")
    def test_initial_state_is_stopped(self, mock_load):
        mock_load.return_value = "STOPPED"
        from survey.daemon import DaemonManager

        dm = DaemonManager()
        self.assertEqual(dm.state, "STOPPED")

    @patch("survey.daemon.DaemonManager._load_state")
    def test_state_transitions_through_save(self, mock_load):
        mock_load.return_value = "STOPPED"
        from survey.daemon import DaemonManager

        dm = DaemonManager()
        dm.state = "STARTING"
        self.assertEqual(dm.state, "STARTING")
        dm.state = "HEALTHY"
        self.assertEqual(dm.state, "HEALTHY")
        dm.state = "DEGRADED"
        self.assertEqual(dm.state, "DEGRADED")
        dm.state = "FAILED"
        self.assertEqual(dm.state, "FAILED")


class TestDaemonManagerProcessCheck(unittest.TestCase):
    @patch("survey.daemon.DaemonManager._load_state")
    def test_is_process_alive_true(self, mock_load):
        mock_load.return_value = "STOPPED"
        from survey.daemon import DaemonManager

        dm = DaemonManager()
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="12345\n")
            self.assertTrue(dm._is_process_alive())

    @patch("survey.daemon.DaemonManager._load_state")
    def test_is_process_alive_false(self, mock_load):
        mock_load.return_value = "STOPPED"
        from survey.daemon import DaemonManager

        dm = DaemonManager()
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stdout="")
            self.assertFalse(dm._is_process_alive())

    @patch("survey.daemon.DaemonManager._load_state")
    def test_is_process_alive_exception(self, mock_load):
        mock_load.return_value = "STOPPED"
        from survey.daemon import DaemonManager

        dm = DaemonManager()
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("pgrep", 5)):
            self.assertFalse(dm._is_process_alive())


class TestDaemonManagerHealthCheck(unittest.TestCase):
    @patch("survey.daemon.DaemonManager._load_state")
    @patch("survey.daemon.DaemonManager._save_state")
    def test_health_check_healthy(self, mock_save, mock_load):
        mock_load.return_value = "STOPPED"
        from survey.daemon import DaemonManager

        dm = DaemonManager()
        dm._is_process_alive = MagicMock(return_value=True)
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0, stdout=json.dumps({"windows": [{"pid": 1234, "window_id": 1}]})
            )
            result = dm.health_check()
        self.assertTrue(result["healthy"])
        self.assertEqual(result["state"], "HEALTHY")

    @patch("survey.daemon.DaemonManager._load_state")
    @patch("survey.daemon.DaemonManager._save_state")
    def test_health_check_failed_process_dead(self, mock_save, mock_load):
        mock_load.return_value = "HEALTHY"
        from survey.daemon import DaemonManager

        dm = DaemonManager()
        dm._is_process_alive = MagicMock(return_value=False)
        result = dm.health_check()
        self.assertFalse(result["healthy"])
        self.assertEqual(result["state"], "FAILED")

    @patch("survey.daemon.DaemonManager._load_state")
    @patch("survey.daemon.DaemonManager._save_state")
    def test_health_check_degraded_no_windows(self, mock_save, mock_load):
        mock_load.return_value = "HEALTHY"
        from survey.daemon import DaemonManager

        dm = DaemonManager()
        dm._is_process_alive = MagicMock(return_value=True)
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=json.dumps({"windows": []}))
            result = dm.health_check()
        self.assertFalse(result["healthy"])
        self.assertEqual(result["state"], "DEGRADED")

    @patch("survey.daemon.DaemonManager._load_state")
    @patch("survey.daemon.DaemonManager._save_state")
    def test_health_check_degraded_timeout(self, mock_save, mock_load):
        mock_load.return_value = "HEALTHY"
        from survey.daemon import DaemonManager

        dm = DaemonManager()
        dm._is_process_alive = MagicMock(return_value=True)
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("cmd", 5)):
            result = dm.health_check()
        self.assertFalse(result["healthy"])
        self.assertEqual(result["state"], "DEGRADED")


class TestDaemonManagerEnsureRunning(unittest.TestCase):
    @patch("survey.daemon.DaemonManager._load_state")
    @patch("survey.daemon.DaemonManager._save_state")
    def test_ensure_running_when_already_healthy(self, mock_save, mock_load):
        mock_load.return_value = "HEALTHY"
        from survey.daemon import DaemonManager

        dm = DaemonManager()
        dm.health_check = MagicMock(
            return_value={"healthy": True, "state": "HEALTHY", "windows_count": 1}
        )
        self.assertTrue(dm.ensure_running())

    @patch("survey.daemon.DaemonManager._load_state")
    @patch("survey.daemon.DaemonManager._save_state")
    @patch("time.sleep")
    def test_ensure_running_restarts_on_failed(self, mock_sleep, mock_save, mock_load):
        mock_load.return_value = "FAILED"
        from survey.daemon import DaemonManager

        dm = DaemonManager()
        dm.health_check = MagicMock(
            return_value={"healthy": False, "state": "FAILED", "reason": "dead"}
        )
        dm.stop = MagicMock(return_value=True)
        dm.start = MagicMock(return_value=True)
        dm._is_process_alive = MagicMock(return_value=True)
        self.assertTrue(dm.ensure_running())
        dm.stop.assert_called_once()
        dm.start.assert_called_once()


class TestDaemonManagerHeartbeat(unittest.TestCase):
    @patch("survey.daemon.DaemonManager._load_state")
    @patch("survey.daemon.DaemonManager._save_state")
    @patch("survey.daemon.is_chrome_alive")
    @patch("survey.daemon.load_state")
    def test_heartbeat_structure(self, mock_load, mock_chrome, mock_save, mock_load_state):
        mock_load_state.return_value = "STOPPED"
        mock_chrome.return_value = True
        mock_load.return_value = {"surveys_completed": 0}
        from survey.daemon import DaemonManager

        dm = DaemonManager()
        dm.health_check = MagicMock(
            return_value={"healthy": True, "state": "HEALTHY", "windows_count": 2}
        )
        result = dm.heartbeat()
        self.assertIn("chrome", result)
        self.assertIn("cua_daemon", result)
        self.assertIn("cua_healthy", result)
        self.assertIn("surveys_completed", result)
        self.assertIn("ts", result)
        self.assertEqual(result["cua_daemon"], "HEALTHY")
        self.assertTrue(result["cua_healthy"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
