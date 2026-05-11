"""================================================================================
stealth-runner / core / langgraph_integration.py  — Bridge: core ↔ LangGraph
================================================================================

ZWECK
-----
Dieses Modul ist die EINZIGE Schicht, die zwischen den core-Modulen
(state-frei, framework-agnostisch) und dem konkreten LangGraph-Agent
(survey-cli/survey/graph/*) sitzt.

Vorteil: wenn wir morgen LangGraph durch ein anderes Framework ersetzen,
muessen wir NUR diese Datei umschreiben — core/* bleibt komplett unberuehrt.

WAS HIER LEBT
-------------
1. inject_core(state)            : injizieren von Config + Budget + Vault in den
                                    LangGraph-State (am initial-node)
2. node_with_core(name, func)    : Decorator der jeden Node mit
                                    a) budget.guard()
                                    b) try/except → Audit + Analytics + Screenshot
                                    c) StateManager step-tracking
                                    umhuellt
3. CoreCheckpointer              : LangGraph-Checkpointer der unseren
                                    StateManager als Persistence nutzt
                                    (resumebar nach Crash)
4. should_skip_due_to_budget()   : LangGraph-Condition fuer add_conditional_edges
                                    "wenn budget knapp → springe zu submit"

WICHTIG
-------
Wir haengen UNS am LangGraph an, nicht andersrum. Der bestehende Graph in
survey-cli/survey/graph/graph.py wird MINIMAL invasiv erweitert:

    from core import bootstrap_core, get_config, get_error_handler, ...
    from core.langgraph_integration import inject_core, node_with_core
    builder.add_node("answer", node_with_core("answer", answer_question))
    initial_state = inject_core(initial_state, ...)

DESIGN-PRINZIP
--------------
core-Klassen werden NICHT modifiziert (kein Monkey-Patching ausser den
StateManager-async-Methoden in state_manager.py selbst). Stattdessen orchestriert
diese Datei die existierenden APIs:
  - SurveyBudget        → state["budget"]
  - ErrorHandler        → _record_failure() + _record_success() direkt
  - AnalyticsCollector  → increment() / observe()
  - StateManager        → start_step/complete_step/fail_step (async)
  - capture_failure     → core.screenshot
================================================================================"""

from __future__ import annotations

import functools
import logging
import time
import traceback
import uuid
from typing import Any, Awaitable, Callable, Optional

from .analytics import AnalyticsCollector
from .config import Config
from .error_handler import ErrorContext, ErrorHandler, ErrorSeverity
from .screenshot import capture_failure
from .security import SecurityManager
from .state_manager import StateManager
from .survey_budget import BudgetExceededError, SurveyBudget

log = logging.getLogger("core.langgraph")

# Diese State-Keys reserviert core — bitte nicht in Node-Code ueberschreiben.
CORE_KEYS = frozenset({
    "run_id", "budget", "_config", "_error_handler",
    "_analytics", "_state_manager", "_security",
})


def inject_core(
    state: dict,
    *,
    config: Config,
    error_handler: ErrorHandler,
    analytics: AnalyticsCollector,
    state_manager: StateManager,
    security: SecurityManager,
    run_id: Optional[str] = None,
    max_seconds: Optional[float] = None,
) -> dict:
    """Reichert den initialen LangGraph-State mit core-Services + Budget an.

    Ruf das EINMAL beim Survey-Start, bevor `graph.invoke(initial_state)`.
    Alle Folge-Nodes lesen aus diesem State.

    Args:
        state:         dein bestehendes initial state dict
        config:        get_config()
        error_handler: get_error_handler()
        analytics:     get_analytics()
        state_manager: get_state_manager()
        security:      get_security_manager()
        run_id:        eindeutige ID — default uuid4 hex
        max_seconds:   Override fuer Survey-Budget (default: config.budget.max_seconds = 120)

    Returns:
        Erweiterter State dict (neue Kopie, originale bleibt unberuehrt).
    """
    rid = run_id or uuid.uuid4().hex
    new_state = dict(state)
    new_state["run_id"] = rid
    new_state["budget"] = SurveyBudget(
        run_id=rid,
        max_seconds=max_seconds if max_seconds is not None else config.budget.max_seconds,
    )
    # underscore-prefixed → signalisiert "private, von Tools nicht modifizieren"
    new_state["_config"] = config
    new_state["_error_handler"] = error_handler
    new_state["_analytics"] = analytics
    new_state["_state_manager"] = state_manager
    new_state["_security"] = security

    # Survey-Start im Audit-Trail vermerken — wichtig fuer GDPR + Forensik
    try:
        security.audit.log(
            event_type=security.audit.PIPELINE_START
            if hasattr(security.audit, "PIPELINE_START") else "PIPELINE_START",
            actor="langgraph",
            action="survey_start",
            resource=rid,
            status="started",
            details={"max_seconds": new_state["budget"].max_seconds},
        )
    except Exception as e:
        log.debug("audit.start.skip err=%s", e)

    log.info(
        "graph.core.injected run_id=%s budget_max=%.0fs",
        rid, new_state["budget"].max_seconds,
    )
    return new_state


