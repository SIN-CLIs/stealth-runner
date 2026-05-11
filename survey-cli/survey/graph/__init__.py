"""================================================================================
SURVEY GRAPH — Öffentliche API
================================================================================

WAS IST DAS?
  survey_cli.survey.graph Modul — öffentlicher Entry-Point für den
  LangGraph Survey-Agent. Exponiert alle relevanten Klassen und
  Funktionen für externe Nutzung.

ARCHITEKTUR:
  survey_cli/
  └── survey/
      └── graph/              ← DIESES MODUL
          ├── __init__.py     ← PUBLIC API (dieses File)
          ├── state.py        ← SurveyState (GraphState)
          ├── nodes.py        ← 8 Graph Nodes
          ├── graph.py        ← StateGraph Builder + Compiler
          └── opencode_tool.py ← CLI Delegation

ÖFFENTLICHE API:
  from survey_cli.survey.graph import (
      SurveyState,        # State-Objekt für Graph-Execution
      create_graph,       # Kompilierter Graph (invoke-able)
      build_graph,        # Un-kompilierter Graph-Builder
      run_survey_loop,    # Standalone Loop (ohne LangGraph)
      delegate_task,      # opencode CLI Delegation
      SurveyGraphError,   # Exception Klasse
  )

USAGE PATTERNS:

  Pattern 1: LangGraph Pipeline (Production)
    >>> from survey_cli.survey.graph import create_graph, SurveyState
    >>> graph = create_graph()
    >>> state = SurveyState(survey_id="67064749", provider="purespectrum")
    >>> final = graph.invoke(state)
    >>> print(f"Status: {final.status}, Earned: €{final.balance_earned}")

  Pattern 2: Standalone Loop (Fallback, keine LangGraph nötig)
    >>> from survey_cli.survey.graph import run_survey_loop, SurveyState
    >>> state = SurveyState(survey_id="67064749", provider="purespectrum")
    >>> final = run_survey_loop(state)
    >>> print(f"Status: {final.status}")

  Pattern 3: Einzelne Nodes (für Testing/Debugging)
    >>> from survey_cli.survey.graph.nodes import ensure_chrome
    >>> state = SurveyState(cdp_port=9999)
    >>> state = ensure_chrome(state)
    >>> print(f"Chrome: {state.dashboard_ws}")

  Pattern 4: Delegation Manual
    >>> from survey_cli.survey.graph import delegate_task
    >>> result = delegate_task(
    ...     survey_id="67064749",
    ...     provider="purespectrum",
    ...     reason="3 consecutive failures at iteration 4",
    ...     tab_ws="ws://127.0.0.1:9999/devtools/page/42",
    ...     iteration=4,
    ... )
    >>> print(f"Delegation: {result['status']}")

  Pattern 5: Graph als Tool in FastAPI
    >>> from survey_cli.survey.graph import create_graph, SurveyState
    >>> @router.post("/survey/run")
    ... async def run_survey(req: SurveyRequest):
    ...     graph = create_graph()
    ...     state = SurveyState(survey_id=req.survey_id, provider=req.provider)
    ...     result = await asyncio.to_thread(graph.invoke, state)
    ...     return {"status": result.status, "earned": result.balance_earned}

LANGGRAPH REQUIREMENT:
  LangGraph muss installiert sein für create_graph() und build_graph().
  run_survey_loop() funktioniert auch ohne LangGraph als Fallback.

  Installation:
    pip install langgraph

KOMPATIBILITÄT:
  - Python 3.10+
  - survey-cli (lokales Modul)
  - LangGraph (optional, für Graph-Compiler)
  - websocket-client (für CDP)

BANNED METHODS — NIEMALS VERWENDEN:
  ❌ playstealth launch — setzt NICHT --force-renderer-accessibility
  ❌ webauto-nodriver — ABSOLUT BANNED
  ❌ cua-driver click (raw index) — instabil, nutze tool_click.py
  ❌ Hardcoded PIDs — dynamisch, niemals hardcodieren
  ❌ pkill -f "Google Chrome" — tötet USER Chrome
  ❌ killall Google Chrome — tötet ALLE Chrome

INTEGRATION CHECKLISTE:
  □ Importiere SurveyState + create_graph
  □ Erstelle initial state mit survey_id + provider
  □ Rufe graph.invoke(state) auf
  □ Prüfe final.status (completed/error/delegated/screen_out)
  □ Logge balance_earned für learn.md

================================================================================"""

from __future__ import annotations

