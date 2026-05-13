"""
test_attestation.py — Unit tests for survey/reliability/attestation.py.

Coverage strategy:
  - Matrix: all 8 rows of the 3-of-3 disagreement matrix.
  - Fallback: all 4 rows of the 2-of-2 matrix (AX-unavailable).
  - Failure modes: channel raises, channel times out, total budget exceeded.
  - Strict mode: treat_unavailable_as_disagree behavior.
  - Latency: parallel-gather respects total budget.

All channels are mocked as plain async functions returning ChannelResult.
No browser, no playwright, no CDP — this module is purely structural.
"""

from __future__ import annotations

import asyncio
import pytest

from survey.reliability.attestation import (
    AttestationChannel,
    AttestationConfig,
    ChannelResult,
    verify_triple,
)


# ── HELPERS ──────────────────────────────────────────────────────────────────


def _make_channel(channel: AttestationChannel, observed: bool, confidence: float = 0.9):
    """Build a fake async channel that just returns the desired observation."""

    async def fn() -> ChannelResult:
        return ChannelResult(
            channel=channel,
            observed_change=observed,
            confidence=confidence,
            detail=f"mock-{channel.value}",
        )

    return fn


def _slow_channel(channel: AttestationChannel, observed: bool, delay_ms: int):
    """Channel that sleeps before responding — used for timeout tests."""

    async def fn() -> ChannelResult:
        await asyncio.sleep(delay_ms / 1000.0)
        return ChannelResult(channel=channel, observed_change=observed, confidence=0.9)

    return fn


def _failing_channel(channel: AttestationChannel):
    """Channel that raises — used for safe-wrapper test."""

    async def fn() -> ChannelResult:
        raise RuntimeError("boom")

    return fn


# ── 3-OF-3 MATRIX (full coverage of all 8 cases) ─────────────────────────────


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("dom", "ax", "vis", "expected_decision", "expected_escalate"),
    [
        (True, True, True, "ok", None),
        (True, True, False, "fail", None),
        (True, False, True, "ok_with_warning", None),
        (True, False, False, "fail", None),
        (False, True, True, "ok_with_warning", None),
        (False, True, False, "fail", None),
        (False, False, True, "fail", None),
        (False, False, False, "fail_escalate", "cua_pixel_click"),
    ],
)
async def test_matrix_3of3_all_combinations(
    dom: bool, ax: bool, vis: bool, expected_decision: str, expected_escalate
) -> None:
    """Exhaustive matrix test — pin every cell."""
    result = await verify_triple(
        channel_dom=_make_channel(AttestationChannel.DOM, dom),
        channel_ax=_make_channel(AttestationChannel.AX, ax),
        channel_vis=_make_channel(AttestationChannel.VISION, vis),
    )
    assert result.decision == expected_decision, (
        f"DOM={dom} AX={ax} VIS={vis} expected {expected_decision}, got {result.decision}"
    )
    assert result.escalate_to == expected_escalate


@pytest.mark.asyncio
async def test_disagreement_signature_3of3() -> None:
    """Signature is a clean 3-bit string in DOM-AX-VIS order."""
    result = await verify_triple(
        channel_dom=_make_channel(AttestationChannel.DOM, True),
        channel_ax=_make_channel(AttestationChannel.AX, False),
        channel_vis=_make_channel(AttestationChannel.VISION, True),
    )
    assert result.disagreement_signature == "101"


# ── 2-OF-2 FALLBACK (AX explicitly None) ─────────────────────────────────────


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("dom", "vis", "expected_decision", "expected_escalate"),
    [
        (True, True, "ok", None),
        (True, False, "ok_with_warning", None),
        (False, True, "ok_with_warning", None),
        (False, False, "fail_escalate", "cua_pixel_click"),
    ],
)
async def test_2of2_fallback_when_ax_passed_none(
    dom: bool, vis: bool, expected_decision: str, expected_escalate
) -> None:
    """When channel_ax=None, we use the 2-of-2 matrix."""
    result = await verify_triple(
        channel_dom=_make_channel(AttestationChannel.DOM, dom),
        channel_ax=None,
        channel_vis=_make_channel(AttestationChannel.VISION, vis),
    )
    assert result.decision == expected_decision
    assert result.escalate_to == expected_escalate
    # Signature must mark AX as unavailable with "_".
    assert "_" in result.disagreement_signature
    assert len(result.disagreement_signature) == 3
    # Only 2 channels in the result list.
    assert len(result.channels) == 2
    assert {c.channel for c in result.channels} == {
        AttestationChannel.DOM,
        AttestationChannel.VISION,
    }