def node_with_core(
    node_name: str,
    func: Callable[[dict], Awaitable[dict]],
    *,
    severity_on_fail: ErrorSeverity = ErrorSeverity.ERROR,
    capture_screenshot_on_fail: bool = True,
    step_index: int = 0,
) -> Callable[[dict], Awaitable[dict]]:
    """Dekoriert einen async LangGraph-Node mit core-Plumbing.

    Pre-Hooks  : budget.guard(node_name), step-tracking start
    Post-Hooks : analytics.timing, step-tracking complete
    On-Failure : capture_failure (screenshot), error_handler._record_failure(),
                  state_manager.fail_step(), re-raise

    Beispiel:
        from core.langgraph_integration import node_with_core
        builder.add_node("answer", node_with_core("answer", _answer_impl))
    """

    @functools.wraps(func)
    async def wrapper(state: dict) -> dict:
        # Defensive: wenn jemand vergisst inject_core() aufzurufen, lass den
        # Node trotzdem laufen — aber LOG es als ERROR und ueberspring core-Hooks.
        if "budget" not in state or "_state_manager" not in state:
            log.error(
                "graph.node.%s missing core injection — running unprotected", node_name
            )
            return await func(state)

        budget: SurveyBudget = state["budget"]
        analytics: AnalyticsCollector = state["_analytics"]
        eh: ErrorHandler = state["_error_handler"]
        sm: StateManager = state["_state_manager"]
        run_id: str = state["run_id"]
        cfg: Config = state["_config"]

        # 1) Hartcheck Budget — wenn schon ueber, wirft BudgetExceededError
        budget.guard(node_name)

        # 2) StateManager step start (resumable persistence)
        step_id = await sm.start_step(run_id, node_name)
        analytics.increment(f"node.{node_name}.started")
        start = time.monotonic()

        try:
            with budget.span(f"node:{node_name}"):
                result = await func(state)
        except BudgetExceededError as be:
            # Budget ueber — nicht als "error" zaehlen sondern als "budget"
            analytics.increment(f"node.{node_name}.budget_exceeded")
            await sm.fail_step(step_id, error="budget_exceeded")
            if capture_screenshot_on_fail and cfg.enable_screenshots_on_error:
                await _safe_capture(cfg, run_id, "budget_exceeded",
                                    {"node": node_name,
                                     "elapsed": be.elapsed,
                                     "limit": be.limit})
            raise
        except Exception as e:
            duration = time.monotonic() - start
            analytics.increment(f"node.{node_name}.failed")
            analytics.record(f"node.{node_name}.duration_seconds", duration)

            # ErrorHandler-Buchhaltung (ohne den Retry-Loop — nur Reporting)
            ctx = ErrorContext(
                step_name=f"langgraph.{node_name}",
                step_index=step_index,
                stack_trace=traceback.format_exc(),
                additional_data={
                    "run_id": run_id,
                    "elapsed_seconds": round(duration, 3),
                    "error_type": type(e).__name__,
                    "severity": severity_on_fail.value
                    if hasattr(severity_on_fail, "value") else str(severity_on_fail),
                },
            )
            try:
                eh._record_failure(f"langgraph.{node_name}", ctx)
            except Exception as inner:
                log.debug("error_handler.record_failure.skip err=%s", inner)

            await sm.fail_step(step_id,
                               error=f"{type(e).__name__}: {str(e)[:500]}")
            if capture_screenshot_on_fail and cfg.enable_screenshots_on_error:
                await _safe_capture(cfg, run_id, f"node_{node_name}_failed",
                                    {"error_type": type(e).__name__,
                                     "error_msg": str(e)[:500]})
            raise

        duration = time.monotonic() - start
        analytics.increment(f"node.{node_name}.succeeded")
        analytics.record(f"node.{node_name}.duration_seconds", duration)
        try:
            eh._record_success(f"langgraph.{node_name}")
        except Exception:
            pass
        await sm.complete_step(step_id, output={"duration_seconds": duration})
        return result

    wrapper.__name__ = f"core_wrapped_{node_name}"
    wrapper.__wrapped__ = func  # type: ignore[attr-defined]
    return wrapper


