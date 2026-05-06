"""Structured logging with structlog + optional OpenTelemetry tracing.

We keep telemetry lightweight: structlog for structured JSON logs by default,
with an OpenTelemetry TracerProvider that writes spans to stderr (console)
during development. In production, point OTEL_EXPORTER at your collector.
"""

from __future__ import annotations

import logging
import sys
from typing import Any

import structlog

_INITIALIZED = False


def init_telemetry(level: str = "INFO") -> None:
    """Initialize structlog once. Idempotent."""
    global _INITIALIZED  # noqa: PLW0603
    if _INITIALIZED:
        return

    logging.basicConfig(stream=sys.stderr, level=level.upper(), format="%(message)s")

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, level.upper(), logging.INFO)
        ),
        logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
        cache_logger_on_first_use=True,
    )

    _INITIALIZED = True


def get_logger(name: str | None = None) -> Any:
    """Get a structlog logger. Init telemetry first if needed."""
    if not _INITIALIZED:
        init_telemetry()
    return structlog.get_logger(name or "stealth_captcha")
