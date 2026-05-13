"""survey/observability/ -- Structured logging, metrics, health, and visual debug.

WARUM: Phase 5 von ULTIMATE-PLAN.md -- "print() in Produktionscode durch
JSONL Logger ersetzen". Alle Survey-Events werden als strukturierte JSONL
geschrieben. Optionale Console-Ausgabe fuer Debug-Modus.

Phase 6 (SR-173): visual debug reports per step -- HTML + SVG overlay over
the screenshot to instantly spot the 4 coord-misalignment bug classes
(iframe-offset, DPR-mismatch, scroll-stale, z-index-overlay).

ARCHITEKTUR:
  observability/
    __init__.py        -> exports: get_logger, VisualDebugDispatcher, ...
    logger.py          -> StructuredLogger: JSONL + optional console
    metrics.py         -> SurveyMetrics singleton + RuntimeHealth
    health.py          -> Daemon/Chrome/Session health checks
    visual_debug.py    -> SR-173: HTML+SVG debug reports (sampled, async-dispatched)

BANNED METHODS -- NIEMALS VERWENDEN:
  - playstealth launch
  - webauto-nodriver -- ABSOLUT BANNED
  - cua-driver click (raw index)
  - --remote-allow-origins=* (ohne Quotes)
  - /tmp/heypiggy-bot (fixed profile)
  - Hardcoded PIDs
  - pkill -f "Google Chrome"
  - killall Google Chrome
  - skylight-cli click --element-index
"""

from .logger import StructuredLogger, get_logger
from .visual_debug import (
    AttestationResultLike,
    Box,
    ElementRef,
    Point,
    VerificationResultLike,
    VisualDebugDispatcher,
    VisualDebugFrame,
    dispatcher_scope,
    element_bbox_in_page_coords,
    render_html_report,
    should_render,
)

__all__ = [
    # logger
    "StructuredLogger",
    "get_logger",
    # visual_debug (SR-173)
    "AttestationResultLike",
    "Box",
    "ElementRef",
    "Point",
    "VerificationResultLike",
    "VisualDebugDispatcher",
    "VisualDebugFrame",
    "dispatcher_scope",
    "element_bbox_in_page_coords",
    "render_html_report",
    "should_render",
]
