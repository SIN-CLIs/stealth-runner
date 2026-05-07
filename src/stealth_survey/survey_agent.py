"""================================================================================
SURVEY AGENT — NEMO Loop: Compact Snapshot → Nemotron Decision → Batch Execute
================================================================================

WAS IST DAS?
  Die Haupt-NEMO-Engine (Nemotron 3 Omni + CDP). Automatisiert Survey-
  Teilnahmen mit minimalen LLM-Calls durch Compact Snapshots und Batch-Execution.

ARCHITEKTUR (NEMO Loop):
  ┌─────────────────────┐
  │   SurveyAgent.run() │
  └─────────────────────┘
         │
         ▼
  ┌─────────────────────┐     ┌─────────────────────┐
  │  Compact Snapshot    │────▶│  Nemotron 3 Omni    │
  │  (@eN Element Refs)  │     │  (Decision)         │
  └─────────────────────┘     └─────────────────────┘
         │                              │
         ▼                              ▼
  ┌─────────────────────┐     ┌─────────────────────┐
  │  Batch Executor     │◄────│  Batch Actions      │
  │  (CDP WebSocket)    │     │  (click/fill/...)   │
  └─────────────────────┘     └─────────────────────┘
         │
         ▼
  ┌─────────────────────┐
  │  Memory + Guardian  │
  │  (Logging, Heal)    │
  └─────────────────────┘
         │
         ▼
    [Loop bis Complete]

VORTEILE gegenüber Legacy (cua-driver Loop):
  - 1 LLM-Call PRO SEITE (nicht pro Element)
  - ~500 tokens in, ~100 tokens out (statt ~5000+)
  - 5× schneller als cua-driver Loop
  - Keine Index-Instabilität (Compact Snapshots)

WARUM NEMO?
  Legacy cua-driver Loop: Agent ruft 20-50x get_window_state(),
  klickt einzelne Elemente, vergisst Zwischenstände.
  NEMO: Ein Snapshot → Eine Decision → Batch Execute → Next Page.

DEPENDENZEN:
  - nim_client.py: Nemotron 3 Omni API Client
  - compact_snapshot.py: DOM → @eN Snapshot Generator
  - batch_executor.py: Actions → CDP WebSocket Execution
  - Optional: stealth_memory (Logging), stealth_guardian (Heal)

BANNED METHODS — NIEMALS VERWENDEN (siehe /banned.md):
  ❌ playstealth launch — setzt NICHT --force-renderer-accessibility
  ❌ webauto-nodriver — ABSOLUT BANNED
  ❌ cua-driver click (raw index) — instabil, nutze BatchExecutor
  ❌ --remote-allow-origins=* (ohne Quotes) — zsh glob expansion
  ❌ /tmp/heypiggy-bot (fixed profile) — korruptiert nach Neustart
  ❌ Hardcoded PIDs — dynamisch, niemals hardcodieren
  ❌ pkill -f "Google Chrome" — tötet USER Chrome
  ❌ killall Google Chrome — tötet ALLE Chrome
  ❌ skylight-cli click --element-index — Index instabil
================================================================================"""

import json
import time
import os
import subprocess
import urllib.request
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field

from .nim_client import NIMSurveyClient, BATCH_TOOL_SCHEMA
from .compact_snapshot import CompactSnapshotGenerator, CompactSnapshot
from .batch_executor import BatchExecutor, BatchResult


@dataclass
class AgentConfig:
    """Configuration for SurveyAgent."""
    # CDP
    cdp_port: int = 9999
    cdp_base_url: str = "http://127.0.0.1:9999/json"

    # NIM
    nim_api_key: Optional[str] = None
    nim_model: str = "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning"
    nim_temperature: float = 0.1

    # Survey loop
    max_iterations: int = 50
    max_surveys: int = 10
    balance_target: float = 5.0
    poll_interval: float = 30.0
    wait_between_actions: float = 2.0
    wait_page_load: float = 5.0

    # Provider options
    skip_providers: List[str] = field(default_factory=lambda: [
        "purespectrum", "surveyrouter"
    ])

    # Features
    use_nim: bool = True
    use_memory: bool = False  # requires stealth-memory
    use_guardian: bool = False  # requires stealth-guardian
    auto_rate: bool = True
    debug: bool = False


