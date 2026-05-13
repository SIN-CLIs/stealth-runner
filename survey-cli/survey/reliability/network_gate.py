"""
Network Gate — Pre-click wait-for-network-quiet primitive.

SR-174: Pre-Click Network Gate (extends SR-169 Selector-Stability).

This module implements the *network half* of the full Pre-Click Stability
Gate. SR-169 (separate ticket) implements the *DOM half* in
``survey/reliability/stability.py``. When SR-169 lands, the canonical
``wait_for_full_stability`` will compose both:

    full_stable = dom_stable AND network_quiet

For SR-174 to be mergeable independently of SR-169, this module ships
:func:`wait_for_network_quiet` as a standalone primitive that any caller
can use today. The composition into ``wait_for_full_stability`` is a
follow-up change in SR-169's PR.

Failure semantics (CEO-rule):
    - We **never** deadlock. On ``max_wait_ms`` timeout we emit a
      ``network_never_quiet`` event and return ``GateResult(quiet=False,
      timed_out=True)``. The caller proceeds (force-proceed); the
      verifier (SR-167) is the second line of defense.
    - All event emission is best-effort. A failing event-emitter never
      raises out of :func:`wait_for_network_quiet`.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Awaitable, Callable

from survey.network.cdp_network_tracker import CdpNetworkTracker, NetworkActivity
from survey.runner_policy import NetworkTuning, get_network_tuning

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class GateResult:
    """Outcome of :func:`wait_for_network_quiet`.

    Attributes:
        quiet: True if the network reached the quiet state before timeout.
        timed_out: True if the gate gave up after ``max_wait_ms``. When
            this is True the caller should force-proceed and rely on the
            post-action verifier (SR-167) to detect downstream damage.
        waited_ms: Total wall-clock milliseconds spent in the gate.
        final_activity: The last :class:`NetworkActivity` snapshot taken
            (useful for diagnostic logging).
    """

    quiet: bool
    timed_out: bool
    waited_ms: int
    final_activity: NetworkActivity


# Type alias for the optional event emitter. Callers pass a coroutine
# function so events can be persisted asynchronously without blocking
# the hot path. Signature kept intentionally tiny: (event_name, payload).
EventEmitter = Callable[[str, dict], Awaitable[None]]


# Internal polling resolution. 10 ms is enough granularity for sub-100ms
# quiet-window detection without burning CPU.
_POLL_INTERVAL_S = 0.010


async def wait_for_network_quiet(
    tracker: CdpNetworkTracker,
    *,
    tuning: NetworkTuning | None = None,
    provider: str | None = None,
    on_event: EventEmitter | None = None,
) -> GateResult:
    """Block until the tracked page's network is quiet, or timeout.

    Quiet is defined by the provided :class:`NetworkTuning`:

        * ``pending_count <= max_pending_requests`` AND
        * ``last_response_age_ms >= network_quiet_ms``

    Resolution: one of ``tuning`` or ``provider`` must be supplied. If
    both are given, ``tuning`` wins (explicit override beats lookup).
    If neither is given the ``"_default"`` provider tuning is used.

    On timeout we emit a ``network_never_quiet`` event (if ``on_event``
    is provided) and return ``GateResult(quiet=False, timed_out=True)``.
    The caller decides what to do next — typically force-proceed and
    let the verifier catch any resulting drift.

    Raises:
        RuntimeError: if the tracker is not attached. Tracker lifecycle is
            the caller's responsibility (use ``async with CdpNetworkTracker(...)``).
    """
    if not tracker.is_attached:
        raise RuntimeError(
            "CdpNetworkTracker must be attached before calling wait_for_network_quiet"
        )

    effective = tuning if tuning is not None else get_network_tuning(provider)

    loop = asyncio.get_running_loop()
    start = loop.time()
    deadline = start + (effective.max_wait_ms / 1000.0)

    last_activity = tracker.activity()

    while True:
        last_activity = tracker.activity()
        if last_activity.is_quiet(
            max_pending=effective.max_pending_requests,
            min_age_ms=effective.network_quiet_ms,
        ):
            waited_ms = int((loop.time() - start) * 1000)
            return GateResult(
                quiet=True,
                timed_out=False,
                waited_ms=waited_ms,
                final_activity=last_activity,
            )

        if loop.time() >= deadline:
            waited_ms = int((loop.time() - start) * 1000)
            await _safe_emit(
                on_event,
                "network_never_quiet",
                {
                    "provider": provider,
                    "waited_ms": waited_ms,
                    "pending_count": last_activity.pending_count,
                    "last_response_age_ms": last_activity.last_response_age_ms,
                    "max_pending_requests": effective.max_pending_requests,
                    "network_quiet_ms": effective.network_quiet_ms,
                    "max_wait_ms": effective.max_wait_ms,
                    "total_started": last_activity.total_started,
                    "total_finished": last_activity.total_finished,
                    "beacons_filtered": last_activity.beacons_filtered,
                },
            )
            return GateResult(
                quiet=False,
                timed_out=True,
                waited_ms=waited_ms,
                final_activity=last_activity,
            )

        # Sleep until next poll or deadline, whichever comes first. Using
        # min() here keeps the worst-case waited_ms close to max_wait_ms
        # rather than overshooting by a full poll interval.
        remaining = deadline - loop.time()
        await asyncio.sleep(min(_POLL_INTERVAL_S, max(0.0, remaining)))


async def _safe_emit(
    emitter: EventEmitter | None,
    event: str,
    payload: dict,
) -> None:
    """Best-effort event emission. A failing emitter never breaks the gate."""
    if emitter is None:
        return
    try:
        await emitter(event, payload)
    except Exception as exc:
        logger.warning("network_gate event emit failed for %s: %s", event, exc)


__all__ = [
    "GateResult",
    "EventEmitter",
    "wait_for_network_quiet",
]
