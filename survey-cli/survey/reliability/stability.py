"""================================================================================
DOM-STABILITY GATE — Pre-Action Hydration / Lazy-Mount Guard (SR-169 Phase 3)
================================================================================

MODUL-KONZEPT (SR-169, 2026-05-13)
-----------------------------------

WARUM ÜBERHAUPT?
    Zwischen `snapshot()` und `click()` vergehen typisch 150-400 ms
    (LLM-Roundtrip für Answer-Selection). In dieser Zeit kann der
    DOM mutieren:

      1) **React-Hydration-Race**: SSR-HTML wird durch hydrierte
         Components ersetzt. `data-react-id` ändert sich. Unsere
         `@eN`-ElementRef zeigt ins Nichts.
      2) **Lazy-loaded Components**: ein Skeleton-Loader wird durch
         den echten Question-Body ersetzt. Selector-Drift.
      3) **Animation-Settle**: Modal slidet rein, button verschiebt
         sich um 60 px während Action gefeuert wird. Click landet
         5 px daneben.

    Resultat: silenter Failure. Klick ging ins Leere. Verifier
    (SR-167) merkt es, aber zu spät — wir haben schon den State
    pollutiert.

LÖSUNG: ACTIVE STABILITY-GATE
-----------------------------
    Vor jedem state-changing Action:

      1) Nimm `samples` (default 3) Single-Element-Hashes des
         Target-Subtree, `stability_ms` (default 150ms) auseinander.
      2) Sind alle identisch → stable, action darf laufen.
      3) Sind sie verschieden → wait + re-sample, bis `max_wait_ms`
         (default 2s) erreicht.
      4) Wenn max_wait überschritten → return stable=False. Caller
         muss force-fresh snapshot + neu planen.

WARUM SUBTREE-HASH STATT FULL-DOM?
    Ein voller DOM-Snapshot kostet 50-150ms auf realen Surveys
    (vielleicht 800 DOM-Nodes nach React-Hydration). Wir bräuchten
    3-5 Samples → 0.5-1.0s nur fürs Gate. Inakzeptabel.

    Ein Subtree-Hash (target-element + 2 levels children) ist
    O(target-size), typisch < 5ms. Damit ist das Gate-Budget
    `stability_ms * samples = 450ms p50`.

DIESES MODUL: backend-agnostisch
---------------------------------
    Wie `attestation.py`: das Hash-Sampling wird über einen async
    Callable injiziert. PR C verdrahtet die CDP-Variante. Tests
    nutzen fake hashers (synchronous, deterministisch).

PUBLIC API
----------
    StabilityVerdict     — Literal: "stable" | "unstable" | "timeout"
    StabilityReport      — dataclass with samples + verdict + timing
    SubtreeHasher        — Protocol für injizierbare hash-fn

    async def wait_for_dom_stability(
        hasher:        SubtreeHasher,
        *,
        stability_ms:  int = 150,
        max_wait_ms:   int = 2000,
        samples:       int = 3,
    ) -> StabilityReport

USAGE PATTERN (PR C wird das tun)
---------------------------------
    >>> async def my_hasher() -> str:
    ...     return subtree_hash(page, element_ref)
    ...
    >>> report = await wait_for_dom_stability(my_hasher)
    >>> if report.verdict == "stable":
    ...     await safe_executor.click(element_ref)
    ... elif report.verdict == "timeout":
    ...     # Force fresh full snapshot upstream and re-plan.
    ...     await snapshot_v2.capture_full(page)
    ...     raise StabilityTimeout(report)
    ... # verdict == "unstable" only happens when samples disagreed but
    ... # we accepted within max_wait — call site usually treats as stable.

PROVIDER-OVERRIDES (folgt SR-159)
---------------------------------
    `runner_policy.py` bekommt einen Hook (PR C):

        runner_policy.stability_overrides = {
            "heypiggy.com":  StabilityConfig(stability_ms=200, max_wait_ms=3000),
            "swagbucks.com": StabilityConfig(stability_ms=100, max_wait_ms=1500),
            "default":       StabilityConfig(),
        }

    Manche Surveys haben besonders nervöses JS — die brauchen mehr
    Settle-Time. Andere sind statisch — die wollen wir nicht mit
    unnötigem Warten ausbremsen.

OBSERVABILITY (folgt SR-191)
----------------------------
    `report.metric_dict()` liefert structlog-ready dict:

        logger.info("dom.stability", **report.metric_dict())

    Felder: verdict, samples_taken, elapsed_ms, distinct_hashes,
            converged_after_sample.

Module Status: NEW (SR-169 Phase 3, 2026-05-13)
================================================================================
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Awaitable, Literal, Optional, Protocol


# ── ENUMS & DATACLASSES ──────────────────────────────────────────────────────


StabilityVerdict = Literal["stable", "unstable", "timeout"]
"""
- "stable":    `samples` consecutive identical hashes observed.
- "unstable":  hashes still differing when budget ran out, but we
               had at least *some* identical pair — caller may
               proceed with caution.
- "timeout":   max_wait_ms exhausted, never converged. Caller MUST
               force-fresh-snapshot and re-plan.
"""


@dataclass(frozen=True)
class StabilityConfig:
    """Tuning. Provider-specific overrides plug in here."""

    stability_ms: int = 150
    """Time between samples."""

    max_wait_ms: int = 2000
    """Hard cap on total time we'll wait for stability."""

    samples: int = 3
    """Number of consecutive identical hashes required to declare stable."""