# ── SYNC-VARIANT fuer survey-cli (Nodes sind dort sync + SurveyState dataclass) ──
#
# Der bestehende Graph in survey-cli/survey/graph/nodes.py hat NUR sync Nodes
# und reicht eine dataclass `SurveyState` rein. Damit wir KEIN Refactoring auf
# async erzwingen, gibt es hier eine parallele Sync-Variante.
#
# Das Wiring ist analog zur async-Variante — Unterschiede:
#   - State ist eine dataclass (oder beliebiges Objekt) statt dict.
#     core liest run_id + core-refs aus state._core_ctx (siehe attach_core_ctx).
#   - Budget-guard ist HARD: bei BudgetExceededError stoppt der Wrapper
#     den restlichen Loop (durch Setzen von state.status = "error" UND
#     state.is_terminal=True — sonst laufen die naechsten Nodes weiter).


class CoreCtx:
    """Container fuer core-Services innerhalb eines SurveyState (sync flow).

    Wird einmal pro Survey via attach_core_ctx() an state._core_ctx geklebt
    und von sync_node_with_core() pro Node konsultiert.
    """
    __slots__ = ("run_id", "budget", "config", "error_handler",
                 "analytics", "state_manager", "security")

    def __init__(self, *, run_id: str, budget: SurveyBudget, config: Config,
                 error_handler: ErrorHandler, analytics: AnalyticsCollector,
                 state_manager: StateManager, security: SecurityManager):
        self.run_id = run_id
        self.budget = budget
        self.config = config
        self.error_handler = error_handler
        self.analytics = analytics
        self.state_manager = state_manager
        self.security = security


def attach_core_ctx(
    state: Any,
    *,
    config: Config,
    error_handler: ErrorHandler,
    analytics: AnalyticsCollector,
    state_manager: StateManager,
    security: SecurityManager,
    run_id: Optional[str] = None,
    max_seconds: Optional[float] = None,
) -> CoreCtx:
    """Haengt einen CoreCtx an state._core_ctx und liefert ihn zurueck.

    state kann eine dataclass, ein pydantic-Model oder ein Plain-Object sein —
    Hauptsache es erlaubt Attribut-Set (setattr funktioniert auf dataclasses
    mit frozen=False, was hier der Fall ist fuer SurveyState).
    """
    rid = run_id or uuid.uuid4().hex
    ctx = CoreCtx(
        run_id=rid,
        budget=SurveyBudget(
            run_id=rid,
            max_seconds=max_seconds if max_seconds is not None else config.budget.max_seconds,
        ),
        config=config,
        error_handler=error_handler,
        analytics=analytics,
        state_manager=state_manager,
        security=security,
    )
    setattr(state, "_core_ctx", ctx)
    try:
        security.audit.log(
            event_type="PIPELINE_START",
            actor="langgraph_sync",
            action="survey_start",
            resource=rid,
            status="started",
            details={"max_seconds": ctx.budget.max_seconds},
        )
    except Exception as e:
        log.debug("audit.start.skip err=%s", e)
    log.info("graph.core.attached run_id=%s budget_max=%.0fs",
             rid, ctx.budget.max_seconds)
    return ctx


