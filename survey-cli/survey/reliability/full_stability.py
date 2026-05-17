"""================================================================================
FULL-STABILITY GATE — DOM + Network composition (SR-246)
================================================================================

MODUL-KONZEPT (SR-246, follow-up auf SR-169 + SR-174)
-----------------------------------------------------

PR #185 (SR-174 Network-Gate) hat im "Out of scope"-Block angekündigt:

    > safe_executor.py integration: waits for SR-169 to land. SR-169 owns
    > stability.py (DOM-subtree-hash); the natural composition is one
    > stability.wait_for_full_stability() that calls both DOM-stability
    > and wait_for_network_quiet.

SR-169 ist seit PR #182 in main. SR-174 ist seit PR #185 in main. Damit ist
die Komposition jetzt safe und nicht-merge-konfliktträchtig. Dieser Modul
liefert genau diese Komposition als kleine, eigenständige Facade.

WAS WIRD KOMPONIERT?
--------------------

    wait_for_dom_stability(...)   ← survey/reliability/stability.py    (SR-169)
    wait_for_network_quiet(...)   ← survey/reliability/network_gate.py (SR-174)

Beide werden SEQUENTIELL ausgeführt — DOM-Stability ZUERST, weil:

  1) Die Network-Gate-Latenz ist meist 0ms im Best-Case (Snapshot ist
     bereits quiet), während DOM-Stability mindestens `samples *
     stability_ms` warten muss.
  2) Wenn DOM unstable bleibt, hat ein nachgelagertes Network-Wait keinen
     Sinn (DOM mutiert noch, Click-Target ist instabil → wir wollen
     früh abbrechen).
  3) Lokales Reasoning: erst Hydration/Layout setzen, dann auf XHR-Settle
     warten. Das ist auch die Reihenfolge, in der ein Mensch wartet.

GLEICHE SEMANTIK WIE TEILE
--------------------------

    - dom verdict == "timeout"   → full verdict = "dom_timeout"     (no network call)
    - network timed_out          → full verdict = "network_timeout"
    - beide ok                   → full verdict = "stable"
    - dom verdict == "unstable"  → full verdict = "stable" (caller-akzeptiert)
                                    network wird trotzdem konsultiert

CEO-RULE: NEVER DEADLOCK
-------------------------
Beide Sub-Gates haben harte Deadlines (`max_wait_ms` / `network_quiet_ms`).
Diese Facade addiert keine eigene Wartezeit. Worst-case-Wartezeit
≤ stability_max_wait_ms + network_max_wait_ms.

PUBLIC API
----------
    FullStabilityVerdict       — Literal: "stable" | "dom_timeout" | "network_timeout"
    FullStabilityReport        — dataclass with both sub-reports + verdict
    wait_for_full_stability(.) — async public entry point

USAGE PATTERN
-------------

    >>> async def hash_target() -> str:
    ...     return cdp_subtree_hash(page, element_ref, max_depth=2)
    ...
    >>> async with CdpNetworkTracker(page) as tracker:
    ...     report = await wait_for_full_stability(
    ...         hasher=hash_target,
    ...         tracker=tracker,
    ...         provider="pollfish",
    ...     )
    ...     if report.verdict == "stable":
    ...         await safe_executor.click(element_ref)
    ...     elif report.verdict == "dom_timeout":
    ...         await snapshot_v2.capture_full(page); raise FullStabilityTimeout(report)
    ...     else:  # network_timeout — caller policy: force-proceed + lean on verifier
    ...         await safe_executor.click(element_ref)

OBSERVABILITY
-------------
    report.metric_dict()  → structlog-ready dict, includes both sub-metrics
    report.dom_report     → original StabilityReport (None on early-skip — never)
    report.network_result → original GateResult       (None on dom_timeout)

SCOPE
-----
- Pure-Python composition. Keine Playwright-Imports.
- Keine Wireup in safe_executor.py — das ist ein eigener PR (SR-247).
  Hier nur die Primitive.

Module Status: NEW (SR-246, follow-up to SR-169 + SR-174)
================================================================================
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Literal, Optional

from survey.reliability.network_gate import (
    EventEmitter,
    GateResult,
    wait_for_network_quiet,
)
from survey.reliability.stability import (
    StabilityConfig,
    StabilityReport,
    SubtreeHasher,
    wait_for_dom_stability,
)
from survey.runner_policy import NetworkTuning, get_network_tuning


# ── ENUM & DATACLASS ─────────────────────────────────────────────────────────


FullStabilityVerdict = Literal["stable", "dom_timeout", "network_timeout"]
"""
- "stable":          DOM converged AND network reached quiet within budget.
                     Action is safe to run.
- "dom_timeout":     DOM never converged. Network was NOT consulted.
                     Caller MUST force-fresh-snapshot and re-plan.
- "network_timeout": DOM converged but network never quiet. Caller policy
                     decides whether to force-proceed (rely on SR-167
                     verifier) or to abort.

