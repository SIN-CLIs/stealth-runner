"""NEMO Survey Runner — the core execution engine.

Loop per page:
  1. Compact Snapshot (CDP)
  2. NIM Decision (Nemotron 3 Omni)
  3. Batch Execute (CDP)
  4. AutoDoc (append-only)
  5. Repeat until completion
"""

import json
import time
import urllib.request
import urllib.parse
import websocket
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from . import chrome
from .snapshot import generate_snapshot, detect_completion, CompactSnapshot
from .nim import NIMClient, get_nim
from .execute import BatchExecutor
from .autodoc import log_earnings, log_error, log_session, log_decision
from .scanner import scan_dashboard, read_balance


@dataclass
class SurveyResult:
    survey_id: str = ""
    provider: str = "unknown"
    status: str = "unknown"  # completed, screen_out, error, blocked
    earned: float = 0.0
    iterations: int = 0
    elapsed_s: float = 0.0
    nim_calls: int = 0
    nim_tokens: int = 0
    error: Optional[str] = None


@dataclass
class RunnerConfig:
    cdp_port: int = 9999
    max_iterations: int = 50
    max_surveys: int = 10
    wait_after_action: float = 3.0
    wait_page_load: float = 5.0
    use_nim: bool = True
    auto_rate: bool = True
    rate_url: str = "https://www.heypiggy.com/?page=dashboard"
    balance_target: float = 5.0
    skip_providers: List[str] = field(default_factory=lambda: [
        "surveyrouter", "gfk"
    ])
    debug: bool = False


