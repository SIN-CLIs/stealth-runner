"""
Unit tests for SR-157 reliability v2 primitives.

Pytest + pytest-asyncio (replaces deprecated unittest+get_event_loop pattern).
"""

from __future__ import annotations

import asyncio
import json
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread

import pytest

from survey.reliability.retry_policy import (
    CircuitBreaker,
    CircuitOpenError,
    CircuitState,
    FatalError,
    HttpError,
    Retryability,
    RetryPolicy,
    TimeBudgetExceeded,
    TransientError,
    default_classify,
)
from survey.reliability.dlq import DLQ


# =============================================================================
# Full Jitter
# =============================================================================


@pytest.mark.asyncio
async def test_full_jitter_within_cap():
    """Full jitter delay is always in [0, capped_delay]."""
    policy = RetryPolicy(base_delay=1.0, max_delay=10.0)
    for attempt in range(5):
        delay = policy._full_jitter_delay(attempt)
        cap = min(1.0 * 2**attempt, 10.0)
        assert 0 <= delay <= cap


@pytest.mark.asyncio
async def test_full_jitter_distribution():
    """Sampled jitter delays span the full range, not clustered near max."""
    policy = RetryPolicy(base_delay=1.0, max_delay=8.0)
    samples = [policy._full_jitter_delay(3) for _ in range(100)]
    # For attempt=3, cap is min(8, 8) = 8. Distribution should span [0, 8].
    assert min(samples) < 2.0  # at least one low sample
    assert max(samples) > 6.0  # at least one high sample


# =============================================================================
# Time Budget
# =============================================================================


@pytest.mark.asyncio
async def test_time_budget_aborts():
    """Time budget aborts long retry chains."""
    policy = RetryPolicy(
        max_attempts=10,
        base_delay=0.1,
        max_delay=0.5,
        max_total_time=0.3,
    )

    async def always_fails():
        raise TransientError("nope")

    with pytest.raises((TimeBudgetExceeded, TransientError)):
        await policy.run(always_fails)


@pytest.mark.asyncio
async def test_time_budget_unused_when_success():
    """Time budget does not interfere with successful calls."""
    policy = RetryPolicy(max_attempts=3, max_total_time=10.0)

    async def succeeds():
        return "ok"

    result = await policy.run(succeeds)
    assert result == "ok"


# =============================================================================
# Circuit Breaker
# =============================================================================


@pytest.mark.asyncio
async def test_circuit_opens_after_threshold():
    """Circuit opens after N consecutive failures."""
    cb = CircuitBreaker(failure_threshold=3, cooldown_seconds=10.0)
    policy = RetryPolicy(max_attempts=1, circuit_breaker=cb)

    async def fails():
        raise TransientError("fail")

    for _ in range(3):
        with pytest.raises(TransientError):
            await policy.run(fails, circuit_key="test_provider")

    assert cb.get_state("test_provider") == CircuitState.OPEN


@pytest.mark.asyncio
async def test_circuit_open_blocks_calls():
    """Open circuit refuses calls with CircuitOpenError."""
    cb = CircuitBreaker(failure_threshold=2, cooldown_seconds=10.0)
    policy = RetryPolicy(max_attempts=1, circuit_breaker=cb)

    async def fails():
        raise TransientError("fail")

    for _ in range(2):
        with pytest.raises(TransientError):
            await policy.run(fails, circuit_key="provider_x")

    with pytest.raises(CircuitOpenError):
        await policy.run(fails, circuit_key="provider_x")


@pytest.mark.asyncio
async def test_circuit_half_open_recovery():
    """Circuit transitions OPEN -> HALF_OPEN -> CLOSED on probe success."""
    cb = CircuitBreaker(failure_threshold=2, cooldown_seconds=0.05)
    policy = RetryPolicy(max_attempts=1, circuit_breaker=cb)

    async def fails():
        raise TransientError("fail")

    async def succeeds():
        return "ok"

    # Open circuit
    for _ in range(2):
        with pytest.raises(TransientError):
            await policy.run(fails, circuit_key="recover")

    assert cb.get_state("recover") == CircuitState.OPEN

    # Wait for cooldown
    await asyncio.sleep(0.1)

    # Probe succeeds → closes
    result = await policy.run(succeeds, circuit_key="recover")
    assert result == "ok"
    assert cb.get_state("recover") == CircuitState.CLOSED


