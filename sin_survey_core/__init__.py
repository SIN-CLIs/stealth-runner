"""sin_survey_core – Aus dem A2A-SIN-Worker extrahierte Survey-Intelligenz.

Dieses Paket bündelt die drei Kernkompetenzen, die unabhängig vom
Automatisierungs-Backend sind:

* ``panels``  – Erkennung von Umfrageplattformen (HeyPiggy, Dynata, Cint …)
* ``rewards`` – Extraktion von EUR-Beträgen aus Seitentexten
* ``errors``  – Klassifikation von Fehlerseiten (disqualified, quota_full …)
"""

from __future__ import annotations

from sin_survey_core.panels.detectors import (
    PANELS,
    PanelRules,
    build_panel_prompt_block,
    detect_panel,
)
from sin_survey_core.rewards.extractor import (
    extract_earnings_summary,
    extract_eur_from_text,
)
from sin_survey_core.errors.templates import (
    SURVEY_ERROR_PATTERNS,
    classify_error,
)

__all__ = [
    "detect_panel",
    "build_panel_prompt_block",
    "PANELS",
    "PanelRules",
    "extract_eur_from_text",
    "extract_earnings_summary",
    "classify_error",
    "SURVEY_ERROR_PATTERNS",
]

__version__ = "0.1.0"
