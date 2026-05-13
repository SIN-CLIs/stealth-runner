"""================================================================================
TRIPLE-CHANNEL ATTESTATION — Anti-"DOM-lies" Verification Core (SR-168 Phase 2B)
================================================================================

MODUL-KONZEPT (SR-168, 2026-05-13)
-----------------------------------

WARUM ÜBERHAUPT?
    Nach einer Aktion (Klick, fill, select) prüft `verifier.py` (SR-167)
    aktuell nur, ob sich der DOM verändert hat. Drei reale Failure-Modi
    schlagen daran vorbei:

      1) `pointer-events: none` Overlay verschluckt den echten Klick,
         DOM ändert sich aber via spätere unrelated reflow → "DOM lies".
      2) React/Vue synthetic events triggern DOM-Updates, aber AX-Tree
         (was Screen-Reader und Bot-Detectors sehen) bleibt unverändert.
      3) Iframe-Klick wird von Parent-Frame "abgefangen" — DOM des
         Iframes ändert sich nicht, AX zeigt aber kurzes Aufflackern.

    Lösung: drei unabhängige Wahrnehmungs-Channel kombinieren:

      A) DOM-Diff      — strukturelle Änderung im Markup
      B) AX-Tree-Diff  — semantische Änderung (was Tools sehen)
      C) Vision-Hash   — pixel-perzeptuelle Änderung (was Menschen sehen)

    Disagreement-Matrix entscheidet, was als Erfolg gilt.

DIESES MODUL: backend-agnostischer Aggregator
---------------------------------------------
    Channels werden als async Callables injiziert. Das macht das Modul:
      • Sofort unit-testbar (mocked channels, deterministisch)
      • Unabhängig von CDP/playwright/cua-driver-Wahl (PR C verdrahtet
        die echten Channels in `survey/reliability/attestation_channels.py`)
      • Wiederverwendbar in CLI-Modus UND Daemon-Modus (gleiche Matrix)

DISAGREEMENT-MATRIX (CANONICAL)
-------------------------------

    (DOM, AX, VISION) → (decision, escalate_to)

      (T, T, T) → ok                — alle 3 sehen Änderung
      (T, T, F) → fail              — Vision sieht nichts → Overlay-Verdacht
      (T, F, T) → ok_with_warning   — AX lag, akzeptabel
      (T, F, F) → fail              — nur DOM → React-stale-state oder Overlay
      (F, T, T) → ok_with_warning   — selector-drift, AX+Vision bestätigen
      (F, T, F) → fail              — selector-drift + Vision-blind
      (F, F, T) → fail              — Pixel-only ohne Semantik = Animation, nicht Antwort
      (F, F, F) → fail_escalate     — komplette Stille, eskaliere zu pixel-click

2-OF-2 FALLBACK
---------------
    Wenn AX-Channel "unavailable" meldet (Chrome ohne
    --force-renderer-accessibility, Cross-Origin-Iframe, etc.), gilt:

      DOM + VISION agree → ok
      one of them        → ok_with_warning
      neither            → fail_escalate

LATENCY-BUDGET
--------------
    Die 3 Channels laufen via asyncio.gather() parallel. Single channel
    timeout: 300 ms. Default total timeout: 350 ms p95.

PUBLIC API
----------
    AttestationChannel  — enum (DOM/AX/VISION)
    ChannelResult       — dataclass per Channel
    AttestationResult   — final aggregated decision
    ChannelFn           — Protocol für injizierbare Channels
    AttestationConfig   — Tuning (timeouts, AX-availability)

    async def verify_triple(
        channel_dom: ChannelFn,
        channel_ax:  ChannelFn | None,        # None = skip → 2-of-2-Modus
        channel_vis: ChannelFn,
        config:      AttestationConfig | None = None,
    ) -> AttestationResult

USAGE PATTERN (PR C wird das tun)
---------------------------------
    >>> result = await verify_triple(
    ...     channel_dom=lambda: dom_diff(snap_pre, snap_post, expected),
    ...     channel_ax=lambda:  ax_diff(ax_pre, ax_post, expected),
    ...     channel_vis=lambda: visual_diff(png_pre, png_post),
    ... )
    >>> if result.decision == "fail_escalate":
    ...     await cua_pixel_click_fallback()

Module Status: NEW (SR-168 Phase 2B, 2026-05-13)
================================================================================
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from enum import Enum
from typing import Awaitable, Literal, Optional, Protocol


# ── ENUMS & DATACLASSES ──────────────────────────────────────────────────────


class AttestationChannel(str, Enum):
    """Identifier for each of the three perception channels."""

    DOM = "dom"
    AX = "ax"
    VISION = "vision"


Decision = Literal["ok", "ok_with_warning", "fail", "fail_escalate"]
EscalateTarget = Literal["cua_pixel_click", "manual_retry"]


@dataclass(frozen=True)
class ChannelResult:
    """
    Result of a single channel's perception attempt.

    Fields:
        channel:           which of the 3 channels this is
        observed_change:   did this channel see the expected change?
        confidence:        0.0 = noise, 1.0 = certain (used for logging)
        detail:            free-form diagnostic ("hamming=12/64", "selector=#q1")
        latency_ms:        how long this channel took
        unavailable:       True iff the channel could not run at all
                           (timeout, exception, AX not granted, etc.)
    """

    channel: AttestationChannel
    observed_change: bool
    confidence: float = 0.0
    detail: str = ""
    latency_ms: int = 0
    unavailable: bool = False


@dataclass(frozen=True)
class AttestationResult:
    """
    Aggregated decision across all channels.

    Fields:
        decision:                 ok / ok_with_warning / fail / fail_escalate
        channels:                 per-channel results
        disagreement_signature:   "111", "101", "1_1" (X = unavailable) for grouping
        duration_ms:              wall-clock for the parallel gather
        escalate_to:              non-None only if decision == "fail_escalate"
    """

    decision: Decision
    channels: list[ChannelResult]
    disagreement_signature: str
    duration_ms: int
    escalate_to: Optional[EscalateTarget] = None


# ── INJECTED CHANNEL CONTRACT ────────────────────────────────────────────────


class ChannelFn(Protocol):
    """
    A channel is an async callable that returns a ChannelResult.

    Channel implementations live in `attestation_channels.py` (PR C).
    They wrap CDP / cua-driver / Pillow operations.

    Pattern: take everything you need via closure at the call site:

        async def my_dom_channel() -> ChannelResult:
            post = await cdp_universal.scan(...)
            return ChannelResult(
                channel=AttestationChannel.DOM,
                observed_change=(pre.hash != post.hash),
                confidence=1.0,
                ...
            )
    """

    def __call__(self) -> Awaitable[ChannelResult]: ...


# ── CONFIG ───────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class AttestationConfig:
    """
    Tuning knobs. Defaults are tuned for survey-style interactions
    (300-400 ms typical react-update latency on consumer hardware).
    """

    per_channel_timeout_ms: int = 300
    total_timeout_ms: int = 350
    """If gather() exceeds this, remaining channels return unavailable=True."""

    treat_unavailable_as_disagree: bool = False
    """
    Tri-state matrix semantics:
      - False (default): unavailable channels are dropped → 2-of-2 mode.
      - True:            unavailable channels count as observed_change=False.
                         Useful for paranoid/strict mode where missing AX
                         must imply we DON'T trust DOM-only success.
    """


# ── MATRIX (3-of-3 TIE-BREAKER) ──────────────────────────────────────────────


# Tuple key: (dom_observed, ax_observed, vision_observed) — all bools, all
# channels available. Value: (decision, escalate_target).
_MATRIX_3OF3: dict[tuple[bool, bool, bool], tuple[Decision, Optional[EscalateTarget]]] = {
    (True, True, True): ("ok", None),
    (True, True, False): ("fail", None),
    (True, False, True): ("ok_with_warning", None),
    (True, False, False): ("fail", None),
    (False, True, True): ("ok_with_warning", None),
    (False, True, False): ("fail", None),
    (False, False, True): ("fail", None),
    (False, False, False): ("fail_escalate", "cua_pixel_click"),
}


def _decide_2of2(
    dom_observed: bool, vision_observed: bool
) -> tuple[Decision, Optional[EscalateTarget]]:
    """
    AX-unavailable fallback. Used when channel_ax was passed None,
    OR when the AX channel returned unavailable=True.
    """
    if dom_observed and vision_observed:
        return ("ok", None)
    if dom_observed or vision_observed:
        return ("ok_with_warning", None)
    return ("fail_escalate", "cua_pixel_click")


# ── PUBLIC ENTRY POINT ───────────────────────────────────────────────────────


async def verify_triple(
    *,
    channel_dom: ChannelFn,
    channel_ax: Optional[ChannelFn],
    channel_vis: ChannelFn,
    config: Optional[AttestationConfig] = None,
) -> AttestationResult:
    """
    Run up to 3 perception channels in parallel and aggregate.

    Channels execute via asyncio.gather() with per-channel timeouts.
    If a channel raises or times out, its result is recorded as
    unavailable=True (NOT counted as observed_change=False).

    The disagreement-matrix then maps the observed-change triple to a
    final Decision. When AX is missing (None passed, or unavailable=True
    in its result), fall back to the 2-of-2 matrix.

    Args:
        channel_dom: required — DOM-diff channel
        channel_ax:  optional — AX-tree diff. Pass None to skip entirely
                     (e.g., when chrome was not launched with
                     --force-renderer-accessibility).
        channel_vis: required — visual-hash channel (uses visual_hash.py)
        config:      tuning. None → AttestationConfig() defaults.

    Returns:
        AttestationResult with .decision in {ok, ok_with_warning, fail,
        fail_escalate}.

    Raises:
        Nothing. All channel exceptions are caught and recorded.
    """
    cfg = config or AttestationConfig()
    t_start = time.perf_counter()

    coros: list[Awaitable[ChannelResult]] = [
        _run_channel_safe(AttestationChannel.DOM, channel_dom, cfg.per_channel_timeout_ms),
        _run_channel_safe(AttestationChannel.VISION, channel_vis, cfg.per_channel_timeout_ms),
    ]
    if channel_ax is not None:
        coros.insert(
            1,
            _run_channel_safe(AttestationChannel.AX, channel_ax, cfg.per_channel_timeout_ms),
        )

    try:
        results = await asyncio.wait_for(
            asyncio.gather(*coros), timeout=cfg.total_timeout_ms / 1000.0
        )
    except asyncio.TimeoutError:
        # Whoever finished gets recorded; the rest get "unavailable=True".
        # Since we already wrap each channel with its own per-channel timeout,
        # hitting this branch is rare (only if many channels jointly exceed
        # the total budget). Build placeholders.
        results = [
            ChannelResult(
                channel=c,
                observed_change=False,
                unavailable=True,
                detail="total_timeout_exceeded",
                latency_ms=cfg.total_timeout_ms,
            )
            for c in (AttestationChannel.DOM, AttestationChannel.AX, AttestationChannel.VISION)
            if c != AttestationChannel.AX or channel_ax is not None
        ]

    duration_ms = int((time.perf_counter() - t_start) * 1000)

    # Index results by channel for matrix lookup.
    by_channel: dict[AttestationChannel, ChannelResult] = {r.channel: r for r in results}
    dom = by_channel[AttestationChannel.DOM]
    vis = by_channel[AttestationChannel.VISION]
    ax: Optional[ChannelResult] = by_channel.get(AttestationChannel.AX)

    # Decide whether AX is usable.
    ax_usable = ax is not None and not ax.unavailable

    if not ax_usable and cfg.treat_unavailable_as_disagree and ax is not None:
        # Strict mode: a present-but-failed AX counts as observed=False.
        # If channel_ax was passed None, we still fall through to 2-of-2.
        ax_usable = True

    if ax_usable and ax is not None:
        triple = (dom.observed_change, ax.observed_change, vis.observed_change)
        decision, escalate = _MATRIX_3OF3[triple]
        sig = "".join("1" if b else "0" for b in triple)
    else:
        decision, escalate = _decide_2of2(dom.observed_change, vis.observed_change)
        # Use "_" for the unavailable AX position so logs can grep these.
        sig = (
            f"{'1' if dom.observed_change else '0'}"
            f"_"
            f"{'1' if vis.observed_change else '0'}"
        )

    # Final result includes the actual (possibly-unavailable) AX entry,
    # so downstream observability sees the truth.
    ordered_channels = [dom]
    if ax is not None:
        ordered_channels.append(ax)
    ordered_channels.append(vis)

    return AttestationResult(
        decision=decision,
        channels=ordered_channels,
        disagreement_signature=sig,
        duration_ms=duration_ms,
        escalate_to=escalate,
    )


# ── INTERNAL: PER-CHANNEL SAFE WRAPPER ───────────────────────────────────────


async def _run_channel_safe(
    channel: AttestationChannel, fn: ChannelFn, timeout_ms: int
) -> ChannelResult:
    """
    Execute one channel function with a hard timeout. Any failure mode
    (exception, timeout) is converted to a `unavailable=True` result so
    the aggregator can downgrade gracefully.
    """
    t_start = time.perf_counter()
    try:
        result = await asyncio.wait_for(fn(), timeout=timeout_ms / 1000.0)
        # Trust the channel's self-reported latency if it set one; else compute.
        if result.latency_ms == 0:
            elapsed = int((time.perf_counter() - t_start) * 1000)
            return ChannelResult(
                channel=result.channel,
                observed_change=result.observed_change,
                confidence=result.confidence,
                detail=result.detail,
                latency_ms=elapsed,
                unavailable=result.unavailable,
            )
        return result
    except asyncio.TimeoutError:
        elapsed = int((time.perf_counter() - t_start) * 1000)
        return ChannelResult(
            channel=channel,
            observed_change=False,
            unavailable=True,
            detail=f"channel_timeout_{timeout_ms}ms",
            latency_ms=elapsed,
        )
    except Exception as exc:  # noqa: BLE001 — channel boundary, deliberately broad
        elapsed = int((time.perf_counter() - t_start) * 1000)
        return ChannelResult(
            channel=channel,
            observed_change=False,
            unavailable=True,
            detail=f"channel_error: {type(exc).__name__}: {exc!s}",
            latency_ms=elapsed,
        )


# ── PUBLIC RE-EXPORTS ────────────────────────────────────────────────────────


__all__ = [
    "AttestationChannel",
    "AttestationConfig",
    "AttestationResult",
    "ChannelFn",
    "ChannelResult",
    "verify_triple",
]
