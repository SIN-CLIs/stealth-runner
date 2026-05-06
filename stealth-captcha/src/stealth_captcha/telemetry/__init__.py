"""Structured logging and OpenTelemetry integration."""

from stealth_captcha.telemetry.tracer import get_logger, init_telemetry

__all__ = ["get_logger", "init_telemetry"]
