"""SurveyOpener — encapsulate survey-tab lifecycle (open, activate, close, refresh).

WARUM: runner.py hatte ~200 Zeilen Tab-Logik gemischt mit NEMO-Loop,
Balance-Tracking und Provider-Details. SurveyOpener lokalisiert ALLES
was mit "Survey öffnen/schliessen/aktivieren" zu tun hat.

ARCHITEKTUR:
  SurveyOpener.open(survey_id, provider, url, dashboard_ws)
    → OpenResult (target=SurveyTarget | None, error=str, status=str)

  SurveyTarget ist die einzige Datenstruktur die der Runner braucht,
  um den NEMO-Loop auszuführen. Kein direkter Tab-Handling mehr im Runner.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Optional, Set

from . import chrome
from .cdp_client import CDPConnection
from .observability.logger import get_logger


try:
    import websocket
except ImportError:
    websocket = None  # type: ignore


@dataclass
class SurveyTarget:
    """Immutable handle for a survey tab/modal."""

    survey_id: str
    provider: str
    ws_url: str
    tab_id: Optional[str] = None
    mode: str = "new_tab"          # "new_tab" | "in_page" | "redirect"
    actual_url: str = ""
    actual_provider: str = ""


@dataclass
class OpenResult:
    """Result of SurveyOpener.open()."""

    target: Optional[SurveyTarget] = None
    error: str = ""
    status: str = "error"          # "error" | "screen_out"


class SurveyOpener:
    """Open surveys via in-page modal or new-tab, with stealth injection."""

    def __init__(self, cdp_port: int = 8888, debug: bool = False):
        self.cdp_port = cdp_port
        self.debug = debug

    # ── Public API ──────────────────────────────────────────────

    def open(
        self,
        survey_id: str,
        provider: str,
        survey_url: str,
        dashboard_ws: Optional[str] = None,
    ) -> OpenResult:
        """Open survey and return an OpenResult.

        Preserves specific error messages so the runner can log earnings
        and return the correct status to callers/tests.
        """
        is_in_page = provider == "in_page_modal"

        if is_in_page and dashboard_ws:
            return self._open_in_page_modal(survey_id, provider, dashboard_ws)

        return self._open_new_tab(survey_id, provider, survey_url)

    def close(self, target: SurveyTarget) -> None:
        """Close the survey tab (no-op for in-page modal)."""
        if target.mode == "in_page" or not target.tab_id:
            return
        self._close_tab(target.tab_id)

    def refresh_ws(self, target: SurveyTarget) -> Optional[str]:
        """Re-discover WS URL after navigation."""
        if target.tab_id:
            fresh = self._refresh_tab_ws(target.tab_id)
            if fresh:
                return fresh
        # Fallback: any non-dashboard tab
        for p in chrome.find_bot_tabs(self.cdp_port):
            url = p.get("url", "")
            if url and "dashboard" not in url and "about:blank" not in url:
                try:
                    ws_url = p["webSocketDebuggerUrl"]
                    fid = p.get("id")
                    if fid:
                        chrome.activate_tab(fid, self.cdp_port)
                    with CDPConnection(ws_url, max_retries=2, timeout=5) as cdp:
                        cdp.call("Runtime.evaluate",
                                 {"expression": "document.readyState"})
                    return ws_url
                except Exception:
                    continue
        return None

    def activate(self, target: SurveyTarget) -> None:
        """Bring tab to foreground (needed for JS event firing)."""
        if target.tab_id:
            chrome.activate_tab(target.tab_id, self.cdp_port)

    # ── In-page modal ───────────────────────────────────────────

    def _open_in_page_modal(
        self,
        survey_id: str,
        provider: str,
        dashboard_ws: str,
    ) -> OpenResult:
        self._pre_survey_cleanup(dashboard_ws)

        tabs_before: Set[str] = set()
        try:
            for p in chrome.find_bot_tabs(self.cdp_port):
                tabs_before.add(p.get("id", ""))
        except Exception:
            pass

        ws = self._click_survey_card(survey_id, dashboard_ws)
        if not ws:
            return OpenResult(
                error="Failed to click survey card (in-page modal)",
                status="error",
            )

        # Some providers open a new tab anyway
        new_ws = self._find_new_tab_after_click(tabs_before)
        if new_ws:
            new_tab_id = None
            for p in chrome.find_bot_tabs(self.cdp_port):
                if p.get("webSocketDebuggerUrl") == new_ws:
                    new_tab_id = p.get("id")
                    break
            if new_tab_id:
                chrome.activate_tab(new_tab_id, self.cdp_port)
                if self.debug:
                    get_logger().info(f"[TAB] Activated new tab {new_tab_id[:8]}",
                                      context="tab_activate", tab_id=new_tab_id[:8])
            return OpenResult(
                target=SurveyTarget(
                    survey_id=survey_id,
                    provider=provider,
                    ws_url=new_ws,
                    tab_id=new_tab_id,
                    mode="redirect",
                ),
            )

        return OpenResult(
            target=SurveyTarget(
                survey_id=survey_id,
                provider=provider,
                ws_url=ws,
                mode="in_page",
            ),
        )

    # ── New tab ─────────────────────────────────────────────────

    def _open_new_tab(
        self,
        survey_id: str,
        provider: str,
        survey_url: str,
    ) -> OpenResult:
        tab_id = self._create_tab(survey_url)
        if not tab_id:
            return OpenResult(
                error="Failed to create browser tab",
                status="error",
            )

        chrome.activate_tab(tab_id, self.cdp_port)
        if self.debug:
            get_logger().info(f"[TAB] Activated new tab {tab_id[:8]}",
                              context="tab_activate", tab_id=tab_id[:8])

        time.sleep(1.5)
        tab_ws, actual_url = self._find_survey_tab_ws(tab_id)

        # Stuck loading page detection
        if tab_ws:
            page_text = self._read_page_text(tab_ws, 500).lower()
            stuck_markers = [
                "loading", "just getting things ready", "won't be long",
            ]
            if any(s in page_text for s in stuck_markers):
                if self.debug:
                    get_logger().info("[RUN] Stuck on loading page — closing tab",
                                      context="loading_stuck", survey_id=survey_id)
                self._close_tab(tab_id)
                return OpenResult(
                    error="Survey stuck on loading page",
                    status="screen_out",
                )

        # Handle CPX redirect / error pages
        if tab_ws:
            page_text = self._read_page_text(tab_ws, 500).lower()
            error_markers = [
                "no app id", "survey not available",
                "error - unable to start survey", "survey closed",
                "link has expired", "survey has ended",
                "leider ist ein fehler aufgetreten", "error occurred",
                "this survey is no longer available", "survey unavailable",
            ]
            if any(s in page_text for s in error_markers):
                if self.debug:
                    get_logger().info("[RUN] Survey expired/error — closing tab",
                                      context="survey_expired", survey_id=survey_id)
                self._close_tab(tab_id)
                return OpenResult(
                    error="Survey URL expired/error page",
                    status="screen_out",
                )

            if "sie werden umgeleitet" in page_text or "redirect" in page_text:
                if self.debug:
                    get_logger().info("[RUN] CPX redirect page — clicking link...",
                                      context="cpx_redirect", survey_id=survey_id)
                self._click_redirect_link(tab_ws)
                time.sleep(2.0)
                tab_ws, actual_url = self._find_survey_tab_ws(tab_id)

        return OpenResult(
            target=SurveyTarget(
                survey_id=survey_id,
                provider=provider,
                ws_url=tab_ws or "",
                tab_id=tab_id,
                mode="new_tab",
                actual_url=actual_url or "",
            ),
        )

    # ── Internal helpers ────────────────────────────────────────

    def _create_tab(self, url: str) -> Optional[str]:
        """Create blank tab, inject stealth, navigate."""
        tab_info = chrome.create_blank_tab(self.cdp_port)
        if not tab_info:
            if self.debug:
                get_logger().info("[STEALTH] Fallback to direct navigation",
                                  context="stealth_fallback")
            return chrome.create_tab(url, self.cdp_port)
        injected = chrome.inject_stealth_to_tab(tab_info["ws_url"])
        if self.debug:
            get_logger().info(f"[STEALTH] {'OK' if injected else 'FAIL'} {tab_info['id'][:8]}",
                              context="stealth_inject", success=injected, tab_id=tab_info['id'][:8])
        navigated = chrome.navigate_tab(tab_info["ws_url"], url)
        if not navigated and self.debug:
            get_logger().warn("[STEALTH] Navigation failed",
                              context="stealth_nav", survey_id=survey_id)
        return tab_info["id"]

    def _click_survey_card(self, survey_id: str, dashboard_ws: str) -> Tuple[Optional[str], Optional[str]]:
        """Execute clickSurvey() in dashboard context via DOM click (reliable).

        Returns:
            (ws_url, tab_id) tuple.
            - ws_url: WebSocket URL of the survey tab (or dashboard if in-page)
            - tab_id: Chrome target ID (for new-tab flow) or None (for in-page)

        Uses element.click() instead of calling clickSurvey(id) directly.
        element.click() works even when clickSurvey() throws TypeError
        (heypiggy's JS expects different data structure than we provide).
        The onclick handler fires regardless of function errors.
        """
        if not websocket:
            return None, None
        try:
            tabs_before = set()
            for p in chrome.find_bot_tabs(self.cdp_port):
                tabs_before.add(p.get("id", ""))

            ws = websocket.create_connection(dashboard_ws, timeout=10)
            click_js = f'''
(function() {{
    var cards = document.querySelectorAll("[onclick*=clickSurvey]");
    for (var c of cards) {{
        var onclick = c.getAttribute("onclick");
        var m = onclick.match(/clickSurvey\\('(\\d+)'\\)/);
        if (m && m[1] === "{survey_id}") {{
            c.click();
            return "clicked";
        }}
    }}
    var first = document.querySelector("[onclick*=clickSurvey]");
    if (first) {{ first.click(); return "clicked_first"; }}
    return "not_found";
}})()
'''
            ws.send(json.dumps({
                "id": 1,
                "method": "Runtime.evaluate",
                "params": {"expression": click_js},
            }))
            json.loads(ws.recv())
            ws.close()
            time.sleep(0.5)

            new_ws = self._find_new_tab_after_click(tabs_before)
            if new_ws:
                # Find tab_id for the new tab
                new_tab_id = None
                for p in chrome.find_bot_tabs(self.cdp_port):
                    if p.get("webSocketDebuggerUrl") == new_ws:
                        new_tab_id = p.get("id")
                        break
                if self.debug:
                    get_logger().info(f"[MODAL] Clicked {survey_id} — new tab: {new_ws[:60]}",
                                      context="survey_card_click", survey_id=survey_id)
                return new_ws, new_tab_id  # Survey tab WS + tab_id

            if self.debug:
                get_logger().info(f"[MODAL] Clicked {survey_id} — in-page modal",
                                  context="survey_card_click", survey_id=survey_id)
            return dashboard_ws, None  # Dashboard WS, no tab_id
        except Exception as e:
            if self.debug:
                get_logger().warn(f"[MODAL] Failed to click survey card: {e}",
                                  context="survey_card_failed", survey_id=survey_id)
            return None, None

    def _click_redirect_link(self, tab_ws: str) -> None:
        """Click 'hier klicken' on CPX redirect page."""
        if not websocket:
            return
        try:
            ws = websocket.create_connection(tab_ws, timeout=10)
            ws.send(json.dumps({
                "id": 0,
                "method": "Runtime.evaluate",
                "params": {"expression": '''
(function() {
    var links = document.querySelectorAll("a");
    for (var i=0;i<links.length;i++) {
        if ((links[i].textContent||"").includes("hier klicken")) {
            links[i].click(); return "clicked";
        }
    }
    if (links.length > 0) { links[0].click(); return "fallback_click"; }
    return "no_link";
})()
'''},
            }))
            json.loads(ws.recv())
            ws.close()
        except Exception:
            pass

    def _find_survey_tab_ws(self, tab_id: str) -> tuple[Optional[str], str]:
        """Find WS URL and actual URL for a tab after redirects."""
        tab_info = chrome.get_ws_for_tab(tab_id, self.cdp_port)
        if tab_info:
            try:
                if not websocket:
                    return None, ""
                ws = websocket.create_connection(tab_info, timeout=8)
                ws.send(json.dumps({
                    "id": 0,
                    "method": "Runtime.evaluate",
                    "params": {
                        "expression": "document.location.href",
                        "returnByValue": True,
                    },
                }))
                r = json.loads(ws.recv())
                ws.close()
                url = r.get("result", {}).get("result", {}).get("value", "")
                if url and "click.cpx" not in url and "dashboard" not in url:
                    return tab_info, url
            except Exception:
                pass

        for p in chrome.find_bot_tabs(self.cdp_port):
            url = p.get("url", "")
            if url and "dashboard" not in url and "about:blank" not in url:
                return p.get("webSocketDebuggerUrl"), url

        return None, ""

    def _close_tab(self, tab_id: str) -> None:
        """Close a browser tab via Target.closeTarget."""
        if not websocket:
            return
        try:
            for p in chrome.find_bot_tabs(self.cdp_port):
                if p.get("id") == tab_id:
                    ws = websocket.create_connection(
                        p["webSocketDebuggerUrl"], timeout=10
                    )
                    ws.send(json.dumps({
                        "id": 1,
                        "method": "Target.closeTarget",
                        "params": {"targetId": tab_id},
                    }))
                    json.loads(ws.recv())
                    ws.close()
                    return
            dash_ws = chrome.find_dashboard_ws(self.cdp_port)
            if dash_ws:
                ws = websocket.create_connection(dash_ws, timeout=10)
                ws.send(json.dumps({
                    "id": 1,
                    "method": "Target.closeTarget",
                    "params": {"targetId": tab_id},
                }))
                json.loads(ws.recv())
                ws.close()
        except Exception:
            pass

    def _refresh_tab_ws(self, tab_id: str) -> Optional[str]:
        """Re-discover WS URL for a tab, with activation."""
        chrome.activate_tab(tab_id, self.cdp_port)
        tab_info = chrome.get_ws_for_tab(tab_id, self.cdp_port)
        if tab_info:
            try:
                with CDPConnection(tab_info, max_retries=2, timeout=5) as cdp:
                    cdp.call("Runtime.evaluate",
                             {"expression": "document.location.href"})
                return tab_info
            except Exception:
                pass
        return None

    def _find_new_tab_after_click(self, known_tab_ids: Set[str]) -> Optional[str]:
        """Detect new tab opened by clickSurvey()."""
        from tools.tool_find_new_tab import find_new_tab
        return find_new_tab(self.cdp_port, known_tab_ids)

    def _pre_survey_cleanup(self, tab_ws: str) -> int:
        """Close stacked modals before opening survey."""
        from tools.tool_close_modals import close_modals
        return close_modals(tab_ws)

    @staticmethod
    def _read_page_text(ws_url: str, max_len: int = 500) -> str:
        """Read page innerText via CDP."""
        if not websocket:
            return ""
        try:
            ws = websocket.create_connection(ws_url, timeout=8)
            ws.send(json.dumps({
                "id": 0,
                "method": "Runtime.evaluate",
                "params": {
                    "expression": f'document.body.innerText.slice(0,{max_len})',
                    "returnByValue": True,
                },
            }))
            r = json.loads(ws.recv())
            ws.close()
            return r.get("result", {}).get("result", {}).get("value", "")
        except Exception:
            return ""
