"""================================================================================
SURVEY STATE — LangGraph GraphState für Survey-Automation
================================================================================

WAS IST DAS?
  SurveyState ist das zentrale State-Objekt für den LangGraph Survey-Agent.
  Es kapselt ALLE Daten die während einer Survey-Session entstehen:
  Survey-ID, Tab-WebSocket, Provider, Iteration, Balance, Fehler-Historie,
  NEMO-Snapshot, NIM-Entscheidungen, Batch-Results.

ARCHITEKTUR:
  LangGraph verwendet TypedDict-basierte States. SurveyState ist die
  Single Source of Truth für den gesamten Graph-Execution-Context.

  ┌─────────────────────────────────────────────────────────────────────────┐
  │                         SURVEY STATE FLOW                               │
  ├─────────────────────────────────────────────────────────────────────────┤
  │                                                                          │
  │  survey_id: "67064749"     ← Start-Input                                 │
  │       │                                                                   │
  │       ▼                                                                   │
  │  tab_ws ──────────────────────┐                                          │
  │  provider: "purespectrum"       │                                        │
  │  dashboard_ws: "ws://..."       │ ← Tab nach open_survey                 │
  │       │                         │                                        │
  │       ▼                         │                                        │
  │  iteration: 0  ───────────────┐ │                                        │
  │       │                     │ │ │                                        │
  │       ▼                     │ │ │                                        │
  │  snapshot_refs: {} ───────┐ │ │ │                                        │
  │       │                 │ │ │ │                                        │
  │       ▼                 │ │ │ │                                        │
  │  nim_actions: [] ──────┐ │ │ │ │                                        │
  │       │               │ │ │ │ │                                        │
  │       ▼               │ │ │ │ │                                        │
  │  batch_result: null ─┘ │ │ │ │ │                                        │
  │       │                 │ │ │ │                                        │
  │       ▼                 ▼ ▼ ▼ ▼                                        │
  │  balance_before: 2.60€   balance_after: ?                               │
  │       │                                                                   │
  │       ▼                                                                   │
  │  status: "running" → "completed" | "screen_out" | "error" | "delegated" │
  │       │                                                                   │
  │       ▼                                                                   │
  │  errors: [] ──── consecutive_failures → "delegated"                     │
  │                                                                          │
  └─────────────────────────────────────────────────────────────────────────┘

ROOT CAUSE (2026-05-09):
  Survey-Tabs die via `Target.createTarget` geöffnet werden haben KEINE
  heypiggy-Cookies → CPX redirect zurück zum Dashboard → €0 verdient.
  FIX: cookies_injected=True setzen NACH tab_open, VOR Page.navigate.

FELDER IM DETAIL:

  survey_id:
    HeyPiggy interne Survey-ID (z.B. "67064749").
    Wird vom Dashboard gescannt und als Start-Input übergeben.

  tab_ws:
    CDP WebSocket URL des Survey-Tabs.
    Wird von SurveyOpener.open() zurückgegeben.
    Format: ws://127.0.0.1:9999/devtools/page/...

  dashboard_ws:
    CDP WebSocket URL des HeyPiggy Dashboard-Tabs.
    Wird für cookie injection und Tab-Management benötigt.
    Wird NICHT geschlossen nach survey open (kann für weitere Surveys
    wiederverwendet werden).

  provider:
    Survey-Provider Name (z.B. "purespectrum", "qualtrics", "tolunastart").
    Bestimmt das CDP Command-Mapping in BatchExecutor.PROVIDER_COMMANDS.
    Wird aus survey_url extrahiert oder von Dashboard gescannt.

  cookies_injected:
    Boolean flag — ob heypiggy Session-Cookies in tab_ws injiziert wurden.
    KRITISCH für Survey-Tabs die via Target.createTarget geöffnet werden.
    False = tab hat keine Session → CPX redirect → €0.
    Wird nach Network.setCookies auf True gesetzt.

  iteration:
    Anzahl der NEMO-Loop-Durchläufe (0-indexed).
    Wird nach jedem snapshot+execute Incrementiert.
    Dient der Fehlerdiagnose: iteration > 10 = wahrscheinlich stuck.

  max_iterations:
    Obergrenze für NEMO-Loop-Durchläufe.
    Default: 15 — genug für 30+ Seiten, aber nicht endlos.
    Wird in __init__ gesetzt und NIEMALS geändert.

  consecutive_failures:
    Anzahl der direkt aufeinanderfolgenden failed Batch-Executions.
    Wird nach jedem execute Incrementiert.
    Wird nach erfolgreichem execute auf 0 resetiert.
    TRIGGER: consecutive_failures >= 3 → human_delegate() wird aufgerufen.
    Warum 3? → 1× Retry ist normal (transient), 2× Retry ist selten,
    3× = echtes Problem das ein Mensch lösen muss.

  balance_before:
    Guthabenstand VOR der Survey-Session in Euro.
    Wird nach Chrome-Start/gemerget aus balance_tracker gelesen.
    Dient der Verification: balance_after > balance_before = Erfolg.

  balance_after:
    Guthabenstand NACH der Survey-Session in Euro.
    Wird nach detect_completion verglichen mit balance_before.
    survey_rater.py oder balance_tracker.py lesen das neue Guthaben.

  status:
    Aktueller Zustand des Survey-Workflows:
    - "initialized": Graph gestartet, Chrome/Tab noch nicht bereit
    - "chrome_ready": Chrome läuft, Dashboard bereit
    - "tab_open": Survey-Tab geöffnet, cookies noch nicht injiziert
    - "cookies_injected": Session-Cookies injiziert, Survey bereit
    - "running": NEMO-Loop aktiv (snapshot → NIM → execute)
    - "screen_out": Survey beendet (0.02€ oder disqualifiziert)
    - "completed": Survey beendet (€ verdient)
    - "error": Schwerer Fehler (Chrome tot, CDP kaputt, etc.)
    - "delegated": An opencode CLI übergeben (3× failures)

  errors:
    Liste aller Fehler während der Session.
    Format: [{"node": str, "error": str, "iteration": int}]
    Wird nach jedem Node-Execution angehängt.
    Dient der post-Session-Analyse.

  snapshot_refs:
    Dict von @eN Element-Referenzen aus dem letzten Compact Snapshot.
    Format: {"@e0": {"role": "radio", "text": "Männlich"}, ...}
    Wird von snapshot_node() gesetzt und an NIM-Entscheidungen übergeben.
    Wird von execute_node() für provider-spezifisches JS-Matching genutzt.

  nim_actions:
    Liste der NIM-NEMOTRON-Entscheidungen für die aktuelle Iteration.
    Format: [{"ref": "@e0", "action": "select"}, {"ref": "@e12", "action": "fill", "value": "32"}]
    Wird von decide_node() gesetzt.
    Wird von execute_node() ausgeführt.

  batch_result:
    Ergebnis der letzten Batch-Execution.
    Format: BatchResult (actions, total_success, total_fail, elapsed_ms)
    Wird von execute_node() gesetzt.
    Wird für completion detection und balance verification genutzt.

  completion_detected:
    Boolean flag ob Survey abgeschlossen ist (completion page, balance erhöht).
    Wird von detect_completion_node() gesetzt.
    True → Graph endet (Status: "completed" oder "screen_out").

  screen_out:
    Boolean flag ob Survey zur screen-out Page navigiert hat (0.02€).
    Wird von detect_completion_node() gesetzt (separate Erkennung von completed).
    True → Status wird "screen_out" (kein echter Verdienst).

  delegation_reason:
    String der erklärt WARUM an opencode CLI delegiert wurde.
    Wird von human_delegate_node() gesetzt.
    Format: "3 consecutive failures at iteration 7: {last_error}"

LEBENSDAUER:
  SurveyState wird einmal pro Survey-Session erstellt und durchläuft
  den gesamten Graph. Es wird NICHT zwischen Sessions geteilt.

ANMERKUNG ZU LANGGRAPH TYPING:
  SurveyState erbt von dict um LangGraph-kompatibel zu sein.
  TypedDict wäre preferiert aber SurveyState nutzt dataclass für
  bessere IDE-Autocomplete und immutability bei einzelnen Feldern.

BANNED METHODS — NIEMALS VERWENDEN:
  ❌ playstealth launch — setzt NICHT --force-renderer-accessibility
  ❌ webauto-nodriver — ABSOLUT BANNED
  ❌ cua-driver click (raw index) — instabil, nutze tool_click.py
  ❌ Hardcoded PIDs — dynamisch, niemals hardcodieren
  ❌ pkill -f "Google Chrome" — tötet USER Chrome
  ❌ killall Google Chrome — tötet ALLE Chrome

DEPENDENCIES:
  - dataclasses.dataclass — SurveyState definition
  - typing — Optional, List, Dict type hints
  - .cdp_client — CDP WebSocket client (Connection, inject_cookies)
  - .chrome — Chrome lifecycle (find_dashboard_ws, is_chrome_alive)
  - .opener — Survey open (SurveyOpener.open → OpenResult.target)
  - .execute — Batch execution (BatchExecutor.execute → BatchResult)
  - .completion_detector — Completion detection
  - .balance_tracker — Balance reading

BEISPIEL-USAGE:
  >>> from survey_cli.survey.graph.state import SurveyState
  >>> state = SurveyState(survey_id="67064749", provider="purespectrum")
  >>> state.status
  'initialized'
  >>> state.tab_ws
  None
  >>> state.iteration
  0

VERWENDUNG IM GRAPH:
  SurveyState ist das einzige Argument das ALLE 6 Nodes bekommen.
  Jeder Node returned eine aktualisierte Kopie (oder modify-in-place).
  LangGraph merged Updates automatisch in den State.

  graph_state_update(state, **update_dict)
  → equivalent to: state.update(update_dict)

================================================================================"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any


@dataclass
class SurveyState:
    """Zentrales State-Objekt für den LangGraph Survey-Agent.

    ALLE Daten die während einer Survey-Session entstehen werden hier
    gekapselt. Keine globalen Variablen, keine Module-Level State.
    Jeder Node bekommt eine Kopie oder modifiziert den State in-place.

    Args:
        survey_id: HeyPiggy Survey-ID (z.B. "67064749")
        provider: Survey-Provider Name (purespectrum, qualtrics, etc.)
        dashboard_ws: CDP WS URL des Dashboard-Tabs (optional, auto-detected)
        tab_ws: CDP WS URL des Survey-Tabs (nach open_survey gesetzt)
        cdp_port: CDP Port des Bot-Chrome (default: 9999)

    Attributes:
        survey_id: HeyPiggy Survey-ID
        tab_ws: CDP WebSocket URL des Survey-Tabs
        dashboard_ws: CDP WebSocket URL des Dashboard-Tabs
        provider: Survey-Provider Name
        cookies_injected: Ob heypiggy-Cookies injiziert wurden
        iteration: NEMO-Loop Iterationszähler (0-indexed)
        max_iterations: Maximale Iterationen (default: 15)
        consecutive_failures: Anzahl direkt aufeinanderfolgender Fehler
        balance_before: Guthaben vor Session (Euro)
        balance_after: Guthaben nach Session (Euro)
        status: Workflow-Status
        errors: Fehler-Historie
        snapshot_refs: @eN Element-Referenzen aus letztem Snapshot
        nim_actions: NIM-Entscheidungen für aktuelle Iteration
        batch_result: Ergebnis der letzten Batch-Execution
        completion_detected: Survey abgeschlossen?
        screen_out: Screen-out Page erreicht?
        delegation_reason: Warum delegiert wurde (wenn delegated)

    Example:
        >>> state = SurveyState(survey_id="67064749", provider="purespectrum")
        >>> state.iteration = 3
        >>> state.consecutive_failures = 2
        >>> state.status = "running"
    """

    # ── Input Fields (set at creation) ──────────────────────────────────────

    survey_id: str = ""
    """HeyPiggy Survey-ID — der Start-Trigger für den gesamten Workflow."""

    provider: str = ""
    """Survey-Provider Name — bestimmt CDP Command Mapping in BatchExecutor."""

    cdp_port: int = 9999
    """CDP Port des Bot-Chrome — HeyPiggy nutzt Port 9999."""

    dashboard_ws: Optional[str] = None
    """CDP WebSocket URL des Dashboard-Tabs. Wird von chrome.find_dashboard_ws()
    auto-detected wenn nicht übergeben. Wird für cookie injection genutzt."""

    survey_url: str = ""
    """Direkte Survey-URL. Optional — wenn gesetzt wird die URL direkt genutzt
    statt via CPX API lookup. Wird von open_survey Node an SurveyOpener.open()
    übergeben. Wird typischerweise von cmd_run via --url Argument gesetzt."""

    # ── Computed Fields (set during graph execution) ─────────────────────────

    tab_ws: Optional[str] = None
    """CDP WebSocket URL des Survey-Tabs. Wird von SurveyOpener.open() gesetzt.
    Format: ws://127.0.0.1:9999/devtools/page/<target_id>

    COOKIE TIMING FIX (2026-05-10):
    Bei 'in_dashboard' mode ist tab_ws == dashboard_ws (dieselbe Tab!).
    Das ist korrekt — die Tab hat bereits Session-Cookies."""

    target_mode: str = "new_tab"
    """Modus des Survey-Tabs — gesteuert von SurveyOpener.SurveyTarget.mode.
    Werte: 'new_tab' (Target.createTarget, braucht cookie injection)
           'in_page' (Survey öffnet sich im Dashboard, kein cookie injection)
           'redirect' (neuer Tab nach window.open interception)
           'in_dashboard' (Dashboard-Tab navigiert zu Survey-URL — keine
               cookie injection nötig da Tab bereits cookies hat!)
    Wird von open_survey node gesetzt und von inject_cookies node gelesen."""

    cookies_injected: bool = False
    """Flag ob heypiggy Session-Cookies in den Survey-Tab injiziert wurden.
    KRITISCH: Survey-Tabs ohne diese Cookies werden von CPX redirected
    und verdienen €0. Wird nach Network.setCookies auf True gesetzt."""

    iteration: int = 0
    """NEMO-Loop Iterationszähler (0-indexed).
    Wird nach jedem snapshot+execute inkrementiert.
    iteration > max_iterations = Graph endet mit error.
    iteration > 10 = wahrscheinlich stuck (log + warn)."""

    max_iterations: int = 15
    """Maximale Anzahl NEMO-Loop-Durchläufe.
    15 Iterationen = genug für 30+ Seiten typical survey.
    Nach Erreichen: Status='error' (nicht delegated)."""

    consecutive_failures: int = 0
    """Anzahl direkt aufeinanderfolgender failed Batch-Executions.
    Wird nach jedem execute inkrementiert.
    Wird nach erfolgreichem execute auf 0 resetiert.
    TRIGGER: consecutive_failures >= 3 → human_delegate() wird aufgerufen."""

    balance_before: float = 0.0
    """Guthabenstand in Euro VOR der Survey-Session.
    Wird von balance_tracker oder direct CDP page read gesetzt.
    Dient der Verification: balance_after > balance_before = Erfolg."""

    balance_after: float = 0.0
    """Guthabenstand in Euro NACH der Survey-Session.
    Wird von balance_tracker nach detect_completion gelesen.
    balance_after - balance_before = verdientes Geld."""

    status: str = "initialized"
    """Aktueller Workflow-Status — steuert welche Node als nächstes läuft.
    Mögliche Werte:
      'initialized'   — Graph gestartet, Chrome/Tab noch nicht bereit
      'chrome_ready'  — Chrome läuft, Dashboard bereit
      'tab_open'      — Survey-Tab geöffnet, cookies noch nicht injiziert
      'cookies_injected' — Session-Cookies injiziert, Survey bereit
      'running'       — NEMO-Loop aktiv (snapshot → NIM → execute)
      'screen_out'    — Survey beendet (0.02€ oder disqualifiziert)
      'completed'     — Survey beendet (€ verdient)
      'error'         — Schwerer Fehler (Chrome tot, CDP kaputt, etc.)
      'delegated'     — An opencode CLI übergeben (3× failures)
    """

    errors: List[Dict[str, Any]] = field(default_factory=list)
    """Fehler-Historie — Liste aller Fehler während der Session.
    Format: [{"node": str, "error": str, "iteration": int, "ts": float}]
    Wird nach jedem Node-Execution angehängt.
    Dient der post-Session-Analyse und learn.md updates."""

    snapshot_refs: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    """@eN Element-Referenzen aus dem letzten Compact Snapshot.
    Format: {"@e0": {"role": "radio", "text": "Männlich", "idx": 0}, ...}
    Wird von snapshot_node() gesetzt.
    Wird von execute_node() für provider-spezifisches JS-Matching genutzt.
    Wird von decide_node() an NIM übergeben."""

    nim_actions: List[Dict[str, Any]] = field(default_factory=list)
    """NIM-NEMOTRON-Entscheidungen für die aktuelle Iteration.
    Format: [{"ref": "@e0", "action": "select"}, {"action": "submit"}]
    Wird von decide_node() gesetzt.
    Wird von execute_node() ausgeführt.
    Empty = keine Actions nötig (z.B. wait page)."""

    batch_result: Optional[Dict[str, Any]] = None
    """Ergebnis der letzten Batch-Execution.
    Format: {"actions": [...], "total_success": int, "total_fail": int,
             "elapsed_ms": float}
    Wird von execute_node() gesetzt.
    Wird für completion detection und balance verification genutzt."""

    completion_detected: bool = False
    """Flag ob Survey abgeschlossen ist (completion page oder balance erhöht).
    Wird von detect_completion_node() gesetzt.
    True → SurveyNode endet den Graph (Status: completed oder screen_out)."""

    screen_out: bool = False
    """Flag ob Survey zur screen-out Page navigiert hat (0.02€, disqualifiziert).
    Wird von detect_completion_node() gesetzt.
    True → Status wird 'screen_out' (kein echter Verdienst).
    Wird SEPARAT von completion_detected gehandhabt."""

    delegation_reason: str = ""
    """Erklärung WARUM an opencode CLI delegiert wurde.
    Wird von human_delegate_node() gesetzt.
    Format: "3 consecutive failures at iteration 7: {last_error_message}"
    Wird für Reporting und learn.md docs genutzt."""

    # ── KANONISCHE PIPELINE FELDER (2026-05-11) ──────────────────────────────
    # Diese Felder ersetzen funktional snapshot_refs + nim_actions wenn der
    # Graph auf die v2-Pipeline (cdp_universal + cdp_actuator + captcha_router)
    # umgestellt ist. snapshot_refs/nim_actions bleiben für Backward-Compat
    # vorhanden — neuer Code MUSS aber universal_elements/decision benutzen.
    #
    # Siehe AGENTS.md "KANONISCHE ARCHITEKTUR (2026-05-11)" und die Module
    # survey-cli/survey/cdp_universal.py + cdp_actuator.py + captcha_router.py.

    universal_elements: List[Dict[str, Any]] = field(default_factory=list)
    """Flache Liste von UniversalElement-Dicts aus cdp_universal.scan().
    Jedes Element: {stable_id, frame_id, role, name, value, tag, text,
                    state, bbox, attrs, frame_url}
    Wird von snapshot_node() gesetzt (ab v2-Pipeline).
    Wird von decide_node() für LLM/Heuristik-Auswahl genutzt.
    stable_id ist der EINZIGE legitime Identifier für click/fill — niemals
    Index oder CSS-Selektor mehr."""

    captcha_frames: List[Dict[str, str]] = field(default_factory=list)
    """Liste der iframes deren URL nach Captcha-Provider aussieht.
    Jedes Element: {frame_id, url}
    Wird von snapshot_node() gesetzt.
    Wird von captcha_node() als Trigger genutzt.
    Detection-Patterns siehe captcha_router.IFRAME_URL_TO_TYPE."""

    last_action_result: Dict[str, Any] = field(default_factory=dict)
    """Result der letzten Aktuator-Aktion (click/fill/press_key).
    Format: {success, reason, before_hash, after_hash, new_url, elapsed_ms,
             stable_id, action_type}
    Wird von execute_node() gesetzt.
    Wird von detect_completion_node() für Navigation-Detection genutzt.
    success=False mit reason='no_dom_change' → wichtigster Indikator dass
    der Klick KEINE Wirkung hatte (= alter Halluzinations-Fall, jetzt sichtbar)."""

    no_dom_change_count: int = 0
    """Anzahl direkt aufeinanderfolgender Aktionen mit reason='no_dom_change'.
    Wird in execute_node() inkrementiert/resetet.
    TRIGGER: no_dom_change_count >= 2 → decide_node MUSS anderes Element wählen
    (Hint wird im next decide_node-Aufruf gesetzt).
    Schutz gegen Endlos-Klick-Loop (Issue #24 anti-stuck loop)."""

    decision: Dict[str, Any] = field(default_factory=dict)
    """Aktuelle Entscheidung des decide_node — ein einziger atomarer Schritt.
    Format: {action: "click"|"fill"|"press_key"|"submit"|"wait"|"done",
             stable_id: str (für click/fill), value: str (für fill),
             key: str (für press_key), reason: str (Begründung der Wahl)}
    Wird von decide_node() gesetzt.
    Wird von execute_node() ausgeführt.
    KEINE Listen mehr — jede Iteration GENAU EINE Aktion. Verifyable."""

    captcha_solved_this_iteration: bool = False
    """Flag ob in dieser Iteration ein Captcha gelöst wurde.
    Wird von captcha_node() auf True gesetzt.
    Wird vor nächster Iteration auf False resetet.
    Dient als Hint für decide_node (Page-Refresh erwartet)."""

    # ══════════════════════════════════════════════════════════════════════════
    # DRAG-DROP DETECTION (2026-05-11)
    # ══════════════════════════════════════════════════════════════════════════

    drag_drop_detected: bool = False
    """Flag ob ein Drag-Drop Puzzle auf der aktuellen Seite erkannt wurde.
    Wird von snapshot_node gesetzt wenn:
      - Angular CDK .cdk-drag/.cdk-drop-list Elemente existieren UND
      - Text-Cue wie 'Bitte legen Sie die Zahl X' gefunden wurde
    Triggert sofortige captcha_node Aktivierung (ohne 2x no_dom_change wait)."""

    drag_drop_target: Optional[str] = None
    """Die Ziel-Zahl für das Drag-Drop Puzzle (z.B. '52', '20').
    Wird aus dem Page-Text extrahiert via Regex.
    Wird an den Angular-Drag-Drop-Solver übergeben."""

    # ══════════════════════════════════════════════════════════════════════════
    # ACTION RECIPE CACHE (SR-243 / SR-244 / SR-245)
    # ══════════════════════════════════════════════════════════════════════════

    recipe_replay_attempted: bool = False
    """Flag the decide_node read-hook flips True the moment it replays a
    cached recipe instead of paying for NIM. The same-iteration
    execute_node will invalidate the recipe if the click did nothing
    (no_dom_change), and the next iteration's should_consult_cache()
    refuses to consult while this flag is True — anti-loop guard.
    Reset by snapshot_node at the top of every iteration."""


    # ── Property Helpers ─────────────────────────────────────────────────────

    @property
    def is_running(self) -> bool:
        """True wenn Graph noch aktiv ist (nicht completed/error/delegated)."""
        return self.status in (
            "initialized", "chrome_ready", "tab_open",
            "cookies_injected", "running"
        )

    @property
    def is_terminal(self) -> bool:
        """True wenn Graph in einem Endzustand ist."""
        return self.status in (
            "completed", "screen_out", "error", "delegated"
        )

    @property
    def should_delegate(self) -> bool:
        """True wenn 3+ consecutive failures erreicht wurden."""
        return self.consecutive_failures >= 3

    @property
    def balance_earned(self) -> float:
        """Berechneter Verdienst: balance_after minus balance_before."""
        return round(self.balance_after - self.balance_before, 2)

    # ── State Mutation Helpers ───────────────────────────────────────────────

    def add_error(self, node: str, error: str) -> None:
        """Füge einen Fehler zur errors-Liste hinzu.

        Args:
            node: Name der Node die den Fehler verursacht hat
            error: Fehlermeldung (max 500 Zeichen)
        """
        import time
        self.errors.append({
            "node": node,
            "error": error[:500],
            "iteration": self.iteration,
            "ts": time.time(),
        })

    def reset_failures(self) -> None:
        """Reset consecutive_failures auf 0 nach erfolgreichem execute."""
        self.consecutive_failures = 0

    def increment_failures(self) -> None:
        """Inkrementiere consecutive_failures nach failed execute."""
        self.consecutive_failures += 1

    def increment_iteration(self) -> None:
        """Inkrementiere iteration nach NEMO-Loop-Durchlauf."""
        self.iteration += 1

    def __repr__(self) -> str:
        """Kompakte String-Repräsentation für Debugging."""
        return (
            f"SurveyState("
            f"id={self.survey_id[:8]}, "
            f"provider={self.provider}, "
            f"iter={self.iteration}, "
            f"fails={self.consecutive_failures}, "
            f"status={self.status}, "
            f"earned=€{self.balance_earned}"
            f")"
        )
