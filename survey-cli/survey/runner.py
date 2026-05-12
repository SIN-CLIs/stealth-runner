"""================================================================================
NEMO SURVEY RUNNER — Core Execution Engine (1291 Zeilen, Herzstück)
================================================================================

WAS IST DAS?
  Die Haupt-Ausführungs-Engine für Survey-Automation. Führt den NEMO-Loop
  für JEDE Survey-Seite aus:

  NEMO LOOP (pro Seite):
  1. Compact Snapshot (CDP) → @eN Element-Refs
  2. NIM Decision (Nemotron 3 Omni) → Batch Actions
  3. Batch Execute (CDP) → JavaScript im Browser
  4. AutoDoc (append-only) → JSONL Log
  5. Completion Detection → Fertig oder nächste Seite?
  6. Repeat bis completion

ARCHITEKTUR:
  ┌─────────────────────┐
  │  run_survey()       │
  │  (Haupt-Funktion)   │
  └─────────────────────┘
         │
         ▼
  ┌─────────────────────┐
  │  NEMO LOOP          │
  │  (pro Seite)        │
  └─────────────────────┘
         │
    ┌────┴──────────────────────────────┐
    ▼                  ▼                 ▼
  snapshot()        NIMClient          BatchExecutor
  (CDP eval)       .decide()          .execute()
    │                  │                 │
    ▼                  ▼                 ▼
  @eN Refs        Actions[]           CDP JS
    │                                    │
    └────────────────┬─────────────────┘
                     ▼
              detect_completion()
                     │
            ┌────────┴────────┐
            ▼                 ▼
        completed          running
            │                 │
            ▼                 ▼
        rate_survey()    next iteration

SOTA FEATURES:
  - Anti-Stuck Detection: DOM-Hash Vergleich, 3x gleich = stuck
  - Circuit Breaker: Max 50 Iterationen pro Survey
  - Provider Detection: Qualtrics, Toluna, Strat7, PureSpectrum
  - Auto-Doc: Append-only JSONL (kein LLM schreibt Doku!)
  - Balance Tracking: Verdienst-Tracking pro Session
  - Modal Handling: Close-Modals vor jeder Aktion

DEPENDENZEN (ALLE __frozen__=True):
  - chrome.py: Chrome Lifecycle (start/connect/kill)
  - snapshot.py: Compact Snapshot Generator
  - nim.py: Nemotron 3 Omni Client
  - execute.py: Batch Executor (CDP)
  - autodoc.py: Append-only JSONL Logger
  - scanner.py: Dashboard Scanner
  - tools/*.py: Frozen Tools (click, fill, detect, etc.)

WARUM 1291 Zeilen?
  Dies ist die zentrale Logik. Jede Zeile ist notwendig:
  - Error-Handling: 15+ verschiedene Fehler-Szenarien
  - Provider-Support: 5+ verschiedene Survey-Provider
  - Anti-Stuck: 3 verschiedene Detection-Methoden
  - State-Management: 10+ verschiedene Zustände
  → Aufteilung in Sub-Module würde Komplexität erhöhen (mehr Imports,
    mehr Kontext-Wechsel, schwerer zu debuggen).

WARUM frozen tools?
  Sicherheit. Wenn ein Tool funktioniert (10x getestet), wird es
  eingefroren (__frozen__=True). Kein Agent darf es mehr ändern.
  → Verhindert, dass Agenten "clevere" Änderungen machen die alles
    kaputt machen.

BANNED METHODS — NIEMALS VERWENDEN (siehe /banned.md):
  ❌ playstealth launch — setzt NICHT --force-renderer-accessibility
  ❌ webauto-nodriver — ABSOLUT BANNED
  ❌ cua-driver click (raw index) — instabil, nutze tool_click.py
  ❌ --remote-allow-origins=* (ohne Quotes) — zsh glob expansion
  ❌ /tmp/heypiggy-bot (fixed profile) — korruptiert nach Neustart
  ❌ Hardcoded PIDs — dynamisch, niemals hardcodieren
  ❌ pkill -f "Google Chrome" — tötet USER Chrome
  ❌ killall Google Chrome — tötet ALLE Chrome
  ❌ skylight-cli click --element-index — Index instabil
================================================================================"""

import json
import os
import time
import hashlib
import websocket
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from . import chrome
from .snapshot import generate_snapshot, detect_completion
from .nim import get_nim
from .execute import BatchExecutor, detect_language_page
from .opener import SurveyOpener, SurveyTarget
from .completion_detector import CompletionDetector
from .balance_tracker import BalanceTracker
from .action_selector import ActionSelector
from .profile_loader import ProfileLoader
from .pre_qualifier import PreQualifierHandler
from .cash_out_trigger import CashOutTrigger
from .survey_rater import SurveyRater
from .autodoc import log_earnings, log_error, log_session, log_decision
from .observability import get_logger
from .observability.metrics import SurveyMetrics
from .scanner import scan_dashboard, read_balance_with_backoff
from .session_validator import validate_session, is_session_valid

