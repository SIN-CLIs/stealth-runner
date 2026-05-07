#!/usr/bin/env python3
"""Test for tool_find_new_tab.py — Tab Change Detector.

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
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

MOCK_TABS = [
    {"id": "tab1", "url": "https://heypiggy.com/dashboard", "type": "page",
     "webSocketDebuggerUrl": "ws://127.0.0.1:9222/devtools/page/tab1"},
    {"id": "tab2", "url": "about:blank", "type": "page",
     "webSocketDebuggerUrl": "ws://127.0.0.1:9222/devtools/page/tab2"},
    {"id": "tab3", "url": "https://survey.qualtrics.com/jfe/form/123", "type": "page",
     "webSocketDebuggerUrl": "ws://127.0.0.1:9222/devtools/page/tab3"},
    {"id": "tab4", "url": "chrome-extension://abc", "type": "background_page"},
]


class TestGetAllTabs(unittest.TestCase):
    """Test get_all_tabs() — fetching Chrome tab list."""

    def setUp(self):
        self._req_patcher = patch("tools.tool_find_new_tab.requests.get")
        self.mock_get = self._req_patcher.start()

    def tearDown(self):
        self._req_patcher.stop()

    def test_get_all_tabs_returns_pages_only(self):
        """get_all_tabs filters to type='page' only."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = MOCK_TABS
        self.mock_get.return_value = mock_resp
        from tools.tool_find_new_tab import get_all_tabs
        tabs = get_all_tabs(9222)
        self.assertEqual(len(tabs), 3)  # tab4 is background_page

    def test_get_all_tabs_connection_error_empty(self):
        """Returns empty list when Chrome not reachable."""
        self.mock_get.side_effect = ConnectionError("refused")
        from tools.tool_find_new_tab import get_all_tabs
        tabs = get_all_tabs(9999)
        self.assertEqual(tabs, [])

    def test_get_all_tabs_calls_correct_url(self):
        """get_all_tabs calls http://127.0.0.1:<port>/json."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = []
        self.mock_get.return_value = mock_resp
        from tools.tool_find_new_tab import get_all_tabs
        get_all_tabs(9333)
        self.mock_get.assert_called_with(
            "http://127.0.0.1:9333/json", timeout=5
        )


class TestGetTabIds(unittest.TestCase):
    """Test get_tab_ids() — extracting IDs as set."""

    def setUp(self):
        self._req_patcher = patch("tools.tool_find_new_tab.requests.get")
        self.mock_get = self._req_patcher.start()

    def tearDown(self):
        self._req_patcher.stop()

    def test_get_tab_ids_returns_set(self):
        mock_resp = MagicMock()
        mock_resp.json.return_value = MOCK_TABS
        self.mock_get.return_value = mock_resp
        from tools.tool_find_new_tab import get_tab_ids
        ids = get_tab_ids(9222)
        self.assertIsInstance(ids, set)
        self.assertIn("tab1", ids)
        self.assertIn("tab3", ids)


class TestFindNewTab(unittest.TestCase):
    """Test find_new_tab() — detecting new tabs."""

    def setUp(self):
        self._req_patcher = patch("tools.tool_find_new_tab.requests.get")
        self.mock_get = self._req_patcher.start()
        self._sleep_patcher = patch("tools.tool_find_new_tab.time.sleep")
        self.mock_sleep = self._sleep_patcher.start()

    def tearDown(self):
        self._req_patcher.stop()
        self._sleep_patcher.stop()

    def test_find_new_tab_detected(self):
        """New survey tab found after known_tab_ids diff."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = MOCK_TABS
        self.mock_get.return_value = mock_resp
        from tools.tool_find_new_tab import find_new_tab
        result = find_new_tab(9222, {"tab1"}, wait_s=0)
        self.assertIsNotNone(result)
        self.assertTrue(result.startswith("ws://"))

    def test_find_new_tab_ignores_about_blank(self):
        """about:blank tabs are ignored."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = MOCK_TABS
        self.mock_get.return_value = mock_resp
        from tools.tool_find_new_tab import find_new_tab
        result = find_new_tab(9222, {"tab1", "tab3"}, wait_s=0)
        self.assertIsNone(result)  # Only tab2 (about:blank) is new

    def test_find_new_tab_no_new_tabs(self):
        """Returns None when all tabs were known."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = MOCK_TABS
        self.mock_get.return_value = mock_resp
        from tools.tool_find_new_tab import find_new_tab
        result = find_new_tab(9222, {"tab1", "tab2", "tab3"}, wait_s=0)
        self.assertIsNone(result)

    def test_find_new_tab_custom_ignore_urls(self):
        """Custom ignore_urls parameter works."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = MOCK_TABS
        self.mock_get.return_value = mock_resp
        from tools.tool_find_new_tab import find_new_tab
        result = find_new_tab(9222, {"tab1", "tab2"}, wait_s=0,
                              ignore_urls=["qualtrics"])
        self.assertIsNone(result)  # tab3 is ignored

    def test_find_new_tab_waits_before_scan(self):
        """Waits wait_s seconds before scanning."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = MOCK_TABS
        self.mock_get.return_value = mock_resp
        from tools.tool_find_new_tab import find_new_tab
        find_new_tab(9222, {"tab1", "tab2"}, wait_s=2.5)
        self.mock_sleep.assert_called_with(2.5)


class TestFindTabByUrl(unittest.TestCase):
    """Test find_tab_by_url() — finding tab by URL substring."""

    def setUp(self):
        self._req_patcher = patch("tools.tool_find_new_tab.requests.get")
        self.mock_get = self._req_patcher.start()

    def tearDown(self):
        self._req_patcher.stop()

    def test_find_tab_by_url_match(self):
        mock_resp = MagicMock()
        mock_resp.json.return_value = MOCK_TABS
        self.mock_get.return_value = mock_resp
        from tools.tool_find_new_tab import find_tab_by_url
        result = find_tab_by_url(9222, "qualtrics")
        self.assertIsNotNone(result)
        self.assertTrue(result.startswith("ws://"))

    def test_find_tab_by_url_no_match(self):
        mock_resp = MagicMock()
        mock_resp.json.return_value = MOCK_TABS
        self.mock_get.return_value = mock_resp
        from tools.tool_find_new_tab import find_tab_by_url
        result = find_tab_by_url(9222, "doesnotexist")
        self.assertIsNone(result)

    def test_find_tab_by_url_case_insensitive(self):
        mock_resp = MagicMock()
        mock_resp.json.return_value = MOCK_TABS
        self.mock_get.return_value = mock_resp
        from tools.tool_find_new_tab import find_tab_by_url
        result = find_tab_by_url(9222, "Qualtrics")
        self.assertIsNotNone(result)


if __name__ == "__main__":
    unittest.main()