@dataclass
class SurveyResult:
    """Result of a single survey run."""
    survey_id: str = ""
    provider: str = "unknown"
    status: str = "unknown"  # "completed", "screen_out", "error", "blocked"
    earned: float = 0.0
    iterations: int = 0
    elapsed_s: float = 0.0
    nim_calls: int = 0
    nim_tokens: int = 0
    error: Optional[str] = None


class SurveyAgent:
    """Next-gen survey automation agent.

    Replaces the cua-driver-based survey_heypiggy.py flow with:
    - CDP WebSocket (no cua-driver daemon)
    - Nemotron 3 Omni decision making
    - Compact @eN snapshots (token-efficient)
    - Batch execution (minimal round-trips)
    """

    def __init__(self, config: Optional[AgentConfig] = None):
        self.config = config or AgentConfig()

        # CDP
        self.cdp_base = f"http://127.0.0.1:{self.config.cdp_port}/json"
        self.snapshot_gen = CompactSnapshotGenerator(port=self.config.cdp_port)

        # NIM
        self.nim = None
        if self.config.use_nim:
            self.nim = NIMSurveyClient(
                api_key=self.config.nim_api_key or os.getenv("NVIDIA_API_KEY"),
                model=self.config.nim_model,
            )

        # State
        self.profile: Dict[str, Any] = {}
        self.learnings: List[str] = []
        self.session_history: List[Dict] = []
        self._dashboard_ws: Optional[str] = None

    def load_profile(self, profile_name: str = "jeremy_schulze"):
        """Load user profile from config/profiles/."""
        try:
            path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                "config", "profiles", f"{profile_name}.json"
            )
            if os.path.exists(path):
                self.profile = json.loads(open(path).read())
                if self.config.debug:
                    print(f"[AGENT] Loaded profile: {profile_name}")
                return True
        except Exception as e:
            print(f"[AGENT] Failed to load profile: {e}")

        # Fallback: hardcoded
        self.profile = {
            "name": "Jeremy Schulze",
            "age": 32,
            "gender": "male",
            "gender_label": "Männlich",
            "city": "Berlin",
            "state": "Berlin",
            "zip": "10785",
            "household_size": 3,
            "marital_status": "married",
            "education": "abitur",
            "employment": "employed_fulltime",
            "employment_label": "Angestellte",
            "household_income": "3000-4000",
            "personal_income": "1000-2000",
            "nationality": "Deutsch",
            "insurance_products": ["haftpflicht"],
            "contracts": ["mobilfunk", "strom"],
        }
        return False

    def _get_dashboard_ws(self) -> Optional[str]:
        """Find WebSocket URL for a dashboard tab."""
        try:
            pages = json.loads(urllib.request.urlopen(self.cdp_base).read())
            for p in pages:
                if "dashboard" in p.get("url", ""):
                    return p.get("webSocketDebuggerUrl")
            if pages:
                return pages[0].get("webSocketDebuggerUrl")
        except Exception:
            pass
        return None

    def _get_tab_info(self, tab_id: str) -> Optional[Dict]:
        """Get tab info (url, ws_url) by tab ID."""
        try:
            pages = json.loads(urllib.request.urlopen(self.cdp_base).read())
            for p in pages:
                if p.get("id") == tab_id:
                    return p
        except Exception:
            pass
        return None

    def _read_balance(self) -> float:
        """Read current balance from dashboard."""
        dashboard_ws = self._get_dashboard_ws()
        if not dashboard_ws:
            return 0.0

        import websocket
        ws = websocket.create_connection(dashboard_ws, timeout=15)
        ws.send(json.dumps({
            "id": 0, "method": "Runtime.evaluate",
            "params": {
                "expression": '(function(){var t=document.body.innerText;var m=t.match(/\\d+\\\\.\\\\d+\\\\s*€/g);return m?m[m.length-1].replace("€","").trim():"0";})()'
            }
        }))
        r = json.loads(ws.recv())
        ws.close()

        try:
            return float(r.get("result", {}).get("result", {}).get("value", "0"))
        except (ValueError, TypeError):
            return 0.0

    def run_survey(self, survey_id: str, survey_url: Optional[str] = None) -> SurveyResult:
        """Run a single survey from ID to completion.

        Args:
            survey_id: CPX survey ID or direct URL
            survey_url: Optional direct URL (skip API call)

        Returns:
            SurveyResult with status and earnings
        """
        result = SurveyResult(survey_id=survey_id)
        start_time = time.monotonic()

        # 0. Get dashboard WS
        dashboard_ws = self._get_dashboard_ws()
        if not dashboard_ws:
            result.error = "No dashboard WebSocket found"
            result.status = "error"
            return result
        self._dashboard_ws = dashboard_ws

        # 1. Get survey URL via API if not provided
        if not survey_url:
            survey_url = self._get_survey_url(survey_id)
            if not survey_url:
                result.error = "Failed to get survey URL"
                result.status = "error"
                return result

        # 2. Open survey in new tab
        tab_id = self._create_target(dashboard_ws, survey_url)
        if not tab_id:
            result.error = "Failed to create target tab"
            result.status = "error"
            return result

        if self.config.debug:
            print(f"[AGENT] Tab created: {tab_id}")

        # 3. Wait for redirects
        time.sleep(self.config.wait_page_load)
        tab_info = self._get_tab_info(tab_id)
        if tab_info:
            actual_url = tab_info.get("url", "")
            result.provider = CompactSnapshotGenerator._detect_provider(actual_url)

        # 4. Check for blocked providers
        if result.provider in self.config.skip_providers:
            if self.config.debug:
                print(f"[AGENT] Skipping blocked provider: {result.provider}")
            result.status = "blocked"
            result.error = f"Blocked provider: {result.provider}"
            self._close_tab(tab_id)
            return result

        # 5. Get tab WebSocket
        tab_ws = tab_info.get("webSocketDebuggerUrl", "") if tab_info else ""

        # 6. Main loop
        import websocket
        balance_before = self._read_balance()

        for iteration in range(self.config.max_iterations):
            result.iterations = iteration + 1

            # 6a. Generate compact snapshot
            snapshot = self.snapshot_gen.generate(tab_ws)
            snapshot.provider = result.provider

            if self.config.debug:
                print(f"[AGENT] Iter {iteration}: {len(snapshot.refs)} elements, "
                      f"provider={result.provider}")

            # 6b. Check completion
            if self._detect_completion(snapshot):
                result.status = "completed"
                if self.config.debug:
                    print(f"[AGENT] Survey completed at iteration {iteration}")
                break

            # 6c. NIM decision
            if self.nim and self.config.use_nim:
                decision = self.nim.decide(
                    snapshot.to_dict(),
                    self.profile,
                    self.learnings,
                    self.session_history,
                    temperature=self.config.nim_temperature,
                )
                actions = decision.get("actions", [])
                result.nim_calls += 1
                result.nim_tokens += decision.get("tokens", {}).get("total", 0)

                if self.config.debug:
                    print(f"[AGENT] NIM: {len(actions)} actions in "
                          f"{decision['elapsed_ms']}ms "
                          f"({decision['tokens']['total']} tokens)")
            else:
                # No NIM: use simple auto-pilot (click first radio, then next)
                actions = self._simple_actions(snapshot)

            # 6d. Check for completion action
            if any(a.get("action") == "complete" for a in actions):
                result.status = "completed"
                break

            # 6e. Execute batch
            executor = BatchExecutor(tab_ws, result.provider)
            batch_result = executor.execute(actions)

            # 6f. Record in history
            self.session_history.append({
                "iteration": iteration,
                "actions": len(actions),
                "success": batch_result.total_success,
                "fail": batch_result.total_fail,
                "provider": result.provider,
            })

            # 6g. Wait for page transition
            time.sleep(self.config.wait_between_actions)

            # 6h. Refresh tab WS (may have changed after redirect)
            tab_info = self._get_tab_info(tab_id)
            if tab_info:
                tab_ws = tab_info.get("webSocketDebuggerUrl", "")

        # 7. Rate survey if completed
        if result.status == "completed" and self.config.auto_rate:
            if self.config.debug:
                print("[AGENT] Rating survey...")
            self._rate_survey()

        # 8. Calculate earnings
        time.sleep(2)
        balance_after = self._read_balance()
        result.earned = round(balance_after - balance_before, 2)
        result.elapsed_s = round(time.monotonic() - start_time, 1)

        # 9. Close survey tab
        self._close_tab(tab_id)

        if self.config.debug:
            print(f"[AGENT] Survey result: {result.status} +{result.earned}€ "
                  f"in {result.elapsed_s}s ({result.iterations} steps, "
                  f"{result.nim_calls} NIM calls)")

        return result

    def run_loop(self, survey_ids: Optional[List[str]] = None) -> List[SurveyResult]:
        """Run multiple surveys in a loop.

        Args:
            survey_ids: List of survey IDs to run. If None, auto-discover from dashboard.

        Returns:
            List of SurveyResults
        """
        results = []

        if survey_ids is None:
            survey_ids = self._scan_dashboard_ids()

        for i, sid in enumerate(survey_ids):
            if i >= self.config.max_surveys:
                break

            # Check balance target
            balance = self._read_balance()
            if balance >= self.config.balance_target:
                print(f"[AGENT] Balance target reached: {balance}€")
                break

            print(f"\n[AGENT] Survey {i+1}/{min(len(survey_ids), self.config.max_surveys)}: {sid}")
            result = self.run_survey(sid)
            results.append(result)

            if result.status == "completed":
                print(f"  ✅ +{result.earned}€ ({result.provider}, "
                      f"{result.elapsed_s}s, {result.nim_calls} NIM calls)")
            elif result.status == "blocked":
                print(f"  ⛔ Blocked: {result.error}")
            else:
                print(f"  ❌ {result.status}: {result.error}")

        # Summary
        total_earned = sum(r.earned for r in results if r.earned > 0)
        completed = sum(1 for r in results if r.status == "completed")
        print(f"\n[AGENT] Summary: {completed}/{len(results)} completed, "
              f"+{total_earned}€ earned")

        return results

    # ── Private helpers ─────────────────────────────────

    def _create_target(self, dashboard_ws: str, url: str) -> Optional[str]:
        """Create a new browser tab via CDP."""
        import websocket
        try:
            ws = websocket.create_connection(dashboard_ws, timeout=15)
            ws.send(json.dumps({
                "id": 1, "method": "Target.createTarget",
                "params": {"url": url}
            }))
            r = json.loads(ws.recv())
            ws.close()
            return r.get("result", {}).get("targetId")
        except Exception as e:
            if self.config.debug:
                print(f"[AGENT] createTarget failed: {e}")
            return None

    def _close_tab(self, tab_id: str):
        """Close a browser tab via CDP."""
        import websocket
        try:
            tab_info = self._get_tab_info(tab_id)
            if tab_info:
                ws_url = tab_info.get("webSocketDebuggerUrl")
                if ws_url:
                    ws = websocket.create_connection(ws_url, timeout=10)
                    ws.send(json.dumps({
                        "id": 1, "method": "Target.closeTarget",
                        "params": {"targetId": tab_id}
                    }))
                    json.loads(ws.recv())
                    ws.close()
        except Exception:
            pass

    def _get_survey_url(self, survey_id: str) -> Optional[str]:
        """Get survey URL from CPX API."""
        details_url = (
            "https://live-api.cpx-research.com/api/get-survey-details.php"
            "?output_method=jsscriptv1"
            "&app_id=11644"
            "&ext_user_id=2525530"
            "&secure_hash=ae75b0feca27c0f8eb356d7117d978ec"
            "&email=zukunftsorientierte.energie@gmail.com"
            "&extra_info_1=offerwall"
            "&main_info=true"
            "&extra_info_3=EUR"
            "&extra_info_4=nomobile"
        )
        try:
            resp = json.loads(urllib.request.urlopen(
                details_url + "&survey_id=" + survey_id, timeout=8
            ).read())
            if resp.get("type") == "okay":
                return resp.get("href")
        except Exception:
            pass
        return None

    def _scan_dashboard_ids(self) -> List[str]:
        """Scan dashboard for survey IDs."""
        dashboard_ws = self._get_dashboard_ws()
        if not dashboard_ws:
            return []

        import websocket
        ws = websocket.create_connection(dashboard_ws, timeout=15)
        ws.send(json.dumps({
            "id": 0, "method": "Runtime.evaluate",
            "params": {
                "expression": '(function(){var out=[];document.querySelectorAll("[onclick*=clickSurvey]").forEach(function(c){var m=c.getAttribute("onclick").match(/\\d+/);if(m)out.push(m[0]);});return out.join("|");})()'
            }
        }))
        r = json.loads(ws.recv())
        ws.close()

        ids_str = r.get("result", {}).get("result", {}).get("value", "")
        return [i for i in ids_str.split("|") if i] if ids_str else []

    def _detect_completion(self, snapshot: CompactSnapshot) -> bool:
        """Detect if survey is completed based on snapshot content."""
        # Check questions for completion markers
        questions = snapshot.semantic.get("questions", [])
        question_text = " ".join(questions).lower()
        completion_markers = [
            "zurück zur website",
            "gutgeschrieben",
            "vielen dank",
            "thank you",
        ]
        if any(m in question_text for m in completion_markers):
            return True

        # Check URL for rating page
        if "rating.php" in snapshot.url.lower():
            return True

        return False

    def _rate_survey(self):
        """Rate a completed survey for +0.01€ bonus."""
        try:
            pages = json.loads(urllib.request.urlopen(self.cdp_base).read())
            for p in pages:
                url = p.get("url", "")
                if "rating.php" in url.lower() or "cpx-research" in url.lower():
                    ws_url = p.get("webSocketDebuggerUrl")
                    if ws_url:
                        import websocket
                        ws = websocket.create_connection(ws_url, timeout=15)
                        ws.send(json.dumps({
                            "id": 0, "method": "Runtime.evaluate",
                            "params": {
                                "expression": 'document.querySelector("button,.btn-blue,input[type=button]").click()'
                            }
                        }))
                        json.loads(ws.recv())
                        ws.close()
                        time.sleep(2)
                        break
        except Exception:
            pass

    def _simple_actions(self, snapshot: CompactSnapshot) -> List[Dict]:
        """Simple auto-pilot actions when NIM is not available.

        Strategy: Click first radio button, then click submit.
        This is a FALLBACK for when NIM is offline.
        """
        actions = []

        # Find first radio or checkbox
        for ref, el_info in snapshot.refs.items():
            if el_info.get("role") in ("radio", "checkbox") and el_info.get("enabled", True):
                actions.append({"ref": ref, "action": "select"})
                break

        # Find a submit/next button
        for ref, el_info in snapshot.refs.items():
            if el_info.get("role") == "button":
                text = el_info.get("text", "").lower()
                if any(kw in text for kw in ["weiter", "next", "submit", "nächste", "weiter →"]):
                    actions.append({"action": "submit"})
                    break

        # Fallback: click any button
        if not any(a.get("action") == "submit" for a in actions):
            actions.append({"action": "submit"})

        return actions

    def add_learning(self, learning: str):
        """Add a learning from this session."""
        self.learnings.append(learning)

    def save_session_log(self, path: str = "sessions/agent_session.jsonl"):
        """Save session history to JSONL."""
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "a") as f:
            for entry in self.session_history:
                f.write(json.dumps(entry) + "\n")
