"""================================================================================
SURVEY GRAPH — LangGraph StateGraph für Survey-Orchestration
================================================================================

WAS IST DAS?
  LangGraph StateGraph der den kompletten Survey-Workflow orchestriert.
  8 Nodes werden via Conditional Edges verbunden — der Graph entscheidet
  autonom was als nächstes passiert basierend auf dem State.

ARCHITEKTUR:
  ┌─────────────────────────────────────────────────────────────────────────┐
  │                    LANGGRAPH STATEGRAPH                                 │
  ├─────────────────────────────────────────────────────────────────────────┤
  │                                                                          │
  │  START                                                                  │
  │    │                                                                    │
  │    ▼                                                                    │
  │  ensure_chrome ──→ [chrome error] ──────────────────────────── END     │
  │    │                                                                    │
  │    ▼                                                                    │
  │  read_balance_before ─────────────────────────────────────────────       │
  │    │                                                                    │
  │    ▼                                                                    │
  │  open_survey ────→ [screen_out] ───────────────────────────── END     │
  │    │              └──→ [open error] ─────────────────────────── END    │
  │    ▼                                                                    │
  │  inject_cookies ──→ [injection error] ──────────────────────── END     │
  │    │                                                                    │
  │    ▼                                                                    │
  │  snapshot ─────────────────────────────────────────────────┐            │
  │    │                                                     │            │
  │    ▼                                                     │            │
  │  decide ─────────────────────────────────────────────────┐│            │
  │    │                                                     ││            │
  │    ▼                                                     ││            │
  │  execute ───────────────────────────────────────────────┐││            │
  │    │                                                     │││            │
  │    │                                                     │││            │
  │    └──→ detect_completion ──→ read_balance_after ──→ [conditional]   │
  │                               │                                           │
  │                               │                                           │
  │                          [continue]                                     │
  │                               │                                           │
  │                               ▼                                           │
  │                    ┌───────────────────────┐                           │
  │                    │   ROUTE (conditional)  │                           │
  │                    │                       │                           │
  │                    │  3× failures?  ──→ human_delegate ──→ END         │
  │                    │  max_iterations? ──→ END                         │
  │                    │  else ──────────────→ snapshot (next iter)       │
  │                    └───────────────────────┘                           │
  │                                                                          │
  └─────────────────────────────────────────────────────────────────────────┘

CONDITIONAL EDGE ROUTING (route()):

  Die route()-Funktion ist das "Gehirn" des Graph. Sie entscheidet
  basierend auf dem aktuellen State was als nächstes passiert.

  Priority-Order (wichtig!):
    1. is_terminal (completed/error/delegated/screen_out) → END
    2. should_delegate (consecutive_failures >= 3) → human_delegate
    3. iteration >= max_iterations → END
    4. else → snapshot (continue NEMO loop)

  Warum diese Reihenfolge?
    - Terminal-Zustand zuerst → kein weiterer Loop nötig
    - Delegate vor Iteration-Check → echte Probleme zuerst eskalieren
    - Iteration-Check als Safety-Net → verhindert Endlos-Loops

NODE DEFINITIONS (8 nodes):

  ensure_chrome   → Chrome starten/verifizieren (nodes.ensure_chrome)
  open_survey     → Survey-Tab öffnen (nodes.open_survey)
  inject_cookies  → Heypiggy-Cookies injizieren (nodes.inject_cookies)
  snapshot        → Compact DOM-Snapshot (nodes.snapshot_node)
  decide          → NIM Decision (nodes.decide_node)
  execute         → Batch-Ausführung (nodes.execute_node)
  detect_completion → Completion-Detection (nodes.detect_completion)
  human_delegate  → An opencode CLI eskalieren (nodes.human_delegate)

START-ZUSTAND:
  state = SurveyState(survey_id="...", provider="...", cdp_port=9999)

KOMMENTIERUNG:
  Jede Edge und jede Condition ist dokumentiert mit:
  - WARUM diese Edge existiert
  - Was passiert wenn die Condition true ist
  - Was passiert wenn die Condition false ist

BANNED METHODS — NIEMALS VERWENDEN:
  ❌ playstealth launch — setzt NICHT --force-renderer-accessibility
  ❌ webauto-nodriver — ABSOLUT BANNED
  ❌ cua-driver click (raw index) — instabil, nutze tool_click.py
  ❌ Hardcoded PIDs — dynamisch, niemals hardcodieren
  ❌ pkill -f "Google Chrome" — tötet USER Chrome
  ❌ killall Google Chrome — tötet ALLE Chrome

DEPENDENCIES:
  - langgraph: StateGraph, START, END
  - .state.SurveyState — GraphState
  - .nodes: Alle 8 Node-Funktionen

================================================================================"""