@dataclass(frozen=True)
class StabilityReport:
    """
    Outcome of a stability-gate run.

    Fields:
        verdict:                stable / unstable / timeout
        samples_taken:          how many hashes we collected total
        elapsed_ms:             wall-clock from start to verdict
        distinct_hashes:        cardinality of {h1, h2, ...}
        converged_after_sample: index of the last hash that started
                                the stable streak (only meaningful when
                                verdict == "stable"). 0-indexed; -1 if
                                never converged.
        hash_trace:             list of all collected hashes in order
                                — for debug logs only, NOT for hot path
    """

    verdict: StabilityVerdict
    samples_taken: int
    elapsed_ms: int
    distinct_hashes: int
    converged_after_sample: int
    hash_trace: list[str] = field(default_factory=list)

    def metric_dict(self) -> dict[str, object]:
        """structlog-ready metrics. Excludes `hash_trace` (PII-shaped)."""
        return {
            "verdict": self.verdict,
            "samples_taken": self.samples_taken,
            "elapsed_ms": self.elapsed_ms,
            "distinct_hashes": self.distinct_hashes,
            "converged_after_sample": self.converged_after_sample,
        }


# ── INJECTED HASHER CONTRACT ─────────────────────────────────────────────────


class SubtreeHasher(Protocol):
    """
    A no-arg async callable returning the current hash of the target
    subtree as a stable string (hex/sha, both fine — we only compare
    for equality).

    Implementations live in `survey/reliability/stability_cdp.py` (PR C)
    and `survey/snapshot.py` (new `subtree_hash()` helper).

    Pattern:
        async def my_hasher() -> str:
            return cdp_subtree_hash(page, element_ref, max_depth=2)
    """

    def __call__(self) -> Awaitable[str]: ...


# ── PUBLIC ENTRY POINT ───────────────────────────────────────────────────────


async def wait_for_dom_stability(
    hasher: SubtreeHasher,
    *,
    config: Optional[StabilityConfig] = None,
) -> StabilityReport:
    """
    Wait until the target subtree's hash stops changing.

    Algorithm:
      Take an initial hash; then repeatedly:
        - sleep stability_ms
        - hash again
        - if `samples` consecutive samples agree → "stable"
        - if budget (max_wait_ms) exceeded → "timeout"

    Notes:
      - Each hasher() invocation has the same per-call timeout as the
        sleep window (`stability_ms`) — if hashing alone exceeds that,
        we count it as a "failed sample" and continue. This prevents
        a stuck CDP call from blocking the gate.
      - All hasher() exceptions are caught and rendered as a synthetic
        hash "ERR:<exception-class>" so the streak resets cleanly.

    Args:
        hasher: async callable returning the current subtree hash
        config: tuning. None → StabilityConfig() defaults.

    Returns:
        StabilityReport with .verdict in {stable, unstable, timeout}.

    Raises:
        Nothing. Errors in the hasher are absorbed.
    """
    cfg = config or StabilityConfig()
    if cfg.samples < 2:
        raise ValueError(f"samples must be >= 2, got {cfg.samples}")

    t_start = time.perf_counter()
    deadline_s = cfg.stability_ms / 1000.0
    budget_s = cfg.max_wait_ms / 1000.0

    trace: list[str] = []
    # `streak_start` = index in `trace` where the current run of identical
    # hashes began. We need `cfg.samples` identical consecutive hashes.
    streak_start = 0

    # First sample.
    trace.append(await _safe_hash(hasher, deadline_s))

    while True:
        elapsed_s = time.perf_counter() - t_start
        if elapsed_s >= budget_s:
            return _build_report("timeout", trace, t_start)

        # Wait the inter-sample window — but respect total budget.
        sleep_s = min(deadline_s, budget_s - elapsed_s)
        if sleep_s > 0:
            await asyncio.sleep(sleep_s)

        trace.append(await _safe_hash(hasher, deadline_s))

        # Did this sample match the previous one?
        if trace[-1] == trace[-2]:
            # Streak continues. Have we reached `samples` identical in a row?
            run_length = len(trace) - streak_start
            if run_length >= cfg.samples:
                return _build_report("stable", trace, t_start, converged_at=streak_start)
        else:
            # Streak broken; new streak starts at this hash.
            streak_start = len(trace) - 1

        # Loop continues; the top-of-loop check handles the budget.


# ── INTERNAL HELPERS ─────────────────────────────────────────────────────────


async def _safe_hash(hasher: SubtreeHasher, timeout_s: float) -> str:
    """
    Invoke the injected hasher with a per-call timeout. Convert all
    failure modes to a synthetic sentinel hash so the streak detector
    treats them as "definitely not stable".

    Returns a string; never raises.
    """
    try:
        return await asyncio.wait_for(hasher(), timeout=timeout_s)
    except asyncio.TimeoutError:
        # Use the current monotonic time as a salt so consecutive
        # timeouts produce DIFFERENT sentinels — that way they break
        # the streak instead of accidentally agreeing.
        return f"ERR:timeout:{time.perf_counter_ns()}"
    except Exception as exc:  # noqa: BLE001 — channel boundary
        return f"ERR:{type(exc).__name__}:{exc!s}:{time.perf_counter_ns()}"


def _build_report(
    verdict: StabilityVerdict,
    trace: list[str],
    t_start: float,
    converged_at: int = -1,
) -> StabilityReport:
    """Compute distinct hash count and elapsed_ms, package up."""
    elapsed_ms = int((time.perf_counter() - t_start) * 1000)
    distinct = len(set(trace))
    return StabilityReport(
        verdict=verdict,
        samples_taken=len(trace),
        elapsed_ms=elapsed_ms,
        distinct_hashes=distinct,
        converged_after_sample=converged_at,
        hash_trace=list(trace),
    )


# ── PUBLIC RE-EXPORTS ────────────────────────────────────────────────────────


__all__ = [
    "StabilityConfig",
    "StabilityReport",
    "StabilityVerdict",
    "SubtreeHasher",
    "wait_for_dom_stability",
]
