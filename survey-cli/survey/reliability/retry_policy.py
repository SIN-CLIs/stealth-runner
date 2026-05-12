"""
Retry Policy — Exponential backoff with retryability classification.

SR-152: Production-grade retry for the survey daemon.

Classifications:
    - TRANSIENT: TimeoutError, ConnectionError, HTTP 5xx → retry with backoff
    - PERMANENT: HTTP 4xx (except 408/429), "account banned" → push to DLQ
    - FATAL: AssertionError, SystemExit, KeyboardInterrupt → halt immediately
"""

from __future__ import annotations

import asyncio
import logging
import random
from enum import Enum
from typing import Any, Awaitable, Callable, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class Retryability(str, Enum):
    """Classification of error retryability."""

    TRANSIENT = "transient"  # Retry with exponential backoff
    PERMANENT = "permanent"  # Do not retry, push to DLQ
    FATAL = "fatal"  # Do not retry, do not DLQ, halt


class TransientError(Exception):
    """Wrapper for transient errors that should be retried."""

    pass


class PermanentError(Exception):
    """Wrapper for permanent errors that should go to DLQ."""

    pass


class FatalError(Exception):
    """Wrapper for fatal errors that should halt execution."""

    pass


def default_classify(error: Exception) -> Retryability:
    """
    Default error classification function.

    Args:
        error: The exception to classify

    Returns:
        Retryability classification
    """
    error_str = str(error).lower()
    type(error).__name__

    # Fatal errors — halt immediately
    if isinstance(error, (AssertionError, SystemExit, KeyboardInterrupt)):
        return Retryability.FATAL
    if isinstance(error, FatalError):
        return Retryability.FATAL

    # Permanent errors — do not retry, push to DLQ
    if isinstance(error, PermanentError):
        return Retryability.PERMANENT
    if any(
        phrase in error_str
        for phrase in [
            "account banned",
            "ip blocked",
            "access denied",
            "forbidden",
            "not authorized",
            "invalid credentials",
            "survey closed",
            "quota exceeded",
        ]
    ):
        return Retryability.PERMANENT

    # Check for HTTP status codes in error message
    if "4" in error_str and any(
        f"{code}" in error_str for code in [400, 401, 402, 403, 404, 405, 406, 410, 422]
    ):
        return Retryability.PERMANENT

    # Transient errors — retry with backoff
    if isinstance(error, (TimeoutError, ConnectionError, OSError)):
        return Retryability.TRANSIENT
    if isinstance(error, TransientError):
        return Retryability.TRANSIENT
    if any(
        phrase in error_str
        for phrase in [
            "timeout",
            "connection reset",
            "connection refused",
            "service unavailable",
            "503",
            "502",
            "500",
            "504",
            "temporary",
            "try again",
            "rate limit",
            "429",
            "408",
        ]
    ):
        return Retryability.TRANSIENT

    # Default: treat unknown errors as permanent to avoid infinite loops
    return Retryability.PERMANENT


class RetryPolicy:
    """
    Exponential backoff retry policy with classification.

    Usage:
        policy = RetryPolicy(max_attempts=3)
        result = await policy.run(my_async_fn)
    """

    def __init__(
        self,
        max_attempts: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        jitter_factor: float = 0.5,
    ):
        """
        Initialize retry policy.

        Args:
            max_attempts: Maximum number of attempts (including first try)
            base_delay: Base delay in seconds for backoff calculation
            max_delay: Maximum delay cap in seconds
            jitter_factor: Jitter factor (0-1) for randomization
        """
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.jitter_factor = jitter_factor

    def _calculate_delay(self, attempt: int) -> float:
        """
        Calculate delay for the given attempt number.

        Formula: delay = min(base * 2^attempt, max_delay) + jitter

        Args:
            attempt: Current attempt number (0-indexed)

        Returns:
            Delay in seconds
        """
        delay = min(self.base_delay * (2**attempt), self.max_delay)
        jitter = random.uniform(0, self.jitter_factor * delay)
        return delay + jitter

    async def run(
        self,
        coro_fn: Callable[[], Awaitable[T]],
        classify_fn: Callable[[Exception], Retryability] = default_classify,
        on_retry: Callable[[int, Exception, float], None] | None = None,
    ) -> T:
        """
        Execute coroutine with retry policy.

        Args:
            coro_fn: Async function to execute (called fresh each attempt)
            classify_fn: Function to classify errors
            on_retry: Optional callback called before each retry (attempt, error, delay)

        Returns:
            Result of successful execution

        Raises:
            Last exception if all retries exhausted or error is non-retryable
        """
        last_error: Exception | None = None

        for attempt in range(self.max_attempts):
            try:
                return await coro_fn()
            except Exception as e:
                last_error = e
                classification = classify_fn(e)

                logger.debug(
                    f"Attempt {attempt + 1}/{self.max_attempts} failed: "
                    f"{type(e).__name__}: {e} (classified as {classification.value})"
                )

                if classification == Retryability.FATAL:
                    logger.error(f"Fatal error, halting: {e}")
                    raise

                if classification == Retryability.PERMANENT:
                    logger.warning(f"Permanent error, not retrying: {e}")
                    raise

                # TRANSIENT — retry if attempts remain
                if attempt + 1 >= self.max_attempts:
                    logger.warning(f"Max attempts ({self.max_attempts}) reached")
                    raise

                delay = self._calculate_delay(attempt)
                logger.info(
                    f"Transient error, retrying in {delay:.2f}s "
                    f"(attempt {attempt + 2}/{self.max_attempts})"
                )

                if on_retry:
                    on_retry(attempt + 1, e, delay)

                await asyncio.sleep(delay)

        # Should not reach here, but satisfy type checker
        assert last_error is not None
        raise last_error


class RetryContext:
    """Context manager for tracking retry state across multiple operations."""

    def __init__(self, policy: RetryPolicy):
        self.policy = policy
        self.attempt_count = 0
        self.errors: list[tuple[int, Exception, Retryability]] = []

    def record_error(self, error: Exception, classification: Retryability) -> None:
        """Record an error that occurred."""
        self.attempt_count += 1
        self.errors.append((self.attempt_count, error, classification))

    @property
    def last_error(self) -> Exception | None:
        """Get the last error that occurred."""
        return self.errors[-1][1] if self.errors else None

    @property
    def total_attempts(self) -> int:
        """Get total number of attempts made."""
        return self.attempt_count

    def to_dict(self) -> dict[str, Any]:
        """Convert context to dictionary for DLQ storage."""
        return {
            "attempt_count": self.attempt_count,
            "errors": [
                {
                    "attempt": attempt,
                    "error_class": type(error).__name__,
                    "error_message": str(error),
                    "classification": classification.value,
                }
                for attempt, error, classification in self.errors
            ],
        }