from __future__ import annotations

from typing import Literal

from .state import SurveyState
from .nodes import (
    ensure_chrome,
    open_survey,
    inject_cookies,
    snapshot_node,
    captcha_node,        # 2026-05-11 NEU: Captcha-Detection + Solve
    decide_node,
    execute_node,
    detect_completion,
    read_balance_before,
    read_balance_after,
    human_delegate,
)

# LangGraph Import — graceful degradation wenn nicht installiert
# CRITICAL FIX: langgraph ist in .venv installiert, aber System-Python 3.14
# sieht es nicht. Wir versuchen den .venv Path hinzuzufügen.
import sys
import os

# Versuche .venv Path zur Sicherheit hinzuzufügen
_VENV_SITE_PACKAGES = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))),
    ".venv", "lib", "python3.12", "site-packages"
)
if os.path.isdir(_VENV_SITE_PACKAGES) and _VENV_SITE_PACKAGES not in sys.path:
    sys.path.insert(0, _VENV_SITE_PACKAGES)

# Auch alternativen Python-Pfad versuchen
_VENV_SITE_PACKAGES_ALT = "/Users/jeremy/dev/stealth-runner/.venv/lib/python3.12/site-packages"
if os.path.isdir(_VENV_SITE_PACKAGES_ALT) and _VENV_SITE_PACKAGES_ALT not in sys.path:
    sys.path.insert(0, _VENV_SITE_PACKAGES_ALT)

try:
    from langgraph.graph import StateGraph, START, END

    LANGGRAPH_AVAILABLE = True
except ImportError:
    LANGGRAPH_AVAILABLE = False


# ── CORE INTEGRATION ──────────────────────────────────────────────────────────
# Core-Module (Issue #81/#82/#83). Wenn core/ am repo-root liegt, koennen wir
# es importieren — sonst laufen die Nodes UNGESCHUETZT (Backward-Compat fuer
# Lokale Test-Runs ohne core/).
#
# Was core hier macht:
#   - sync_node_with_core: wrappt jede Node mit budget-guard, error-handler,
#     analytics, screenshot-on-failure, state-tracking
#   - run_survey_with_core: bootstrapt core, attached SurveyState._core_ctx,
#     ruft run_survey_loop, persistiert final-checkpoint
#
# Wenn core import failed: nodes laufen wie vorher (no-op wrapper).

try:
    # Repo-Root in sys.path haengen, sodass `import core` funktioniert.
    _REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))
    )))
    if _REPO_ROOT not in sys.path:
        sys.path.insert(0, _REPO_ROOT)
    from core.langgraph_integration import (
        sync_node_with_core,
        run_survey_with_core,
    )
    from core import (
        # SR-106: bootstrap_core is an intentional availability-probe import.
        # It's referenced in the module docstring at the bottom as a documented
        # capability (FS-Layout setup). The try/except ImportError surrounding
        # this block uses successful import as the CORE_AVAILABLE flag; removing
        # bootstrap_core would weaken that signal even though it's not directly
        # called from this module.
        bootstrap_core,  # noqa: F401
        BudgetExceededError,
    )
    CORE_AVAILABLE = True
