"""================================================================================
stealth-runner / core / error_handler.py  — Enterprise Error Handling
================================================================================

HERKUNFT
--------
Aus Delqhi/sin-hermes-agent (.open-auth-rotator/openai/core/error_handler.py)
1:1 uebernommen — das Modul ist universal und an keiner Stelle openai-spezifisch.

ZWECK
-----
EINE Stelle fuer alle Failure-Modi des Survey-Agents:
  - Typed exception hierarchy:    StepError -> RecoverableError | FatalError
  - Retry-Strategien:             exponential, linear, jitter
  - Circuit Breaker pro Step:     3x Fail -> Step blocked fuer 60s
  - ErrorContext:                 Stack-Trace + Screenshot + retry-count
  - Recovery-Callbacks:           optionaler Cleanup vor Retry

WANN BENUTZEN?
--------------
Immer wenn eine async-Operation fehlschlagen KANN und ein Retry sinnvoll
waere. Konkret in stealth-runner:
  - Captcha-Solve            -> RecoverableError (anderer Solver versuchen)
  - CDP-WebSocket-Reconnect  -> RecoverableError (Chrome respawnen)
  - Survey-Open-Redirect     -> FatalError (Account-Cookies tot, kein Retry)
  - Decide-LLM-Timeout       -> RecoverableError (anderes Model)
  - Browser-Crash            -> FatalError (Chrome-Process tot)

INTEGRATION MIT LANGGRAPH
-------------------------
Jeder LangGraph-Node wird mit ``@handler.with_retry()`` dekoriert
ODER manuell ueber ``await handler.execute_with_recovery(...)``
ausgefuehrt. Siehe core/langgraph_integration.py.

CIRCUIT-BREAKER-LOGIK
---------------------
  FAILURE_THRESHOLD=3   : nach 3 Fails geht Breaker OPEN
  RESET_TIMEOUT=60s     : nach 60s OPEN -> HALF_OPEN
  HALF_OPEN_MAX=1       : 1 Probe-Request, wenn OK -> CLOSED, sonst -> OPEN

So verhindern wir, dass ein kaputter Step (z. B. tote Provider-API)
das gesamte Survey-Budget verbrennt. Stattdessen wird der Step uebersprungen
oder eskaliert.

BANNED
------
- Kein bare ``except:``  -- immer typed
- Kein ``except Exception: pass`` ohne Context-Log
- Keine Retries OHNE backoff (DDoSed sich selbst)
- Keine Retries auf FatalError (Definition: nicht retry-bar)
================================================================================"""

from __future__ import annotations

import asyncio
import random
import time
import traceback
from dataclasses import dataclass, field
from enum import Enum
from functools import wraps
from typing import Any, Awaitable, Callable, Optional


# -- ENUMS ----------------------------------------------------------------------