@pytest.mark.asyncio
async def test_2of2_signature_format() -> None:
    """When AX is missing, signature uses '_' for the AX position."""
    result = await verify_triple(
        channel_dom=_make_channel(AttestationChannel.DOM, True),
        channel_ax=None,
        channel_vis=_make_channel(AttestationChannel.VISION, False),
    )
    # DOM=1, AX=_, VIS=0 → "1_0"
    assert result.disagreement_signature == "1_0"


# ── AX UNAVAILABLE AT RUNTIME (not passed-None) ──────────────────────────────


@pytest.mark.asyncio
async def test_ax_returns_unavailable_falls_back_to_2of2() -> None:
    """
    If channel_ax is supplied but reports unavailable=True at runtime
    (e.g. Chrome lacked --force-renderer-accessibility), we degrade
    to the 2-of-2 matrix automatically.
    """

    async def ax_unavailable() -> ChannelResult:
        return ChannelResult(
            channel=AttestationChannel.AX,
            observed_change=False,
            unavailable=True,
            detail="ax_tree_disabled",
        )

    result = await verify_triple(
        channel_dom=_make_channel(AttestationChannel.DOM, True),
        channel_ax=ax_unavailable,
        channel_vis=_make_channel(AttestationChannel.VISION, True),
    )
    # 2-of-2 with both observed → ok (not "ok_with_warning"!)
    assert result.decision == "ok"
    # But the result list keeps the AX entry so logs can see it.
    assert len(result.channels) == 3
    ax_entry = next(c for c in result.channels if c.channel == AttestationChannel.AX)
    assert ax_entry.unavailable is True


@pytest.mark.asyncio
async def test_strict_mode_unavailable_counts_as_disagree() -> None:
    """
    With treat_unavailable_as_disagree=True, an unavailable AX channel
    is treated as observed_change=False in the 3-of-3 matrix instead of
    triggering 2-of-2 fallback.
    """

    async def ax_unavailable() -> ChannelResult:
        return ChannelResult(
            channel=AttestationChannel.AX,
            observed_change=False,
            unavailable=True,
            detail="strict",
        )

    cfg = AttestationConfig(treat_unavailable_as_disagree=True)
    result = await verify_triple(
        channel_dom=_make_channel(AttestationChannel.DOM, True),
        channel_ax=ax_unavailable,
        channel_vis=_make_channel(AttestationChannel.VISION, True),
        config=cfg,
    )
    # (T, F, T) in 3-of-3 → ok_with_warning, NOT plain ok.
    assert result.decision == "ok_with_warning"


# ── FAILURE MODES (channel raises / times out) ───────────────────────────────


@pytest.mark.asyncio
async def test_channel_exception_is_caught_as_unavailable() -> None:
    """A raising channel must NOT crash verify_triple."""
    result = await verify_triple(
        channel_dom=_make_channel(AttestationChannel.DOM, True),
        channel_ax=_failing_channel(AttestationChannel.AX),
        channel_vis=_make_channel(AttestationChannel.VISION, True),
    )
    # AX unavailable → 2-of-2 with DOM+VIS both T → ok.
    assert result.decision == "ok"
    ax_entry = next(c for c in result.channels if c.channel == AttestationChannel.AX)
    assert ax_entry.unavailable is True
    assert "RuntimeError" in ax_entry.detail


@pytest.mark.asyncio
async def test_channel_timeout_is_caught_as_unavailable() -> None:
    """A slow channel must be killed by the per-channel timeout."""
    cfg = AttestationConfig(per_channel_timeout_ms=20, total_timeout_ms=200)
    result = await verify_triple(
        channel_dom=_make_channel(AttestationChannel.DOM, True),
        channel_ax=_slow_channel(AttestationChannel.AX, True, delay_ms=200),
        channel_vis=_make_channel(AttestationChannel.VISION, True),
        config=cfg,
    )
    # AX times out → degrades to 2-of-2 → ok.
    assert result.decision == "ok"
    ax_entry = next(c for c in result.channels if c.channel == AttestationChannel.AX)
    assert ax_entry.unavailable is True
    assert "timeout" in ax_entry.detail.lower()


