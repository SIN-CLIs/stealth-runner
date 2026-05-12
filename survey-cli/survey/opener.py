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
from .session_validator import is_session_valid, validate_session


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

    def __init__(self, cdp_port: int = 9999, debug: bool = False):
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

        COOKIE TIMING FIX (2026-05-10):
        Previously this method used _open_new_tab() which created a new tab via
        Target.createTarget. That new tab had NO heypiggy session cookies (they
        were only injected into the dashboard tab at Chrome startup).

        The redirect chain CPX → Samplicio → Cint → Potloc ran WITHOUT session
        cookies → Heypiggy completion tracking couldn't associate survey completion
        with the user session → balance stayed at €0.

        FIX: When dashboard_ws is available, use _open_in_dashboard_tab() to
        navigate the EXISTING dashboard tab (which HAS cookies) to the survey URL.
        After survey completes, caller navigates back to dashboard URL.
        """
        is_in_page = provider == "in_page_modal"

        if is_in_page and dashboard_ws:
            return self._open_in_page_modal(survey_id, provider, dashboard_ws)

        if dashboard_ws:
            return self._open_in_dashboard_tab(survey_id, provider, survey_url, dashboard_ws)

        return self._open_new_tab(survey_id, provider, survey_url)

    def close(self, target: SurveyTarget) -> None:
        """Close the survey tab (no-op for in-page/in_dashboard modal).

        For in_dashboard mode: the tab is the dashboard tab — do NOT close it.
        The caller (runner) should navigate it back to the dashboard URL after
        the survey completes. Closing the dashboard tab would leave the browser
        with no active tab.
        """
        if target.mode in ("in_page", "in_dashboard") or not target.tab_id:
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
        # SESSION VALIDATION (2026-05-10): Validate before clicking survey card
        # If session is invalid, clicking the card won't work properly
        if not is_session_valid(self.cdp_port):
            if self.debug:
                print("[SESSION] Session invalid in _open_in_page_modal — attempting recovery...")
            recovered = validate_session(self.cdp_port, auto_recover=True)
            if not recovered:
                return OpenResult(
                    error="Session invalid (recovery failed) — cannot open survey",
                    status="error",
                )

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
                    print(f"[TAB] Activated new tab {new_tab_id[:8]}")

            # COOKIE INJECTION FIX (2026-05-10):
            # When a new tab opens via window.open, it MAY not have cookies
            # (depends on Chrome's cookie jar sharing). Safer to explicitly inject.
            if new_ws:
                cookies_ok = chrome.inject_heypiggy_cookies_to_tab(
                    new_ws, debug=self.debug
                )
                if self.debug:
                    print(f"[COOKIES] Injected into new tab: {'OK' if cookies_ok else 'FAIL'}")

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
            print(f"[TAB] Activated new tab {tab_id[:8]}")

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
                    print("[RUN] Stuck on loading page — closing tab")
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
                    print("[RUN] Survey expired/error — closing tab")
                self._close_tab(tab_id)
                return OpenResult(
                    error="Survey URL expired/error page",
                    status="screen_out",
                )

            if "sie werden umgeleitet" in page_text or "redirect" in page_text:
                if self.debug:
                    print("[RUN] CPX redirect page — clicking link...")
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

    # ── Navigate dashboard tab (COOKIE TIMING FIX 2026-05-10) ───

    def _open_in_dashboard_tab(
        self,
        survey_id: str,
        provider: str,
        survey_url: str,
        dashboard_ws: str,
    ) -> OpenResult:
        """Navigate the dashboard tab to the survey URL.

        COOKIE TIMING FIX (2026-05-10):
        The dashboard tab HAS heypiggy session cookies (injected at Chrome startup).
        Creating a new tab via Target.createTarget creates a tab WITHOUT those cookies.
        The CPX redirect chain (CPX → Samplicio → Cint → Potloc) runs without session
        cookies → Heypiggy completion tracking can't associate completion → balance = €0.

        This method navigates the EXISTING dashboard tab (with cookies) to the survey URL.
        The survey runs in the dashboard tab context, preserving session cookies through
        the entire redirect chain.

        After survey completes (completion/disqualification/error), the caller MUST
        navigate the tab back to the dashboard URL.

        Args:
            survey_id: HeyPiggy survey ID
            provider: Provider name (purespectrum, samplicio, cint, etc.)
            survey_url: Full survey URL from CPX API
            dashboard_ws: WebSocket URL of the dashboard tab (HAS cookies!)

        Returns:
            OpenResult with SurveyTarget where:
            - ws_url = dashboard_ws (the same tab!)
            - tab_id = None (dashboard tab, no separate tab_id)
            - mode = "in_dashboard" (caller must navigate back to dashboard after)
            - actual_url = "" (unknown until after navigation)
        """
        # SESSION VALIDATION (2026-05-10): Validate before navigating to survey
        # If session is invalid, navigating won't register completion → €0
        if not is_session_valid(self.cdp_port):
            if self.debug:
                print("[SESSION] Session invalid in _open_in_dashboard_tab — attempting recovery...")  # noqa: E501
            recovered = validate_session(self.cdp_port, auto_recover=True)
            if not recovered:
                return OpenResult(
                    error="Session invalid (recovery failed) — cannot open survey",
                    status="error",
                )

        self._pre_survey_cleanup(dashboard_ws)

        if not websocket:
            return OpenResult(error="websocket not available", status="error")

        try:
            ws = websocket.create_connection(dashboard_ws, timeout=15)
            ws.send(json.dumps({
                "id": 1,
                "method": "Page.navigate",
                "params": {"url": survey_url},
            }))
            r = json.loads(ws.recv())
            ws.close()

            frame_id = r.get("result", {}).get("frameId")
            if self.debug:
                print(f"[DASHBOARD NAV] frameId={frame_id}, survey_id={survey_id}")

            time.sleep(2.5)  # Wait for initial redirects (CPX → Survey provider)

            return OpenResult(
                target=SurveyTarget(
                    survey_id=survey_id,
                    provider=provider,
                    ws_url=dashboard_ws,       # SAME tab, but now at survey URL
                    tab_id=None,               # No separate tab — same dashboard tab
                    mode="in_dashboard",       # NEW mode: navigate back after!
                    actual_url=survey_url,
                ),
                status="survey_opened",
            )
        except Exception as e:
            if self.debug:
                print(f"[DASHBOARD NAV] Failed: {e}")
            return OpenResult(error=f"Failed to navigate dashboard tab: {e}", status="error")

    # ── Post-completion: Navigate dashboard tab back ─────────────

    def navigate_back_to_dashboard(self, dashboard_ws: str) -> bool:
        """Navigate a tab back to the heypiggy dashboard.

        COOKIE TIMING FIX (2026-05-10):
        When the survey ran in the dashboard tab (mode='in_dashboard'), the tab
        is still at the survey URL after completion. HeyPiggy needs the user
        back on the dashboard to register the completion and update balance.

        This method navigates the tab back to the dashboard URL so HeyPiggy
        can properly track the survey completion and credit the balance.

        Args:
            dashboard_ws: WebSocket URL of the tab to navigate (should be
                          the same as the survey tab's WS when mode='in_dashboard')

        Returns:
            True if navigation was initiated successfully
        """
        if not websocket:
            return False
        try:
            ws = websocket.create_connection(dashboard_ws, timeout=15)
            ws.send(json.dumps({
                "id": 1,
                "method": "Page.navigate",
                "params": {"url": "https://www.heypiggy.com/?page=dashboard"},
            }))
            r = json.loads(ws.recv())
            ws.close()
            frame_id = r.get("result", {}).get("frameId")
            if self.debug:
                print(f"[DASHBOARD BACK] frameId={frame_id}")
            time.sleep(1.5)  # Wait for dashboard to load
            return frame_id is not None
        except Exception as e:
            if self.debug:
                print(f"[DASHBOARD BACK] Failed: {e}")
            return False

    # ── Internal helpers ────────────────────────────────────────

    def _create_tab(self, url: str) -> Optional[str]:
        """Create blank tab, inject stealth, inject cookies, navigate.

        COOKIE TIMING FIX (2026-05-10):
        Previously this method created a blank tab, injected stealth, then navigated.
        The new tab had NO heypiggy session cookies — the redirect chain ran without
        session cookies → Heypiggy completion tracking couldn't associate the survey
        completion with the user session → balance stayed at €0.

        FIX: Inject the 7 critical HeyPiggy cookies BEFORE Page.navigate.
        Order: create blank tab → inject stealth → inject cookies → navigate.
        The cookies are injected via Network.setCookies (synchronous — in jar instantly).
        """
        tab_info = chrome.create_blank_tab(self.cdp_port)
        if not tab_info:
            if self.debug:
                print("[STEALTH] Fallback to direct navigation")
            return chrome.create_tab(url, self.cdp_port)
        injected = chrome.inject_stealth_to_tab(tab_info["ws_url"])
        if self.debug:
            print(f"[STEALTH] {'OK' if injected else 'FAIL'} {tab_info['id'][:8]}")

        # COOKIE INJECTION — MUST happen before navigation!
        cookies_ok = chrome.inject_heypiggy_cookies_to_tab(
            tab_info["ws_url"], debug=self.debug
        )
        if self.debug:
            print(f"[COOKIES] {'OK' if cookies_ok else 'FAIL'} {tab_info['id'][:8]}")

        navigated = chrome.navigate_tab(tab_info["ws_url"], url)
        if not navigated and self.debug:
            print("[STEALTH] Navigation failed")
        return tab_info["id"]

    def _click_survey_card(self, survey_id: str, dashboard_ws: str) -> Optional[str]:
        """Execute clickSurvey() in dashboard context."""
        if not websocket:
            return None
        try:
            ws = websocket.create_connection(dashboard_ws, timeout=10)
            ws.send(json.dumps({
                "id": 1,
                "method": "Runtime.evaluate",
                "params": {"expression": f'clickSurvey("{survey_id}")'},
            }))
            json.loads(ws.recv())
            ws.close()
            if self.debug:
                print(f"[MODAL] Clicked survey card {survey_id}")
            return dashboard_ws
        except Exception as e:
            if self.debug:
                print(f"[MODAL] Failed to click survey card: {e}")
            return None

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
        try:
            from ..tools.tool_find_new_tab import find_new_tab
        except ImportError:
            from tools.tool_find_new_tab import find_new_tab
        return find_new_tab(self.cdp_port, known_tab_ids)

    def _pre_survey_cleanup(self, tab_ws: str) -> int:
        """Close stacked modals before opening survey."""
        try:
            from ..tools.tool_close_modals import close_modals
        except ImportError:
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
