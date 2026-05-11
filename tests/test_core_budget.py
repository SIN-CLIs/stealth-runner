"""Tests fuer core.survey_budget — 120s Hardlimit, guard(), span()."""

from __future__ import annotations

import time

import pytest


def test_budget_within_limit_no_exception():
    """Solange unter max_seconds: guard() returnt None ohne Exception."""
    from core import SurveyBudget
    b = SurveyBudget(run_id="t1", max_seconds=10.0)
    b.guard("node1")  # MUSS nicht werfen
    assert not b.is_exceeded
    assert b.elapsed < 10.0


def test_budget_exceeded_raises():
    """Wenn elapsed >= max_seconds: guard() MUSS BudgetExceededError werfen."""
    from core import SurveyBudget, BudgetExceededError
    b = SurveyBudget(run_id="t2", max_seconds=0.001)
    time.sleep(0.05)
    with pytest.raises(BudgetExceededError) as exc:
        b.guard("node_x")
    assert exc.value.elapsed > 0.001
    assert exc.value.limit == 0.001
    assert "node_x" in str(exc.value) or "node_x" in exc.value.node


def test_budget_span_tracks_node_duration():
    """span(node_name) MUSS Zeit pro Node im snapshot()['steps'] persistieren."""
    from core import SurveyBudget
    b = SurveyBudget(run_id="t3", max_seconds=10.0)
    with b.span("snapshot"):
        time.sleep(0.02)
    with b.span("decide"):
        time.sleep(0.01)
    snap = b.snapshot()
    names = [s["name"] for s in snap["steps"]]
    assert "snapshot" in names
    assert "decide" in names
    durations = {s["name"]: s["duration_seconds"] for s in snap["steps"]}
    assert durations["snapshot"] >= 0.015
    assert durations["decide"] >= 0.005
    # Total elapsed muss >= laengster span sein
    assert snap["elapsed_seconds"] >= durations["snapshot"]


def test_budget_remaining_decreases():
    """remaining MUSS monoton fallen."""
    from core import SurveyBudget
    b = SurveyBudget(run_id="t4", max_seconds=2.0)
    r1 = b.remaining
    time.sleep(0.05)
    r2 = b.remaining
    assert r2 < r1, f"remaining should decrease: r1={r1}, r2={r2}"


def test_budget_snapshot_is_json_serializable():
    """snapshot() MUSS via json.dumps() serialisierbar sein
    (sonst kann StateManager.save_checkpoint() es nicht persistieren).
    """
    import json
    from core import SurveyBudget
    b = SurveyBudget(run_id="t5", max_seconds=10.0)
    with b.span("foo"):
        time.sleep(0.001)
    snap = b.snapshot()
    serialized = json.dumps(snap)  # MUSS nicht werfen
    parsed = json.loads(serialized)
    assert parsed["run_id"] == "t5"
