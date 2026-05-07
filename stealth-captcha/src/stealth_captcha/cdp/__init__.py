"""Chrome DevTools Protocol client + browser launcher.

WARUM: Jede Captcha-Interaktion braucht CDP. Dieses Paket bündelt
alle CDP-Komponenten (Browser-Launcher, WebSocket-Client, Target-Discovery)
in einem Import. Kein Modul außerhalb dieses Packages darf direkt
mit Chrome kommunizieren.

ARCHITEKTUR: Package-Root. Exportiert StealthBrowser, CDPClient,
CDPSession, TargetInfo, find_page, get_browser_ws, list_targets.
Alle Klassen sind async und verwenden tenacity für Reconnect.

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