Note: when wait_for_dom_stability returns "unstable" (had at least one
matching pair but no full streak within budget), we treat that as
"caller-accepted as good-enough" and proceed to the network check.
"""


@dataclass(frozen=True)
class FullStabilityReport:
    """Outcome of a wait_for_full_stability() run.

    Fields:
        verdict:        stable / dom_timeout / network_timeout
        elapsed_ms:     wall-clock from facade entry to facade exit
        dom_report:     the underlying StabilityReport (always present)
        network_result: the underlying GateResult, or None if we short-
                        circuited on dom_timeout (network was not called).
    """

    verdict: FullStabilityVerdict
    elapsed_ms: int
    dom_report: StabilityReport
    network_result: Optional[GateResult]

    def metric_dict(self) -> dict[str, object]:
        """structlog-ready combined metrics. Excludes hash traces."""
        out: dict[str, object] = {
            "verdict": self.verdict,
            "elapsed_ms": self.elapsed_ms,
            "dom_verdict": self.dom_report.verdict,
            "dom_samples_taken": self.dom_report.samples_taken,
            "dom_elapsed_ms": self.dom_report.elapsed_ms,
            "dom_distinct_hashes": self.dom_report.distinct_hashes,
        }
        if self.network_result is not None:
            out.update(
                {
                    "network_quiet": self.network_result.quiet,
                    "network_timed_out": self.network_result.timed_out,
                    "network_waited_ms": self.network_result.waited_ms,
                    "network_pending_count": self.network_result.final_activity.pending_count,
                    "network_last_response_age_ms": (
                        self.network_result.final_activity.last_response_age_ms
                    ),
                }
            )
        else:
            out["network_quiet"] = False
            out["network_skipped"] = True
        return out


# ── PUBLIC ENTRY POINT ───────────────────────────────────────────────────────


async def wait_for_full_stability(
    *,
    hasher: SubtreeHasher,
    tracker: object,  # duck-typed: must satisfy CdpNetworkTracker shape
    stability_config: Optional[StabilityConfig] = None,
    network_tuning: Optional[NetworkTuning] = None,
    provider: Optional[str] = None,
    on_event: Optional[EventEmitter] = None,
) -> FullStabilityReport:
    """Wait for both DOM and network to be stable, in that order.

    Algorithm:
      1) Run wait_for_dom_stability(hasher, stability_config).
      2) If verdict == "timeout": short-circuit with "dom_timeout".
         Network is NOT consulted (would be wasted budget).
      3) Otherwise call wait_for_network_quiet(tracker, ...).
      4) Combine into FullStabilityReport.

    Args:
        hasher: async no-arg callable returning the subtree hash. Must
            be the SAME contract as wait_for_dom_stability expects.
        tracker: an attached CdpNetworkTracker (caller owns the lifecycle).
        stability_config: tuning for the DOM half. None → defaults.
        network_tuning: explicit tuning for the network half. Wins over
            ``provider`` if both supplied.
        provider: provider key (e.g. "pollfish") for default tuning lookup.
            Used only when ``network_tuning`` is None.
        on_event: optional async event emitter, forwarded to the network
            gate. Best-effort — failure here never propagates.

    Returns:
        FullStabilityReport with verdict in {stable, dom_timeout,
        network_timeout}. ``dom_report`` is always populated;
        ``network_result`` is ``None`` only on dom_timeout.

    Raises:
        RuntimeError: if the tracker is not attached. Tracker lifecycle is
            the caller's responsibility (mirrors wait_for_network_quiet).

    Notes:
        - DOM-first ordering is intentional. See module docstring.
        - This facade adds zero own wait time. Worst-case latency ≤
          stability_max_wait_ms + network_max_wait_ms.
    """
    t_start = time.perf_counter()

    dom_report = await wait_for_dom_stability(hasher, config=stability_config)

    if dom_report.verdict == "timeout":
        elapsed_ms = int((time.perf_counter() - t_start) * 1000)
        return FullStabilityReport(
            verdict="dom_timeout",
            elapsed_ms=elapsed_ms,
            dom_report=dom_report,
            network_result=None,
        )

    # Resolve effective tuning the same way wait_for_network_quiet would —
    # we duplicate the lookup here only so that None/provider semantics
    # remain explicit and we can pass an explicit `tuning=` to keep the
    # network gate honest about its inputs.
    effective_tuning = (
        network_tuning if network_tuning is not None else get_network_tuning(provider)
    )

    network_result = await wait_for_network_quiet(
        tracker,  # type: ignore[arg-type]  # duck-typed at runtime
        tuning=effective_tuning,
        provider=provider,
        on_event=on_event,
    )

    elapsed_ms = int((time.perf_counter() - t_start) * 1000)
    verdict: FullStabilityVerdict = (
        "stable" if network_result.quiet else "network_timeout"
    )

    return FullStabilityReport(
        verdict=verdict,
        elapsed_ms=elapsed_ms,
        dom_report=dom_report,
        network_result=network_result,
    )


__all__ = [
    "FullStabilityReport",
    "FullStabilityVerdict",
    "wait_for_full_stability",
]
