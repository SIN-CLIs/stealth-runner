"""sin_survey_core – Aus dem A2A-SIN-Worker extrahierte Survey-Intelligenz."""
from __future__ import annotations

from sin_survey_core.panels.detectors import (
    PANELS, PanelRules, build_panel_prompt_block, detect_panel,
)
from sin_survey_core.rewards.extractor import (
    EarningsSummary, extract_earnings_summary, extract_eur_from_text,
)
from sin_survey_core.errors.templates import (
    ErrorCategory, ErrorInfo, classify_error,
)

__all__ = [
    "detect_panel", "build_panel_prompt_block", "PANELS", "PanelRules",
    "extract_eur_from_text", "extract_earnings_summary", "EarningsSummary",
    "classify_error", "ErrorInfo", "ErrorCategory",
]
__version__ = "0.2.0"
