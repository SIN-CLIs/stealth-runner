"""
Retry Policy v2 — Full Jitter, total-time budget, circuit breaker (SR-157).

Improvements over SR-152:
    - Full Jitter (AWS-recommended) instead of additive jitter
    - max_total_time budget to abort long retry chains
    - Per-key circuit breaker (closed -> open -> half-open)
    - Typed HTTP exceptions instead of string-matching
"""

from __future__ import annotations

import asyncio
import logging
import random
import time
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Awaitable, Callable, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class Retryability(str, Enum):
    """Classification of error retryability."""

    TRANSIENT = "transient"
    PERMANENT = "permanent"
    FATAL = "fatal"


# =============================================================================
# Typed exceptions — replace string matching
# =============================================================================


class TransientError(Exception):
    """Retryable error."""

    pass


class PermanentError(Exception):
    """Non-retryable error, push to DLQ."""

    pass


class FatalError(Exception):
    """Halt-immediately error."""

    pass


class HttpError(Exception):
    """HTTP error with typed status code."""

    def __init__(self, status: int, message: str = ""):
        self.status = status
        super().__init__(f"HTTP {status}: {message}" if message else f"HTTP {status}")


class TimeBudgetExceeded(Exception):
    """Total retry time budget exhausted."""

    pass


class CircuitOpenError(Exception):
    """Circuit breaker is open, refusing call."""

    pass


# =============================================================================
# Classification
# =============================================================================


def default_classify(error: Exception) -> Retryability:
    """
    Default error classification — prefers typed exceptions over string matching.
    """
    # Fatal
    if isinstance(error, (AssertionError, SystemExit, KeyboardInterrupt, FatalError)):
        return Retryability.FATAL

    # Typed wrappers win
    if isinstance(error, TransientError):
        return Retryability.TRANSIENT
    if isinstance(error, PermanentError):
        return Retryability.PERMANENT

    # Typed HTTP
    if isinstance(error, HttpError):
        # 408 Request Timeout and 429 Rate Limit are transient
        if error.status in (408, 429):
            return Retryability.TRANSIENT
        # 5xx are transient
        if 500 <= error.status < 600:
            return Retryability.TRANSIENT
        # Other 4xx are permanent
        if 400 <= error.status < 500:
            return Retryability.PERMANENT

    # Network errors are transient
    if isinstance(error, (TimeoutError, ConnectionError, asyncio.TimeoutError)):
        return Retryability.TRANSIENT
    if isinstance(error, OSError):
        # ECONNRESET, ECONNREFUSED, etc.
        return Retryability.TRANSIENT

    # String-matching fallback for legacy/untyped errors
    error_str = str(error).lower()
    permanent_phrases = (
        "account banned",
        "ip blocked",
        "access denied",
        "forbidden",
        "not authorized",
        "invalid credentials",
        "survey closed",
        "quota exceeded",
    )
    if any(p in error_str for p in permanent_phrases):
        return Retryability.PERMANENT

    # Default: permanent (prevents infinite loops on unknown errors)
    return Retryability.PERMANENT


# =============================================================================
# Circuit Breaker
# =============================================================================


class CircuitState(str, Enum):
    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Refusing calls
    HALF_OPEN = "half_open"  # Probing for recovery


@dataclass
class CircuitStats:
    """Per-key circuit breaker state."""

    state: CircuitState = CircuitState.CLOSED
    consecutive_failures: int = 0
    opened_at: float = 0.0
    half_open_probes: int = 0


