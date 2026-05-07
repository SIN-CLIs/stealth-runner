"""Structured logging with structlog + optional OpenTelemetry tracing.

WARUM: Debugging von CDP-Interaktionen und Captcha-Solvern erfordert
strukturierte Logs. Unstrukturierte print()-Statements verlieren Kontext
(Race-Conditions, Timing, Session-IDs). structlog garantiert JSON-kompatible
Ausgabe für ELK/CloudWatch.

ARCHITEKTUR: structlog als Default-Logger (JSON nach stderr).
OpenTelemetry TracerProvider optional (OTEL_EXPORTER env var).
Kein globaler State — Logger wird pro Modul via get_logger(__name__) geholt.
Production: OTEL_EXPORTER an Collector binden. Development: stderr.

BANNED METHODS — NIEMALS VERWENDEN:
❌ playstealth launch
❌ webauto-nodriver — ABSOLUT BANNED
❌ cua-driver click (raw index)
❌ --remote-allow-origins=* (ohne Quotes)
❌ /tmp/heypiggy-bot (fixed profile)
❌ Hardcoded PIDs
❌ pkill -f "Google Chrome"
❌ killall Google Chrome
❌ skylight-cli click --element-index
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
