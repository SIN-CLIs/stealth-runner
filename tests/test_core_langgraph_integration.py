# tests/test_core_langgraph_integration.py
# ─────────────────────────────────────────────────────────────────────────────
# Integrations-Tests fuer core.langgraph_integration:
#   - sync_node_with_core: budget-guard + success/fail path
#   - run_survey_with_core: top-level Runner mit final checkpoint
#   - should_skip_due_to_budget: conditional edge routing
#   - CoreCheckpointer: LangGraph-Compatible Checkpoint-Adapter
#
# Wir nutzen eine MINI FakeState dataclass die SurveyState nachbildet, um die
# Tests vom echten survey-cli zu entkoppeln (kein Chrome, kein CDP).
# ─────────────────────────────────────────────────────────────────────────────
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import List, Dict, Any

import pytest

from core import (
    SurveyBudget,
    BudgetExceededError,
    bootstrap_core,
    get_config,
    get_error_handler,
    get_analytics,
    get_state_manager,
    get_security_manager,
)
from core.langgraph_integration import (
    attach_core_ctx,
    sync_node_with_core,
    run_survey_with_core,
    should_skip_due_to_budget,
    inject_core,
    node_with_core,
    CoreCheckpointer,
)


@dataclass
class FakeState:
    survey_id: str = "x"
    status: str = "pending"
    iteration: int = 0
    errors: List[Dict[str, Any]] = field(default_factory=list)
    balance_before: float = 0.0
    balance_after: float = 0.0


def _attach(state: FakeState, *, max_seconds: float = 5.0) -> None:
    attach_core_ctx(
        state,
        config=get_config(),
        error_handler=get_error_handler(),
        analytics=get_analytics(),
        state_manager=get_state_manager(),
        security=get_security_manager(),
        max_seconds=max_seconds,
    )


# ── sync_node_with_core ──────────────────────────────────────────────────────


def test_sync_wrapper_success_path(core_bootstrap) -> None:
    state = FakeState()
    _attach(state)
    def node(s):
        s.iteration += 1
        return s
    wrapped = sync_node_with_core("snapshot", node, capture_screenshot_on_fail=False)
    out = wrapped(state)
    assert out.iteration == 1


def test_sync_wrapper_reraises_exception(core_bootstrap) -> None:
    state = FakeState()
    _attach(state)
    def bad(s):
        raise RuntimeError("boom")
    wrapped = sync_node_with_core("bad", bad, capture_screenshot_on_fail=False)
    with pytest.raises(RuntimeError):
        wrapped(state)


def test_sync_wrapper_budget_aborts_gracefully(core_bootstrap) -> None:
    """Wenn Budget abgelaufen, darf der Wrapper NICHT raisen, sondern state.status
    auf 'error' setzen — sonst killt das den LangGraph."""
    state = FakeState()
    _attach(state, max_seconds=0.001)
    time.sleep(0.05)  # Budget verstrichen
    def node(s):
        s.iteration += 1
        return s
    wrapped = sync_node_with_core("snapshot", node, capture_screenshot_on_fail=False)
    result = wrapped(state)
    assert result.status == "error"
    assert result.iteration == 0, "Node-Func darf NICHT ausgefuehrt werden"
    assert any("budget_exceeded" in e.get("error", "") for e in result.errors)


def test_sync_wrapper_without_core_ctx_runs_unprotected(core_bootstrap) -> None:
    """Backward-Compat: ohne _core_ctx laeuft die Node unprotected (mit warning)."""
    state = FakeState()  # KEIN attach_core_ctx
    def node(s):
        s.iteration += 99
        return s
    wrapped = sync_node_with_core("snapshot", node)
    out = wrapped(state)
    assert out.iteration == 99


# ── run_survey_with_core ─────────────────────────────────────────────────────


def test_run_survey_with_core_happy_path(core_bootstrap) -> None:
    state = FakeState(survey_id="happy")
    def loop(s):
        s.status = "completed"
        s.balance_after = s.balance_before + 0.42
        return s
    final = run_survey_with_core(state, run_fn=loop, max_seconds=2.0)
    assert final.status == "completed"
    assert final.balance_after == pytest.approx(0.42)


def test_run_survey_with_core_swallows_budget_exception(core_bootstrap) -> None:
    state = FakeState(survey_id="budget")
    def loop(s):
        raise BudgetExceededError(elapsed=120.5, limit=120.0)
    final = run_survey_with_core(state, run_fn=loop, max_seconds=120.0)
    assert final.status == "error"


def test_run_survey_with_core_swallows_unhandled_exception(core_bootstrap) -> None:
    state = FakeState(survey_id="crash")
    def loop(s):
        raise RuntimeError("unexpected")
    final = run_survey_with_core(state, run_fn=loop, max_seconds=10.0)
    assert final.status == "error"


# ── should_skip_due_to_budget ────────────────────────────────────────────────


def test_should_skip_continue_when_budget_ok(core_bootstrap) -> None:
    state = {"budget": SurveyBudget(run_id="r", max_seconds=10.0)}
    assert should_skip_due_to_budget(state, estimate_seconds=1.0) == "continue"


def test_should_skip_submit_early_when_budget_tight(core_bootstrap) -> None:
    state = {"budget": SurveyBudget(run_id="r", max_seconds=10.0)}
    assert should_skip_due_to_budget(state, estimate_seconds=999.0) == "submit_early"


# ── CoreCheckpointer ─────────────────────────────────────────────────────────


def test_core_checkpointer_aput_aget(core_bootstrap) -> None:
    cp = CoreCheckpointer(get_state_manager())
    cfg_inp = {"configurable": {"thread_id": "thread-xyz"}}
    asyncio.run(cp.aput(cfg_inp, {"graph": "midway"}, {"meta": "yes"}))
    loaded = asyncio.run(cp.aget(cfg_inp))
    assert loaded is not None
    assert loaded["run_id"] == "thread-xyz"


# ── async node_with_core ─────────────────────────────────────────────────────


def test_async_node_with_core_success(core_bootstrap) -> None:
    async def run():
        async def nd(state):
            return {"answered": True}
        wrapped = node_with_core("a", nd)
        state = inject_core(
            {},
            config=get_config(),
            error_handler=get_error_handler(),
            analytics=get_analytics(),
            state_manager=get_state_manager(),
            security=get_security_manager(),
            max_seconds=2.0,
        )
        return await wrapped(state)
    r = asyncio.run(run())
    assert r["answered"] is True
