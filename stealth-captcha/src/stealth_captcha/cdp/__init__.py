"""Chrome DevTools Protocol client + browser launcher.

Provides async CDP over WebSocket with auto-reconnect, session management,
and target discovery. All CDP commands used by the solvers go through this.
"""

from stealth_captcha.cdp.browser import StealthBrowser
from stealth_captcha.cdp.client import CDPClient, CDPSession
from stealth_captcha.cdp.targets import TargetInfo, find_page, get_browser_ws, list_targets

__all__ = [
    "CDPClient",
    "CDPSession",
    "StealthBrowser",
    "TargetInfo",
    "find_page",
    "list_targets",
    "get_browser_ws",
]
