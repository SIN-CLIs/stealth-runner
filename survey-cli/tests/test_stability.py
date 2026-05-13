"""
test_stability.py — Unit tests for survey/reliability/stability.py.

Coverage strategy:
  - Happy path: hash converges immediately (3 identical samples)
  - Late convergence: 2 different + 3 identical → stable
  - Never converges: every sample differs → timeout
  - Hasher raises → counted as broken streak, not crash
  - Hasher times out → counted as broken streak
  - Latency: total elapsed_ms ≤ max_wait_ms
  - Custom samples count (e.g. 2 instead of 3)
  - Edge: samples < 2 must raise

Hashers are plain async closures returning canned strings.
No browser, no playwright — purely structural.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator

import pytest

from survey.reliability.stability import (
    StabilityConfig,
    StabilityReport,
    wait_for_dom_stability,
)


# ── HELPERS ──────────────────────────────────────────────────────────────────


def _scripted_hasher(values: list[str]):
    """
    Build a hasher that returns the i-th element each call.
    Once the script is exhausted, repeats the last value (mimicking
    a real DOM that has settled).
    """
    it: Iterator[str] = iter(values)
    last = {"v": values[0]}

    async def fn() -> str:
        try:
            last["v"] = next(it)
        except StopIteration:
            pass
        return last["v"]

    return fn


def _delayed_hasher(values: list[str], delay_ms: int):
    """Hasher that sleeps before responding — for timeout tests."""
    it: Iterator[str] = iter(values)
    last = {"v": values[0]}

    async def fn() -> str:
        await asyncio.sleep(delay_ms / 1000.0)
        try:
            last["v"] = next(it)
        except StopIteration:
            pass
        return last["v"]

    return fn


def _raising_hasher(values: list[str], raise_at_index: int):
    """Hasher that raises on a specific call."""
    state = {"i": 0}

    async def fn() -> str:
        i = state["i"]
        state["i"] += 1
        if i == raise_at_index:
            raise RuntimeError("simulated CDP failure")
        return values[min(i, len(values) - 1)]

    return fn


# ── HAPPY PATH ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_stable_immediately_3_identical_samples() -> None:
    """3 consecutive identical hashes → stable on the 3rd sample."""
    hasher = _scripted_hasher(["abc", "abc", "abc"])
    cfg = StabilityConfig(stability_ms=10, max_wait_ms=200, samples=3)
    report = await wait_for_dom_stability(hasher, config=cfg)

    assert report.verdict == "stable"
    assert report.samples_taken == 3
    assert report.distinct_hashes == 1
    assert report.converged_after_sample == 0
    assert report.hash_trace == ["abc", "abc", "abc"]


@pytest.mark.asyncio
async def test_stable_after_initial_drift() -> None:
    """
    2 different hashes, then 3 identical → stable.
    Tests that the streak counter resets correctly.
    """
    hasher = _scripted_hasher(["a", "b", "c", "c", "c"])
    cfg = StabilityConfig(stability_ms=5, max_wait_ms=500, samples=3)
    report = await wait_for_dom_stability(hasher, config=cfg)

    assert report.verdict == "stable"
    assert report.samples_taken == 5
    assert report.distinct_hashes == 3
    # Streak of "c"s started at index 2.
    assert report.converged_after_sample == 2


# ── TIMEOUT ──────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_timeout_when_hash_never_converges() -> None:
    """Every sample differs → eventually times out."""
    # Generate an "infinite" set of unique values via iteration index.
    counter = {"n": 0}

    async def fn() -> str:
        counter["n"] += 1
        return f"hash_{counter['n']}"

    cfg = StabilityConfig(stability_ms=10, max_wait_ms=60, samples=3)
    report = await wait_for_dom_stability(fn, config=cfg)

    assert report.verdict == "timeout"
    assert report.elapsed_ms >= 60
    # Caller is supposed to escalate (force-fresh snapshot).
    assert report.converged_after_sample == -1


# ── HASHER FAILURES ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_hasher_exception_breaks_streak_but_does_not_crash() -> None:
    """
    Even if the hasher raises mid-flight, wait_for_dom_stability
    must return cleanly. The error sentinel breaks the current streak.
    """
    # Samples: a, a, RAISE, a, a, a → after raise, new streak of 3 a's.
    hasher = _raising_hasher(["a", "a", "?", "a", "a", "a"], raise_at_index=2)
    cfg = StabilityConfig(stability_ms=5, max_wait_ms=500, samples=3)
    report = await wait_for_dom_stability(hasher, config=cfg)

    # The exception broke the streak, so we needed all 6 samples.
    assert report.verdict == "stable"
    assert report.samples_taken == 6
    # One of the trace entries should be the error sentinel.
    assert any(h.startswith("ERR:RuntimeError") for h in report.hash_trace)


@pytest.mark.asyncio
async def test_hasher_timeout_breaks_streak() -> None:
    """
    A slow hasher (exceeds per-call timeout = stability_ms) is recorded
    as a synthetic "ERR:timeout:..." hash, breaking the streak.
    """
    # delay 100ms > stability_ms 20ms → every call times out.
    hasher = _delayed_hasher(["a", "a", "a", "a", "a"], delay_ms=100)
    cfg = StabilityConfig(stability_ms=20, max_wait_ms=200, samples=3)
    report = await wait_for_dom_stability(hasher, config=cfg)

    # All samples were ERR:timeout:<ts>. Each timeout uses a unique ns
    # timestamp, so the streak never establishes.
    assert report.verdict == "timeout"
    assert all(h.startswith("ERR:timeout:") for h in report.hash_trace)
    # Every hash sentinel is unique because of the ns suffix.
    assert report.distinct_hashes == report.samples_taken


# ── CUSTOM CONFIG ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_samples_count_2_is_enough() -> None:
    """With samples=2 we accept stable after 1 repeat."""
    hasher = _scripted_hasher(["x", "x"])
    cfg = StabilityConfig(stability_ms=5, max_wait_ms=100, samples=2)
    report = await wait_for_dom_stability(hasher, config=cfg)

    assert report.verdict == "stable"
    assert report.samples_taken == 2


@pytest.mark.asyncio
async def test_samples_count_below_2_raises_at_call() -> None:
    """samples=1 makes no sense (1 sample is trivially 'stable')."""
    hasher = _scripted_hasher(["a"])
    cfg = StabilityConfig(stability_ms=5, max_wait_ms=100, samples=1)
    with pytest.raises(ValueError, match="samples must be >= 2"):
        await wait_for_dom_stability(hasher, config=cfg)


# ── LATENCY INVARIANTS ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_elapsed_within_budget() -> None:
    """elapsed_ms must be < max_wait_ms + small jitter even on timeout."""
    counter = {"n": 0}

    async def fn() -> str:
        counter["n"] += 1
        return f"hash_{counter['n']}"

    cfg = StabilityConfig(stability_ms=10, max_wait_ms=80, samples=3)
    report = await wait_for_dom_stability(fn, config=cfg)

    assert report.elapsed_ms < 150, (
        f"max_wait_ms=80, but elapsed={report.elapsed_ms}ms — gate not respecting budget"
    )


@pytest.mark.asyncio
async def test_stable_path_fast_path_under_budget() -> None:
    """When the DOM is already stable, we should NOT wait for full max_wait."""
    hasher = _scripted_hasher(["same", "same", "same"])
    cfg = StabilityConfig(stability_ms=5, max_wait_ms=10_000, samples=3)
    report = await wait_for_dom_stability(hasher, config=cfg)

    assert report.verdict == "stable"
    # Stable in 3 samples × 5 ms = ~10 ms (plus some scheduling jitter).
    # Strict upper bound 150 ms — anything more means we're regression-broken.
    assert report.elapsed_ms < 150


# ── REPORT API ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_metric_dict_excludes_hash_trace() -> None:
    """metric_dict() must be log-safe (no large hash arrays)."""
    hasher = _scripted_hasher(["h", "h", "h"])
    cfg = StabilityConfig(stability_ms=5, max_wait_ms=50, samples=3)
    report = await wait_for_dom_stability(hasher, config=cfg)

    metrics = report.metric_dict()
    assert "hash_trace" not in metrics
    assert metrics["verdict"] == "stable"
    assert metrics["samples_taken"] == 3
    assert metrics["distinct_hashes"] == 1
    assert metrics["converged_after_sample"] == 0
    assert isinstance(metrics["elapsed_ms"], int)


@pytest.mark.asyncio
async def test_report_is_frozen() -> None:
    """StabilityReport is immutable for log integrity."""
    hasher = _scripted_hasher(["h", "h", "h"])
    cfg = StabilityConfig(stability_ms=5, max_wait_ms=50, samples=3)
    report = await wait_for_dom_stability(hasher, config=cfg)

    with pytest.raises((AttributeError, TypeError, Exception)):
        report.verdict = "timeout"  # type: ignore[misc]


# ── DEFAULTS ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_default_config_works_without_config_arg() -> None:
    """Passing no config uses StabilityConfig() defaults."""
    hasher = _scripted_hasher(["d", "d", "d"])
    report = await wait_for_dom_stability(hasher)

    # Default is stability_ms=150, samples=3 — so this takes ~300 ms.
    assert isinstance(report, StabilityReport)
    assert report.verdict == "stable"
