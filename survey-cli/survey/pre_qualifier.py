"""PreQualifierHandler — browser-based and API-based pre-qualifier answering.

WARUM: runner.py hatte ~320 Zeilen Pre-Qualifier-Logik (API + Browser).
PreQualifierHandler konsolidiert ALLES was mit "Beantworte die Fragen
BEVOR die eigentliche Umfrage startet" zu tun hat.

TWO MODES:
  1. API mode: CPX API calls (handle_pre_qualifier_api)
  2. Browser mode: CDP JS evaluation (handle_pre_qualifier_browser)

BANNED METHODS — NIEMALS VERWENDEN:
  ❌ playstealth launch
  ❌ webauto-nodriver — ABSOLUT BANNED
  ❌ cua-driver click (raw index)
  ❌ Hardcoded PIDs
"""

import json
import time
import urllib.parse
import urllib.request
from typing import Dict, Any, Optional

from . import chrome
from .execute import BatchExecutor

try:
    import websocket
except ImportError:
    websocket = None  # type: ignore


class PreQualifierHandler:
    """Answer CPX pre-qualifier questions via API or browser automation."""

    def __init__(self, cdp_port: int = 9999, debug: bool = False):
        self.cdp_port = cdp_port
        self.debug = debug

    # ── API Mode ────────────────────────────────────────────────

    def handle_pre_qualifier_api(
        self,
        survey_id: str,
        survey_details: Dict[str, Any],
        profile: Dict[str, Any],
    ) -> Optional[str]:
        """Answer pre-qualifier questions via CPX API. Handles MULTI-STEP qualifiers.

        CPX asks 1-N questions before routing to actual survey. Loop until
        we get type=okay with href, or hit max retries.

        Returns:
            Survey URL string on success, None on failure.
        """
        from .chrome import get_details_url

        max_retries = 8
        details_url = get_details_url(self.cdp_port)
        current_details = survey_details

        for step in range(max_retries):
            question_text = current_details.get("question_text", "")
            question_key = current_details.get("question_key", "")
            answers_raw = current_details.get("answers", {})

            if not answers_raw or not question_key:
                if self.debug:
                    print(f"[PREQ] Step {step}: No answers/key — aborting")
                return None

            answer_keys = list(answers_raw.keys())
            q_lower = question_text.lower()
            answer_idx = None

            # Match question to profile
            if any(kw in q_lower for kw in ["alter", "age", "alters"]):
                age = profile.get("age", 32)
                if age < 18:
                    answer_idx = 0
                elif age < 25:
                    answer_idx = 1
                elif age < 35:
                    answer_idx = 2
                elif age < 45:
                    answer_idx = 3
                elif age < 55:
                    answer_idx = 4
                else:
                    answer_idx = 5

            elif any(kw in q_lower for kw in ["geschlecht", "gender"]):
                answer_idx = 0 if profile.get("gender", "male") == "male" else 1

            elif any(kw in q_lower for kw in ["bundesland", "wohnort", "region", "stadt"]):
                for i, k in enumerate(answer_keys):
                    if "berlin" in answers_raw[k].get("text", "").lower():
                        answer_idx = i
                        break

            elif any(kw in q_lower for kw in ["einkommen", "income"]):
                answer_idx = 2  # middle bracket

            elif any(kw in q_lower for kw in ["bildung", "education", "schulabschluss"]):
                edu = profile.get("education", "abitur")
                for i, k in enumerate(answer_keys):
                    if edu in answers_raw[k].get("text", "").lower():
                        answer_idx = i
                        break

            elif any(kw in q_lower for kw in ["beschäftigung", "employment", "berufstätig"]):
                answer_idx = 1  # employed

            # Default: first non-"cannot answer" option
            if answer_idx is None:
                for i, k in enumerate(answer_keys):
                    if "nicht beantworten" not in answers_raw[k].get("text", "").lower():
                        answer_idx = i
                        break
                if answer_idx is None:
                    answer_idx = 0

            if answer_idx >= len(answer_keys):
                return None

            selected_key = answer_keys[answer_idx]
            selected_text = answers_raw[selected_key].get("text", "")

            if self.debug:
                print(
                    f"[PREQ] Step {step}: Q={question_text[:50]}... → {selected_text[:50]}"
                )

            # POST answer
            try:
                msg_button = current_details.get("message_button", "einreichen")
                post_url = (
                    details_url
                    + "&survey_id="
                    + survey_id
                    + "&"
                    + urllib.parse.quote(question_key)
                    + "="
                    + urllib.parse.quote(selected_key)
                    + "&message_button="
                    + urllib.parse.quote(msg_button)
                )
                resp_json = json.loads(
                    urllib.request.urlopen(post_url, timeout=8).read()
                )

                # Check if we got the real survey URL
                if resp_json.get("status") == "success" and resp_json.get("href"):
                    if self.debug:
                        print(f"[PREQ] Got survey URL: {resp_json['href'][:60]}")
                    return resp_json.get("href")

                # More questions
                if resp_json.get("type") == "question":
                    current_details = resp_json
                    if self.debug:
                        print(f"[PREQ] → Next question, retrying...")
                    continue

                # Other response type
                if self.debug:
                    print(
                        f"[PREQ] Step {step}: unexpected response type: {resp_json.get('type')}"
                    )
                return None

            except Exception as e:
                if self.debug:
                    print(f"[PREQ] Step {step} POST failed: {e}")
                return None

        if self.debug:
            print(f"[PREQ] Max retries ({max_retries}) exceeded")
        return None

    # ── Browser Mode ────────────────────────────────────────────

    def handle_pre_qualifier_browser(
        self,
        survey_id: str,
        tab_closer=None,
    ) -> Dict[str, Any]:
        """Handle CPX pre-qualifier in browser. Answer via CDP → wait for redirect.

        Args:
            survey_id: CPX survey ID
            tab_closer: Optional callable(tab_id) to close a tab

        Returns:
            {"redirect_url": "..."} on success
            {"aborted": True} on failure
        """
        if not websocket:
            return {"aborted": True}

        dash_ws = chrome.find_dashboard_ws(self.cdp_port)
        if not dash_ws:
            return {"aborted": True}

        try:
            ws = websocket.create_connection(dash_ws, timeout=10)
            ws.send(
                json.dumps(
                    {
                        "id": 0,
                        "method": "Runtime.evaluate",
                        "params": {
                            "expression": f"clickSurvey('{survey_id}'); '';"
                        },
                    }
                )
            )
            json.loads(ws.recv())
            ws.close()
        except Exception as e:
            if self.debug:
                print(f"[PREQ-BROWSER] clickSurvey failed: {e}")
            return {"aborted": True}

        # Wait for new tab
        time.sleep(3)

        # Find pre-qualifier tab
        preq_tab = None
        for attempt in range(10):
            for p in chrome.find_bot_tabs(self.cdp_port):
                url = p.get("url", "")
                if "click.cpx" in url or "cpx" in url.lower():
                    preq_tab = p
                    break
            if preq_tab:
                break
            time.sleep(1)

        if not preq_tab:
            return {"aborted": True}

        tab_ws = preq_tab.get("webSocketDebuggerUrl")
        tab_id = preq_tab.get("id")

        if self.debug:
            print(f"[PREQ-BROWSER] Tab opened: {preq_tab.get('url','')[:60]}")

        # Answer pre-qualifier questions
        max_steps = 8
        for step in range(max_steps):
            time.sleep(2)

            # Check redirect to actual survey
            try:
                ws2 = websocket.create_connection(tab_ws, timeout=8)
                ws2.send(
                    json.dumps(
                        {
                            "id": 0,
                            "method": "Runtime.evaluate",
                            "params": {"expression": "window.location.href"},
                        }
                    )
                )
                r = json.loads(ws2.recv())
                current_url = (
                    r.get("result", {}).get("result", {}).get("value", "")
                )
                ws2.close()

                if (
                    current_url
                    and "click.cpx" not in current_url
                    and current_url != preq_tab.get("url", "")
                ):
                    if current_url.startswith("http"):
                        if tab_closer:
                            tab_closer(tab_id)
                        return {"redirect_url": current_url}
            except Exception:
                pass

            # Read page text
            page_text = BatchExecutor.read_page_text(tab_ws, 1000)
            if not page_text.strip():
                time.sleep(2)
                page_text = BatchExecutor.read_page_text(tab_ws, 1000)
            if not page_text.strip():
                continue

            # Find and click answer
            answer_clicked = self._click_first_answer(tab_ws)
            if not answer_clicked:
                if self.debug:
                    print(f"[PREQ-BROWSER] Step {step}: No answer elements")
                time.sleep(2)
                continue

            if self.debug:
                print(f"[PREQ-BROWSER] Step {step}: {answer_clicked}")

            # Click submit
            coords = self._find_submit_coords(tab_ws)
            if coords and coords != (0, 0):
                self._dispatch_mouse_click(tab_ws, coords)
                if self.debug:
                    print(f"[PREQ-BROWSER] Clicked submit!")

        # Max steps reached
        if tab_closer:
            tab_closer(tab_id)
        return {"aborted": True}

    # ── Internal helpers ────────────────────────────────────────

    @staticmethod
    def _click_first_answer(tab_ws: str) -> Optional[str]:
        """Click first non-'cannot answer' radio option. Returns selection text."""
        if not websocket:
            return None
        try:
            ws = websocket.create_connection(tab_ws, timeout=8)
            ws.send(
                json.dumps(
                    {
                        "id": 0,
                        "method": "Runtime.evaluate",
                        "params": {
                            "expression": """(function(){
    var els = document.querySelectorAll('input[type=radio]');
    if(els.length === 0) els = document.querySelectorAll('[role=radio]');
    for(var i=0;i<els.length;i++){
        var el = els[i];
        var label = el.closest('label') || el.parentElement;
        var text = (label ? label.textContent : el.value || '').trim();
        if(text && !text.includes('nicht beantworten') && !text.includes('cannot answer')){
            el.click();
            return 'selected:' + text.slice(0,40);
        }
    }
    if(els.length > 0){ els[0].click(); return 'fallback:first'; }
    return 'no answers';
})();"""
                        },
                    }
                )
            )
            r = json.loads(ws.recv())
            ws.close()
            return r.get("result", {}).get("result", {}).get("value", "")
        except Exception:
            return None

    @staticmethod
    def _find_submit_coords(tab_ws: str) -> tuple:
        """Find submit button coordinates for mouse dispatch."""
        if not websocket:
            return (0, 0)
        try:
            ws = websocket.create_connection(tab_ws, timeout=8)
            ws.send(
                json.dumps(
                    {
                        "id": 0,
                        "method": "Runtime.evaluate",
                        "params": {
                            "expression": """(function(){
    var btn = document.querySelector('button[type=submit],input[type=submit],.submit-btn,[onclick*="submit"],button:not([disabled])');
    if(btn){ var r=btn.getBoundingClientRect(); return r.x+r.width/2+','+(r.y+r.height/2); }
    return '0,0';
})();"""
                        },
                    }
                )
            )
            r = json.loads(ws.recv())
            ws.close()
            coords = r.get("result", {}).get("result", {}).get("value", "0,0")
            x, y = map(float, coords.split(","))
            return (x, y)
        except Exception:
            return (0, 0)

    @staticmethod
    def _dispatch_mouse_click(tab_ws: str, coords: tuple) -> None:
        """Dispatch CDP mouse events at coordinates."""
        if not websocket or coords == (0, 0):
            return
        x, y = coords
        for et in ["mouseMoved", "mousePressed", "mouseReleased"]:
            try:
                ws = websocket.create_connection(tab_ws, timeout=8)
                ws.send(
                    json.dumps(
                        {
                            "id": 0,
                            "method": "Input.dispatchMouseEvent",
                            "params": {
                                "type": et,
                                "x": x,
                                "y": y,
                                "button": "left",
                                "clickCount": 1,
                            },
                        }
                    )
                )
                json.loads(ws.recv())
                ws.close()
            except Exception:
                pass