@pytest.mark.asyncio
async def test_circuit_per_key_isolation():
    """Failures on one key don't affect another."""
    cb = CircuitBreaker(failure_threshold=2, cooldown_seconds=10.0)
    policy = RetryPolicy(max_attempts=1, circuit_breaker=cb)

    async def fails():
        raise TransientError("fail")

    async def succeeds():
        return "ok"

    for _ in range(2):
        with pytest.raises(TransientError):
            await policy.run(fails, circuit_key="provider_a")

    assert cb.get_state("provider_a") == CircuitState.OPEN
    # provider_b should be untouched
    result = await policy.run(succeeds, circuit_key="provider_b")
    assert result == "ok"
    assert cb.get_state("provider_b") == CircuitState.CLOSED


# =============================================================================
# Typed HTTP Classification
# =============================================================================


def test_http_5xx_is_transient():
    assert default_classify(HttpError(500)) == Retryability.TRANSIENT
    assert default_classify(HttpError(502)) == Retryability.TRANSIENT
    assert default_classify(HttpError(503)) == Retryability.TRANSIENT
    assert default_classify(HttpError(504)) == Retryability.TRANSIENT


def test_http_4xx_is_permanent():
    assert default_classify(HttpError(400)) == Retryability.PERMANENT
    assert default_classify(HttpError(401)) == Retryability.PERMANENT
    assert default_classify(HttpError(403)) == Retryability.PERMANENT
    assert default_classify(HttpError(404)) == Retryability.PERMANENT


def test_http_429_408_are_transient():
    """Special-case 4xx codes that should be retried."""
    assert default_classify(HttpError(408)) == Retryability.TRANSIENT
    assert default_classify(HttpError(429)) == Retryability.TRANSIENT


def test_fatal_classification():
    assert default_classify(AssertionError()) == Retryability.FATAL
    assert default_classify(FatalError("boom")) == Retryability.FATAL


# =============================================================================
# DLQ — Idempotency
# =============================================================================


def test_dlq_push_is_idempotent(tmp_path):
    """Pushing the same (survey_id, persona_id, url) twice returns same ID."""
    dlq = DLQ(dlq_path=tmp_path)

    id1 = dlq.push("s1", "p1", "lucid", "https://x.com", Exception("e"), 1)
    id2 = dlq.push("s1", "p1", "lucid", "https://x.com", Exception("e"), 1)

    assert id1 == id2


def test_dlq_push_different_urls_different_ids(tmp_path):
    """Different urls produce different DLQ records."""
    dlq = DLQ(dlq_path=tmp_path)

    id1 = dlq.push("s1", "p1", "lucid", "https://a.com", Exception("e"), 1)
    id2 = dlq.push("s1", "p1", "lucid", "https://b.com", Exception("e"), 1)

    assert id1 != id2


# =============================================================================
# DLQ — Claim / Release
# =============================================================================


def test_claim_succeeds_for_pending(tmp_path):
    """Worker can claim a pending record."""
    dlq = DLQ(dlq_path=tmp_path, worker_id="worker-a")
    dlq_id = dlq.push("s1", "p1", "lucid", "url", Exception("e"), 1)

    assert dlq.claim(dlq_id) is True
    record = dlq.get(dlq_id)
    assert record.status == "claimed"
    assert record.claim_owner == "worker-a"