def sync_node_with_core(
    node_name: str,
    func: Callable[[Any], Any],
    *,
    severity_on_fail: ErrorSeverity = ErrorSeverity.ERROR,
    capture_screenshot_on_fail: bool = True,
    step_index: int = 0,
) -> Callable[[Any], Any]:
    """Sync-Variante von node_with_core fuer survey-cli Nodes.

    Beispiel im survey-cli/survey/graph/graph.py:

        from core.langgraph_integration import sync_node_with_core
        graph.add_node("snapshot",  sync_node_with_core("snapshot",  snapshot_node))
        graph.add_node("decide",    sync_node_with_core("decide",    decide_node))
        graph.add_node("execute",   sync_node_with_core("execute",   execute_node))

    Wenn state._core_ctx fehlt (z.B. Tests ohne attach_core_ctx), lauft der
    Node UNGESCHUETZT — wir loggen es als WARNING aber crashen nicht.
    """

    @functools.wraps(func)
    def wrapper(state: Any) -> Any:
        ctx: Optional[CoreCtx] = getattr(state, "_core_ctx", None)
        if ctx is None:
            log.warning(
                "graph.sync.%s missing _core_ctx — running unprotected", node_name,
            )
            return func(state)

        # 1) Budget-Hartcheck — wirft BudgetExceededError wenn Zeit aus
        try:
            ctx.budget.guard(node_name)
        except BudgetExceededError as be:
            # Hart-abbrechen: state.status setzen, Nodes danach skippen
            ctx.analytics.increment(f"node.{node_name}.budget_exceeded")
            try:
                setattr(state, "status", "error")
                errors = getattr(state, "errors", None)
                if errors is not None and hasattr(errors, "append"):
                    errors.append({
                        "node": node_name,
                        "error": f"budget_exceeded:{be.elapsed:.1f}s",
                        "iteration": getattr(state, "iteration", -1),
                    })
            except Exception:
                pass
            # Screenshot best-effort (sync via asyncio.run)
            if capture_screenshot_on_fail and ctx.config.enable_screenshots_on_error:
                _safe_capture_sync(ctx.config, ctx.run_id, "budget_exceeded",
                                   {"node": node_name,
                                    "elapsed": be.elapsed,
                                    "limit": be.limit})
            # Wir RE-RAISEN NICHT — sonst crasht der LangGraph. Stattdessen
            # signalisieren wir via state.status="error" dass die naechste
            # Routing-Funktion auf END schaltet.
            return state

        # 2) Step-Tracking (async unter der Haube, kurz via asyncio.run)
        try:
            import asyncio as _aio
            step_id = _aio.run(ctx.state_manager.start_step(ctx.run_id, node_name))
        except RuntimeError:
            # event loop already running — ueberspringen, wir verlieren nur
            # Persistence in diesem Edge-Case (z.B. Test der bereits asyncio
            # nutzt). Nicht-fatal.
            step_id = None
        ctx.analytics.increment(f"node.{node_name}.started")
        start = time.monotonic()

        try:
            with ctx.budget.span(f"node:{node_name}"):
                result = func(state)
        except Exception as e:
            duration = time.monotonic() - start
            ctx.analytics.increment(f"node.{node_name}.failed")
            ctx.analytics.record(f"node.{node_name}.duration_seconds", duration)

            err_ctx = ErrorContext(
                step_name=f"langgraph.{node_name}",
                step_index=step_index,
                stack_trace=traceback.format_exc(),
                additional_data={
                    "run_id": ctx.run_id,
                    "elapsed_seconds": round(duration, 3),
                    "error_type": type(e).__name__,
                    "severity": severity_on_fail.value
                    if hasattr(severity_on_fail, "value") else str(severity_on_fail),
                },
            )
            try:
                ctx.error_handler._record_failure(f"langgraph.{node_name}", err_ctx)
            except Exception:
                pass

            if step_id is not None:
                try:
                    import asyncio as _aio
                    _aio.run(ctx.state_manager.fail_step(
                        step_id, error=f"{type(e).__name__}: {str(e)[:500]}"
                    ))
                except RuntimeError:
                    pass

            if capture_screenshot_on_fail and ctx.config.enable_screenshots_on_error:
                _safe_capture_sync(ctx.config, ctx.run_id,
                                   f"node_{node_name}_failed",
                                   {"error_type": type(e).__name__,
                                    "error_msg": str(e)[:500]})
            raise

        duration = time.monotonic() - start
        ctx.analytics.increment(f"node.{node_name}.succeeded")
        ctx.analytics.record(f"node.{node_name}.duration_seconds", duration)
        try:
            ctx.error_handler._record_success(f"langgraph.{node_name}")
        except Exception:
            pass
        if step_id is not None:
            try:
                import asyncio as _aio
                _aio.run(ctx.state_manager.complete_step(
                    step_id, output={"duration_seconds": duration}
                ))
            except RuntimeError:
                pass
        return result

    wrapper.__name__ = f"core_sync_wrapped_{node_name}"
    wrapper.__wrapped__ = func  # type: ignore[attr-defined]
    return wrapper


def _safe_capture_sync(cfg: Config, run_id: str, reason: str, extra: dict) -> None:
    """capture_failure aus sync-Kontext — best effort, schluckt Exceptions."""
    try:
        import asyncio as _aio
        _aio.run(capture_failure(
            cdp_url=cfg.chrome.cdp_url,
            run_id=run_id,
            reason=reason,
            extra=extra,
            base_dir=cfg.screenshot_dir,
        ))
    except RuntimeError:
        # event loop already running — schedule fire-and-forget
        try:
            _aio.get_event_loop().create_task(capture_failure(  # type: ignore
                cdp_url=cfg.chrome.cdp_url, run_id=run_id,
                reason=reason, extra=extra, base_dir=cfg.screenshot_dir,
            ))
        except Exception:
            pass
    except Exception as e:
        log.warning("graph.capture_failed.sync run_id=%s reason=%s err=%s",
                    run_id, reason, e)