class CircuitBreaker:
    """
    Per-key circuit breaker.

    Closes after N consecutive failures, half-opens after cooldown,
    closes again on probe success.
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        cooldown_seconds: float = 30.0,
        half_open_max_probes: int = 1,
    ):
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds
        self.half_open_max_probes = half_open_max_probes
        self._circuits: dict[str, CircuitStats] = defaultdict(CircuitStats)

    def check(self, key: str) -> None:
        """
        Check circuit state before making a call.

        Raises:
            CircuitOpenError: If circuit is open and cooldown not elapsed
        """
        stats = self._circuits[key]

        if stats.state == CircuitState.OPEN:
            elapsed = time.monotonic() - stats.opened_at
            if elapsed >= self.cooldown_seconds:
                # Transition to half-open
                stats.state = CircuitState.HALF_OPEN
                stats.half_open_probes = 0
                logger.info(f"Circuit '{key}' transitioning to HALF_OPEN")
            else:
                remaining = self.cooldown_seconds - elapsed
                raise CircuitOpenError(f"Circuit '{key}' open, retry in {remaining:.1f}s")

        if stats.state == CircuitState.HALF_OPEN:
            if stats.half_open_probes >= self.half_open_max_probes:
                raise CircuitOpenError(f"Circuit '{key}' half-open, probe limit reached")
            stats.half_open_probes += 1

    def record_success(self, key: str) -> None:
        """Record a successful call — close circuit if half-open."""
        stats = self._circuits[key]
        if stats.state == CircuitState.HALF_OPEN:
            logger.info(f"Circuit '{key}' closing after successful probe")
        stats.state = CircuitState.CLOSED
        stats.consecutive_failures = 0
        stats.half_open_probes = 0

    def record_failure(self, key: str) -> None:
        """Record a failed call — open circuit if threshold reached."""
        stats = self._circuits[key]
        stats.consecutive_failures += 1

        if stats.state == CircuitState.HALF_OPEN:
            # Failed probe — re-open
            stats.state = CircuitState.OPEN
            stats.opened_at = time.monotonic()
            logger.warning(f"Circuit '{key}' re-opening after failed probe")
        elif stats.consecutive_failures >= self.failure_threshold:
            stats.state = CircuitState.OPEN
            stats.opened_at = time.monotonic()
            logger.warning(f"Circuit '{key}' opening after {stats.consecutive_failures} failures")

    def get_state(self, key: str) -> CircuitState:
        """Get current circuit state for a key."""
        return self._circuits[key].state


# =============================================================================
# Retry Policy
# =============================================================================


class RetryPolicy:
    """
    Production retry policy with Full Jitter, time budget, and circuit breaker.

    Usage:
        policy = RetryPolicy(
            max_attempts=5,
            max_total_time=120.0,
            circuit_breaker=CircuitBreaker(),
        )
        result = await policy.run(my_fn, circuit_key="lucid")
    """

    def __init__(
        self,
        max_attempts: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        max_total_time: float | None = None,
        circuit_breaker: CircuitBreaker | None = None,
    ):
        """
        Args:
            max_attempts: Maximum number of attempts
            base_delay: Base delay for backoff
            max_delay: Cap on individual delay
            max_total_time: Total time budget (None = unlimited)
            circuit_breaker: Optional circuit breaker for per-key tracking
        """
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.max_total_time = max_total_time
        self.circuit_breaker = circuit_breaker

    def _full_jitter_delay(self, attempt: int) -> float:
        """
        Full Jitter delay (AWS-recommended).

        Formula: delay = uniform(0, min(base * 2^attempt, max_delay))

        Reduces thundering herd vs additive jitter when many clients retry
        concurrently. See: aws.amazon.com/blogs/architecture/exponential-backoff-and-jitter/
        """
        capped = min(self.base_delay * (2**attempt), self.max_delay)
        return random.uniform(0, capped)

    async def run(
        self,
        coro_fn: Callable[[], Awaitable[T]],
        classify_fn: Callable[[Exception], Retryability] = default_classify,
        on_retry: Callable[[int, Exception, float], None] | None = None,
        circuit_key: str | None = None,
    ) -> T:
        """
        Execute with retry, time budget, and optional circuit breaker.

        Args:
            coro_fn: Async function to call
            classify_fn: Error classifier
            on_retry: Callback (attempt, error, delay)
            circuit_key: Key for circuit breaker (e.g. "lucid", "toluna")

        Raises:
            TimeBudgetExceeded: max_total_time elapsed
            CircuitOpenError: Circuit breaker refused the call
            Original exception: On final failure or non-retryable error
        """
        start_time = time.monotonic()
        last_error: Exception | None = None

        for attempt in range(self.max_attempts):
            # Check circuit before call
            if self.circuit_breaker and circuit_key:
                self.circuit_breaker.check(circuit_key)

            # Check time budget before attempt
            elapsed = time.monotonic() - start_time
            if self.max_total_time is not None and elapsed >= self.max_total_time:
                raise TimeBudgetExceeded(
                    f"Total time budget {self.max_total_time}s exceeded after {elapsed:.1f}s"
                )

            try:
                result = await coro_fn()
                if self.circuit_breaker and circuit_key:
                    self.circuit_breaker.record_success(circuit_key)
                return result

            except Exception as e:
                last_error = e
                classification = classify_fn(e)

                logger.debug(
                    f"Attempt {attempt + 1}/{self.max_attempts}: "
                    f"{type(e).__name__}: {e} [{classification.value}]"
                )

                # Update circuit on transient/permanent (not on fatal)
                if self.circuit_breaker and circuit_key and classification != Retryability.FATAL:
                    self.circuit_breaker.record_failure(circuit_key)

                if classification == Retryability.FATAL:
                    raise

                if classification == Retryability.PERMANENT:
                    raise

                # TRANSIENT — check budget before sleeping
                if attempt + 1 >= self.max_attempts:
                    raise

                delay = self._full_jitter_delay(attempt)

                # Check that sleeping won't blow the budget
                if self.max_total_time is not None:
                    elapsed_after = (time.monotonic() - start_time) + delay
                    if elapsed_after >= self.max_total_time:
                        raise TimeBudgetExceeded(
                            f"Sleep of {delay:.2f}s would exceed budget {self.max_total_time}s"
                        )

                if on_retry:
                    on_retry(attempt + 1, e, delay)

                await asyncio.sleep(delay)

        assert last_error is not None
        raise last_error


# =============================================================================
# Retry Context (unchanged from v1, kept for backward compat)
# =============================================================================


@dataclass
class RetryContext:
    """Tracks retry state across operations."""

    policy: RetryPolicy
    attempt_count: int = 0
    errors: list[tuple[int, Exception, Retryability]] = field(default_factory=list)

    def record_error(self, error: Exception, classification: Retryability) -> None:
        self.attempt_count += 1
        self.errors.append((self.attempt_count, error, classification))

    @property
    def last_error(self) -> Exception | None:
        return self.errors[-1][1] if self.errors else None

    @property
    def total_attempts(self) -> int:
        return self.attempt_count

    def to_dict(self) -> dict[str, Any]:
        return {
            "attempt_count": self.attempt_count,
            "errors": [
                {
                    "attempt": a,
                    "error_class": type(e).__name__,
                    "error_message": str(e),
                    "classification": c.value,
                }
                for a, e, c in self.errors
            ],
        }
