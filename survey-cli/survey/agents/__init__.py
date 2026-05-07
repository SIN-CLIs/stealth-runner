"""
survey/agents/__init__.py — SOTA Parallel AI Framework (2026-05-06)

WARUM: Survey-Automation braucht mehrere Spezial-Agenten (Element-Scan,
Persona-Matching, Page-Klassifizierung, Action-Generierung, Verify).
Sequentielle Ausführung dauert 5-10s. Parallelisierung via
ThreadPoolExecutor reduziert auf ~500ms (determiniert durch den
langsamsten Thread = nemotron-nano mit 500ms).

ARCHITEKTUR: Package-Root. Exportiert ParallelOrchestrator, TaskRouter,
ElementMapper, PersonaChecker, PageClassifier, AnswerGenerator,
ActionVerifier. Jeder Agent ist eine eigenständige Klasse mit
.call()-Interface. ThreadPoolExecutor mit max_workers=5.
Gesamtzeit = max(80ms, 500ms, 80ms, 500ms, 80ms) = ~500ms.
Kein globaler State — jeder Call ist stateless.

BANNED METHODS — NIEMALS VERWENDEN:
❌ playstealth launch
❌ webauto-nodriver — ABSOLUT BANNED
❌ cua-driver click (raw index)
❌ --remote-allow-origins=* (ohne Quotes)
❌ /tmp/heypiggy-bot (fixed profile)
❌ Hardcoded PIDs
❌ pkill -f "Google Chrome"
❌ killall Google Chrome
❌ skylight-cli click --element-index
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