def test_claim_blocks_other_worker(tmp_path):
    """A second worker cannot claim a held record."""
    dlq_a = DLQ(dlq_path=tmp_path, worker_id="worker-a")
    dlq_b = DLQ(dlq_path=tmp_path, worker_id="worker-b")
    dlq_id = dlq_a.push("s1", "p1", "lucid", "url", Exception("e"), 1)

    assert dlq_a.claim(dlq_id, ttl=60) is True
    assert dlq_b.claim(dlq_id) is False


def test_claim_expires(tmp_path):
    """An expired claim can be re-acquired by another worker."""
    dlq_a = DLQ(dlq_path=tmp_path, worker_id="worker-a")
    dlq_b = DLQ(dlq_path=tmp_path, worker_id="worker-b")
    dlq_id = dlq_a.push("s1", "p1", "lucid", "url", Exception("e"), 1)

    assert dlq_a.claim(dlq_id, ttl=0) is True
    time.sleep(0.01)
    # After TTL expiration, worker-b can claim
    assert dlq_b.claim(dlq_id) is True


def test_release_returns_to_pending(tmp_path):
    """Release reverts status to pending."""
    dlq = DLQ(dlq_path=tmp_path, worker_id="worker-a")
    dlq_id = dlq.push("s1", "p1", "lucid", "url", Exception("e"), 1)

    dlq.claim(dlq_id)
    assert dlq.release(dlq_id) is True
    record = dlq.get(dlq_id)
    assert record.status == "pending"
    assert record.claim_owner == ""


# =============================================================================
# DLQ — Escalation
# =============================================================================


def test_escalation_after_max_replay_attempts(tmp_path):
    """After max_replay_attempts failed replays, record is escalated."""
    dlq = DLQ(dlq_path=tmp_path, max_replay_attempts=3)
    dlq_id = dlq.push("s1", "p1", "lucid", "url", Exception("e"), 1)

    dlq.mark_failed_replay(dlq_id)
    dlq.mark_failed_replay(dlq_id)
    dlq.mark_failed_replay(dlq_id)

    record = dlq.get(dlq_id)
    assert record.status == "escalated"
    assert record.escalated is True
    assert record.replay_attempts == 3


# =============================================================================
# Async Webhook
# =============================================================================


class _WebhookHandler(BaseHTTPRequestHandler):
    received: list[dict] = []

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        _WebhookHandler.received.append(json.loads(body))
        self.send_response(200)
        self.end_headers()

    def log_message(self, *args, **kwargs):
        pass


@pytest.mark.asyncio
async def test_async_webhook_delivery(tmp_path):
    """Webhook delivers asynchronously without blocking event loop."""
    _WebhookHandler.received = []
    server = HTTPServer(("127.0.0.1", 0), _WebhookHandler)
    port = server.server_address[1]
    Thread(target=server.handle_request, daemon=True).start()

    try:
        dlq = DLQ(
            dlq_path=tmp_path,
            webhook_url=f"http://127.0.0.1:{port}/webhook",
        )
        dlq.push("s1", "p1", "lucid", "url", Exception("test"), 1)

        # Give the background task time to deliver
        for _ in range(50):
            if _WebhookHandler.received:
                break
            await asyncio.sleep(0.05)

        assert len(_WebhookHandler.received) == 1
        assert "SR-157" in _WebhookHandler.received[0]["text"]
    finally:
        server.server_close()


# =============================================================================
# Integration
# =============================================================================


@pytest.mark.asyncio
async def test_retry_with_circuit_and_budget():
    """All three primitives compose correctly."""
    cb = CircuitBreaker(failure_threshold=10, cooldown_seconds=10.0)
    policy = RetryPolicy(
        max_attempts=5,
        base_delay=0.01,
        max_delay=0.05,
        max_total_time=2.0,
        circuit_breaker=cb,
    )

    call_count = 0

    async def fails_then_succeeds():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise HttpError(503)
        return "recovered"

    result = await policy.run(fails_then_succeeds, circuit_key="integration")
    assert result == "recovered"
    assert call_count == 3
    assert cb.get_state("integration") == CircuitState.CLOSED