# ── Core Classes ───────────────────────────────────────────────────────────────

# SurveyState ist die zentrale State-Klasse. Importiere sie ZUERST
# weil alle anderen Module sie als Dependency haben.
from .state import SurveyState

# ── Graph Builder & Runner ─────────────────────────────────────────────────────

# create_graph(): Factory für kompilierten LangGraph.
# Nutze dies für Production — idempotent, wiederverwendbar.
#
# Example:
#   graph = create_graph()
#   final = graph.invoke(SurveyState(survey_id="...", provider="..."))
from .graph import create_graph, build_graph, run_survey_loop

# ── Individual Nodes (für Testing/Debugging) ──────────────────────────────────

# Einzelne Nodes können direkt aufgerufen werden für isoliertes Testing.
# Nützlich für: Node-Einzeltests, Debugging, Graph-Development.
#
# Example:
#   state = SurveyState(survey_id="67064749", provider="purespectrum")
#   state = ensure_chrome(state)  # Chrome starten
#   state = open_survey(state)     # Survey öffnen
#   state = inject_cookies(state)  # Cookies injizieren
#   state = snapshot_node(state)   # Snapshot machen
#   state = decide_node(state)     # NIM entscheiden
#   state = execute_node(state)    # Batch ausführen
from .nodes import (
    ensure_chrome,
    open_survey,
    inject_cookies,
    snapshot_node,
    decide_node,
    execute_node,
    detect_completion,
    human_delegate,
)

# ── Delegation Tool ────────────────────────────────────────────────────────────

# delegate_task(): Delegiere Problem an opencode CLI.
# Wird automatisch von human_delegate_node aufgerufen wenn
# consecutive_failures >= 3. Kann auch manuell aufgerufen werden.
#
# Example:
#   result = delegate_task(
#       survey_id="67064749",
#       provider="purespectrum",
#       reason="3 consecutive failures at iteration 4",
#       tab_ws="ws://...",
#       iteration=4,
#   )
#   if result["status"] == "ok":
#       print("Agent hat das Problem gelöst")
from .opencode_tool import delegate_task, delegate_if_needed

# ── Exception Class ────────────────────────────────────────────────────────────

# SurveyGraphError: Custom Exception für Graph-spezifische Fehler.
# Nutze dies für Error-Handling in FastAPI Endpoints.
#
# Example:
#   try:
#       graph = create_graph()
#       result = graph.invoke(state)
#   except SurveyGraphError as e:
#       logger.error(f"Graph failed: {e}")
#       return {"error": str(e)}


class SurveyGraphError(Exception):
    """Exception für Survey Graph Fehler.

    Wird geworfen wenn:
      - LangGraph nicht installiert ist (bei create_graph)
      - Chrome nicht gestartet werden kann (bei ensure_chrome)
      - Survey nicht geöffnet werden kann (bei open_survey)
      - CDP Verbindung fehlschlägt (bei inject_cookies/snapshot/execute)
      - Timeout bei opencode Delegation erreicht

    Attributes:
        node: Name der Node die den Fehler verursacht hat
        state: SurveyState zum Zeitpunkt des Fehlers
        original_error: Original-Exception wenn wrapped
    """

    def __init__(
        self,
        message: str,
        node: str = "",
        state: "SurveyState" = None,
        original_error: Exception = None,
    ):
        super().__init__(message)
        self.node = node
        self.state = state
        self.original_error = original_error

    def __repr__(self) -> str:
        parts = [f"SurveyGraphError({self.node}): {str(self)}"]
        if self.original_error:
            parts.append(f"original={self.original_error}")
        return ", ".join(parts)


# ── Version Info ───────────────────────────────────────────────────────────────

__version__ = "1.0.0"
__langgraph_required__ = True
__langgraph_min_version__ = "0.0.1"

# ── Public API Summary ─────────────────────────────────────────────────────────
#
# __all__ definiert was bei "from .graph import *" importiert wird.
# Alle wichtigen Klassen und Funktionen sind hier aufgelistet.

__all__ = [
    # State
    "SurveyState",
    # Graph
    "create_graph",
    "build_graph",
    "run_survey_loop",
    # Nodes
    "ensure_chrome",
    "open_survey",
    "inject_cookies",
    "snapshot_node",
    "decide_node",
    "execute_node",
    "detect_completion",
    "human_delegate",
    # Delegation
    "delegate_task",
    "delegate_if_needed",
    # Error
    "SurveyGraphError",
    # Version
    "__version__",
]