# ── LATENCY / PARALLELISM ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_channels_run_in_parallel() -> None:
    """
    Three 50 ms channels via gather should complete in ~50 ms, not 150 ms.
    Pads for CI jitter: assert < 120 ms.
    """
    cfg = AttestationConfig(per_channel_timeout_ms=200, total_timeout_ms=200)
    result = await verify_triple(
        channel_dom=_slow_channel(AttestationChannel.DOM, True, delay_ms=50),
        channel_ax=_slow_channel(AttestationChannel.AX, True, delay_ms=50),
        channel_vis=_slow_channel(AttestationChannel.VISION, True, delay_ms=50),
        config=cfg,
    )
    assert result.decision == "ok"
    assert result.duration_ms < 120, (
        f"expected parallel ~50 ms, got {result.duration_ms} ms"
    )


@pytest.mark.asyncio
async def test_per_channel_latency_recorded() -> None:
    """Each channel result must carry latency_ms ≥ 0."""
    result = await verify_triple(
        channel_dom=_slow_channel(AttestationChannel.DOM, True, delay_ms=10),
        channel_ax=_slow_channel(AttestationChannel.AX, True, delay_ms=10),
        channel_vis=_slow_channel(AttestationChannel.VISION, True, delay_ms=10),
    )
    for c in result.channels:
        assert c.latency_ms >= 0
        assert c.latency_ms < 100  # generous upper bound for CI


# ── RESULT SHAPE INVARIANTS ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_result_channels_are_ordered_dom_ax_vis() -> None:
    """Result channel list is in a stable order: DOM, AX, VIS."""
    result = await verify_triple(
        channel_dom=_make_channel(AttestationChannel.DOM, True),
        channel_ax=_make_channel(AttestationChannel.AX, True),
        channel_vis=_make_channel(AttestationChannel.VISION, True),
    )
    order = [c.channel for c in result.channels]
    assert order == [
        AttestationChannel.DOM,
        AttestationChannel.AX,
        AttestationChannel.VISION,
    ]


@pytest.mark.asyncio
async def test_result_is_frozen_dataclass() -> None:
    """AttestationResult is immutable to avoid post-hoc tampering in logs."""
    result = await verify_triple(
        channel_dom=_make_channel(AttestationChannel.DOM, True),
        channel_ax=_make_channel(AttestationChannel.AX, True),
        channel_vis=_make_channel(AttestationChannel.VISION, True),
    )
    with pytest.raises((AttributeError, TypeError, Exception)):
        result.decision = "fail"  # type: ignore[misc]


# ── escalate_to FIELD INVARIANTS ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_escalate_to_only_set_for_fail_escalate() -> None:
    """escalate_to must be None for everything except fail_escalate."""
    # Build an ok-result.
    ok_result = await verify_triple(
        channel_dom=_make_channel(AttestationChannel.DOM, True),
        channel_ax=_make_channel(AttestationChannel.AX, True),
        channel_vis=_make_channel(AttestationChannel.VISION, True),
    )
    assert ok_result.escalate_to is None

    # Build a fail (not escalate) result.
    fail_result = await verify_triple(
        channel_dom=_make_channel(AttestationChannel.DOM, True),
        channel_ax=_make_channel(AttestationChannel.AX, True),
        channel_vis=_make_channel(AttestationChannel.VISION, False),  # (T,T,F)→fail
    )
    assert fail_result.decision == "fail"
    assert fail_result.escalate_to is None

    # Build a fail_escalate result.
    esc_result = await verify_triple(
        channel_dom=_make_channel(AttestationChannel.DOM, False),
        channel_ax=_make_channel(AttestationChannel.AX, False),
        channel_vis=_make_channel(AttestationChannel.VISION, False),
    )
    assert esc_result.decision == "fail_escalate"
    assert esc_result.escalate_to == "cua_pixel_click"
