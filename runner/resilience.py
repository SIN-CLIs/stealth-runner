"""Resilienz-Patterns: Retry, Circuit Breaker, Graceful Shutdown."""
from __future__ import annotations
import signal, asyncio, logging
from typing import Callable, Coroutine, Any
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

logger = logging.getLogger("stealth-runner.resilience")

def vision_retry(max_attempts: int = 3):
    return retry(stop=stop_after_attempt(max_attempts), wait=wait_exponential(multiplier=0.5, min=0.5, max=10),
                 retry=retry_if_exception_type((TimeoutError, ConnectionError, OSError)), reraise=True)

_shutdown_handlers: list[Callable[[], Coroutine[Any, Any, None]]] = []

def register_shutdown_handler(handler: Callable[[], Coroutine[Any, Any, None]]) -> None:
    _shutdown_handlers.append(handler)

def install_shutdown_handlers() -> None:
    loop = asyncio.get_event_loop()
    async def _handle(sig): 
        for h in _shutdown_handlers: await h()
        loop.stop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, lambda s=sig: asyncio.create_task(_handle(s)))
