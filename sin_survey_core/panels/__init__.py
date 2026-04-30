"""Panel-Provider-Erkennung für Umfrageplattformen.

Provider (8): PureSpectrum, Dynata, Sapio, Cint, Lucid, HeyPiggy, MarketSight, Bilendi
"""

from __future__ import annotations

from sin_survey_core.panels.detectors import (
    PANELS,
    PanelRules,
    build_panel_prompt_block,
    detect_panel,
    detect_panel_dq,
    detect_quality_trap,
)

__all__ = [
    "detect_panel",
    "build_panel_prompt_block",
    "detect_panel_dq",
    "detect_quality_trap",
    "PANELS",
    "PanelRules",
]

__version__ = "0.2.0"