class ErrorSeverity(Enum):
    """Severity fuer Alerting + Audit-Filter."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class RetryStrategy(Enum):
    """Wann/wie soll retried werden?

    NONE                : Kein Retry (Compile-Time-Fehler etc.)
    IMMEDIATE           : Sofort wieder (0.1s, e.g. transient connect race)
    LINEAR              : base_delay * attempt
    EXPONENTIAL         : base_delay * 2**attempt
    EXPONENTIAL_JITTER  : EXPONENTIAL * random(0.5, 1.5)  -- recommended default
    """
    NONE = "none"
    IMMEDIATE = "immediate"
    LINEAR = "linear"
    EXPONENTIAL = "exponential"
    EXPONENTIAL_JITTER = "exponential_jitter"


# -- ERROR CONTEXT --------------------------------------------------------------


@dataclass
class ErrorContext:
    """Reichhaltiger Kontext der bei jedem Fehler erfasst wird.

    Wird in AuditLogger geschrieben + an Screenshots gehaengt.
    additional_data: Frei nutzbar (z. B. stable_id des fehlgeschlagenen Klicks).
    """
    step_name: str
    step_index: int
    timestamp: float = field(default_factory=time.time)
    url: str = ""
    screenshot_path: str = ""
    browser_logs: list = field(default_factory=list)
    stack_trace: str = ""
    retry_count: int = 0
    recovery_attempted: bool = False
    additional_data: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "step_name": self.step_name,
            "step_index": self.step_index,
            "timestamp": self.timestamp,
            "url": self.url,
            "screenshot_path": self.screenshot_path,
            "browser_logs": self.browser_logs,
            "stack_trace": self.stack_trace,
            "retry_count": self.retry_count,
            "recovery_attempted": self.recovery_attempted,
            **self.additional_data,
        }


# -- EXCEPTION HIERARCHY --------------------------------------------------------


class StepError(Exception):
    """Basis aller Step-Failures. Tragen Context + Severity."""

    def __init__(
        self,
        message: str,
        context: Optional[ErrorContext] = None,
        severity: ErrorSeverity = ErrorSeverity.ERROR,
    ):
        super().__init__(message)
        self.context = context
        self.severity = severity

    def __str__(self) -> str:
        base = super().__str__()
        if self.context:
            return f"{base} [step={self.context.step_name}, retry={self.context.retry_count}]"
        return base


class RecoverableError(StepError):
    """Fehler den wir retryen DUERFEN. Suggested-Strategy darf der Aufrufer
    setzen (z. B. IMMEDIATE bei reinen Race-Conditions)."""

    def __init__(
        self,
        message: str,
        context: Optional[ErrorContext] = None,
        suggested_strategy: RetryStrategy = RetryStrategy.EXPONENTIAL_JITTER,
    ):
        super().__init__(message, context, ErrorSeverity.WARNING)
        self.suggested_strategy = suggested_strategy


class FatalError(StepError):
    """Nicht retry-bar. Pipeline MUSS abbrechen.

    Beispiele:
      - Chrome-Binary nicht installiert
      - Supabase-URL ungueltig
      - Survey-Account gebannt (Cookies tot)
    """

    def __init__(self, message: str, context: Optional[ErrorContext] = None):
        super().__init__(message, context, ErrorSeverity.CRITICAL)


# -- CIRCUIT BREAKER ------------------------------------------------------------


@dataclass
class CircuitBreakerState:
    """Per-Step Circuit-Breaker.

    CLOSED       : alles ok, requests durchlassen
    OPEN         : Threshold ueberschritten, requests BLOCKED bis RESET_TIMEOUT
    HALF_OPEN    : RESET_TIMEOUT abgelaufen, 1 Probe-Request erlaubt
    """
    failures: int = 0
    last_failure: float = 0.0
    is_open: bool = False
    half_open_attempts: int = 0

    FAILURE_THRESHOLD = 3
    RESET_TIMEOUT = 60.0
    HALF_OPEN_MAX = 1


# -- ERROR HANDLER --------------------------------------------------------------


class ErrorHandler:
    """Zentraler Error-Handler.

    Public API:
      with_retry(strategy=...)            -> Decorator fuer async-Funktionen
      execute_with_recovery(...)          -> manueller call
      get_error_summary()                 -> fuer /health-Endpoint
    """

    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        on_error: Optional[Callable] = None,
    ):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.on_error = on_error
        self._circuit_breakers: dict[str, CircuitBreakerState] = {}
        self._error_history: list[ErrorContext] = []

    # -- Circuit-Breaker-Logik ----------------------------------------------

    def _get_circuit_breaker(self, step_name: str) -> CircuitBreakerState:
        if step_name not in self._circuit_breakers:
            self._circuit_breakers[step_name] = CircuitBreakerState()
        return self._circuit_breakers[step_name]

    def _check_circuit_breaker(self, step_name: str) -> bool:
        """True = darf laufen. False = geblockt."""
        cb = self._get_circuit_breaker(step_name)
        if not cb.is_open:
            return True
        if time.time() - cb.last_failure > CircuitBreakerState.RESET_TIMEOUT:
            cb.is_open = False
            cb.half_open_attempts = 0
            return True
        if cb.half_open_attempts < CircuitBreakerState.HALF_OPEN_MAX:
            cb.half_open_attempts += 1
            return True
        return False

    def _record_failure(self, step_name: str, context: ErrorContext) -> None:
        cb = self._get_circuit_breaker(step_name)
        cb.failures += 1
        cb.last_failure = time.time()
        if cb.failures >= CircuitBreakerState.FAILURE_THRESHOLD:
            cb.is_open = True
            print(f"[CIRCUIT_BREAKER] Opened for step: {step_name}")
        self._error_history.append(context)
        if len(self._error_history) > 1000:
            self._error_history = self._error_history[-500:]

    def _record_success(self, step_name: str) -> None:
        cb = self._get_circuit_breaker(step_name)
        cb.failures = 0
        cb.is_open = False
        cb.half_open_attempts = 0

    # -- Retry-Math ---------------------------------------------------------

    def calculate_delay(self, attempt: int, strategy: RetryStrategy) -> float:
        if strategy == RetryStrategy.NONE:
            return 0.0
        if strategy == RetryStrategy.IMMEDIATE:
            return 0.1
        if strategy == RetryStrategy.LINEAR:
            return min(self.base_delay * attempt, self.max_delay)
        if strategy == RetryStrategy.EXPONENTIAL:
            return min(self.base_delay * (2 ** attempt), self.max_delay)
        if strategy == RetryStrategy.EXPONENTIAL_JITTER:
            base = min(self.base_delay * (2 ** attempt), self.max_delay)
            return base * (0.5 + random.random())
        return self.base_delay

    # -- Async-Decorator ----------------------------------------------------

    def with_retry(
        self,
        strategy: RetryStrategy = RetryStrategy.EXPONENTIAL_JITTER,
        max_retries: Optional[int] = None,
    ):
        """Decorator: retry async-Funktion mit Circuit-Breaker.

        Beispiel:
            @handler.with_retry(strategy=RetryStrategy.EXPONENTIAL_JITTER)
            async def solve_captcha(detection): ...
        """
        retries = max_retries if max_retries is not None else self.max_retries

        def decorator(func: Callable[..., Awaitable[Any]]):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                step_name = func.__name__
                for attempt in range(retries + 1):
                    if not self._check_circuit_breaker(step_name):
                        raise FatalError(
                            f"Circuit breaker open for {step_name}",
                            ErrorContext(step_name=step_name, step_index=-1),
                        )
                    try:
                        result = await func(*args, **kwargs)
                        self._record_success(step_name)
                        return result
                    except FatalError:
                        raise
                    except RecoverableError as e:
                        ctx = e.context or ErrorContext(step_name=step_name, step_index=-1)
                        ctx.retry_count = attempt
                        ctx.stack_trace = traceback.format_exc()
                        self._record_failure(step_name, ctx)
                        if self.on_error:
                            await self.on_error(e, ctx)
                        if attempt < retries:
                            delay = self.calculate_delay(attempt, e.suggested_strategy)
                            print(
                                f"[RETRY] {step_name} attempt {attempt+1}/{retries} "
                                f"after {delay:.1f}s"
                            )
                            await asyncio.sleep(delay)
                        else:
                            raise FatalError(
                                f"Max retries ({retries}) exceeded for {step_name}",
                                ctx,
                            ) from e
                    except Exception as e:
                        ctx = ErrorContext(
                            step_name=step_name,
                            step_index=-1,
                            retry_count=attempt,
                            stack_trace=traceback.format_exc(),
                        )
                        self._record_failure(step_name, ctx)
                        if attempt < retries:
                            delay = self.calculate_delay(attempt, strategy)
                            print(
                                f"[RETRY] {step_name} unexpected error, "
                                f"attempt {attempt+1}/{retries}"
                            )
                            await asyncio.sleep(delay)
                        else:
                            raise FatalError(
                                f"Unexpected error in {step_name}: {e}", ctx
                            ) from e
            return wrapper
        return decorator

    # -- Manueller Aufruf mit Recovery-Hook ---------------------------------

    async def execute_with_recovery(
        self,
        step_func: Callable,
        step_name: str,
        step_index: int,
        recovery_func: Optional[Callable] = None,
    ) -> bool:
        """Fuehrt step_func aus. Bei Fehler: recovery_func + Retry.

        Wird fuer LangGraph-Nodes genutzt die nicht async sind ODER
        wo eine explizite Recovery-Action noetig ist (z. B. Chrome neustarten).
        """
        for attempt in range(self.max_retries + 1):
            if not self._check_circuit_breaker(step_name):
                print(f"[CIRCUIT_BREAKER] Blocking execution of {step_name}")
                return False
            try:
                result = (
                    await step_func()
                    if asyncio.iscoroutinefunction(step_func)
                    else step_func()
                )
                self._record_success(step_name)
                return bool(result) if result is not None else True
            except Exception as e:
                ctx = ErrorContext(
                    step_name=step_name,
                    step_index=step_index,
                    retry_count=attempt,
                    stack_trace=traceback.format_exc(),
                )
                self._record_failure(step_name, ctx)
                if self.on_error:
                    try:
                        if asyncio.iscoroutinefunction(self.on_error):
                            await self.on_error(e, ctx)
                        else:
                            self.on_error(e, ctx)
                    except Exception as cb_err:
                        print(f"[ERROR_HANDLER] on_error callback failed: {cb_err}")

                if recovery_func and attempt < self.max_retries:
                    try:
                        print(f"[RECOVERY] Attempting recovery for {step_name}")
                        if asyncio.iscoroutinefunction(recovery_func):
                            await recovery_func()
                        else:
                            recovery_func()
                        ctx.recovery_attempted = True
                        continue
                    except Exception as rerr:
                        print(f"[RECOVERY] Recovery failed: {rerr}")

                if attempt < self.max_retries:
                    delay = self.calculate_delay(attempt, RetryStrategy.EXPONENTIAL_JITTER)
                    print(
                        f"[RETRY] {step_name} attempt {attempt+1}/{self.max_retries} "
                        f"in {delay:.1f}s"
                    )
                    await asyncio.sleep(delay)
                else:
                    print(f"[FATAL] {step_name} failed after {self.max_retries} retries")
                    return False
        return False

    # -- Summary fuer /health -----------------------------------------------

    def get_error_summary(self) -> dict:
        if not self._error_history:
            return {"total_errors": 0, "by_step": {}, "recent": []}
        by_step: dict[str, int] = {}
        for ctx in self._error_history:
            by_step[ctx.step_name] = by_step.get(ctx.step_name, 0) + 1
        return {
            "total_errors": len(self._error_history),
            "by_step": by_step,
            "recent": [ctx.to_dict() for ctx in self._error_history[-10:]],
            "circuit_breakers": {
                name: {"is_open": cb.is_open, "failures": cb.failures}
                for name, cb in self._circuit_breakers.items()
            },
        }
