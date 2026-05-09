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
  │    └──→ detect_completion ──→ [completed/screen_out] ─→ END            │
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
    decide_node,
    execute_node,
    detect_completion,
    human_delegate,
)

# LangGraph Import — graceful degradation wenn nicht installiert
try:
    from langgraph.graph import StateGraph, START, END

    LANGGRAPH_AVAILABLE = True
except ImportError:
    LANGGRAPH_AVAILABLE = False


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
      START → ensure_chrome → open_survey → inject_cookies
            → snapshot → decide → execute → detect_completion
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

    # Schritt 2: Nodes hinzufügen
    # Jede Node wrapped eine existierende Funktion.
    # Keine neue Logik — nur delegate + state update.
    graph.add_node("ensure_chrome", ensure_chrome)
    graph.add_node("open_survey", open_survey)
    graph.add_node("inject_cookies", inject_cookies)
    graph.add_node("snapshot", snapshot_node)
    graph.add_node("decide", decide_node)
    graph.add_node("execute", execute_node)
    graph.add_node("detect_completion", detect_completion)
    graph.add_node("human_delegate", human_delegate)

    # Schritt 3: Start-Edge (START → ensure_chrome)
    graph.add_edge(START, "ensure_chrome")

    # Schritt 4: Setup-Edges (linear, kein Routing)
    # Diese Edges laufen IMMER in der gleichen Reihenfolge.
    # Kein Conditional — jede Node muss erfolgreich sein.
    graph.add_edge("ensure_chrome", "open_survey")
    graph.add_edge("open_survey", "inject_cookies")
    graph.add_edge("inject_cookies", "snapshot")

    # Schritt 5: NEMO-Loop Edge (snapshot → decide → execute → detect_completion)
    # Nach detect_completion wird route() aufgerufen für conditional routing.
    graph.add_edge("snapshot", "decide")
    graph.add_edge("decide", "execute")
    graph.add_edge("execute", "detect_completion")

    # Schritt 6: Conditional Edge nach detect_completion
    # route() entscheidet ob: snapshot (continue) | human_delegate | END
    graph.add_conditional_edges(
        "detect_completion",
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


# ── COMPILED GRAPH FACTORY ─────────────────────────────────────────────────────


def create_graph():
    """Factory: Erstelle und kompiliere den Survey-Graph.

    Convenience-Wrapper für:
      graph = build_graph()
      compiled = graph.compile()
      return compiled

    Returns:
        Compiled Graph — invoke(initial_state) → final_state

    Example:
        >>> survey_graph = create_graph()
        >>> initial = SurveyState(survey_id="67064749", provider="purespectrum")
        >>> final = survey_graph.invoke(initial)
        >>> final.status
        'completed'
    """
    if not LANGGRAPH_AVAILABLE:
        raise ImportError(
            "langgraph is not installed. "
            "Install with: pip install langgraph"
        )
    _graph = build_graph()
    return _graph.compile()


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
    # Balance vor der Session lesen (SR-41)
    try:
        from ..scanner import read_balance
        state.balance_before = read_balance(port=state.cdp_port)
    except Exception:
        state.balance_before = 0.0

    # Phase 1: Setup
    state = ensure_chrome(state)
    if state.status == "error":
        return state

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

        # Iteration inkrementieren (NEMO Schritt 2 — JEDE Iteration, nicht nur bei Actions!)
        state.increment_iteration()

        # NIM entscheiden (NEMO Schritt 3)
        state = decide_node(state)

        # Fallback: NEMO snapshot ohne Actions → nur detect completion
        if not state.nim_actions:
            state = detect_completion(state)
        else:
            # Batch ausführen (NEMO Schritt 4)
            state = execute_node(state)
            # completion detection
            state = detect_completion(state)

        # Routing
        next_node = route(state)
        if next_node == "END":
            break
        elif next_node == "human_delegate":
            state = human_delegate(state)
            break
        # else: continue to next iteration (loop)

    # Balance nach der Session lesen (SR-41)
    try:
        from ..scanner import read_balance
        state.balance_after = read_balance(port=state.cdp_port)
    except Exception:
        state.balance_after = state.balance_before

    return state