# ── TOP-LEVEL RUNNER fuer survey-cli ─────────────────────────────────────────


def run_survey_with_core(
    state: Any,
    *,
    run_fn: Callable[[Any], Any],
    max_seconds: Optional[float] = None,
) -> Any:
    """Top-Level Convenience: bootstrappt core, attached Ctx, fuehrt run_fn aus.

    Beispiel im survey-cli main:

        from survey.graph.graph import run_survey_loop
        from survey.graph.state import SurveyState
        from core.langgraph_integration import run_survey_with_core

        state = SurveyState(survey_id="67064749", provider="purespectrum")
        final = run_survey_with_core(state, run_fn=run_survey_loop, max_seconds=120)

    Args:
        state:        Initialer SurveyState
        run_fn:       Eine sync-Funktion die state nimmt + finalen state liefert
                      (typisch: run_survey_loop oder graph.invoke)
        max_seconds:  Override fuer Survey-Budget (default 120s)

    Returns:
        Finaler state inkl. _core_ctx mit budget.snapshot() + analytics
    """
    # Lokale Importe (avoid circular)
    from . import (
        bootstrap_core, get_config, get_error_handler, get_analytics,
        get_state_manager, get_security_manager,
    )

    # Bootstrap core (idempotent — bei wiederholtem Aufruf no-op)
    import asyncio as _aio
    try:
        _aio.run(bootstrap_core())
    except RuntimeError:
        # event loop already running — wir laufen wahrscheinlich aus async
        # context (FastAPI). Caller soll dann run_survey_with_core_async nutzen.
        log.warning("run_survey_with_core: event loop already running, "
                    "skipping bootstrap (call await bootstrap_core() yourself)")

    ctx = attach_core_ctx(
        state,
        config=get_config(),
        error_handler=get_error_handler(),
        analytics=get_analytics(),
        state_manager=get_state_manager(),
        security=get_security_manager(),
        max_seconds=max_seconds,
    )

    start = time.monotonic()
    try:
        result = run_fn(state)
    except BudgetExceededError as be:
        log.error("survey.budget_exceeded run_id=%s elapsed=%.1fs",
                  ctx.run_id, be.elapsed)
        ctx.analytics.increment("survey.budget_exceeded")
        try:
            setattr(state, "status", "error")
        except Exception:
            pass
        result = state
    except Exception as e:
        log.exception("survey.unhandled_exception run_id=%s err=%s",
                      ctx.run_id, e)
        ctx.analytics.increment("survey.unhandled_exception")
        try:
            setattr(state, "status", "error")
        except Exception:
            pass
        result = state

    duration = time.monotonic() - start
    ctx.analytics.record("survey.total_duration_seconds", duration)
    ctx.analytics.increment(
        "survey.completed"
        if getattr(state, "status", "") == "completed" else "survey.not_completed"
    )

    # Final-Snapshot persistieren (resumable post-mortem)
    try:
        _aio.run(ctx.state_manager.save_checkpoint(
            ctx.run_id,
            checkpoint=ctx.budget,  # nutzt budget.snapshot()
            metadata={
                "status": getattr(state, "status", "?"),
                "iteration": getattr(state, "iteration", -1),
                "balance_before": getattr(state, "balance_before", 0.0),
                "balance_after": getattr(state, "balance_after", 0.0),
                "duration_seconds": round(duration, 3),
            },
        ))
    except RuntimeError:
        pass
    except Exception as e:
        log.debug("survey.checkpoint.skip err=%s", e)

    log.info(
        "survey.completed run_id=%s status=%s duration=%.1fs",
        ctx.run_id, getattr(state, "status", "?"), duration,
    )
    return result


async def _safe_capture(cfg: Config, run_id: str, reason: str,
                        extra: dict) -> None:
    """capture_failure aber NIE schmeissend (failure-handling darf nicht falln)."""
    try:
        await capture_failure(
            cdp_url=cfg.chrome.cdp_url,
            run_id=run_id,
            reason=reason,
            extra=extra,
            base_dir=cfg.screenshot_dir,
        )
    except Exception as e:
        log.warning("graph.capture_failed run_id=%s reason=%s err=%s",
                    run_id, reason, e)


