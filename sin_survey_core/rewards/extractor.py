"""EUR-Betrag-Extraktion aus Umfrage-Seitentexten.

Verwendet vorkompilierte Regex-Patterns auf Modulebene für maximale Performance.
Unterstützt 6 EUR-Formate: €-Symbol, EUR-Suffix, Verdienst/Reward-Labels.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final


_EUR_PATTERNS: Final[list[re.Pattern[str]]] = [
    re.compile(r"Verdienst[s]?\s*[=:]?\s*(\d+[.,]\d{2})", re.IGNORECASE),
    re.compile(r"Reward[s]?\s*[=:]?\s*(\d+[.,]\d{2})", re.IGNORECASE),
    re.compile(r"(\d+[.,]\d{2})\s*[€]", re.IGNORECASE),
    re.compile(r"[€]\s*(\d+[.,]\d{2})", re.IGNORECASE),
    re.compile(r"EUR\s*[=:]\s*(\d+[.,]\d+)", re.IGNORECASE),
    re.compile(r"(\d+[.,]\d{2})\s*EUR", re.IGNORECASE),
]


def extract_eur_from_text(text: str) -> float:
    """Extrahiert den ersten EUR-Betrag aus einem beliebigen Text."""
    if not text:
        return 0.0
    for pattern in _EUR_PATTERNS:
        match = pattern.search(text)
        if match:
            return float(match.group(1).replace(",", "."))
    return 0.0


@dataclass(frozen=True, slots=True)
class EarningsSummary:
    """Strukturierte EUR-Auszahlung aus einem Survey-Chunk."""
    eur: float
    page_text: str


def extract_earnings_summary(page_text: str) -> EarningsSummary:
    """Extrahiert EUR-Betrag und gibt eine Zusammenfassung zurück."""
    eur = extract_eur_from_text(page_text)
    return EarningsSummary(eur=eur, page_text=page_text[:200])
