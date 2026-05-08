"""Tests for Agent-Toolbox API endpoints.

WARUM: Die API muss isoliert testbar sein (kein echter Browser nötig).
Wir patchen BrowserManager und Auth-Flows.
"""

import unittest
from unittest.mock import MagicMock, patch, AsyncMock
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient


class TestBrowserEndpoints(unittest.TestCase):
    """Test /browser/* endpoints with mocked BrowserManager."""

    def setUp(self):
        # Patch BrowserManager before importing app
        self.bm_patcher = patch("api.main.BrowserManager")
        self.mock_bm_cls = self.bm_patcher.start()
        self.mock_bm = MagicMock()
        self.mock_bm_cls.return_value = self.mock_bm

        # Import app AFTER patch
        from api.main import app
        self.client = TestClient(app)

    def tearDown(self):
        self.bm_patcher.stop()

    def test_browser_start_success(self):
        """POST /browser/start returns success."""
        self.mock_bm.start = AsyncMock(return_value=MagicMock())
        self.mock_bm._last_used = 1234567890

        r = self.client.post("/browser/start", json={"profile_name": "test"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["status"], "success")
        self.assertEqual(r.json()["profile"], "test")

    def test_browser_stop_success(self):
        """POST /browser/stop returns success."""
        self.mock_bm.stop = AsyncMock(return_value=None)

        r = self.client.post("/browser/stop")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["status"], "success")

    def test_browser_health_not_running(self):
        """GET /browser/health when browser not running."""
        self.mock_bm.health = AsyncMock(return_value={
            "running": False,
            "profile": None,
            "last_used": 0.0,
            "idle_seconds": None,
        })

        r = self.client.get("/browser/health")
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.json()["running"])


class TestHeyPiggyLoginEndpoint(unittest.TestCase):
    """Test /services/heypiggy/login endpoint."""

    def setUp(self):
        self.bm_patcher = patch("api.main.BrowserManager")
        self.mock_bm_cls = self.bm_patcher.start()
        self.mock_bm = MagicMock()
        self.mock_bm_cls.return_value = self.mock_bm

        from api.main import app
        self.client = TestClient(app)

    def tearDown(self):
        self.bm_patcher.stop()

    @patch("api.main.GoogleOAuthFlow")
    def test_login_success(self, mock_flow_cls):
        """POST /services/heypiggy/login returns success."""
        self.mock_bm.start = AsyncMock(return_value=MagicMock())
        mock_flow = MagicMock()
        mock_flow.execute.return_value = MagicMock(
            status="ok", pid=123, wid=456, reason=None
        )
        mock_flow_cls.return_value = mock_flow

        r = self.client.post("/services/heypiggy/login",
                             json={"profile_name": "test", "pid": 123})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["status"], "success")
        self.assertEqual(r.json()["service"], "heypiggy")

    @patch("api.main.GoogleOAuthFlow")
    def test_login_already_logged_in(self, mock_flow_cls):
        """POST /services/heypiggy/login when already logged in."""
        mock_flow = MagicMock()
        mock_flow.execute.return_value = MagicMock(
            status="already_logged_in", pid=123, wid=456, reason=None
        )
        mock_flow_cls.return_value = mock_flow

        r = self.client.post("/services/heypiggy/login",
                             json={"profile_name": "test", "pid": 123})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["status"], "already_logged_in")

    @patch("api.main.GoogleOAuthFlow")
    def test_login_error(self, mock_flow_cls):
        """POST /services/heypiggy/login with error."""
        mock_flow = MagicMock()
        mock_flow.execute.return_value = MagicMock(
            status="error", pid=None, wid=None, reason="chrome_not_started"
        )
        mock_flow_cls.return_value = mock_flow

        r = self.client.post("/services/heypiggy/login",
                             json={"profile_name": "test", "pid": 123})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["status"], "error")
        self.assertEqual(r.json()["message"], "chrome_not_started")


class TestCookieEndpoint(unittest.TestCase):
    """Test /tools/extract-cookies endpoint."""

    def setUp(self):
        self.bm_patcher = patch("api.main.BrowserManager")
        self.mock_bm_cls = self.bm_patcher.start()
        self.mock_bm = MagicMock()
        self.mock_bm_cls.return_value = self.mock_bm

        from api.main import app
        self.client = TestClient(app)

    def tearDown(self):
        self.bm_patcher.stop()

    def test_extract_cookies_success(self):
        """POST /tools/extract-cookies returns cookies."""
        mock_ctx = MagicMock()
        mock_ctx.cookies = AsyncMock(return_value=[
            {"name": "session", "value": "abc123", "domain": ".heypiggy.com"},
        ])
        self.mock_bm.start = AsyncMock(return_value=mock_ctx)

        r = self.client.post("/tools/extract-cookies",
                             json={"profile_name": "test"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["status"], "success")
        self.assertEqual(r.json()["count"], 1)


class TestUtilityEndpoints(unittest.TestCase):
    """Test /tools/navigate, /tools/screenshot, /tools/page-content."""

    def setUp(self):
        self.bm_patcher = patch("api.main.BrowserManager")
        self.mock_bm_cls = self.bm_patcher.start()
        self.mock_bm = MagicMock()
        self.mock_bm_cls.return_value = self.mock_bm

        from api.main import app
        self.client = TestClient(app)

    def tearDown(self):
        self.bm_patcher.stop()

    def test_navigate_success(self):
        """POST /tools/navigate returns page title."""
        mock_page = MagicMock()
        mock_page.goto = AsyncMock(return_value=None)
        mock_page.title = AsyncMock(return_value="Example Domain")
        self.mock_bm.get_page = AsyncMock(return_value=mock_page)

        r = self.client.post("/tools/navigate",
                             json={"profile_name": "test", "url": "https://example.com"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["status"], "success")
        self.assertEqual(r.json()["url"], "https://example.com")
        self.assertEqual(r.json()["title"], "Example Domain")

    def test_screenshot_success(self):
        """POST /tools/screenshot returns base64 image."""
        mock_page = MagicMock()
        mock_page.screenshot = AsyncMock(return_value=b"\x89PNG\r\n\x1a\n")
        self.mock_bm.get_page = AsyncMock(return_value=mock_page)

        r = self.client.post("/tools/screenshot",
                             json={"profile_name": "test", "full_page": True})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["status"], "success")
        self.assertTrue(len(r.json()["base64_image"]) > 0)

    def test_page_content_success(self):
        """POST /tools/page-content returns page text."""
        mock_page = MagicMock()
        mock_page.url = "https://example.com"
        mock_page.title = AsyncMock(return_value="Example")
        mock_page.inner_text = AsyncMock(return_value="Hello World")
        mock_page.content = AsyncMock(return_value="<html><body>Hello</body></html>")
        self.mock_bm.get_page = AsyncMock(return_value=mock_page)

        r = self.client.post("/tools/page-content",
                             json={"profile_name": "test"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["status"], "success")
        self.assertEqual(r.json()["text"], "Hello World")
        self.assertEqual(r.json()["title"], "Example")


if __name__ == "__main__":
    unittest.main()
