"""Structured Logging mit structlog."""
from __future__ import annotations
import uuid
import structlog

structlog.configure(
    processors=[structlog.processors.add_log_level, structlog.processors.TimeStamper(fmt="iso"),
                structlog.dev.ConsoleRenderer() if __debug__ else structlog.processors.JSONRenderer()],
    context_class=dict, logger_factory=structlog.PrintLoggerFactory(), cache_logger_on_first_use=True)

def get_logger(correlation_id: str | None = None) -> structlog.BoundLogger:
    return structlog.get_logger().bind(correlation_id=correlation_id or uuid.uuid4().hex[:12])
