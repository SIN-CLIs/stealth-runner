"""Fehlerklassifikation für Umfrage-Abbrüche (4 Kategorien, mehrsprachig)."""

from __future__ import annotations

from sin_survey_core.errors.templates import (
    ErrorCategory,
    ErrorInfo,
    classify_error,
)

__all__ = ["classify_error", "ErrorInfo", "ErrorCategory"]
__version__ = "0.2.0"