class SurveyRunner:
    """NEMO survey execution engine."""

    def __init__(self, config: Optional[RunnerConfig] = None):
        self.config = config or RunnerConfig()
        self.nim = get_nim() if self.config.use_nim else None
        self.profile = self._load_profile()
        self.learnings: List[str] = []
        self.history: List[Dict] = []

    def run_survey(self, survey_id: str,
                   survey_url: Optional[str] = None) -> SurveyResult:
        """Run a single survey from ID to completion.

        Args:
            survey_id: CPX survey ID
            survey_url: Optional direct URL (skip API)

        Returns:
            SurveyResult with status and earnings
        """
        result = SurveyResult(survey_id=survey_id)
        start_time = time.monotonic()

        # 0. Connect to dashboard + CLEAN ZOMBIE TABS
        dashboard_ws = chrome.find_dashboard_ws(self.config.cdp_port)
        if not dashboard_ws:
            result.error = "No dashboard WebSocket found"
            result.status = "error"
            log_error("run_survey", result.error, survey_id)
            return result

        # Clean all non-dashboard tabs (zombie prevention)
        tabs_before = len(chrome.find_bot_tabs(self.config.cdp_port))
        for p in chrome.find_bot_tabs(self.config.cdp_port):
            if p.get("url") and "dashboard" not in p.get("url", "").lower():
                try:
                    import websocket as ws_lib
                    w = ws_lib.create_connection(p["webSocketDebuggerUrl"], timeout=8)
                    w.send(json.dumps({"id":1,"method":"Target.closeTarget",
                                       "params":{"targetId": p["id"]}}))
                    json.loads(w.recv())
                    w.close()
                except Exception:
                    pass
        tabs_after = len(chrome.find_bot_tabs(self.config.cdp_port))
        if tabs_before != tabs_after and self.config.debug:
            print(f"[RUN] Cleaned {tabs_before - tabs_after} zombie tabs")

        # 1. Get survey URL
        if not survey_url:
            # Check if it's a pre-qualifier
            details = chrome.get_survey_details(survey_id)
            if details.get("type") == "question":
                if self.config.debug:
                    print(f"[RUN] Pre-qualifier detected: {details.get('question','?')[:60]}")
                survey_url = self.handle_pre_qualifier(survey_id, details)
                if not survey_url:
                    result.error = "Pre-qualifier failed"
                    result.status = "screen_out"
                    log_earnings(survey_id, "pre_qualifier", 0, "screen_out", 0)
                    return result
            else:
                survey_url = details.get("href")

            if not survey_url:
                # No survey URL from API — try browser-based pre-qualifier
                if self.config.debug:
                    print(f"[RUN] No href from API for {survey_id} — trying browser pre-qualifier")
                preq_result = self._handle_pre_qualifier_browser(survey_id)
                if preq_result.get("redirect_url"):
                    survey_url = preq_result["redirect_url"]
                    if self.config.debug:
                        print(f"[RUN] Browser pre-qualifier → {survey_url[:60]}")
                else:
                    result.status = "screen_out"
                    result.error = "No survey URL (pre-qualifier failed or not available)"
                    log_earnings(survey_id, "pre_qualifier", 0, "screen_out", 0)
                    return result

        provider = self._detect_provider(survey_url)
        result.provider = provider

        # 1b. Check blocked providers
        if provider in self.config.skip_providers:
            result.status = "blocked"
            result.error = f"Blocked provider: {provider}"
            log_earnings(survey_id, provider, 0, "blocked", 0)
            return result

        # 1c. Unknown provider → use generic fallback (tries all click patterns)
        if provider == "unknown":
            provider = "generic"
            result.provider = "generic"
            if self.config.debug:
                print(f"[RUN] Unknown provider — using generic fallback commands")

        if self.config.debug:
            print(f"[RUN] {survey_id} → {provider} (CPX: {survey_url[:60]})")

        # 2. Open survey in new tab
        tab_id = self._create_tab(dashboard_ws, survey_url)
        if not tab_id:
            result.error = "Failed to create browser tab"
            result.status = "error"
            return result

        # 3. Wait for CPX redirect + handle redirect page + detect REAL provider
        # Fast-fail: if page is still loading after timeout, skip
        tab_ws, actual_url = self._find_survey_tab_ws(tab_id)
        
        # Check for stuck loading pages
        if tab_ws:
            page_text = BatchExecutor.read_page_text(tab_ws, 500).lower()
            if any(s in page_text for s in ["loading", "just getting things ready", "won't be long"]):
                if self.config.debug:
                    print("[RUN] Stuck on loading page — skipping")
                self._close_tab(tab_id)
                result.status = "screen_out"
                result.error = "Survey stuck on loading page"
                log_earnings(survey_id, "unknown", 0, "screen_out", 0)
                return result
        
        time.sleep(self.config.wait_page_load)
        
        # Handle CPX redirect page (if stuck on "Sie werden umgeleitet")
        tab_ws, actual_url = self._find_survey_tab_ws(tab_id)
        if tab_ws:
            page_text = BatchExecutor.read_page_text(tab_ws, 500)
            # Detect expired CPX URL ("No app id was specified")
            if "no app id" in page_text.lower() or "survey not available" in page_text.lower():
                if self.config.debug:
                    print("[RUN] CPX URL expired or survey not available — skipping")
                self._close_tab(tab_id)
                result.status = "screen_out"
                result.error = "CPX survey not available (expired/removed)"
                log_earnings(survey_id, "unknown", 0, "screen_out", 0)
                return result
            page_text = BatchExecutor.read_page_text(tab_ws, 500)
            if "umgeleitet" in page_text.lower() or "redirect" in page_text.lower():
                if self.config.debug:
                    print("[RUN] CPX redirect page — clicking link...")
                self._click_redirect_link(tab_ws)
                time.sleep(self.config.wait_page_load)
                tab_ws, actual_url = self._find_survey_tab_ws(tab_id)

        if not tab_ws:
            result.status = "screen_out"
            result.error = "Survey tab not found after redirect (screen-out?)"
            log_earnings(survey_id, "unknown", 0, "screen_out", 0)
            return result

        # Detect real provider from actual URL (not CPX URL)
        real_provider = self._detect_provider(actual_url) if actual_url else provider
        if real_provider != provider and real_provider != "unknown":
            result.provider = real_provider
            provider = real_provider
            if self.config.debug:
                print(f"[RUN] Real provider: {provider} ({actual_url[:60]})")

        # 4. Handle PureSpectrum captcha preflight (if applicable)
        if provider == "purespectrum" and tab_ws:
            captcha_result = self._handle_purespectrum_preflight(tab_ws, survey_id)
            if not captcha_result.get("success"):
                result.status = "blocked"
                result.error = f"PureSpectrum captcha: {captcha_result.get('error', 'unknown')}"
                log_earnings(survey_id, provider, 0, "blocked", 0,
                            {"captcha_error": captcha_result.get("error")})
                self._close_tab(tab_id)
                return result
            # Captcha solved, wait for page transition
            time.sleep(self.config.wait_page_load)
            # Refresh tab WS
            tab_info = chrome.get_ws_for_tab(tab_id, self.config.cdp_port)
            if tab_info:
                tab_ws = tab_info

        # 5. NEMO Loop — with Circuit Breaker + Tab Re-Discovery
        nim_calls = 0
        balance_before = read_balance(self.config.cdp_port)
        consecutive_fails = 0
        max_consecutive_fails = 5  # Circuit breaker: stop after 5 fails
        prev_page_hash = ""  # Detect infinite loops (same page every time)
        loop_detection_threshold = 4  # Stop if same page 4× in a row

        for iteration in range(self.config.max_iterations):
            result.iterations = iteration + 1

            try:
                # 5a. Tab re-discovery: WS may be stale after navigation
                tab_ws_current = self._refresh_tab_ws(tab_id)
                if not tab_ws_current:
                    result.error = "Tab disappeared (screen-out or redirect)"
                    result.status = "screen_out"
                    break
                tab_ws = tab_ws_current

                # 5b. Compact snapshot
                snapshot = generate_snapshot(tab_ws)

                if self.config.debug and iteration % 5 == 0:
                    print(f"  [iter {iteration}] {snapshot.provider} "
                          f"({len(snapshot.refs)} el)")

                # 5c. Loop detection: same page content 4× = stuck
                # CompactSnapshot has refs + semantic, NOT .text
                ref_keys = list(snapshot.refs.keys())[:5]
                page_hash = hash(str(ref_keys)) if ref_keys else hash(snapshot.url)
                if page_hash == prev_page_hash:
                    consecutive_fails += 1
                    if consecutive_fails >= loop_detection_threshold:
                        result.error = f"Stuck on same page ({loop_detection_threshold}×)"
                        result.status = "error"
                        break
                else:
                    consecutive_fails = 0
                    prev_page_hash = page_hash

                # 5d. Empty snapshot: page not loaded — skip iteration
                if len(snapshot.refs) == 0:
                    time.sleep(self.config.wait_page_load)
                    continue

                # 5e. Check completion
                if detect_completion(snapshot.url + " " + snapshot.title) or \
                   self._detect_completion_text(tab_ws):
                    result.status = "completed"
                    break

                # 5f. NIM decision (with retry on empty actions)
                if self.nim and self.config.use_nim:
                    decision = self.nim.decide(
                        snapshot.to_dict(), self.profile,
                        self.learnings, self.history
                    )
                    actions = decision.get("actions", [])
                    nim_calls += 1
                    result.nim_calls = nim_calls
                    result.nim_tokens += decision.get("tokens", {}).get("total", 0)

                    # Retry NIM once if actions empty (first call might miss content)
                    if not actions and iteration < 3:
                        time.sleep(1)
                        decision = self.nim.decide(snapshot.to_dict(), self.profile,
                                                  self.learnings, self.history)
                        actions = decision.get("actions", [])
                else:
                    actions = self._simple_actions(snapshot, tab_ws)

                # 5g. Check for complete action
                if any(a.get("action") == "complete" for a in actions):
                    result.status = "completed"
                    break

                # 5h. Log decision
                log_decision(
                    len(snapshot.refs), actions, nim_calls,
                    decision.get("elapsed_ms", 0) if self.nim else 0,
                    survey_id, provider
                )

                # 5i. Execute batch with circuit breaker
                executor = BatchExecutor(tab_ws, provider)
                batch_result = executor.execute(actions)

                # Circuit breaker: 3+ failed actions in batch = abort
                if batch_result.total_fail >= 3:
                    consecutive_fails += 2
                    if self.config.debug:
                        print(f"  [iter {iteration}] Circuit breaker: {batch_result.total_fail} fails")
                    if consecutive_fails >= max_consecutive_fails:
                        result.error = f"Circuit breaker triggered ({batch_result.total_fail} fail, {consecutive_fails} streak)"
                        result.status = "blocked"
                        break

                # 5j. Record history
                self.history.append({
                    "iteration": iteration,
                    "actions": len(actions),
                    "success": batch_result.total_success,
                    "fail": batch_result.total_fail,
                    "page_hash": page_hash,
                })

                # 5k. Wait for page transition
                time.sleep(self.config.wait_after_action)

            except Exception as e:
                if self.config.debug:
                    print(f"  [iter {iteration}] Error: {e}")
                consecutive_fails += 1
                if consecutive_fails >= max_consecutive_fails:
                    result.error = f"Circuit breaker: {str(e)[:100]}"
                    result.status = "blocked"
                    break
                result.error = str(e)[:200]
                result.status = "error"
                log_error("run_survey", e, survey_id, provider,
                          {"iteration": iteration})
                # Continue loop but increment fail counter
                time.sleep(1)

        # 6. Close tab
        self._close_tab(tab_id)

        # 7. Rate survey
        if result.status == "completed" and self.config.auto_rate:
            self._rate_survey()

        # 8. Calculate earnings
        time.sleep(2)
        balance_after = read_balance(self.config.cdp_port)
        result.earned = round(balance_after - balance_before, 2)
        result.elapsed_s = round(time.monotonic() - start_time, 1)

        # 9. Log earnings
        log_earnings(survey_id, provider, result.earned, result.status,
                     result.elapsed_s, {"iterations": result.iterations})

        if self.config.debug:
            print(f"[RESULT] {survey_id}: {result.status} +{result.earned}€ "
                  f"in {result.elapsed_s}s")

        return result

    def run_loop(self, max_surveys: Optional[int] = None) -> List[SurveyResult]:
        """Auto-loop: scan → filter → run → repeat.

        Args:
            max_surveys: Max surveys to run (overrides config)

        Returns:
            List of SurveyResults
        """
        if max_surveys:
            self.config.max_surveys = max_surveys

        results = []

        # Scan dashboard
        viable = scan_dashboard(
            port=self.config.cdp_port,
            skip_providers=self.config.skip_providers
        )

        if not viable:
            print("[LOOP] No viable surveys found")
            return results

        for i, survey in enumerate(viable):
            if i >= self.config.max_surveys:
                break

            # Prioritize OK surveys over pre-qualifiers (pre-qualifiers require
            # browser-based answering which is complex — skip for now)
            if survey.get("provider") == "pre_qualifier":
                if self.config.debug:
                    print(f"[LOOP] Skipping pre-qualifier {survey['id']} (browser-based)")
                continue

            # Check balance target
            balance = read_balance(self.config.cdp_port)
            if balance >= self.config.balance_target:
                print(f"[LOOP] Balance target reached: {balance}€")
                # Trigger cash-out flow
                self._trigger_cash_out()
                break

            sid = survey["id"]
            href = survey.get("href", "")
            print(f"\n[{i+1}/{min(len(viable), self.config.max_surveys)}] "
                  f"Survey: {sid} ({survey['provider']})")

            result = self.run_survey(sid, survey_url=href)
            results.append(result)

            if result.status == "completed":
                print(f"  ✅ +{result.earned}€ ({result.provider}, "
                      f"{result.elapsed_s}s)")
            elif result.status == "blocked":
                print(f"  ⛔ Blocked: {result.error}")
            else:
                print(f"  ❌ {result.status}: {result.error}")

        # Summary
        total = sum(r.earned for r in results if r.earned > 0)
        complete = sum(1 for r in results if r.status == "completed")
        print(f"\n{'='*50}")
        print(f"  LOOP COMPLETE: {complete}/{len(results)} surveys")
        print(f"  +{total}€ earned")
        print(f"{'='*50}\n")

        log_session("loop", "ok", {
            "surveys_run": len(results),
            "completed": complete,
            "earned": total,
        })

        return results

    # ── Private ─────────────────────────────────────

    def _create_tab(self, dashboard_ws, url):
        """Create a new browser tab via CDP Target.createTarget."""
        return chrome.create_tab(url, self.config.cdp_port)

    def _click_redirect_link(self, tab_ws):
        """Click the 'hier klicken' link on CPX redirect page."""
        try:
            ws = websocket.create_connection(tab_ws, timeout=10)
            ws.send(json.dumps({
                "id": 0, "method": "Runtime.evaluate",
                "params": {"expression": '''
(function() {
    var links = document.querySelectorAll("a");
    for (var i=0;i<links.length;i++) {
        if ((links[i].textContent||"").includes("hier klicken")) {
            links[i].click(); return "clicked";
        }
    }
    // Fallback: any link
    if (links.length > 0) { links[0].click(); return "fallback_click"; }
    return "no_link";
})()
                '''
            }}))
            json.loads(ws.recv())
            ws.close()
        except Exception:
            pass

    def _find_survey_tab_ws(self, tab_id):
        """Find WebSocket URL for the actual survey tab after CPX redirect.
        
        CPX URLs redirect through multiple hops. The original tab_id
        may have been replaced or a new tab opened. Find the real
        survey tab (not dashboard, not about:blank).
        
        Returns:
            (ws_url, page_url) tuple or (None, None)
        """
        # 1. Try the original tab first
        tab_info = chrome.get_ws_for_tab(tab_id, self.config.cdp_port)
        if tab_info:
            # Check if it's still the CPX redirect or has landed on a survey
            try:
                import websocket as ws_lib
                ws = ws_lib.create_connection(tab_info, timeout=8)
                ws.send(json.dumps({
                    "id": 0, "method": "Runtime.evaluate",
                    "params": {"expression": "document.location.href", "returnByValue": True}
                }))
                r = json.loads(ws.recv())
                ws.close()
                url = r.get("result", {}).get("result", {}).get("value", "")
                if url and "click.cpx" not in url and "dashboard" not in url:
                    return tab_info, url
            except Exception:
                pass
        
        # 2. Fallback: find any non-dashboard, non-blank tab
        for p in chrome.find_bot_tabs(self.config.cdp_port):
            url = p.get("url", "")
            if url and "dashboard" not in url and "about:blank" not in url:
                return p.get("webSocketDebuggerUrl"), url
        
        return None, None

    def _close_tab(self, tab_id):
        """Close a browser tab. Tolerates already-closed tabs."""
        try:
            # Try using the original tab's WS to close it
            for p in chrome.find_bot_tabs(self.config.cdp_port):
                if p.get("id") == tab_id:
                    ws = websocket.create_connection(p["webSocketDebuggerUrl"], timeout=10)
                    ws.send(json.dumps({
                        "id": 1, "method": "Target.closeTarget",
                        "params": {"targetId": tab_id}
                    }))
                    json.loads(ws.recv())
                    ws.close()
                    return
            # If not found, try closing via dashboard WS
            dash_ws = chrome.find_dashboard_ws(self.config.cdp_port)
            if dash_ws:
                ws = websocket.create_connection(dash_ws, timeout=10)
                ws.send(json.dumps({
                    "id": 1, "method": "Target.closeTarget",
                    "params": {"targetId": tab_id}
                }))
                json.loads(ws.recv())
                ws.close()
        except Exception:
            pass  # Tab already closed — that's fine

    def _refresh_tab_ws(self, tab_id):
        """Re-discover WebSocket URL for tab after navigation.

        After executing actions, the tab may have navigated to a new page
        or been replaced. Re-find the WS URL to prevent stale WS errors.

        Returns:
            Fresh WS URL or None if tab is gone (screen-out)
        """
        # Try original tab first
        tab_info = chrome.get_ws_for_tab(tab_id, self.config.cdp_port)
        if tab_info:
            try:
                import websocket as ws_lib
                ws = ws_lib.create_connection(tab_info, timeout=5)
                ws.send(json.dumps({
                    "id": 0, "method": "Runtime.evaluate",
                    "params": {"expression": "document.location.href"}
                }))
                json.loads(ws.recv())
                ws.close()
                return tab_info  # Tab still alive
            except Exception:
                pass  # Tab WS stale — search all tabs

        # Fallback: find any non-dashboard tab with matching URL pattern
        for p in chrome.find_bot_tabs(self.config.cdp_port):
            url = p.get("url", "")
            if url and "dashboard" not in url and "about:blank" not in url:
                # Verify it's still accessible
                try:
                    ws = websocket.create_connection(p["webSocketDebuggerUrl"], timeout=5)
                    ws.send(json.dumps({
                        "id": 0, "method": "Runtime.evaluate",
                        "params": {"expression": "document.readyState"}
                    }))
                    json.loads(ws.recv())
                    ws.close()
                    return p["webSocketDebuggerUrl"]
                except Exception:
                    continue

        return None  # Tab is gone (screen-out closed it)

    def _detect_provider(self, url):
        """Detect provider from URL."""
        from .scanner import detect_provider
        return detect_provider(url)

    def _handle_pre_qualifier_browser(self, survey_id):
        """Handle CPX pre-qualifier in browser. Answer via CDP → wait for redirect.

        Returns:
            {"redirect_url": "..."} on success
            {"aborted": True} on failure
        """
        from .chrome import create_tab, find_bot_tabs

        # Build CPX click URL using dashboard context
        dash_ws = chrome.find_dashboard_ws(self.config.cdp_port)
        if not dash_ws:
            return {"aborted": True}

        try:
            # Execute clickSurvey in browser context to get the survey tab
            ws = websocket.create_connection(dash_ws, timeout=10)
            ws.send(json.dumps({
                "id": 0, "method": "Runtime.evaluate",
                "params": {"expression": f"clickSurvey('{survey_id}'); '';"}
            }))
            json.loads(ws.recv())
            ws.close()
        except Exception as e:
            if self.config.debug:
                print(f"[PREQ-BROWSER] clickSurvey failed: {e}")
            return {"aborted": True}

        # Wait for new tab to open
        time.sleep(3)

        # Find the pre-qualifier tab
        preq_tab = None
        for attempt in range(10):
            for p in find_bot_tabs(self.config.cdp_port):
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

        if self.config.debug:
            print(f"[PREQ-BROWSER] Tab opened: {preq_tab.get('url','')[:60]}")

        # Loop: answer pre-qualifier questions until redirect
        max_steps = 8
        for step in range(max_steps):
            time.sleep(2)

            # Check if we've been redirected to actual survey
            try:
                ws2 = websocket.create_connection(tab_ws, timeout=8)
                ws2.send(json.dumps({
                    "id": 0, "method": "Runtime.evaluate",
                    "params": {"expression": "window.location.href"}
                }))
                r = json.loads(ws2.recv())
                current_url = r.get("result", {}).get("result", {}).get("value", "")
                ws2.close()

                # Check if redirected to non-CPX URL
                if current_url and "click.cpx" not in current_url and current_url != preq_tab.get("url", ""):
                    # Redirected! Close pre-qualifier tab, return survey URL
                    if current_url.startswith("http"):
                        self._close_tab(tab_id)
                        return {"redirect_url": current_url}

            except Exception:
                pass

            # Read current page text
            page_text = BatchExecutor.read_page_text(tab_ws, 1000)

            if not page_text.strip():
                time.sleep(2)
                page_text = BatchExecutor.read_page_text(tab_ws, 1000)

            if not page_text.strip():
                continue  # Page not loaded yet

            # Find radio buttons (pre-qualifier answers)
            ws3 = websocket.create_connection(tab_ws, timeout=8)
            ws3.send(json.dumps({
                "id": 0, "method": "Runtime.evaluate",
                "params": {"expression": """
(function(){
    // Try multiple answer element types
    var selectors = [
        'input[type=radio]',           // standard radio
        '[role=radio]',                // ARIA radio
        '.answer-option',              // custom class
        '.survey-option',              // custom class
        '.cp-answer'                   // CPX specific
    ];
    var results = {};
    selectors.forEach(function(sel){
        var els = document.querySelectorAll(sel);
        if(els.length > 0){
            results[sel] = els.length;
        }
    });
    return JSON.stringify(results);
})();
"""
                }
            }))
            r = json.loads(ws3.recv())
            answer_types = json.loads(r.get("result", {}).get("result", {}).get("value", "{}"))
            ws3.close()

            if not answer_types:
                if self.config.debug:
                    print(f"[PREQ-BROWSER] Step {step}: No answer elements found")
                time.sleep(2)
                continue

            # Select first non-"cannot answer" answer
            ws4 = websocket.create_connection(tab_ws, timeout=8)
            ws4.send(json.dumps({
                "id": 0, "method": "Runtime.evaluate",
                "params": {"expression": """
(function(){
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
    // Fallback: select first
    if(els.length > 0){ els[0].click(); return 'fallback:first'; }
    return 'no answers';
})();
"""
                }
            }))
            r = json.loads(ws4.recv())
            selected = r.get("result", {}).get("result", {}).get("value", "")
            ws4.close()

            if self.config.debug:
                print(f"[PREQ-BROWSER] Step {step}: {selected}")

            if "selected" in selected or "fallback" in selected:
                time.sleep(1)
                # Click submit button
                ws5 = websocket.create_connection(tab_ws, timeout=8)
                ws5.send(json.dumps({
                    "id": 0, "method": "Runtime.evaluate",
                    "params": {"expression": """
(function(){
    var btn = document.querySelector('button[type=submit],input[type=submit],.submit-btn,[onclick*="submit"],button:not([disabled])');
    if(btn){ var r=btn.getBoundingClientRect(); return r.x+r.width/2+','+(r.y+r.height/2); }
    return '0,0';
})();
"""
                    }
                }))
                r = json.loads(ws5.recv())
                coords = r.get("result", {}).get("result", {}).get("value", "0,0")
                x, y = map(float, coords.split(","))
                ws5.close()

                if x > 0:
                    for et in ["mouseMoved", "mousePressed", "mouseReleased"]:
                        ws6 = websocket.create_connection(tab_ws, timeout=8)
                        ws6.send(json.dumps({"id": 0, "method": "Input.dispatchMouseEvent",
                            "params": {"type": et, "x": x, "y": y, "button": "left", "clickCount": 1}}))
                        json.loads(ws6.recv())
                        ws6.close()
                    if self.config.debug:
                        print(f"[PREQ-BROWSER] Clicked submit!")

        # Max steps reached
        self._close_tab(tab_id)
        return {"aborted": True}

    def _trigger_cash_out(self):
        """Navigate to cash-out page when balance target is reached.

        Uses cua-driver to click Auszahlung sidebar item (the one in the
        main modal, not the mobile tab bar). Finds the correct element
        via cua-driver list_windows → get_window_state → depth>5 filter.
        """
        try:
            # Use cua-driver to click Auszahlung in sidebar
            import subprocess, json as json_mod

            # Get window
            result = subprocess.run(
                ["cua-driver", "call", "list_windows"],
                capture_output=True, text=True, timeout=10
            )
            windows = json_mod.loads(result.stdout)
            hp_window = next(
                (w for w in windows.get("windows", []) if "HeyPiggy" in w.get("title", "")),
                None
            )
            if not hp_window:
                print("[CASH] HeyPiggy window not found")
                return

            pid = hp_window["pid"]
            wid = hp_window["window_id"]

            # Get AX tree and find "Auszahlung" element
            result = subprocess.run(
                ["cua-driver", "call", "get_window_state"],
                input=json_mod.dumps({"pid": pid, "window_id": wid}).encode(),
                capture_output=True, text=True, timeout=15
            )
            state = json_mod.loads(result.stdout)

            # Find Auszahlung link in sidebar (depth > 5 for content)
            # Look for AXLink with text "Auszahlung" in sidebar
            import re
            tree = state.get("tree_markdown", "")
            lines = tree.split("\n")
            idx = None
            for i, line in enumerate(lines):
                if re.search(r'\[(\d+)\].*Auszahlung', line):
                    m = re.search(r'\[(\d+)\]', line)
                    if m:
                        idx = int(m.group(1))
                        break

            if idx is not None:
                result = subprocess.run(
                    ["cua-driver", "call", "click"],
                    input=json_mod.dumps({"pid": pid, "window_id": wid,
                                         "element_index": idx}).encode(),
                    capture_output=True, text=True, timeout=15
                )
                print(f"[CASH] Clicked Auszahlung sidebar: {result.stdout[:100]}")
                log_session("cash_out", "triggered", {"balance_target": self.config.balance_target})
            else:
                print("[CASH] Auszahlung element not found in AX tree")

        except Exception as e:
            print(f"[CASH] Cash-out trigger failed: {e}")

    def _detect_completion_text(self, ws_url):
        """Check page text for completion markers."""
        text = BatchExecutor.read_page_text(ws_url)
        return detect_completion(text)

    def _handle_purespectrum_preflight(self, tab_ws, survey_id):
        """Handle PureSpectrum pre-survey flow: cookie + ROBOT + captcha + puzzle."""
        from survey.providers.purespectrum import solve_purespectrum_preflight
        return solve_purespectrum_preflight(tab_ws, debug=self.config.debug)

    def _rate_survey(self):
        """Rate completed survey for +0.01€ bonus."""
        try:
            pages = chrome.find_bot_tabs(self.config.cdp_port)
            for p in pages:
                url = p.get("url", "")
                if "rating.php" in url.lower() or "cpx-research" in url.lower():
                    ws_url = p.get("webSocketDebuggerUrl")
                    if ws_url:
                        ws = websocket.create_connection(ws_url, timeout=15)
                        ws.send(json.dumps({
                            "id": 0, "method": "Runtime.evaluate",
                            "params": {
                                "expression":
                                    'document.querySelector("button,.btn-blue,input[type=button]")'
                                    '.click()'
                            }
                        }))
                        json.loads(ws.recv())
                        ws.close()
                        time.sleep(2)
                        break
        except Exception:
            pass

    def _simple_actions(self, snapshot, tab_ws=None):
        """Simple auto-pilot when NIM not available. Smart selection + verify.

        Strategy:
        1. Find first unchecked radio → select it
        2. Find enabled submit button → click it
        3. Fallback: fill first textarea with plausible persona answer
        """
        actions = []

        # 1. Select first unchecked radio/checkbox
        for ref, info in snapshot.refs.items():
            role = info.get("role", "")
            if role in ("radio", "checkbox") and info.get("enabled", True):
                text = info.get("text", "").lower()
                # Prefer common persona answers
                preferred = ["berlin", "männlich", "weiblich", "deutsch",
                            "angestellt", "verheiratet", "mittlere", "master"]
                if any(p in text for p in preferred):
                    actions.append({"ref": ref, "action": "select"})
                    break
        else:
            # No preferred answer found — select first available
            for ref, info in snapshot.refs.items():
                if info.get("role") in ("radio", "checkbox") and info.get("enabled", True):
                    actions.append({"ref": ref, "action": "select"})
                    break

        # 2. Find enabled submit/next button
        for ref, info in snapshot.refs.items():
            if info.get("role") == "button":
                text = info.get("text", "").lower()
                enabled = info.get("enabled", True)
                if enabled and any(kw in text for kw in
                    ["weiter", "next", "submit", "nächste", "submit", "forward", "fortfahren"]):
                    actions.append({"action": "submit"})
                    break
        else:
            # No submit button found — check for textarea (open-ended question)
            for ref, info in snapshot.refs.items():
                if info.get("role") == "textbox":
                    # Fill with short plausible answer
                    placeholder = info.get("placeholder", "").lower()
                    if "gemüse" in placeholder or "hobby" in placeholder:
                        actions.append({"ref": ref, "action": "fill",
                                        "value": "Karotten werden von vielen Menschen gegessen, weil sie gesund und vielseitig sind."})
                    elif "beschreiben" in placeholder:
                        actions.append({"ref": ref, "action": "fill",
                                        "value": "Ich finde das Thema interessant und nehme gerne an Umfragen teil."})
                    else:
                        actions.append({"ref": ref, "action": "fill",
                                        "value": "Ja"})
                    break

        # Safety cap: never return more than 2 actions
        return actions[:2]

    def _load_profile(self):
        """Load profile from JSON file or fallback. Calculates age dynamically."""
        import os
        from datetime import date
        paths = [
            os.path.join(os.path.dirname(__file__), "profiles", "jeremy_schulze.json"),
            os.path.join(os.path.dirname(os.path.dirname(__file__)),
                         "config", "profiles", "jeremy_schulze.json"),
        ]
        profile = None
        for path in paths:
            if os.path.exists(path):
                try:
                    profile = json.loads(open(path).read())
                    break
                except Exception:
                    pass

        if not profile:
            profile = {
                "name": "Jeremy Schulze",
                "date_of_birth": "1993-11-13",
                "gender": "male", "gender_label": "Männlich",
                "city": "Berlin", "state": "Berlin", "zip": "10785",
                "household_size": 3, "marital_status": "married",
                "education": "abitur", "employment": "employed_fulltime",
                "employment_label": "Angestellte",
                "household_income": "3000-4000", "personal_income": "1000-2000",
                "nationality": "Deutsch", "language": "Deutsch",
            }

        # Dynamically calculate age from date_of_birth
        if "date_of_birth" in profile and "age" not in profile:
            try:
                dob = profile["date_of_birth"]
                born = date.fromisoformat(dob)
                today = date.today()
                profile["age"] = today.year - born.year - (
                    (today.month, today.day) < (born.month, born.day)
                )
            except (ValueError, TypeError):
                profile["age"] = 32

        return profile

    def handle_pre_qualifier(self, survey_id, survey_details):
        """Answer pre-qualifier questions via CPX API. Handles MULTI-STEP qualifiers.

        CPX asks 1-N questions before routing to actual survey. Loop until
        we get type=okay with href, or hit max retries.

        API response format:
        {
            "type": "question" | "okay",
            "question_text": "...",    # for type=question
            "question_key": "cpxq_...",  # POST parameter name
            "answers": {key: {text, key}},  # DICT not list
            "message_button": "einreichen"
        }
        """
        from .chrome import get_details_url

        max_retries = 8
        details_url = get_details_url(self.config.cdp_port)
        current_details = survey_details

        for step in range(max_retries):
            question_text = current_details.get("question_text", "")
            question_key = current_details.get("question_key", "")
            answers_raw = current_details.get("answers", {})

            if not answers_raw or not question_key:
                if self.config.debug:
                    print(f"[PREQ] Step {step}: No answers/key — aborting")
                return None

            answer_keys = list(answers_raw.keys())
            profile = self.profile
            q_lower = question_text.lower()
            answer_idx = None

            # Match question to profile
            if any(kw in q_lower for kw in ["alter", "age", "alters"]):
                age = profile.get("age", 32)
                if age < 18: answer_idx = 0
                elif age < 25: answer_idx = 1
                elif age < 35: answer_idx = 2
                elif age < 45: answer_idx = 3
                elif age < 55: answer_idx = 4
                else: answer_idx = 5

            elif any(kw in q_lower for kw in ["geschlecht", "gender"]):
                answer_idx = 0 if profile.get("gender", "male") == "male" else 1

            elif any(kw in q_lower for kw in ["bundesland", "wohnort", "region", "stadt"]):
                for i, k in enumerate(answer_keys):
                    if "berlin" in answers_raw[k].get("text", "").lower():
                        answer_idx = i; break

            elif any(kw in q_lower for kw in ["einkommen", "income"]):
                answer_idx = 2  # middle bracket

            elif any(kw in q_lower for kw in ["bildung", "education", "schulabschluss"]):
                edu = profile.get("education", "abitur")
                for i, k in enumerate(answer_keys):
                    if edu in answers_raw[k].get("text", "").lower():
                        answer_idx = i; break

            elif any(kw in q_lower for kw in ["beschäftigung", "employment", "berufstätig"]):
                answer_idx = 1  # employed

            # Default: first non-"cannot answer" option
            if answer_idx is None:
                for i, k in enumerate(answer_keys):
                    if "nicht beantworten" not in answers_raw[k].get("text", "").lower():
                        answer_idx = i; break
                if answer_idx is None:
                    answer_idx = 0

            if answer_idx >= len(answer_keys):
                return None

            selected_key = answer_keys[answer_idx]
            selected_text = answers_raw[selected_key].get("text", "")

            if self.config.debug:
                print(f"[PREQ] Step {step}: Q={question_text[:50]}... → {selected_text[:50]}")

            # POST answer
            try:
                post_url = (details_url + "&survey_id=" + survey_id +
                            "&" + urllib.parse.quote(question_key) + "=" +
                            urllib.parse.quote(selected_key))
                resp_json = json.loads(urllib.request.urlopen(post_url, timeout=8).read())

                # Check if we got the real survey URL
                if resp_json.get("status") == "success" and resp_json.get("href"):
                    if self.config.debug:
                        print(f"[PREQ] ✅ Got survey URL: {resp_json['href'][:60]}")
                    return resp_json.get("href")

                # Check if more questions (type still "question")
                if resp_json.get("type") == "question":
                    current_details = resp_json
                    if self.config.debug:
                        print(f"[PREQ] → Next question, retrying...")
                    continue

                # Other response type
                if self.config.debug:
                    print(f"[PREQ] Step {step}: unexpected response type: {resp_json.get('type')}")
                return None

            except Exception as e:
                if self.config.debug:
                    print(f"[PREQ] Step {step} POST failed: {e}")
                return None

        if self.config.debug:
            print(f"[PREQ] Max retries ({max_retries}) exceeded")
        return None
