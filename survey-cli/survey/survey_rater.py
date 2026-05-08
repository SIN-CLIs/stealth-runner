"""SurveyRater — click rating button for +0.01€ bonus on completed surveys.

WARUM: runner.py hatte ~25 Zeilen Rating-Logik.
SurveyRater isoliert ALLES was mit "Umfrage bewerten" zu tun hat.

BANNED METHODS — NIEMALS VERWENDEN:
  ❌ playstealth launch
  ❌ webauto-nodriver — ABSOLUT BANNED
  ❌ cua-driver click (raw index)
  ❌ Hardcoded PIDs
"""

import json
import time
from typing import Optional

from . import chrome
from .observability.logger import get_logger

try:
    import websocket
except ImportError:
    websocket = None  # type: ignore


class SurveyRater:
    """Rate completed survey pages for +0.01€ bonus."""

    def __init__(self, cdp_port: int = 8888, debug: bool = False):
        self.cdp_port = cdp_port
        self.debug = debug

    def rate(self) -> bool:
        """Find rating page and click rating button.

        Scans all browser tabs for rating.php or cpx-research URLs,
        then clicks the first button/blue button/input found.

        Returns:
            True if rating button was clicked, False otherwise.
        """
        if not websocket:
            return False

        try:
            pages = chrome.find_bot_tabs(self.cdp_port)
            for p in pages:
                url = p.get("url", "")
                if "rating.php" in url.lower() or "cpx-research" in url.lower():
                    ws_url = p.get("webSocketDebuggerUrl")
                    if ws_url:
                        ws = websocket.create_connection(ws_url, timeout=15)
                        ws.send(
                            json.dumps(
                                {
                                    "id": 0,
                                    "method": "Runtime.evaluate",
                                    "params": {
                                        "expression": 'document.querySelector("button,.btn-blue,input[type=button]").click()'
                                    },
                                }
                            )
                        )
                        json.loads(ws.recv())
                        ws.close()
                        time.sleep(2)
                        if self.debug:
                            get_logger().info("[RATE] Clicked rating button", context="survey_rating")
                        return True
        except Exception as e:
            if self.debug:
                get_logger().warn(f"[RATE] Rating failed: {e}", context="survey_rating_failed")
        return False
