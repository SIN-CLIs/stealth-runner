"""================================================================================
stealth-runner / core / survey_budget.py  — 2-Minuten Wallclock-Budget
================================================================================

ZWECK
-----
Production-Hartwand fuer das User-Ziel "Eine Survey darf nie laenger als
2 Minuten dauern". Wird in jeden LangGraph-Node injiziert und prueft VOR jeder
Aktion, ob das Budget noch reicht.

WARUM EIGENES MODUL (nicht Config)?
-----------------------------------
Config = statische Werte. SurveyBudget = LAUFENDER ZUSTAND einer einzelnen
Survey-Run-ID. Pro Survey ein eigenes Budget-Objekt; ein einzelner LangGraph
checkt budget.guard(node_name) → wirft BudgetExceededError wenn Zeit aus.

API
---
  budget = SurveyBudget(run_id="abc", max_seconds=120)
  with budget.span("step:demographics"):           # context-manager Timing
      ...
  if budget.would_exceed(estimate_seconds=15):     # planning Check
      ...
  budget.guard("ai:answer_question")               # hart abbrechen wenn ueber

  result = budget.snapshot()  # → dict fuer Analytics / State Persistence

THREAD-SAFETY
-------------
Eine Survey laeuft sequenziell durch den Graph — kein Locking noetig.
Falls parallel Sub-Tasks gestartet werden, MUSS jeder ein eigenes Sub-Budget
erhalten (siehe SurveyBudget.subbudget(percent)).
================================================================================"""

from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Iterator, Optional

log = logging.getLogger("core.budget")


class BudgetExceededError(RuntimeError):
    """Wird vom guard() geworfen, wenn das Survey-Budget aufgebraucht ist.

    Der LangGraph fangs in einem dedizierten Error-Node, persistiert den
    Survey-State (resumebar) und beendet sauber statt zu haengen.
    """

    def __init__(self, run_id: str, node: str, elapsed: float, limit: float):
        super().__init__(
            f"budget.exceeded run_id={run_id} node={node} "
            f"elapsed={elapsed:.2f}s limit={limit:.2f}s"
        )
        self.run_id = run_id
        self.node = node
        self.elapsed = elapsed
        self.limit = limit


@dataclass
class StepTiming:
    """Eine einzelne Step-Messung innerhalb einer Survey."""
    name: str
    start: float
    end: Optional[float] = None
    duration: Optional[float] = None
    exceeded: bool = False  # True wenn dieser Step das Budget ueberschritten hat


@dataclass
class SurveyBudget:
    """Wallclock-Budget fuer EINE Survey.

    Anwendung im Graph-Node:

        async def node_answer(state):
            budget = state["budget"]            # injected aus initial state
            budget.guard("answer_question")     # hart abbrechen wenn schon ueber
            with budget.span("answer_question"):
                answer = await llm.generate(...)
            return {"answer": answer}
    """
    run_id: str
    max_seconds: float = 120.0
    # interne Felder — NICHT von aussen anfassen
    _started_at: float = field(default_factory=time.monotonic)
    _steps: list[StepTiming] = field(default_factory=list)

    # ── Querying ──────────────────────────────────────────────────────────

    @property
    def elapsed(self) -> float:
        """Vergangene Wallclock-Sekunden seit Start."""
        return time.monotonic() - self._started_at

    @property
    def remaining(self) -> float:
        """Restliche Budget-Sekunden. Kann negativ werden (= bereits ueber)."""
        return self.max_seconds - self.elapsed

    @property
    def is_exceeded(self) -> bool:
        return self.elapsed > self.max_seconds

    def would_exceed(self, estimate_seconds: float) -> bool:
        """Plan-Check: wuerde eine Aktion mit `estimate_seconds` Dauer
        das Budget sprengen?

        Nuetzlich vor LLM-Calls mit hoher Latenz — wenn ja, ueberspringe
        oder waehle Fallback-Strategie.
        """
        return self.elapsed + estimate_seconds > self.max_seconds

    # ── Enforcement ───────────────────────────────────────────────────────

    def guard(self, node_name: str) -> None:
        """Pflicht-Check an jedem Node-Eingang. Wirft, wenn ueber Budget.

        Im LangGraph idealerweise als pre-hook via add_node(..., before=guard).
        """
        if self.is_exceeded:
            elapsed = self.elapsed
            log.error(
                "budget.guard.exceeded run_id=%s node=%s elapsed=%.2fs",
                self.run_id, node_name, elapsed,
            )
            raise BudgetExceededError(
                self.run_id, node_name, elapsed, self.max_seconds
            )

    # ── Timing ────────────────────────────────────────────────────────────

    @contextmanager
    def span(self, name: str) -> Iterator[StepTiming]:
        """Context-Manager fuer das Timing eines einzelnen Steps.

        Speichert Start/End/Duration und markiert exceeded=True wenn dieser
        Step alleine das Restbudget ueberzogen hat — wichtig fuer Analytics
        (z. B. "welcher Step ist im 95p der Killer?").
        """
        step = StepTiming(name=name, start=time.monotonic())
        self._steps.append(step)
        try:
            yield step
        finally:
            step.end = time.monotonic()
            step.duration = step.end - step.start
            step.exceeded = self.is_exceeded
            log.debug(
                "budget.span run_id=%s step=%s duration=%.3fs remaining=%.2fs",
                self.run_id, name, step.duration, self.remaining,
            )

    # ── Sub-Budgets ───────────────────────────────────────────────────────

    def subbudget(self, percent: float, suffix: str = "sub") -> "SurveyBudget":
        """Erzeugt ein Sub-Budget mit `percent` (0..1) des Restbudgets.

        Use-Case: parallele Captcha-Solver-Versuche mit je 30 % des Rests.
        """
        if not 0.0 < percent <= 1.0:
            raise ValueError(f"percent muss in (0, 1] sein, got {percent}")
        return SurveyBudget(
            run_id=f"{self.run_id}:{suffix}",
            max_seconds=max(self.remaining * percent, 1.0),
        )

    # ── Reporting ─────────────────────────────────────────────────────────

    def snapshot(self) -> dict:
        """Serialisierbares Dict fuer Persistence (StateManager) + Analytics."""
        return {
            "run_id": self.run_id,
            "max_seconds": self.max_seconds,
            "elapsed_seconds": round(self.elapsed, 3),
            "remaining_seconds": round(self.remaining, 3),
            "is_exceeded": self.is_exceeded,
            "step_count": len(self._steps),
            "steps": [
                {
                    "name": s.name,
                    "duration_seconds": round(s.duration or 0.0, 3),
                    "exceeded": s.exceeded,
                }
                for s in self._steps
            ],
            "slowest_step": (
                max(
                    (s for s in self._steps if s.duration is not None),
                    key=lambda s: s.duration or 0.0,
                    default=None,
                ).name
                if any(s.duration for s in self._steps)
                else None
            ),
        }
