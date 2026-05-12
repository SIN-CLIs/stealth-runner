"""CompletionDetector — centralized survey-completion detection.

WARUM: runner.py hatte completion-Logik über 3 Methoden verteilt
(_detect_completion_text, _scan_completion_all_tabs, detect_completion).
CompletionDetector konsolidiert ALLES was mit "Ist die Umfrage fertig?"
zu tun hat in EINEM Modul.

ARCHITEKTUR:
  CompletionDetector.detect(text)      -> bool (page text analysis)
  CompletionDetector.detect_ws(ws_url) -> bool (read page + detect)
  CompletionDetector.scan_all_tabs(port) -> bool (cross-tab scan)

BANNED METHODS — NIEMALS VERWENDEN:
  ❌ playstealth launch
  ❌ webauto-nodriver — ABSOLUT BANNED
  ❌ cua-driver click (raw index)
  ❌ Hardcoded PIDs
"""

from . import chrome
from .snapshot import detect_completion as _detect_completion_text
from .execute import BatchExecutor


class CompletionDetector:
    """Detect whether a survey has completed, screen-out, or is still running."""

    def __init__(self, cdp_port: int = 9999, debug: bool = False):
        self.cdp_port = cdp_port
        self.debug = debug

    # ── Public API ──────────────────────────────────────────────

    def detect(self, text: str) -> bool:
        """Check if page text contains completion markers."""
        return _detect_completion_text(text)

    def detect_ws(self, ws_url: str, max_len: int = 500) -> bool:
        """Read page text via CDP and check for completion markers."""
        try:
            text = BatchExecutor.read_page_text(ws_url, max_len)
            return self.detect(text)
        except Exception:
            return False

    def scan_all_tabs(self) -> bool:
        """Scan ALL browser tabs for completion markers.

        WHY: Survey completion may redirect to a different tab
        (e.g., back to dashboard after payout). Scanning all tabs
        ensures we don't miss completion signals.
        """
        try:
            for tab in chrome.find_bot_tabs(self.cdp_port):
                url = tab.get("url", "").lower()
                if "dashboard" in url or "about:blank" in url:
                    continue
                ws_url = tab.get("webSocketDebuggerUrl")
                if ws_url and self.detect_ws(ws_url):
                    if self.debug:
                        print(f"[COMPLETION] Detected on tab {url[:60]}")
                    return True
        except Exception:
            pass
        return False