# ── Conditional Edges ────────────────────────────────────────────────────────


def should_skip_due_to_budget(
    state: dict,
    *,
    estimate_seconds: float = 5.0,
    on_ok: str = "continue",
    on_low_budget: str = "submit_early",
) -> str:
    """LangGraph-Condition fuer add_conditional_edges.

    Wenn das Restbudget den Estimate nicht mehr packt, signalisieren wir
    "spring direkt zum Submit-Node" statt weiteren Fragen.

    Beispiel:
        builder.add_conditional_edges(
            "answer",
            functools.partial(should_skip_due_to_budget, estimate_seconds=15),
            {"continue": "next_question", "submit_early": "submit"},
        )
    """
    budget: Optional[SurveyBudget] = state.get("budget")
    if budget is None:
        return on_ok  # kein Budget injected → kein Skip
    if budget.would_exceed(estimate_seconds):
        log.warning(
            "graph.budget.skip run_id=%s remaining=%.1fs need=%.1fs",
            budget.run_id, budget.remaining, estimate_seconds,
        )
        return on_low_budget
    return on_ok


# ── Checkpointer ────────────────────────────────────────────────────────────


class CoreCheckpointer:
    """Minimaler LangGraph-kompatibler Checkpointer auf Basis unseres StateManagers.

    LangGraph 0.2+ erwartet ein Objekt mit aput()/aget()/alist() async methods.
    Wir mappen das auf StateManager.save_checkpoint / load_checkpoint.

    WARUM EIGEN statt sqlite-checkpointer von langgraph nutzen?
    1. Schon eigene SQLite via StateManager — keine zweite Datei.
    2. Wir wollen das Budget-Snapshot mit-persistieren (siehe save_checkpoint).
    3. Bei Resume nach Crash: gleicher StateManager weiss bereits ueber den Run.

    Achtung: dieser Checkpointer ist KEIN Full-Featured Langgraph-Checkpointer —
    er implementiert nur das Subset, das survey-cli braucht. Wenn ihr branch-
    history/replay wollt → langgraph_sqlite_checkpoint nehmen.
    """

    def __init__(self, state_manager: StateManager):
        self.sm = state_manager

    async def aput(self, config: dict, checkpoint: Any, metadata: dict) -> dict:
        run_id = (config or {}).get("configurable", {}).get("thread_id") or uuid.uuid4().hex
        await self.sm.save_checkpoint(run_id, checkpoint, metadata or {})
        return {"configurable": {"thread_id": run_id}}

    async def aget(self, config: dict) -> Optional[dict]:
        run_id = (config or {}).get("configurable", {}).get("thread_id")
        if not run_id:
            return None
        return await self.sm.load_checkpoint(run_id)

    async def alist(self, config: dict, *, limit: Optional[int] = None) -> list:
        run_id = (config or {}).get("configurable", {}).get("thread_id")
        return await self.sm.list_checkpoints(run_id, limit=limit or 10)


# ── Convenience: ein-Zeilen Setup fuer survey-cli graph.py ──────────────────


async def setup_graph_with_core(builder: Any) -> Any:
    """Optionaler Helper: wrappt alle vorhandenen Nodes eines StateGraph-builders
    automatisch mit node_with_core(). Ruft NUR fuer Nodes deren Name nicht
    mit "_" beginnt.

    Beispiel:
        builder = StateGraph(MyState)
        builder.add_node("answer", answer_impl)
        builder.add_node("solve_captcha", captcha_impl)
        await setup_graph_with_core(builder)        # wrappt alle
        graph = builder.compile()

    Achtung: nur sinnvoll wenn der builder ein simples .nodes dict expose'd —
    Stand LangGraph 0.2: builder.nodes ist ein internal field. Wenn das in
    eurer Version nicht klappt, manuell node_with_core() pro add_node nutzen.
    """
    nodes = getattr(builder, "nodes", None)
    if not nodes:
        log.warning("setup_graph_with_core: builder.nodes nicht zugaenglich, skip")
        return builder
    for name, spec in list(nodes.items()):
        if name.startswith("_"):
            continue
        original = getattr(spec, "func", None) or getattr(spec, "runnable", None)
        if original and callable(original):
            wrapped = node_with_core(name, original)
            # Schreib zurueck — Format ist version-abhaengig
            try:
                spec.func = wrapped  # type: ignore[attr-defined]
            except Exception:
                pass
    return builder