except ImportError as _core_err:
    CORE_AVAILABLE = False
    # Fallback: identity wrapper, kein Schutz, aber Code laeuft.
    def sync_node_with_core(name, func, **_kw):  # type: ignore[no-redef]
        return func
    def run_survey_with_core(state, *, run_fn, **_kw):  # type: ignore[no-redef]
        return run_fn(state)
    class BudgetExceededError(Exception):  # type: ignore[no-redef]
        pass


# ── ROUTING FUNCTION ───────────────────────────────────────────────────────────
# Funktion: route() — Conditional Edge Routing
# Args:     state: SurveyState
# Returns:  str — next node name oder "END"
# Lines:    ~20
#
# Routing-Priority (in dieser Reihenfolge prüfen!):
#   1. is_terminal → END
#   2. should_delegate (>= 3 failures) → human_delegate
#   3. iteration >= max_iterations → END
#   4. else → "snapshot"


def route(state: SurveyState) -> Literal[
    "snapshot", "human_delegate", "END"
]:
    """Entscheide welche Node als nächstes ausgeführt wird.

    Dies ist das zentrale Routing "Gehirn" des Graph. Nach jedem
    execute + detect_completion wird diese Funktion aufgerufen.

    Routing-Priority (CRITICAL — in dieser Reihenfolge prüfen!):

      1. is_terminal
         → state.status in {completed, screen_out, error, delegated}
         → END (Graph beendet, kein weiterer Loop)
         → Warum zuerst? Terminal-Zustand = Survey fertig oder kaputt.
           Kein weiterer Loop nötig.

      2. should_delegate (consecutive_failures >= 3)
         → human_delegate (Escalation an opencode CLI)
         → Warum vor iteration-Check? Echte Probleme zuerst eskalieren.
           3× failures = Browser-/Provider-Problem, kein Loop-Problem.

      3. iteration >= max_iterations
         → END (Safety-Net gegen Endlos-Loop)
         → Warum nach delegate? Iteration-Limit ist weniger wichtig
           als echte Probleme zu eskalieren.
         → 15 Iterationen = ~45+ Seiten typical survey, mehr = stuck.

      4. else
         → "snapshot" (NEMO Loop fortsetzen)
         → WICHTIG: snapshot-NODE inkrementiert iteration danach!

    Args:
        state: SurveyState mit status, consecutive_failures, iteration

    Returns:
        "snapshot" → NEMO Loop fortsetzen ( nächste Iteration)
        "human_delegate" → An opencode CLI eskalieren
        "END" → Graph beendet

    Example:
        >>> state = SurveyState(iteration=2, consecutive_failures=1)
        >>> route(state)
        'snapshot'

        >>> state = SurveyState(iteration=7, consecutive_failures=3)
        >>> route(state)
        'human_delegate'
    """
    # Priority 1: Terminal-Zustand → END
    if state.is_terminal:
        return "END"

    # Priority 2: 3× failures → delegate
    if state.should_delegate:
        return "human_delegate"

    # Priority 3: Iteration-Limit erreicht → END
    if state.iteration >= state.max_iterations:
        return "END"

    # Priority 4: Normaler Loop → snapshot (continue)
    return "snapshot"


# ── GRAPH BUILDER ──────────────────────────────────────────────────────────────


