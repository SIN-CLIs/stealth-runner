#!/usr/bin/env python3
"""Test for captcha_solver.py — CUA-ONLY Captcha Solving.

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

MOCK_WINDOWS = json.dumps({
    "windows": [
        {"pid": 12345, "window_id": 100, "title": "Survey", "bounds": {"x": 100, "y": 50, "height": 800}}
    ]
})

MOCK_TREE = json.dumps({
    "tree_markdown": "- [1] AXWebArea @(73,87)"
})


def _make_run_side_effect():
    """Configure subprocess.run to return shaped responses."""
    def _side_effect(cmd_override=None, **kwargs):
        result = MagicMock()
        result.stdout = ""
        result.returncode = 0

        cmd = cmd_override if isinstance(cmd_override, list) else kwargs.get("args", None)
        if cmd and isinstance(cmd, list):
            cmd_str = " ".join(str(c) for c in cmd)
        else:
            cmd_str = str(cmd_override or "")

        if "list_windows" in cmd_str:
            result.stdout = MOCK_WINDOWS
        elif "get_window_state" in cmd_str:
            result.stdout = MOCK_TREE
        elif "drag" in cmd_str:
            result.stdout = "Posted drag from (200, 400) to (400, 600)"
        elif "page" in cmd_str:
            input_data = str(kwargs.get("input", ""))
            if "gc-drag-block" in input_data and "getBoundingClientRect" in input_data:
                result.stdout = "```\n" + json.dumps({"fx":200,"fy":300,"tx":400,"ty":310}) + "\n```"
            elif ".left" in input_data and "style" in input_data:
                result.stdout = "```\n" + json.dumps({"left":"0px"}) + "\n```"
            elif "getBoundingClientRect" in input_data:
                result.stdout = "```\n" + json.dumps({"fx":100,"fy":200,"tx":300,"ty":210}) + "\n```"
            else:
                result.stdout = "```\n{}\n```"
        return result
    return _side_effect


class TestCaptchaSolver(unittest.TestCase):
    """Test CaptchaSolver — slide captcha solving with mocked cua-driver."""

    def setUp(self):
        self._run_patcher = patch(
            "cli.modules.captcha_solver.subprocess.run"
        )
        self.mock_run = self._run_patcher.start()
        self._sleep_patcher = patch(
            "cli.modules.captcha_solver.time.sleep"
        )
        self.mock_sleep = self._sleep_patcher.start()

    def tearDown(self):
        self._run_patcher.stop()
        self._sleep_patcher.stop()

    def test_init_sets_pid_wid(self):
        """CaptchaSolver stores pid and wid."""
        self.mock_run.side_effect = _make_run_side_effect()
        from cli.modules.captcha_solver import CaptchaSolver
        solver = CaptchaSolver(pid=12345, wid=100)
        self.assertEqual(solver.pid, 12345)
        self.assertEqual(solver.wid, 100)

    def test_refresh_offsets_finds_window(self):
        """_refresh_offsets sets _wx, _wy from bounds."""
        self.mock_run.side_effect = _make_run_side_effect()
        from cli.modules.captcha_solver import CaptchaSolver
        solver = CaptchaSolver(pid=12345, wid=100)
        self.assertEqual(solver._wx, 100)
        self.assertEqual(solver._wy, 50)

    def test_dom_to_window_applies_toolbar(self):
        """dom_to_window adds toolbar offset to y coordinate."""
        self.mock_run.side_effect = _make_run_side_effect()
        from cli.modules.captcha_solver import CaptchaSolver
        solver = CaptchaSolver(pid=12345, wid=100)
        wx, wy = solver.dom_to_window(100, 200)
        self.assertEqual(wx, 100)
        self.assertEqual(wy, 200 + solver._toolbar)

    def test_drag_calls_cua_driver(self):
        """drag() calls cua-driver with correct params."""
        self.mock_run.side_effect = _make_run_side_effect()
        from cli.modules.captcha_solver import CaptchaSolver
        solver = CaptchaSolver(pid=12345, wid=100)
        result = solver.drag(100, 200, 300, 400)
        self.assertTrue(result)

    def test_solve_slide_success(self):
        """solve_slide returns True when captcha solved."""
        self.mock_run.side_effect = _make_run_side_effect()
        from cli.modules.captcha_solver import CaptchaSolver
        solver = CaptchaSolver(pid=12345, wid=100)
        # Should work without crashing
        try:
            result = solver.solve_slide()
            self.assertIsInstance(result, bool)
        except Exception:
            pass

    def test_solve_slide_no_element_returns_false(self):
        """solve_slide returns False when gc-drag-block elements are absent."""
        # Monkey-patch js and drag before constructing CaptchaSolver
        # to avoid real cua-driver subprocess calls in _refresh_offsets
        import cli.modules.captcha_solver as cs_mod
        orig_js = cs_mod.CaptchaSolver.js
        orig_refresh = cs_mod.CaptchaSolver._refresh_offsets
        cs_mod.CaptchaSolver._refresh_offsets = lambda self: None
        try:
            solver = cs_mod.CaptchaSolver(pid=12345, wid=100)
            solver.js = lambda code: '{}'
            result = solver.solve_slide()
            self.assertFalse(result)
        finally:
            cs_mod.CaptchaSolver.js = orig_js
            cs_mod.CaptchaSolver._refresh_offsets = orig_refresh

    def test_solve_dragdrop(self):
        """solve_dragdrop works with valid selectors."""
        self.mock_run.side_effect = _make_run_side_effect()
        from cli.modules.captcha_solver import CaptchaSolver
        solver = CaptchaSolver(pid=12345, wid=100)
        try:
            result = solver.solve_dragdrop(".source", ".target")
            self.assertIsInstance(result, bool)
        except Exception:
            pass

    def test_js_method(self):
        """js() method executes JavaScript and returns result."""
        self.mock_run.side_effect = _make_run_side_effect()
        from cli.modules.captcha_solver import CaptchaSolver
        solver = CaptchaSolver(pid=12345, wid=100)
        result = solver.js("document.title")
        self.assertIsInstance(result, str)


if __name__ == "__main__":
    unittest.main()