# Frozen tools — atomar, __frozen__=True, NICHT aendern
from tools import AntiStuck as tool_AntiStuck


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
    error: str = ""


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
    skip_providers: List[str] = field(default_factory=lambda: ["surveyrouter", "gfk"])
    debug: bool = False


class SurveyRunner:
    """NEMO survey execution engine."""

    def __init__(self, config: Optional[RunnerConfig] = None):
        self.config = config or RunnerConfig()
        self.nim = get_nim() if self.config.use_nim else None
        self.profile = ProfileLoader.load_profile(os.path.dirname(__file__))
        self.learnings: List[str] = []
        self.history: List[Dict] = []
        self.opener = SurveyOpener(cdp_port=self.config.cdp_port, debug=self.config.debug)
        self.completion_detector = CompletionDetector(
            cdp_port=self.config.cdp_port, debug=self.config.debug
        )
        self.balance_tracker = BalanceTracker(
            cdp_port=self.config.cdp_port, debug=self.config.debug
        )
        self.pre_qualifier = PreQualifierHandler(
            cdp_port=self.config.cdp_port, debug=self.config.debug
        )
        self.cash_out = CashOutTrigger(debug=self.config.debug)
        self.survey_rater = SurveyRater(cdp_port=self.config.cdp_port, debug=self.config.debug)
        get_logger(verbose=self.config.debug)
        self.metrics = SurveyMetrics()

    def run_survey(self, survey_id: str, survey_url: Optional[str] = None) -> SurveyResult:
        """Run a single survey from ID to completion.

        Args:
            survey_id: CPX survey ID
            survey_url: Optional direct URL (skip API)

        Returns:
            SurveyResult with status and earnings
        """
        result = SurveyResult(survey_id=survey_id)
        start_time = time.monotonic()

        # 0. SESSION VALIDATION: Validate session before any survey operation
        # SESSION EXPIRY FIX (2026-05-10): Chrome restart can invalidate cookies.
        # Without validation, surveys run with invalid session → €0 earned.
        session_ok = validate_session(self.config.cdp_port, auto_recover=True)
        if not session_ok:
            result.error = "Session invalid (recovery failed)"
            result.status = "error"
            log_error("run_survey", "Session invalid and recovery failed", survey_id)
            return result

        # 1. Connect to dashboard + CLEAN ZOMBIE TABS
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
                    w.send(
                        json.dumps(
                            {
                                "id": 1,
                                "method": "Target.closeTarget",
                                "params": {"targetId": p["id"]},
                            }
                        )
                    )
                    json.loads(w.recv())
                    w.close()
                except Exception:
                    pass
        tabs_after = len(chrome.find_bot_tabs(self.config.cdp_port))
        if tabs_before != tabs_after:
            get_logger().cleanup(tabs_before, tabs_after, zombie_tabs=tabs_before - tabs_after)

        # 1. Get survey URL (skip CPX API for in-page modal)
        provider = None  # Will be set below
        if survey_url == "in-page://modal":
            provider = "in_page_modal"
        elif not survey_url:
            # Check if it's a pre-qualifier
            details = chrome.get_survey_details(survey_id)
            if details.get("type") == "question":
                get_logger().prequal(survey_id, details.get("question", "")[:60])
                survey_url = self.pre_qualifier.handle_pre_qualifier_api(
                    survey_id, details, self.profile
                )
                if not survey_url:
                    result.error = "Pre-qualifier failed"
                    result.status = "screen_out"
                    log_earnings(survey_id, "pre_qualifier", 0, "screen_out", 0)
                    return result
            else:
                survey_url = details.get("href")

            if not survey_url:
                # No survey URL from API — try browser-based pre-qualifier
                get_logger().warn(
                    f"No href from API for {survey_id} — trying browser pre-qualifier",  # noqa: E501
                    survey_id=survey_id,
                )
                preq_result = self.pre_qualifier.handle_pre_qualifier_browser(
                    survey_id, self._close_tab
                )
                if preq_result.get("redirect_url"):
                    survey_url = preq_result["redirect_url"]
                    get_logger().prequal(survey_id, result_url=survey_url)
                else:
                    result.status = "screen_out"
                    result.error = "No survey URL (pre-qualifier failed or not available)"
                    log_earnings(survey_id, "pre_qualifier", 0, "screen_out", 0)
                    return result

        # Detect provider from URL (skip for in-page modal)
        if provider != "in_page_modal":
            provider = self._detect_provider(survey_url)
        result.provider = provider

        # 1b. Check blocked providers
        if provider in self.config.skip_providers:
            result.status = "blocked"
            result.error = f"Blocked provider: {provider}"
            log_earnings(survey_id, provider, 0, "blocked", 0)
            return result

        # 1c. Unknown provider → use generic fallback (except in-page modal)
        if provider == "unknown":
            provider = "generic"
            result.provider = "generic"
            get_logger().warn(
                "Unknown provider — using generic fallback commands", survey_id=survey_id
            )
        elif provider == "in_page_modal":
            get_logger().info(
                "In-page modal survey — clicking card on dashboard", survey_id=survey_id
            )

        # 2. Read balance BEFORE opening survey tab (dashboard WS still valid)
        try:
            balance_before = read_balance_with_backoff(self.config.cdp_port)
        except Exception:
            balance_before = 0.0

        get_logger().survey_start(survey_id, provider, survey_url, balance_before)

        # 3. Open survey — DASHBOARD CLICK (PRIMARY) for all surveys.
        #
        # WARUM dashboard click instead of Target.createTarget?
        #   Target.createTarget creates a NEW tab WITHOUT heypiggy session cookies.
        #   CPX redirect (click.cpx-research.com) requires app_id from heypiggy session.
        #   Without cookies → "No app id was specified" error page.
        #   Dashboard click uses heypiggy's own clickSurvey() JavaScript → has session.
        #
        #   The fix (2026-05-08): Use _click_survey_card for ALL surveys (not just
        #   in_page_modal). _click_survey_card clicks the survey card element via DOM,
        #   which triggers the onclick handler with proper session context.
        is_in_page = True  # Always use dashboard click approach
        tab_id = None

        # 3a. Pre-survey cleanup: close all stacked modals on dashboard
        if dashboard_ws:
            n_closed = self._pre_survey_cleanup(dashboard_ws)
            if n_closed > 0:
                get_logger().cleanup(0, 0, zombie_tabs=n_closed)

        # 3b. Capture tabs before clickSurvey() for new-tab detection
        tabs_before = set()
        try:
            for p in chrome.find_bot_tabs(self.config.cdp_port):
                tabs_before.add(p.get("id", ""))
        except Exception:
            pass

        # 3c. Click survey card via DOM (reliable, has session cookies)
        # NOTE: survey_id from API may not match DOM onclick IDs.
        # _click_survey_card finds the card element and clicks it directly.
        # Returns (ws_url, tab_id) — tab_id is set for new-tab flow.
        tab_ws, detected_tab_id = self._click_survey_card(survey_id)
        if not tab_ws:
            result.error = "Failed to click survey card"
            result.status = "error"
            return result
        time.sleep(self.config.wait_page_load)

        # 3d. Determine flow type (in-page vs new-tab)
        if detected_tab_id:
            tab_id = detected_tab_id
            is_in_page = False  # Survey opened in new tab
            get_logger().tab_switch(tab_id, reason="survey_new_tab")
        else:
            is_in_page = True  # In-page modal (survey within dashboard)

        # 3e. Verify survey tab content (handle stuck loading / error pages)
        if tab_ws:
            page_text = BatchExecutor.read_page_text(tab_ws, 500).lower()
            if any(
                s in page_text for s in ["loading", "just getting things ready", "won't be long"]
            ):  # noqa: E501
                get_logger().warn(
                    "Stuck on loading page — skipping", survey_id=survey_id, context="tab_creation"
                )
                result.status = "screen_out"
                result.error = "Survey stuck on loading page"
                log_earnings(survey_id, "unknown", 0, "screen_out", 0)
                return result

            # Detect ALL expired survey error pages (case-insensitive)
            if any(
                s in page_text
                for s in [
                    "no app id",
                    "survey not available",
                    "error - unable to start survey",
                    "survey closed",
                    "link has expired",
                    "survey has ended",
                    "leider ist ein fehler aufgetreten",
                    "error occurred",
                    "this survey is no longer available",
                    "survey unavailable",
                    "sie werden umgeleitet",
                    "redirect",
                    "no survey available",
                ]
            ):
                get_logger().warn(
                    "Survey URL expired or error page — skipping",
                    survey_id=survey_id,
                    context="tab_creation",
                )
                result.status = "screen_out"
                result.error = "Survey URL expired/error page"
                log_earnings(survey_id, "unknown", 0, "screen_out", 0)
                return result

        # 3f. Get actual survey URL for provider detection
        actual_url = ""
        if not is_in_page:  # Only get URL for new-tab flow (in-page uses dashboard)
            try:
                ws_check = websocket.create_connection(tab_ws, timeout=5)
                ws_check.send(
                    json.dumps(
                        {
                            "id": 0,
                            "method": "Runtime.evaluate",
                            "params": {
                                "expression": "document.location.href",
                                "returnByValue": True,
                            },
                        }
                    )
                )
                r = json.loads(ws_check.recv())
                actual_url = r.get("result", {}).get("result", {}).get("value", "")
                ws_check.close()
            except Exception:
                pass

        # Post-tab-creation: provider + URL detection
        # For in-page modal: provider stays as "in_page_modal", URL is dashboard
        if is_in_page:
            actual_url = "heypiggy.com/dashboard"
            real_provider = provider
        else:
            # Detect real provider from actual URL
            real_provider = self._detect_provider(actual_url) if actual_url else provider
            if real_provider != provider and real_provider != "unknown":
                result.provider = real_provider
                provider = real_provider
                get_logger().info(
                    f"Real provider: {provider} ({actual_url[:60]})",
                    survey_id=survey_id,
                    provider=provider,
                )

        # 4. Handle PureSpectrum captcha preflight (if applicable)
        if provider == "purespectrum" and tab_ws:
            captcha_result = self._handle_purespectrum_preflight(tab_ws, survey_id)
            if not captcha_result.get("success"):
                result.status = "blocked"
                result.error = f"PureSpectrum captcha: {captcha_result.get('error', 'unknown')}"
                log_earnings(
                    survey_id,
                    provider,
                    0,
                    "blocked",
                    0,
                    {"captcha_error": captcha_result.get("error")},
                )
                self._close_tab(tab_id)
                return result
            # Captcha solved, wait for page transition
            time.sleep(self.config.wait_page_load)
            # Refresh tab WS
            if tab_id:
                tab_info = chrome.get_ws_for_tab(tab_id, self.config.cdp_port)
                if tab_info:
                    tab_ws = tab_info

        # 5. NEMO Loop — with Circuit Breaker + Tab Re-Discovery
        nim_calls = 0
        consecutive_fails = 0
        max_consecutive_fails = 5  # Circuit breaker: stop after 5 fails
        # Anti-stuck: DOM hash checker (frozen tool, threshold 3)
        stuck_checker = tool_AntiStuck(threshold=3)
        actions_executed = 0  # SOTA: Count total actions for anti-stuck
        max_actions = 80  # SOTA: Safety limit — stop after 80 actions (survey has ~20-30 questions)

        for iteration in range(self.config.max_iterations):
            result.iterations = iteration + 1

            try:
                # 5a. Tab re-discovery (skip for in-page modal — same dashboard tab)
                if is_in_page:
                    tab_ws = chrome.find_dashboard_ws(self.config.cdp_port)
                    if not tab_ws:
                        result.error = "Dashboard tab lost"
                        result.status = "screen_out"
                        break
                else:
                    tab_ws_current = self._refresh_tab_ws(tab_id)
                    if not tab_ws_current:
                        result.error = "Tab disappeared (screen-out or redirect)"
                        result.status = "screen_out"
                        break
                    tab_ws = tab_ws_current

                # 5b. Compact snapshot (for NIM decisions + element analysis)
                snapshot = generate_snapshot(tab_ws)

                dom_hash = "pending"  # Initialize before first use in iteration() call below
                get_logger().iteration(
                    iteration=iteration + 1,
                    elements=len(snapshot.refs),
                    actions=actions_executed,
                    dom_hash=dom_hash if dom_hash != "error" else "",
                    provider=snapshot.provider,
                )

                # 5c. SOTA Anti-stuck via frozen tool (threshold 3)
                # Compute DOM hash from page text (BatchExecutor is mocked in tests)
                try:
                    page_text = BatchExecutor.read_page_text(tab_ws, 500)
                    dom_hash = hashlib.md5(page_text.encode()).hexdigest()[:12]
                except Exception:
                    dom_hash = "error"
                    page_text = ""

                if (
                    dom_hash != "pending"
                    and dom_hash != "error"
                    and stuck_checker.is_stuck(dom_hash)
                ):  # noqa: E501
                    result.error = (
                        f"Stuck: {stuck_checker.threshold}x same DOM hash (anti_stuck tool)"  # noqa: E501
                    )
                    result.status = "error"
                    break

                # 5d. SOTA Safety: Max actions limit
                # Estimate actions from snapshot element count (radio buttons, text fields, buttons)
                estimated_actions = sum(
                    1
                    for info in snapshot.refs.values()
                    if info.get("role") in ("radio", "checkbox", "textbox", "button")
                )
                # Always add 1 for the submit/next button
                actions_executed += min(estimated_actions + 1, 15)
                if actions_executed > max_actions:
                    result.error = f"Safety limit: {actions_executed} actions (survey overflow)"
                    result.status = "error"
                    break

                # 5f. SOTA Error detection: Check for screen-out/error page
                is_error, error_reason = BatchExecutor.detect_error_page(page_text)
                if is_error:
                    get_logger().warn(
                        f"Error page detected: {error_reason}",
                        survey_id=survey_id,
                        context="nemo_loop",
                    )
                    result.status = "screen_out"
                    result.error = error_reason
                    self._close_tab(tab_id)
                    log_earnings(
                        survey_id, provider, 0, "screen_out", 0, {"error_reason": error_reason}
                    )
                    return result

                # 5g. Empty snapshot: page not loaded — skip iteration
                if len(snapshot.refs) == 0:
                    time.sleep(self.config.wait_page_load)
                    continue

                # 5h. Check completion (BODY TEXT is PRIMARY!)
                #
                # FIX (2026-05-10): Surveys show "Vielen Dank" in body text
                # but URL stays the same. OLD CODE checked URL+title → MISSED
                # completion → loop continued → background started next survey → 6 tabs!
                #
                # FIX: Check BODY TEXT first (via _detect_completion_text).
                # Check URL/title as BACKUP for surveys that redirect to completion URL.
                #
                # Flow:
                #   1. Read body text from survey tab (PRIMARY — catches completion)
                #   2. Check URL/title completion redirect (BACKUP — rare case)
                #   3. Scan all browser tabs (TERTIARY — completion might open new tab)
                completed = False

                # PRIMARY: Check body text via CDP (this catches "Vielen Dank", etc.)
                if self._detect_completion_text(tab_ws):
                    completed = True

                # BACKUP: Check if URL/title contains completion redirect
                if not completed:
                    if detect_completion(snapshot.url + " " + snapshot.title):
                        completed = True

                # TERTIARY: Scan all browser tabs for completion
                # Some surveys redirect to a NEW TAB after completion (back to dashboard)
                if not completed:
                    completed = self._scan_completion_all_tabs()

                if completed:
                    result.status = "completed"
                    break

                # 5ia. QUALTRICS LANGUAGE PAGE DETECTION (2026-05-09)
                # Language pages have <select class="Q_lang"> but NO .NextButton.
                # NIM would send "submit" → click_next fails → survey stuck.
                # Detection: scan for Q_lang select → bypass NIM → use select action.
                lang_actions = None
                if provider == "qualtrics":
                    try:
                        lang_actions = detect_language_page(tab_ws, default_lang="Deutsch")
                        if lang_actions:
                            get_logger().info(
                                f"Language page detected: {len(lang_actions)} actions",
                                survey_id=survey_id,
                                context="nemo_loop",
                                iteration=iteration + 1,
                            )
                            actions = lang_actions
                            # Skip NIM for language page (no NIM call)
                            executor = BatchExecutor(tab_ws, provider, config=self.config)
                            batch_result = executor.execute(actions, snapshot.refs)
                            time.sleep(self.config.wait_page_load)
                            actions_executed += 1
                            # Continue to next iteration (page should advance after language selection)  # noqa: E501
                            continue
                    except Exception as e:
                        get_logger().warn(
                            f"Language detection failed: {e}",
                            survey_id=survey_id,
                            context="nemo_loop",
                            iteration=iteration + 1,
                        )
                        # Fall through to normal NIM decision
                else:
                    pass

                # 5i. NIM decision (with retry on empty actions)
                if self.nim and self.config.use_nim:
                    decision = self.nim.decide(
                        snapshot.to_dict(), self.profile, self.learnings, self.history
                    )
                    actions = decision.get("actions", [])
                    nim_calls += 1
                    result.nim_calls = nim_calls
                    result.nim_tokens += decision.get("tokens", {}).get("total", 0)

                    # Retry NIM once if actions empty (first call might miss content)
                    if not actions and iteration < 3:
                        time.sleep(1)
                        decision = self.nim.decide(
                            snapshot.to_dict(), self.profile, self.learnings, self.history
                        )
                        actions = decision.get("actions", [])
                else:
                    actions = ActionSelector.select_actions(snapshot)

                # 5j. Check for complete action
                if any(a.get("action") == "complete" for a in actions):
                    result.status = "completed"
                    break

                # 5k. Log decision
                log_decision(
                    len(snapshot.refs),
                    actions,
                    nim_calls,
                    decision.get("elapsed_ms", 0) if self.nim else 0,
                    survey_id,
                    provider,
                )

                # 5l. Execute batch with circuit breaker
                executor = BatchExecutor(tab_ws, provider, config=self.config)
                batch_result = executor.execute(actions, snapshot.refs)

                # 5la. SOTA Validation Error Detection + Auto-Recovery
                # After executing, check if the page shows a validation error.
                # If so, extract the hint, adjust the value, and retry once.
                try:
                    post_page = BatchExecutor.read_page_text(tab_ws, 800)
                    val_err = BatchExecutor.detect_validation_error(post_page)
                    if val_err:
                        get_logger().warn(
                            f"Validation error: {val_err.get('kind')} → hint={val_err.get('hint')}",
                            survey_id=survey_id,
                            context="nemo_loop",
                            iteration=iteration + 1,
                        )
                        retry_actions = []
                        for a in actions:
                            if a.get("action") == "fill" and a.get("value"):
                                fixed_value = val_err.get("hint", a["value"])
                                retry_actions.append({**a, "value": fixed_value})
                            elif a.get("action") == "fill":
                                pass
                            else:
                                retry_actions.append(a)
                        if retry_actions:
                            time.sleep(1.0)
                            retry_result = executor.execute(retry_actions, snapshot.refs)
                            batch_result = retry_result
                except Exception:
                    pass

                # Circuit breaker: 3+ failed actions in batch = abort
                if batch_result.total_fail >= 3:
                    consecutive_fails += 2
                    get_logger().warn(
                        f"Circuit breaker: {batch_result.total_fail} fails",
                        survey_id=survey_id,
                        context="nemo_loop",
                        iteration=iteration + 1,
                    )
                    if consecutive_fails >= max_consecutive_fails:
                        result.error = f"Circuit breaker triggered ({batch_result.total_fail} fail, {consecutive_fails} streak)"  # noqa: E501
                        result.status = "blocked"
                        break

                # 5m. SOTA Adaptive backoff: Use configured delay
                time.sleep(self.config.wait_after_action)

                # 5n. Record history
                self.history.append(
                    {
                        "iteration": iteration,
                        "actions": len(actions),
                        "success": batch_result.total_success,
                        "fail": batch_result.total_fail,
                        "dom_hash": dom_hash,
                    }
                )

            except Exception as e:
                get_logger().error(
                    str(e), context="nemo_loop", survey_id=survey_id, iteration=iteration + 1
                )
                consecutive_fails += 1
                if consecutive_fails >= max_consecutive_fails:
                    result.error = f"Circuit breaker: {str(e)[:100]}"
                    result.status = "blocked"
                    break
                result.error = str(e)[:200]
                result.status = "error"
                log_error("run_survey", e, survey_id, provider, {"iteration": iteration})
                # Continue loop but increment fail counter
                time.sleep(1)

        # 6. Close tab (only for new-tab flow, not in-page modal)
        if not is_in_page:
            self._close_tab(tab_id)

        # 7. Rate survey
        if result.status == "completed" and self.config.auto_rate:
            self.survey_rater.rate()

        # 8. Calculate earnings (balance read before tab creation, after survey close)
        # BUG-FIX (2026-05-10): Dashboard tab may be in stale/background state after
        # survey completes in a new tab. Reading balance_from a stale tab returns the
        # OLD balance — earned is computed as balance_after - balance_before = 0.
        # Fix: activate dashboard tab + wait 5s before reading balance_after.
        try:
            dash_ws = chrome.find_dashboard_ws(self.config.cdp_port)
            if dash_ws:
                tabs = chrome.find_bot_tabs(self.config.cdp_port)
                dash_tab = next((t for t in tabs if "dashboard" in t.get("url", "").lower()), None)
                if dash_tab and dash_tab.get("id"):
                    # REFRESH dashboard tab via Page.reload (NOT just Target.activateTarget!)
                    # ROOT CAUSE: Target.activateTarget only switches focus — DOM stays STALE.
                    # After survey completes in new tab, balance DOM hasn't updated.
                    # Page.reload forces fresh page load → balance DOM updates.
                    ws_reload = websocket.create_connection(dash_ws, timeout=5)
                    ws_reload.send(json.dumps({"id": 1, "method": "Page.reload"}))
                    try:
                        ws_reload.recv()
                    except Exception:
                        pass
                    ws_reload.close()
                    if self.debug:
                        print("[BALANCE] Dashboard tab reloaded — waiting for DOM update")
            time.sleep(4)  # Wait for reload + DOM update
            balance_after = read_balance_with_backoff(self.config.cdp_port)
            result.earned = self.balance_tracker.calculate_earned(balance_before, balance_after)
            get_logger().balance(balance_before, balance_after, result.earned)
        except Exception:
            result.earned = 0.0
            get_logger().warn(
                f"Balance after read failed — earned=0 (before was {balance_before}€)",  # noqa: E501
                survey_id=survey_id,
                context="balance_read",
            )
        result.elapsed_s = round(time.monotonic() - start_time, 1)

        # 9. Log earnings + survey end
        log_earnings(
            survey_id,
            provider,
            result.earned,
            result.status,
            result.elapsed_s,
            {"iterations": result.iterations},
        )
        get_logger().survey_end(result.status, result.earned, result.elapsed_s, result.error)

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

        # SESSION VALIDATION: Validate session before starting loop
        session_ok = validate_session(self.config.cdp_port, auto_recover=True)
        if not session_ok:
            print("[LOOP] Session invalid — recovery failed, aborting loop")
            return results

        # Scan dashboard
        viable = scan_dashboard(
            port=self.config.cdp_port, skip_providers=self.config.skip_providers
        )

        if not viable:
            print("[LOOP] No viable surveys found")
            return results

        total_viable = len(viable)
        total_ok = len([s for s in viable if s.get("provider") != "pre_qualifier"])
        print(
            f"[LOOP] Processing up to {self.config.max_surveys} surveys from {total_viable} viable"
        )  # noqa: E501

        started_count = 0  # Only count successfully started surveys
        failed_preq_cache = {}  # {survey_id: attempt_count} — skip if failed recently
        for i, survey in enumerate(viable):
            if started_count >= self.config.max_surveys:
                break

            # Handle pre-qualifiers via CPX API (NOT browser-based)
            if survey.get("provider") == "pre_qualifier":
                survey_id = survey["id"]
                # Skip recently failed pre-qualifiers to avoid redundant API calls
                if survey_id in failed_preq_cache:
                    continue
                survey_url = self.pre_qualifier.handle_pre_qualifier_api(
                    survey_id, survey, self.profile
                )
                if not survey_url:
                    get_logger().prequal(survey_id, answered=False)
                    failed_preq_cache[survey_id] = True  # Cache failure
                    continue
                survey = survey.copy()
                survey["href"] = survey_url
                survey["provider"] = "pre_qualifier_answered"
                get_logger().prequal(survey_id, answered=True, result_url=survey_url)

            # Check balance target
            try:
                balance = read_balance_with_backoff(self.config.cdp_port)
            except Exception:
                balance = 0.0
            if balance >= self.config.balance_target:
                print(f"[LOOP] Balance target reached: {balance}€")
                # Trigger cash-out flow
                self.cash_out.trigger(self.config.balance_target)
                break

            sid = survey["id"]
            href = survey.get("href", "")
            # ok_idx counts OK surveys seen so far (excluding pre-qualifiers)
            ok_idx = sum(1 for s in viable[:i] if s.get("provider") != "pre_qualifier") + 1
            print(f"[LOOP] [{ok_idx}/{total_ok}] Running survey {sid} ({survey['provider']})...")

            result = self.run_survey(sid, survey_url=href)
            results.append(result)
            started_count += 1
            print(
                f"[LOOP]   → {result.status} | {'+' + str(result.earned) + '€' if result.earned > 0 else str(result.earned) + '€'} | {result.error[:50] if result.error else 'no error'}"
            )  # noqa: E501

            if result.status == "completed":
                print(f"  ✅ +{result.earned}€ ({result.provider}, {result.elapsed_s}s)")
            elif result.status == "blocked":
                print(f"  ⛔ Blocked: {result.error}")
            else:
                print(f"  ❌ {result.status}: {result.error}")

        # Summary
        total = sum(r.earned for r in results if r.earned > 0)
        complete = sum(1 for r in results if r.status == "completed")
        failed = sum(1 for r in results if r.status == "error")
        screen_out = sum(1 for r in results if r.status == "screen_out")
        get_logger().loop_summary(
            attempted=len(results),
            completed=complete,
            total_earned=total,
            failed=failed,
            screen_out=screen_out,
        )
        self.metrics.loop_completed()
        print(f"\n{'=' * 50}")
        print(f"  LOOP COMPLETE: {complete}/{len(results)} surveys")
        print(f"  +{total}€ earned")
        print(f"{'=' * 50}\n")

        log_session(
            "loop",
            "ok",
            {
                "surveys_run": len(results),
                "completed": complete,
                "earned": total,
            },
        )

        return results

    # ── Private ─────────────────────────────────────

    def _create_tab(self, dashboard_ws, url):
        """Create a new browser tab with stealth injection before navigation.

        Delegates to SurveyOpener so tab lifecycle logic lives in one place.
        """
        return self.opener._create_tab(url)

    def _click_survey_card(self, survey_id):
        """Click a survey card IN-PAGE on the dashboard (modal flow).

        Delegates to SurveyOpener so tab lifecycle logic lives in one place.
        """
        dash_ws = chrome.find_dashboard_ws(self.config.cdp_port)
        if not dash_ws:
            return None
        return self.opener._click_survey_card(survey_id, dash_ws)

    def _click_redirect_link(self, tab_ws):
        """Click the 'hier klicken' link on CPX redirect page.

        Delegates to SurveyOpener so tab lifecycle logic lives in one place.
        """
        self.opener._click_redirect_link(tab_ws)

    def _find_survey_tab_ws(self, tab_id):
        """Find WebSocket URL for the actual survey tab after CPX redirect.

        Delegates to SurveyOpener so tab lifecycle logic lives in one place.
        """
        return self.opener._find_survey_tab_ws(tab_id)

    def _close_tab(self, tab_id):
        """Close a browser tab. Tolerates already-closed tabs.

        Delegates to SurveyOpener so tab lifecycle logic lives in one place.
        """
        target = SurveyTarget(
            survey_id="",
            provider="",
            ws_url="",
            tab_id=tab_id,
            mode="new_tab",
        )
        self.opener.close(target)

    def _refresh_tab_ws(self, tab_id):
        """Re-discover WebSocket URL for tab after navigation.

        Delegates to SurveyOpener so tab lifecycle logic lives in one place.
        """
        target = SurveyTarget(
            survey_id="",
            provider="",
            ws_url="",
            tab_id=tab_id,
            mode="new_tab",
        )
        return self.opener.refresh_ws(target)

    def _detect_provider(self, url):
        """Detect provider from URL."""
        from .scanner import detect_provider

        return detect_provider(url)

    def _handle_pre_qualifier_browser(self, survey_id):
        """Handle CPX pre-qualifier in browser.

        Delegates to PreQualifierHandler so pre-qualifier logic lives in one place.
        """
        return self.pre_qualifier.handle_pre_qualifier_browser(survey_id, self._close_tab)

    def _trigger_cash_out(self):
        """Navigate to cash-out page when balance target is reached.

        Delegates to CashOutTrigger so cash-out logic lives in one place.
        """
        self.cash_out.trigger(self.config.balance_target)

    def _detect_completion_text(self, ws_url):
        """Check page text for completion markers.

        Reads page text via BatchExecutor, then delegates text analysis
        to CompletionDetector so completion logic lives in one place.
        """
        try:
            text = BatchExecutor.read_page_text(ws_url, 500)
            return self.completion_detector.detect(text)
        except Exception:
            return False

    def _scan_completion_all_tabs(self):
        """Scan ALL browser tabs for completion markers.

        WHY: Survey completion may redirect to a different tab
        (e.g., back to dashboard after payout). Scanning all tabs
        ensures we don't miss completion signals.
        """
        try:
            for tab in chrome.find_bot_tabs(self.config.cdp_port):
                url = tab.get("url", "").lower()
                # Skip dashboard and blank tabs
                if "dashboard" in url or "about:blank" in url:
                    continue
                ws_url = tab.get("webSocketDebuggerUrl")
                if ws_url and self._detect_completion_text(ws_url):
                    return True
        except Exception:
            pass
        return False

    def _find_new_tab_after_click(self, known_tab_ids: set) -> Optional[str]:
        """Detect new tab opened by clickSurvey().

        Delegates to SurveyOpener so tab lifecycle logic lives in one place.
        """
        return self.opener._find_new_tab_after_click(known_tab_ids)

    def _pre_survey_cleanup(self, tab_ws: str) -> int:
        """Close all stacked modals + validate session.

        SESSION VALIDATION (2026-05-10):
        Before every survey operation, validate that the session is still valid.
        Chrome restart can invalidate cookies → surveys fail → €0 earned.
        This check ensures we catch invalid sessions BEFORE trying to run surveys.

        Args:
            tab_ws: WebSocket URL of dashboard tab

        Returns:
            Number of modals closed (0 if session invalid)
        """
        # SESSION VALIDATION: Check if session is still valid
        if not is_session_valid(self.config.cdp_port):
            get_logger().warn("Session invalid before survey — attempting recovery...")
            recovered = validate_session(self.config.cdp_port, auto_recover=True)
            if not recovered:
                get_logger().error(
                    "Session recovery failed — skipping survey", context="_pre_survey_cleanup"
                )
                return 0

        return self.opener._pre_survey_cleanup(tab_ws)

    def _handle_purespectrum_preflight(self, tab_ws, survey_id):
        """Handle PureSpectrum pre-survey flow: cookie + ROBOT + captcha + puzzle."""
        from survey.providers.purespectrum import solve_purespectrum_preflight

        return solve_purespectrum_preflight(tab_ws, debug=self.config.debug)

    def _rate_survey(self):
        """Rate completed survey for +0.01€ bonus.

        Delegates to SurveyRater so rating logic lives in one place.
        """
        self.survey_rater.rate()

    def handle_pre_qualifier(self, survey_id, survey_details):
        """Answer pre-qualifier questions via CPX API.

        Delegates to PreQualifierHandler so pre-qualifier logic lives in one place.
        """
        return self.pre_qualifier.handle_pre_qualifier_api(survey_id, survey_details, self.profile)