def build_graph() -> StateGraph:
    """Baue den Survey-StateGraph.

    Graph-Struktur:
      START → ensure_chrome → read_balance_before → open_survey → inject_cookies
            → snapshot → decide → execute → detect_completion → read_balance_after
            → [conditional routing via route()]
              ├── snapshot (continue)
              ├── human_delegate (3× failures)
              └── END (terminal/max_iterations)

    Jede Node bekommt den aktuellen State und returned den updated State.
    LangGraph merged die Updates automatisch in den State.

    Returns:
        Compiled StateGraph (zustandslos, wiederverwendbar)

    Note:
        graph = build_graph() → compiled = graph.compile()
        compiled.invoke(initial_state) → final_state
    """
    if not LANGGRAPH_AVAILABLE:
        raise ImportError(
            "langgraph is not installed. "
            "Install with: pip install langgraph"
        )

    # Schritt 1: StateGraph mit SurveyState als Schema erstellen
    # We use dict as schema for LangGraph compatibility
    graph = StateGraph(state_schema=SurveyState)

    # Schritt 2: Nodes hinzufügen — JEDE NODE wird mit sync_node_with_core
    # gewrappt. Das injiziert:
    #   - Survey-Budget-Guard (BudgetExceededError nach 120s default)
    #   - error_handler._record_failure/_record_success
    #   - analytics counter + duration histogram
    #   - state_manager.start_step/complete_step/fail_step
    #   - capture_failure() Screenshot wenn config.enable_screenshots_on_error
    # Wenn core nicht verfuegbar ist, ist sync_node_with_core ein no-op
    # identity wrapper (siehe oben CORE_AVAILABLE branch).
    graph.add_node("ensure_chrome",
                   sync_node_with_core("ensure_chrome", ensure_chrome,
                                       capture_screenshot_on_fail=False))
    graph.add_node("read_balance_before",
                   sync_node_with_core("read_balance_before", read_balance_before))
    graph.add_node("open_survey",
                   sync_node_with_core("open_survey", open_survey))
    graph.add_node("inject_cookies",
                   sync_node_with_core("inject_cookies", inject_cookies,
                                       capture_screenshot_on_fail=False))
    graph.add_node("snapshot",
                   sync_node_with_core("snapshot", snapshot_node))
    # 2026-05-11: Captcha-Detection laeuft NACH snapshot, VOR decide.
    # NO-OP wenn keine Captcha-iframes UND no_dom_change_count < 2.
    graph.add_node("captcha",
                   sync_node_with_core("captcha", captcha_node))
    graph.add_node("decide",
                   sync_node_with_core("decide", decide_node))
    graph.add_node("execute",
                   sync_node_with_core("execute", execute_node))
    graph.add_node("detect_completion",
                   sync_node_with_core("detect_completion", detect_completion))
    graph.add_node("read_balance_after",
                   sync_node_with_core("read_balance_after", read_balance_after))
    graph.add_node("human_delegate",
                   sync_node_with_core("human_delegate", human_delegate,
                                       capture_screenshot_on_fail=False))

    # Schritt 3: Start-Edge (START → ensure_chrome)
    graph.add_edge(START, "ensure_chrome")

    # Schritt 4: Setup-Edges (linear, kein Routing)
    # Diese Edges laufen IMMER in der gleichen Reihenfolge.
    # Kein Conditional — jede Node muss erfolgreich sein.
    graph.add_edge("ensure_chrome", "read_balance_before")
    graph.add_edge("read_balance_before", "open_survey")
    graph.add_edge("open_survey", "inject_cookies")
    graph.add_edge("inject_cookies", "snapshot")

    # Schritt 5: NEMO-Loop Edge (snapshot → decide → execute → detect_completion)
    # Nach detect_completion wird route() aufgerufen für conditional routing.
    # NEMO-Loop NEU: snapshot → captcha (no-op meistens) → decide → execute
    graph.add_edge("snapshot", "captcha")
    graph.add_edge("captcha", "decide")
    graph.add_edge("decide", "execute")
    graph.add_edge("execute", "detect_completion")

    # Schritt 5b: Balance nach Survey lesen (nach detect_completion, vor Routing)
    graph.add_edge("detect_completion", "read_balance_after")

    # Schritt 6: Conditional Edge nach read_balance_after
    # route() entscheidet ob: snapshot (continue) | human_delegate | END
    graph.add_conditional_edges(
        "read_balance_after",
        route,
        {
            "snapshot": "snapshot",        # Continue: NEMO Loop
            "human_delegate": "human_delegate",  # Escalation
            "END": END,                    # Terminal
        },
    )

    # Schritt 7: human_delegate → END (nach Delegation immer END)
    graph.add_edge("human_delegate", END)

    return graph


