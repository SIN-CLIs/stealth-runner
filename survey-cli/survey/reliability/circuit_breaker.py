"""================================================================================
CIRCUIT BREAKER — Three-state breaker for unstable external dependencies (SR-253)
================================================================================

MODUL-KONZEPT (SR-253)
----------------------

Stealth-Runner hat mehrere externe Calls mit "kann ploetzlich fuer 30s
komplett tot sein"-Verhalten:

  - NIM-API (`survey/nim.py`): Modell-Endpoint hat regelmaessig 5xx-Bursts
  - OpenAI Vision-Fallback (#239): Rate-Limit oder Provider-Outage
  - 2captcha / capsolver-API: Anti-Bot-Service-Maintenance
  - Heypiggy-Login: Session-Endpoint kann temporaer down sein

`RetryPolicy` (SR-238) loest pro-Call-Retries mit Backoff. Was sie NICHT
loest: bei einem 5-Minuten-Provider-Outage retried der Caller jeden Call
3x mit exponentiellem Backoff, bevor er aufgibt — das frisst
Rate-Limit-Budget und produziert massiv Tail-Latenz fuer Endbenutzer.

CircuitBreaker schliesst die Luecke: nach N Failures in Folge oeffnet
der Breaker fuer cooldown_s Sekunden und liefert sofort
`CircuitOpenError` ohne den eigentlichen Call zu machen. Nach Cooldown
geht er in HALF_OPEN: ein einzelner Probe-Call entscheidet, ob er
wieder schliesst (CLOSED, normal) oder erneut oeffnet.

DESIGN
------
Klassischer 3-State-Breaker (Hystrix/Polly-Pattern):

  CLOSED    -- normal: jeder Call geht durch.
              N consecutive failures -> OPEN
  OPEN      -- alle Calls sofort denied mit CircuitOpenError.
              Nach cooldown_s -> HALF_OPEN
  HALF_OPEN -- ein einzelner Probe-Call ist erlaubt.
              Success -> CLOSED. Failure -> OPEN (cooldown reset).

Thread-safe via threading.Lock. Injectable now_fn fuer Tests.

WARUM EXCEPTION als Signal statt Bool-Return?
- Caller-Code bleibt linear: `try: breaker.call(fn) except CircuitOpenError`
- Differenzierbar von echten downstream-Errors via Type
- Kompatibel mit RetryPolicy: classify CircuitOpenError als FATAL
  -> Retry stoppt sofort, kein blindes Hammern auf den offenen Breaker.

PUBLIC API
----------
    CircuitState           Literal['closed', 'open', 'half_open']
    CircuitOpenError       Exception, raised when breaker denies
    CircuitBreaker
        failure_threshold, cooldown_s
        success_threshold? (default 1)
        now_fn? exception_predicate?
        call(fn, *args, **kwargs) -> Any
        record_success() / record_failure()  (manual mode)
        state -> CircuitState
        stats() -> dict

OBSERVABILITY
-------------
stats() liefert structlog-faehig:
    state, total_calls, total_successes, total_failures,
    total_short_circuited, consecutive_failures, last_failure_ts.

USAGE
-----

    # Decorator-style mit call() wrapper
    >>> breaker = CircuitBreaker(failure_threshold=5, cooldown_s=30)
    >>> def safe_nim_call():
    ...     return breaker.call(nim.complete, prompt='...')

    # Combined mit RetryPolicy: classify CircuitOpenError als FATAL
    >>> def classify(e):
    ...     if isinstance(e, CircuitOpenError):
    ...         return Retryability.FATAL  # don't retry hammer
    ...     return default_classify(e)
    >>> retry = RetryPolicy(classify_fn=classify, ...)

    # Manual mode wenn call() inappropriate
    >>> if breaker.allow_request():
    ...     try:
    ...         result = expensive_call()
    ...         breaker.record_success()
    ...     except DownstreamError:
    ...         breaker.record_failure()
    ...         raise
    ... else:
    ...     fall_back_to_cache()

NICHT-ZIELE
-----------
- Kein distributed/Redis-backed breaker (wuerde gegen process-lokale
  Caller-State-Decision sprechen).
- Keine async-Variante — sync API ist der kleinere Nenner. Async-Wrapper
  als Folge-PR moeglich.
- Kein automatic registry oder global instance.

Module Status: NEW (SR-253)
================================================================================
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Any, Callable, Literal, Optional

CircuitState = Literal["closed", "open", "half_open"]


class CircuitOpenError(Exception):
    """Raised by ``CircuitBreaker.call`` when the breaker is OPEN.

    Distinct from any downstream exception — caller code can match
    on this type to fall back to cache, return stale data, or skip.
    """

    def __init__(self, name: str, retry_after_s: float):
        self.name = name
        self.retry_after_s = retry_after_s
        super().__init__(
            f"circuit '{name}' is OPEN, retry_after={retry_after_s:.1f}s"
        )


@dataclass
class _Stats:
    """Internal counters; only mutated under CircuitBreaker._lock."""

    total_calls: int = 0
    total_successes: int = 0
    total_failures: int = 0
    total_short_circuited: int = 0
    last_failure_ts: float = 0.0


class CircuitBreaker:
    """Three-state circuit breaker.

    State machine:
        CLOSED      Every call passes through. ``failure_threshold``
                    consecutive failures move to OPEN.
        OPEN        Every call is short-circuited with CircuitOpenError.
                    After ``cooldown_s`` seconds, transitions to HALF_OPEN.
        HALF_OPEN   Up to ``success_threshold`` probe calls are allowed
                    (default 1). Each success increments a probe counter;
                    reaching ``success_threshold`` transitions to CLOSED.
                    Any failure transitions back to OPEN with the cooldown
                    timer reset.

    Args:
        failure_threshold:   Consecutive failures while CLOSED before
                             tripping to OPEN. Must be >= 1.
        cooldown_s:          Seconds to stay in OPEN before allowing a
                             probe. Must be > 0.
        success_threshold:   Successes required in HALF_OPEN to close.
                             Default 1. Set higher to require multiple
                             stable probes before fully reopening traffic.
        name:                Optional label included in stats() and error.
        now_fn:              Time source. Default time.monotonic.
                             Tests inject a fake clock.
        exception_predicate: ``Callable[[Exception], bool]`` — return True
                             for exceptions that should count as failure.
                             Default: every exception counts. Use this to
                             ignore expected errors (e.g. 4xx client errors
                             that don't indicate provider unhealth).

    Raises:
        ValueError: if thresholds are out of range.
    """

    def __init__(
        self,
        *,
        failure_threshold: int = 5,
        cooldown_s: float = 30.0,
        success_threshold: int = 1,
        name: str = "",
        now_fn: Callable[[], float] = time.monotonic,
        exception_predicate: Optional[Callable[[Exception], bool]] = None,
    ) -> None:
        if failure_threshold < 1:
            raise ValueError(
                f"failure_threshold must be >= 1, got {failure_threshold!r}"
            )
        if cooldown_s <= 0:
            raise ValueError(f"cooldown_s must be > 0, got {cooldown_s!r}")
        if success_threshold < 1:
            raise ValueError(
                f"success_threshold must be >= 1, got {success_threshold!r}"
            )

        self._failure_threshold = failure_threshold
        self._cooldown_s = float(cooldown_s)
        self._success_threshold = success_threshold
        self._name = name
        self._now_fn = now_fn
        self._exception_predicate = exception_predicate

        self._lock = threading.Lock()
        self._state: CircuitState = "closed"
        self._consecutive_failures = 0
        self._half_open_successes = 0
        self._opened_at: float = 0.0
        self._stats = _Stats()

    # ── State queries ───────────────────────────────────────────────────────

    @property
    def name(self) -> str:
        return self._name

    @property
    def state(self) -> CircuitState:
        """Current state. Triggers a cooldown-elapsed check first."""
        with self._lock:
            self._maybe_transition_to_half_open_locked()
            return self._state

    @property
    def consecutive_failures(self) -> int:
        with self._lock:
            return self._consecutive_failures

    def allow_request(self) -> bool:
        """Non-call probe: returns True if a real call would be permitted.

        Use when ``call()`` is inappropriate (e.g. you need to pass a
        complex callable shape). Combine with ``record_success`` /
        ``record_failure`` to drive the breaker manually.

        Note: in HALF_OPEN, only one probe is allowed at a time.
        Concurrent allow_request() calls in HALF_OPEN may both return
        True only if neither has yet recorded an outcome — this is the
        same race as call(). Manual users should hold an external
        per-key lock if strict single-probe semantics are required.
        """
        with self._lock:
            self._maybe_transition_to_half_open_locked()
            if self._state == "open":
                self._stats.total_short_circuited += 1
                return False
            return True

    # ── Outcome recording ──────────────────────────────────────────────────

    def record_success(self) -> None:
        """Record a successful call outcome in manual mode."""
        with self._lock:
            self._stats.total_calls += 1
            self._stats.total_successes += 1
            if self._state == "half_open":
                self._half_open_successes += 1
                if self._half_open_successes >= self._success_threshold:
                    self._transition_to_closed_locked()
            else:
                # CLOSED success resets the failure streak.
                self._consecutive_failures = 0

    def record_failure(self) -> None:
        """Record a failed call outcome in manual mode."""
        with self._lock:
            self._stats.total_calls += 1
            self._stats.total_failures += 1
            self._stats.last_failure_ts = self._now_fn()
            if self._state == "half_open":
                # Probe failed -> reopen with fresh cooldown.
                self._transition_to_open_locked()
                return
            self._consecutive_failures += 1
            if self._consecutive_failures >= self._failure_threshold:
                self._transition_to_open_locked()

    # ── call() wrapper ─────────────────────────────────────────────────────

    def call(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        """Invoke ``fn(*args, **kwargs)`` if the breaker permits.

        Behaviour:
          - CLOSED / HALF_OPEN: call fn. Success -> record_success and
            return. Failure (where exception_predicate returns True) ->
            record_failure and re-raise. Other exceptions are re-raised
            without affecting breaker state.
          - OPEN: raise CircuitOpenError WITHOUT calling fn.

        The ``exception_predicate`` lets the caller distinguish
        "downstream is unhealthy" (e.g. 5xx, ConnectionError) from
        "I gave bad input" (e.g. ValueError, 4xx) — only the former
        should trip the breaker.
        """
        if not self.allow_request():
            with self._lock:
                retry_after = self._retry_after_locked()
            raise CircuitOpenError(self._name, retry_after)
        try:
            result = fn(*args, **kwargs)
        except Exception as exc:  # noqa: BLE001 — intentional broad
            if self._exception_predicate is None or self._exception_predicate(exc):
                self.record_failure()
            else:
                # Bookkeeping: count the call but don't trip.
                with self._lock:
                    self._stats.total_calls += 1
            raise
        self.record_success()
        return result

    # ── Internal transitions (caller MUST hold self._lock) ─────────────────

    def _maybe_transition_to_half_open_locked(self) -> None:
        if self._state != "open":
            return
        if self._now_fn() >= self._opened_at + self._cooldown_s:
            self._state = "half_open"
            self._half_open_successes = 0

    def _transition_to_open_locked(self) -> None:
        self._state = "open"
        self._opened_at = self._now_fn()
        self._half_open_successes = 0

    def _transition_to_closed_locked(self) -> None:
        self._state = "closed"
        self._consecutive_failures = 0
        self._half_open_successes = 0

    def _retry_after_locked(self) -> float:
        if self._state != "open":
            return 0.0
        elapsed = self._now_fn() - self._opened_at
        remaining = self._cooldown_s - elapsed
        return max(0.0, remaining)

    # ── Observability ──────────────────────────────────────────────────────

    def stats(self) -> dict[str, Any]:
        """structlog-ready snapshot of breaker counters and state."""
        with self._lock:
            self._maybe_transition_to_half_open_locked()
            return {
                "name": self._name,
                "state": self._state,
                "failure_threshold": self._failure_threshold,
                "cooldown_s": self._cooldown_s,
                "success_threshold": self._success_threshold,
                "consecutive_failures": self._consecutive_failures,
                "total_calls": self._stats.total_calls,
                "total_successes": self._stats.total_successes,
                "total_failures": self._stats.total_failures,
                "total_short_circuited": self._stats.total_short_circuited,
                "last_failure_ts": self._stats.last_failure_ts,
                "retry_after_s": self._retry_after_locked(),
            }


__all__ = ["CircuitBreaker", "CircuitOpenError", "CircuitState"]
