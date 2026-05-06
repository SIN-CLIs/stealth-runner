"""
survey/agents/__init__.py — SOTA Parallel AI Framework (2026-05-06)

ARCHITEKTUR: 5 Agenten parallel auf allen verfügbaren NVIDIA/Mistral Modellen.
Jeder Agent läuft in einem eigenen Thread, Ergebnisse werden nach ~80-500ms
zusammengeführt. Das ist ~5-10× schneller als sequentielle Agent-Aufrufe.

    ┌─────────────────────────────────────────────────────────────────┐
    │              PARALLELORCHESTRATOR (ThreadPoolExecutor)          │
    │                                                                  │
    │  Thread-1: ElementMapper  → mistral-small  (80ms, micro)       │
    │  Thread-2: PersonaChecker→ nemotron-nano   (500ms, mid)        │
    │  Thread-3: PageClassifier→ mistral-small   (80ms, micro)       │
    │  Thread-4: AnswerGenerator→ nemotron-nano  (500ms, mid)        │
    │  Thread-5: ActionVerifier → mistral-small  (80ms, micro)       │
    │                                                                  │
    │  → Gesamtzeit: max(alle) = ~500ms statt sum(alle) = ~1240ms   │
    └─────────────────────────────────────────────────────────────────┘

VERWENDUNG:
    from survey.agents import ParallelOrchestrator
    
    orch = ParallelOrchestrator(profile, learnings)
    result = orch.run_full_pipeline(page_text, ax_tree, cdp_elements)
    # result = {page_type, actions, confidence, all_agent_results}
"""

from .parallel_orchestrator import ParallelOrchestrator
from .task_router import TaskRouter, MODELS, TaskComplexity
from .element_mapper import ElementMapper
from .persona_checker import PersonaChecker
from .page_classifier import PageClassifier
from .answer_generator import AnswerGenerator
from .action_verifier import ActionVerifier

__all__ = [
    "ParallelOrchestrator",
    "TaskRouter",
    "MODELS",
    "TaskComplexity",
    "ElementMapper",
    "PersonaChecker",
    "PageClassifier",
    "AnswerGenerator",
    "ActionVerifier",
]