# ── COMPILED GRAPH FACTORY ───────────────────────────────────────────────���─────


def create_graph(*, checkpointer: Any = None, with_checkpoint: bool = True):
    """Factory: Erstelle und kompiliere den Survey-Graph.

    Convenience-Wrapper für:
      graph = build_graph()
      compiled = graph.compile(checkpointer=...)
      return compiled

    Args:
        checkpointer: Optionales LangGraph BaseCheckpointSaver. Wenn None
            und with_checkpoint=True, wird ein SqliteSaver via
            `survey.graph.checkpointer.create_sqlite_checkpointer()`
            angelegt (DB unter $STATE_DIR/langgraph_checkpoints.db).
        with_checkpoint: Wenn False, wird der Graph ohne Checkpointing
            kompiliert — Backwards-compat für Tests und für Hosts ohne
            langgraph[sqlite] extras.

    Returns:
        Compiled Graph — `compiled.invoke(state, config=...)` → final_state.

    Resume-Semantik (SR-238):
        Beim invoke MUSS jetzt ein `config={"configurable": {"thread_id":
        ...}}` mitgegeben werden, damit der Checkpointer den passenden
        Thread anhebt. `survey.graph.checkpointer.make_run_config(state)`
        baut den Config-Dict deterministisch aus survey_id + provider.

    Example:
        >>> from survey.graph.checkpointer import make_run_config
        >>> survey_graph = create_graph()
        >>> initial = SurveyState(survey_id="67064749", provider="purespectrum")
        >>> final = survey_graph.invoke(initial, config=make_run_config(initial))
        >>> final.status
        'completed'
    """
    if not LANGGRAPH_AVAILABLE:
        raise ImportError(
            "langgraph is not installed. "
            "Install with: pip install langgraph"
        )
    _graph = build_graph()

    saver: Any = checkpointer
    if saver is None and with_checkpoint:
        try:
            from .checkpointer import create_sqlite_checkpointer

            saver = create_sqlite_checkpointer()
        except Exception:
            # Defensive: any failure to materialise the saver falls back
            # to the historic non-checkpointed compile path.
            saver = None

    if saver is None:
        return _graph.compile()
    return _graph.compile(checkpointer=saver)


# ── STANDALONE RUNNER (ohne LangGraph) ────────────────────────────────────────
# Falls LangGraph nicht installiert ist, fallback auf simpler Loop-Runner.
# Dieselbe Logik wie der Graph, aber ohne LangGraph-Overhead.


def run_survey_loop(state: SurveyState) -> SurveyState:
    """Standalone Survey-Loop ohne LangGraph.

    Fallback für Umgebungen wo LangGraph nicht installiert ist.
    Implementiert dieselbe Logik wie der kompilierte Graph:
      1. Balance lesen (balance_before)
      2. ensure_chrome
      3. open_survey
      4. inject_cookies
      5. NEMO Loop: snapshot → decide → execute → detect_completion
      6. Routing: continue / delegate / END
      7. Balance lesen (balance_after)

    Args:
        state: SurveyState mit survey_id, provider, cdp_port

    Returns:
        Finaler State nach Graph-Execution

    Note:
        Identisch zu: create_graph().invoke(state)
    """
    # Phase 1: Setup
    state = ensure_chrome(state)
    if state.status == "error":
        return state

    state = read_balance_before(state)

    state = open_survey(state)
    if state.status in ("screen_out", "error"):
        return state

    state = inject_cookies(state)
    if state.status == "error":
        return state

    # Phase 2: NEMO Loop
    while not state.is_terminal:
        # Snapshot machen (NEMO Schritt 1)
        state = snapshot_node(state)
        if state.status == "error":
            break

        # NEU 2026-05-11: Captcha-Detection vor decide.
        # NO-OP wenn keine Captcha-iframes und no_dom_change_count < 2.
        state = captcha_node(state)

        # Iteration inkrementieren (NEMO Schritt 2)
        state.increment_iteration()

        # decide (Heuristik oder LLM)
        state = decide_node(state)

        # Execute decision (auch "wait" wird sauber gehandelt in execute_node)
        state = execute_node(state)
        state = detect_completion(state)
        state = read_balance_after(state)

        # Routing
        next_node = route(state)
        if next_node == "END":
            break
        elif next_node == "human_delegate":
            state = human_delegate(state)
            break
        # else: continue to next iteration (loop)

    return state


