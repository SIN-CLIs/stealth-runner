"""EUR-Betrag-Extraktion aus Umfrage-Seitentexten.

Bietet zwei Funktionen:

* :func:`extract_eur_from_text` – Einzelbetrag aus beliebigem Text
* :func:`extract_earnings_summary` – Zusammenfassung inkl. Text-Snippet
"""

from __future__ import annotations

from sin_survey_core.rewards.extractor import (
    EarningsSummary,
    extract_earnings_summary,
    extract_eur_from_text,
)

__all__ = [
    "extract_eur_from_text",
    "extract_earnings_summary",
    "EarningsSummary",
]

__version__ = "0.2.0"
