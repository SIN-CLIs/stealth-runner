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
        "purespectrum", "surveyrouter", "gfk"
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

        # 0. Connect to dashboard
        dashboard_ws = chrome.find_dashboard_ws(self.config.cdp_port)
        if not dashboard_ws:
            result.error = "No dashboard WebSocket found"
            result.status = "error"
            log_error("run_survey", result.error, survey_id)
            return result

        # 1. Get survey URL
        if not survey_url:
            survey_url = chrome.get_survey_url(survey_id)
            if not survey_url:
                result.error = "Failed to get survey URL"
                result.status = "error"
                log_error("run_survey", result.error, survey_id)
                return result

        provider = self._detect_provider(survey_url)
        result.provider = provider

        # 2. Check blocked providers
        if provider in self.config.skip_providers:
            result.status = "blocked"
            result.error = f"Blocked provider: {provider}"
            log_earnings(survey_id, provider, 0, "blocked", 0)
            return result

        if self.config.debug:
            print(f"[RUN] {survey_id} → {provider}")

        # 3. Open survey in new tab
        tab_id = self._create_tab(dashboard_ws, survey_url)
        if not tab_id:
            result.error = "Failed to create browser tab"
            result.status = "error"
            return result

        # 4. Wait for redirects
        time.sleep(self.config.wait_page_load)

        tab_info = chrome.get_ws_for_tab(tab_id, self.config.cdp_port)
        tab_ws = tab_info if tab_info else chrome.find_survey_tab(self.config.cdp_port)

        # 5. NEMO Loop
        nim_calls = 0
        balance_before = read_balance(self.config.cdp_port)

        for iteration in range(self.config.max_iterations):
            result.iterations = iteration + 1

            try:
                # 5a. Compact snapshot
                snapshot = generate_snapshot(tab_ws)

                if self.config.debug and iteration % 5 == 0:
                    print(f"  [iter {iteration}] {snapshot.provider} "
                          f"({len(snapshot.refs)} el)")

                # 5b. Check completion
                if detect_completion(snapshot.url + " " + snapshot.title) or \
                   self._detect_completion_text(tab_ws):
                    result.status = "completed"
                    break

                # 5c. NIM decision
                if self.nim and self.config.use_nim:
                    decision = self.nim.decide(
                        snapshot.to_dict(), self.profile,
                        self.learnings, self.history
                    )
                    actions = decision.get("actions", [])
                    nim_calls += 1
                    result.nim_calls = nim_calls
                    result.nim_tokens += decision.get("tokens", {}).get("total", 0)
                else:
                    actions = self._simple_actions(snapshot)

                # 5d. Check for complete action
                if any(a.get("action") == "complete" for a in actions):
                    result.status = "completed"
                    break

                # 5e. Log decision
                log_decision(
                    len(snapshot.refs), actions, nim_calls,
                    decision.get("elapsed_ms", 0) if self.nim else 0,
                    survey_id, provider
                )

                # 5f. Execute batch
                executor = BatchExecutor(tab_ws, provider)
                batch_result = executor.execute(actions)

                # 5g. Record history
                self.history.append({
                    "iteration": iteration,
                    "actions": len(actions),
                    "success": batch_result.total_success,
                    "fail": batch_result.total_fail,
                })

                # 5h. Wait for page transition
                time.sleep(self.config.wait_after_action)

            except Exception as e:
                if self.config.debug:
                    print(f"  [iter {iteration}] Error: {e}")
                result.error = str(e)[:200]
                result.status = "error"
                log_error("run_survey", e, survey_id, provider,
                          {"iteration": iteration})
                break

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

            # Check balance target
            balance = read_balance(self.config.cdp_port)
            if balance >= self.config.balance_target:
                print(f"[LOOP] Balance target reached: {balance}€")
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
        try:
            ws = websocket.create_connection(dashboard_ws, timeout=15)
            ws.send(json.dumps({
                "id": 1, "method": "Target.createTarget",
                "params": {"url": url}
            }))
            r = json.loads(ws.recv())
            ws.close()
            return r.get("result", {}).get("targetId")
        except Exception:
            return None

    def _close_tab(self, tab_id):
        """Close a browser tab."""
        try:
            tab_info = chrome.get_ws_for_tab(tab_id, self.config.cdp_port)
            if tab_info:
                ws = websocket.create_connection(tab_info, timeout=10)
                ws.send(json.dumps({
                    "id": 1, "method": "Target.closeTarget",
                    "params": {"targetId": tab_id}
                }))
                json.loads(ws.recv())
                ws.close()
        except Exception:
            pass

    def _detect_provider(self, url):
        """Detect provider from URL."""
        from .scanner import detect_provider
        return detect_provider(url)

    def _detect_completion_text(self, ws_url):
        """Check page text for completion markers."""
        text = BatchExecutor.read_page_text(ws_url)
        return detect_completion(text)

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

    def _simple_actions(self, snapshot):
        """Simple auto-pilot when NIM not available."""
        actions = []
        for ref, info in snapshot.refs.items():
            if info.get("role") in ("radio", "checkbox") and info.get("enabled", True):
                actions.append({"ref": ref, "action": "select"})
                break
        for ref, info in snapshot.refs.items():
            if info.get("role") == "button":
                text = info.get("text", "").lower()
                if any(kw in text for kw in ["weiter", "next", "submit", "nächste"]):
                    actions.append({"action": "submit"})
                    break
        else:
            actions.append({"action": "submit"})
        return actions

    def _load_profile(self):
        """Load profile from JSON file or fallback."""
        import os
        paths = [
            os.path.join(os.path.dirname(__file__), "profiles", "jeremy_schulze.json"),
            os.path.join(os.path.dirname(os.path.dirname(__file__)),
                         "config", "profiles", "jeremy_schulze.json"),
        ]
        for path in paths:
            if os.path.exists(path):
                try:
                    return json.loads(open(path).read())
                except Exception:
                    pass

        return {
            "name": "Jeremy Schulze",
            "age": 32, "gender": "male", "gender_label": "Männlich",
            "city": "Berlin", "state": "Berlin", "zip": "10785",
            "household_size": 3, "marital_status": "married",
            "education": "abitur", "employment": "employed_fulltime",
            "employment_label": "Angestellte",
            "household_income": "3000-4000", "personal_income": "1000-2000",
            "nationality": "Deutsch", "language": "Deutsch",
        }