# ── PROTECTED RUNNER (Empfohlener Public Entrypoint) ──────────────────────────


def run_survey_protected(
    state: SurveyState,
    *,
    use_langgraph: bool = True,
    max_seconds: float | None = None,
) -> SurveyState:
    """Empfohlener PUBLIC-Entrypoint. Faehrt eine Survey mit FULL CORE PROTECTION
    durch (budget-guard, error-handler, analytics, screenshots, audit-log).

    Was passiert hier?
      1. core.bootstrap_core() — FS-Layout (state/, screenshots/, audit-logs/)
      2. core.attach_core_ctx() — SurveyBudget(120s) + alle core-Services
         an state._core_ctx (jede Node greift darauf zu)
      3. Run loop:
           - use_langgraph=True  → create_graph().invoke(state)  (preferred)
           - use_langgraph=False → run_survey_loop(state)        (fallback)
      4. Auto-Persist: budget snapshot + survey metadata via
         StateManager.save_checkpoint(run_id, ...)

    GARANTIEN:
      - Survey laeuft NIE laenger als max_seconds (default 120s)
      - Bei jedem Node-Failure wird ein Screenshot gemacht (sofern
        config.enable_screenshots_on_error=True)
      - Alle Errors werden in errors/ persistiert (state.errors[] + JSON)
      - Analytics werden nach jedem Run in state/analytics_*.json geflusht

    Args:
        state:         Initialer SurveyState
        use_langgraph: LangGraph (True, default) oder Manual-Loop (False)
        max_seconds:   Survey-Budget Override (None → core.config.budget.max_seconds)

    Returns:
        Finaler SurveyState mit:
          state.status        ∈ {completed, screen_out, error, delegated, error}
          state._core_ctx     CoreCtx mit budget.snapshot()
          state.balance_after gefuelt fuer ROI-Tracking

    Beispiel:
        >>> from survey.graph.state import SurveyState
        >>> from survey.graph.graph import run_survey_protected
        >>> state = SurveyState(survey_id="67064749", provider="heypiggy")
        >>> final = run_survey_protected(state, max_seconds=120)
        >>> print(final.status, final.balance_after - final.balance_before)
    """
    if use_langgraph and LANGGRAPH_AVAILABLE:
        compiled = create_graph()
        # SR-238: deterministic thread_id so a crash + resume picks up
        # exactly where the previous attempt left off, with no double
        # cash-out (see SR-237 ledger for the side-effect side of this).
        from .checkpointer import make_run_config

        run_config = make_run_config(state)

        def _run(s):
            # LangGraph kennt unsere CoreCtx-Attribute nicht — bei dict-state
            # waere das ein Problem, aber wir nutzen SurveyState (dataclass)
            # die Attribute behaelt. LangGraph macht aber eine Kopie pro
            # Node — wir muessen sicherstellen, dass _core_ctx persistiert.
            # Die SurveyState-class hat _core_ctx als Plain-Attribut, das
            # bei dataclass.replace() copied wird.
            return compiled.invoke(s, config=run_config)
        return run_survey_with_core(state, run_fn=_run, max_seconds=max_seconds)
    return run_survey_with_core(state, run_fn=run_survey_loop,
                                 max_seconds=max_seconds)
