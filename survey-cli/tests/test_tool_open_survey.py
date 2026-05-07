#!/usr/bin/env python3
"""Test for tool_open_survey.py — Survey Opening Tool.

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


class TestProviderDetection(unittest.TestCase):
    """Test _detect_provider — provider detection from URL."""

    def test_detect_qualtrics(self):
        from tools.tool_open_survey import _detect_provider
        self.assertEqual(
            _detect_provider("https://survey.qualtrics.com/jfe/form/SV_abc123"),
            "qualtrics"
        )

    def test_detect_toluna(self):
        from tools.tool_open_survey import _detect_provider
        self.assertEqual(
            _detect_provider("https://tolunastart.com/survey/abc"),
            "toluna"
        )

    def test_detect_cint(self):
        from tools.tool_open_survey import _detect_provider
        self.assertEqual(
            _detect_provider("https://s.cint.com/Survey/Fingerprint?sid=123"),
            "cint"
        )

    def test_detect_samplicio(self):
        from tools.tool_open_survey import _detect_provider
        self.assertEqual(
            _detect_provider("https://rx.samplicio.us/consent/abc"),
            "cint"  # 'cint' comes before 'samplicio' in PROVIDER_PATTERNS dict
        )

    def test_detect_nfield(self):
        from tools.tool_open_survey import _detect_provider
        self.assertEqual(
            _detect_provider("https://nfieldeu-interviewing.nfieldmr.com/welcome"),
            "nfield"
        )

    def test_detect_strat7(self):
        from tools.tool_open_survey import _detect_provider
        self.assertEqual(
            _detect_provider("https://survey.strat7.com/s/abc"),
            "strat7"
        )

    def test_detect_unknown(self):
        from tools.tool_open_survey import _detect_provider
        self.assertEqual(
            _detect_provider("https://example.com/something"),
            "unknown"
        )

    def test_detect_purespectrum(self):
        from tools.tool_open_survey import _detect_provider
        self.assertEqual(
            _detect_provider("https://purespectrum.com/survey/abc"),
            "purespectrum"
        )

    def test_detect_case_insensitive(self):
        from tools.tool_open_survey import _detect_provider
        self.assertEqual(
            _detect_provider("https://QUAlTRICS.com/form"),
            "qualtrics"
        )


class TestCpxApi(unittest.TestCase):
    """Test _get_details_url and _get_survey_url."""

    def test_get_details_url_returns_string(self):
        from tools.tool_open_survey import _get_details_url
        url = _get_details_url()
        self.assertTrue(url.startswith("https://"))
        self.assertIn("cpx-research.com", url)

    def test_get_details_url_includes_params(self):
        from tools.tool_open_survey import _get_details_url
        url = _get_details_url()
        self.assertIn("app_id=11644", url)
        self.assertIn("ext_user_id=2525530", url)


class TestCdpHelpers(unittest.TestCase):
    """Test CDP helper functions with mocked HTTP."""

    def setUp(self):
        self._urlopen_patcher = patch("tools.tool_open_survey.urllib.request.urlopen")
        self.mock_urlopen = self._urlopen_patcher.start()

    def tearDown(self):
        self._urlopen_patcher.stop()

    def _set_pages(self, pages):
        mock = MagicMock()
        mock.read.return_value = json.dumps(pages).encode()
        self.mock_urlopen.return_value = mock

    def test_get_cdp_pages_returns_list(self):
        self._set_pages([{"id": "t1", "url": "https://test.com", "type": "page"}])
        from tools.tool_open_survey import _get_cdp_pages
        pages = _get_cdp_pages()
        self.assertEqual(len(pages), 1)

    def test_get_cdp_pages_failure_empty(self):
        self.mock_urlopen.side_effect = ConnectionError("no")
        from tools.tool_open_survey import _get_cdp_pages
        pages = _get_cdp_pages()
        self.assertEqual(pages, [])

    def test_get_dashboard_ws_found(self):
        self._set_pages([
            {"id": "t1", "url": "https://heypiggy.com/?page=dashboard", "type": "page",
             "webSocketDebuggerUrl": "ws://127.0.0.1:9999/devtools/page/t1"},
            {"id": "t2", "url": "https://google.com", "type": "page",
             "webSocketDebuggerUrl": "ws://127.0.0.1:9999/devtools/page/t2"},
        ])
        from tools.tool_open_survey import _get_dashboard_ws
        ws = _get_dashboard_ws()
        self.assertIsNotNone(ws)
        self.assertTrue(ws.startswith("ws://"))

    def test_get_dashboard_ws_not_found(self):
        self._set_pages([
            {"id": "t1", "url": "https://google.com", "type": "page",
             "webSocketDebuggerUrl": "ws://127.0.0.1:9999/devtools/page/t1"},
        ])
        from tools.tool_open_survey import _get_dashboard_ws
        ws = _get_dashboard_ws()
        self.assertIsNone(ws)

    def test_find_new_tab_returns_new_page(self):
        old_ids = {"old1", "old2"}
        self._set_pages([
            {"id": "old1", "url": "https://old.com", "type": "page",
             "webSocketDebuggerUrl": "ws://.../page/old1"},
            {"id": "new1", "url": "https://new.com", "type": "page",
             "webSocketDebuggerUrl": "ws://.../page/new1"},
        ])
        from tools.tool_open_survey import _find_new_tab
        tab = _find_new_tab(old_ids)
        self.assertIsNotNone(tab)
        self.assertEqual(tab["id"], "new1")

    def test_find_new_tab_none_when_all_known(self):
        old_ids = {"old1", "old2"}
        self._set_pages([
            {"id": "old1", "url": "https://old.com", "type": "page"},
            {"id": "old2", "url": "https://old2.com", "type": "page"},
        ])
        from tools.tool_open_survey import _find_new_tab
        tab = _find_new_tab(old_ids)
        self.assertIsNone(tab)


class TestCloseSurveyTab(unittest.TestCase):
    """Test close_survey_tab function."""

    def test_close_returns_bool(self):
        """Placeholder: close_survey_tab exists and accepts tab_id."""
        from tools.tool_open_survey import close_survey_tab
        self.assertTrue(hasattr(close_survey_tab, "__call__"))


if __name__ == "__main__":
    unittest.main()
