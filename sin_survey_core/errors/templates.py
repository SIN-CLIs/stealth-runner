"""Fehlerklassifikation für Umfrage-Abbrüche — ErrorCategory Enum + ErrorInfo Dataclass."""
from __future__ import annotations
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

class ErrorCategory(StrEnum):
    DISQUALIFIED = "disqualified"
    QUOTA_FULL = "quota_full"
    ATTENTION_FAILED = "attention_failed"
    NOT_FOUND = "not_found"

@dataclass(frozen=True, slots=True)
class ErrorInfo:
    category: ErrorCategory
    message: str
    matched_marker: str = ""

_ERROR_MARKERS: Final[dict[ErrorCategory, tuple[str, ...]]] = {
    ErrorCategory.DISQUALIFIED: (
        "did not qualify", "do not qualify", "you are not qualified",
        "keine teilnahme moeglich", "sie gehoeren nicht zur zielgruppe",
        "leider nicht qualifiziert", "we are unable to offer you",
    ),
    ErrorCategory.QUOTA_FULL: (
        "quota full", "quota has been reached", "survey is full",
        "alle plaetze sind belegt", "keine weiteren teilnehmer",
    ),
    ErrorCategory.ATTENTION_FAILED: (
        "attention check failed", "failed the attention check",
        "did not pass the quality check", "aufmerksamkeitstest nicht bestanden",
    ),
    ErrorCategory.NOT_FOUND: (
        "survey not found", "page not found", "umfrage nicht gefunden",
        "could not find a survey", "error 404", "not available",
    ),
}

def classify_error(page_text: str, *, fallback_message: str = "Unknown error") -> ErrorInfo | None:
    if not page_text or not page_text.strip():
        return None
    low = page_text.lower()
    for category, markers in _ERROR_MARKERS.items():
        for marker in markers:
            if marker.lower() in low:
                return ErrorInfo(category=category, message=f"Survey error: {category.value} ({marker})", matched_marker=marker)
    return None
