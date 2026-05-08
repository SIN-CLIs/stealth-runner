"""survey/observability/ — Structured logging, metrics, and health monitoring.

WARUM: Phase 5 von ULTIMATE-PLAN.md — "print() in Produktionscode durch
JSONL Logger ersetzen". Alle Survey-Events werden als strukturierte JSONL
geschrieben. Optionale Console-Ausgabe fuer Debug-Modus.

ARCHITEKTUR:
  observability/
    __init__.py        -> exports: get_logger, SurveyMetrics, RuntimeHealth
    logger.py          -> StructuredLogger: JSONL + optional console
    metrics.py         -> SurveyMetrics singleton + RuntimeHealth
    health.py          -> Daemon/Chrome/Session health checks

BANNED METHODS — NIEMALS VERWENDEN:
  ❌ playstealth launch
  ❌ webauto-nodriver — ABSOLUT BANNED
  ❌ cua-driver click (raw index)
  ❌ --remote-allow-origins=* (ohne Quotes)
  ❌ /tmp/heypiggy-bot (fixed profile)
  ❌ Hardcoded PIDs
  ❌ pkill -f "Google Chrome"
  ❌ killall Google Chrome
  ❌ skylight-cli click --element-index
"""

from .logger import StructuredLogger, get_logger, reset_logger
from .metrics import SurveyMetrics, reset_metrics
from .health import RuntimeHealth, check_and_alert, is_session_corrupted

__all__ = [
    "StructuredLogger",
    "get_logger",
    "reset_logger",
    "SurveyMetrics",
    "reset_metrics",
    "RuntimeHealth",
    "check_and_alert",
    "is_session_corrupted",
]