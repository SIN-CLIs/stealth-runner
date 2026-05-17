"""================================================================================
RATE LIMIT — Thread-safe token bucket for replay/retry budgeting (SR-251)
================================================================================

MODUL-KONZEPT (SR-251)
----------------------

Mehrere geplante Wireups brauchen ein "max N Aktionen pro Zeitfenster":

  - DLQ-Replay (#247 SR-152): wenn `dlq.replay_pending()` einen Cron
    triggert, soll er bei 100+ pending nicht alle gleichzeitig knallen.
    Pro-Run-Budget: z. B. 5 Replays/Minute.

  - LangGraph-Resume (#238 SR-238): nach einem Crash gibt es vielleicht
    20 unterbrochene Surveys. Wir wollen sie nicht auf einmal
    re-spawnen, sonst killt der erste Persona-Burst die Anti-Detection.

  - Sweep-Reaper (#246 SR-247): `sweep_expired()` zwischen Persona-Pools
    soll auf grossen Stores (10k+ Personas) nicht den Filesystem-IO
    monopolisieren.

  - Vision-Fallback (#239 SR-239): pro Survey-Run nur N OpenAI-Vision-
    Calls — Cost-Budget.

Wiederholungs-Boilerplate dieser Form gehoert nicht in jeden Caller.
Eine kleine, pruefbare TokenBucket-Implementierung deckt alle Faelle.

DESIGN
------

Klassischer leaky/refill Token-Bucket:

  - capacity     = max Tokens auf einmal
  - refill_rate  = Tokens/Sekunde nachgefuellt
  - now()        = injizierbar fuer Tests (default time.monotonic)
  - lock         = threading.Lock — alle Methoden sind thread-safe

Aufrufer nutzt `try_acquire(tokens=1)` (non-blocking) oder
`acquire(tokens=1, max_wait_s=...)` (blocking with hard cap).

WARUM threading.Lock + monotonic statt asyncio:

  Die meisten Callsites (DLQ-Replay, sweep_expired) sind sync.
  asyncio-only-Implementations zwingen sync-Callsites zum
  `asyncio.run()` — das ist auf survey/safe_executor.py-Pfad
  bereits problematisch (siehe SR-173 Begruendung). Sync ist der
  kleinere gemeinsame Nenner; eine async-Wrapper-Schicht kann ohne
  API-Bruch nachgereicht werden.

PUBLIC API
----------
    TokenBucket
        capacity, refill_rate, now_fn, initial_tokens?
        try_acquire(tokens=1) -> bool
        acquire(tokens=1, max_wait_s=...) -> bool       # blocks via sleep_fn
        available_tokens() -> float                     # diagnostic
        time_until(tokens) -> float                     # seconds until N tokens

OBSERVABILITY
-------------

stats() -> dict[str, float|int] gibt structlog-faehige Metriken aus:
    capacity, refill_rate, available_tokens, total_acquired,
    total_denied, ratio_denied.

USAGE PATTERN
-------------

    >>> # 5 replays per minute, burst-fenster 5
    >>> bucket = TokenBucket(capacity=5, refill_rate=5/60)
    >>> for record in dlq.list_pending():
    ...     if not bucket.try_acquire():
    ...         logger.info('rate_limited', skipped=record.id)
    ...         continue
    ...     dlq.replay(record.id)

    >>> # synchronous "block up to 30s for a token"
    >>> if bucket.acquire(max_wait_s=30):
    ...     run_expensive_thing()

NICHT-ZIELE
-----------
- KEIN distributed rate-limit (Redis/etc).
- KEIN asyncio-flavor — bewusst sync. Async-Wrapper als
  Folge-PR moeglich.
- Kein automatic registry / global instance.

Module Status: NEW (SR-251)
================================================================================
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Callable, Optional


_DEFAULT_NOW: Callable[[], float] = time.monotonic
_DEFAULT_SLEEP: Callable[[float], None] = time.sleep


@dataclass
class _Stats:
    """Mutable counters; only touched under TokenBucket._lock."""

    total_acquired: int = 0
    total_denied: int = 0


class TokenBucket:
    """Classic token-bucket rate limiter, thread-safe, dependency-free.

    The bucket holds at most ``capacity`` tokens. Tokens refill at
    ``refill_rate`` per second (linear). Each successful ``acquire`` /
    ``try_acquire`` consumes ``tokens`` tokens.

    Args:
        capacity:           Maximum tokens the bucket holds. Must be > 0.
                            int or float. Acts as the burst limit.
        refill_rate:        Tokens added per second. Must be >= 0.
                            ``refill_rate=5/60`` means 5 tokens/min.
                            ``refill_rate=0`` is legal — bucket only
                            ever drains (useful for one-shot quotas).
        initial_tokens:     Starting tokens. Default = capacity (full bucket).
                            Set to 0 to force callers to wait for refill.
        now_fn:             Time source. Default ``time.monotonic``.
                            Tests inject a mutable clock.
        sleep_fn:           Sleep function used by ``acquire()`` blocking
                            mode. Default ``time.sleep``. Tests inject a
                            no-op so the test runs instantly.
        name:               Optional label, included in stats(). Useful
                            when multiple buckets share a structlog stream.

    Raises:
        ValueError: if capacity <= 0, refill_rate < 0, or
                    initial_tokens < 0 / > capacity.
    """

    def __init__(
        self,
        capacity: float,
        refill_rate: float,
        *,
        initial_tokens: Optional[float] = None,
        now_fn: Callable[[], float] = _DEFAULT_NOW,
        sleep_fn: Callable[[float], None] = _DEFAULT_SLEEP,
        name: str = "",
    ) -> None:
        if capacity <= 0:
            raise ValueError(f"capacity must be > 0, got {capacity!r}")
        if refill_rate < 0:
            raise ValueError(f"refill_rate must be >= 0, got {refill_rate!r}")
        start = capacity if initial_tokens is None else initial_tokens
        if start < 0 or start > capacity:
            raise ValueError(
                f"initial_tokens must be in [0, {capacity}], got {start!r}"
            )
        self._capacity = float(capacity)
        self._refill_rate = float(refill_rate)
        self._tokens = float(start)
        self._now_fn = now_fn
        self._sleep_fn = sleep_fn
        self._name = name
        self._lock = threading.Lock()
        self._last_refill_ts = self._now_fn()
        self._stats = _Stats()

    # ── Internal: refill tokens linearly since last call ────────────────────

    def _refill_locked(self) -> None:
        """Caller MUST hold self._lock."""
        if self._refill_rate == 0:
            return
        now = self._now_fn()
        elapsed = now - self._last_refill_ts
        if elapsed <= 0:
            # Clock skew or now_fn returning equal values — no-op.
            return
        added = elapsed * self._refill_rate
        self._tokens = min(self._capacity, self._tokens + added)
        self._last_refill_ts = now

    # ── Public ──────────────────────────────────────────────────────────────

    @property
    def capacity(self) -> float:
        return self._capacity

    @property
    def refill_rate(self) -> float:
        return self._refill_rate

    @property
    def name(self) -> str:
        return self._name

    def available_tokens(self) -> float:
        """Tokens currently in the bucket. Triggers a refill computation."""
        with self._lock:
            self._refill_locked()
            return self._tokens

    def time_until(self, tokens: float) -> float:
        """Seconds until at least ``tokens`` tokens will be available.

        Returns 0.0 if already available, +inf if refill_rate is 0 and
        the bucket can't reach the requested level by refill alone.
        """
        if tokens <= 0:
            return 0.0
        with self._lock:
            self._refill_locked()
            if self._tokens >= tokens:
                return 0.0
            if self._refill_rate <= 0:
                return float("inf")
            deficit = tokens - self._tokens
            return deficit / self._refill_rate

    def try_acquire(self, tokens: float = 1) -> bool:
        """Non-blocking acquire. Returns True on success, False if not
        enough tokens are currently available.

        Args:
            tokens: How many tokens to consume. Must be > 0 and
                    <= capacity (else always False).
        """
        if tokens <= 0:
            return True  # no-op
        with self._lock:
            self._refill_locked()
            if tokens > self._capacity:
                # Defensive: caller asked for more than the bucket can
                # ever hold. Deny and count.
                self._stats.total_denied += 1
                return False
            if self._tokens >= tokens:
                self._tokens -= tokens
                self._stats.total_acquired += 1
                return True
            self._stats.total_denied += 1
            return False

    def acquire(
        self,
        tokens: float = 1,
        *,
        max_wait_s: float = 0.0,
        poll_interval_s: float = 0.05,
    ) -> bool:
        """Blocking acquire — sleeps until tokens are available, up to
        ``max_wait_s`` seconds total. Returns True on success, False on
        timeout or if the request can never be fulfilled.

        Args:
            tokens:           Tokens to consume. > 0.
            max_wait_s:       Hard wall-clock cap. 0 = behave like
                              try_acquire (no sleep).
            poll_interval_s:  How often to recheck the bucket while
                              waiting. Default 50ms — fine-grained enough
                              for typical replay cadences.

        Notes:
            We compute sleep durations from time_until() rather than
            polling blindly, so a 30s wait for a slow refill_rate doesn't
            wake 600 times.
        """
        if tokens <= 0:
            return True
        if self.try_acquire(tokens):
            return True
        if max_wait_s <= 0:
            return False

        deadline = self._now_fn() + max_wait_s
        while True:
            wait_s = self.time_until(tokens)
            if wait_s == float("inf"):
                # Never satisfiable.
                return False
            now = self._now_fn()
            if now >= deadline:
                return False
            sleep_for = min(wait_s, deadline - now, poll_interval_s)
            if sleep_for > 0:
                self._sleep_fn(sleep_for)
            if self.try_acquire(tokens):
                return True

    def stats(self) -> dict[str, float]:
        """structlog-ready snapshot."""
        with self._lock:
            self._refill_locked()
            attempts = self._stats.total_acquired + self._stats.total_denied
            ratio = (
                self._stats.total_denied / attempts if attempts > 0 else 0.0
            )
            return {
                "name": self._name,
                "capacity": self._capacity,
                "refill_rate": self._refill_rate,
                "available_tokens": self._tokens,
                "total_acquired": self._stats.total_acquired,
                "total_denied": self._stats.total_denied,
                "ratio_denied": ratio,
            }


__all__ = ["TokenBucket"]
