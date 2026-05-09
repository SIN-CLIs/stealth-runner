"""StructuredLogger — JSONL file logging + optional console output.

WARUM: Alle Survey-Events muessen als strukturierte JSONL geloggt werden.
Optionale Console-Ausgabe fuer Debug-Modus. Kein print() mehr in
survey/ Package (nur CLI-Ausgabe).

ARCHITEKTUR:
  - JSONL Datei: logs/iterations-{YYYY-MM-DD}.jsonl pro Tag
  - Console: nur wenn verbose=True (vom Runner gesteuert)
  - Survey-scoped: Jeder Eintrag hat survey_id + provider
  - Tag-basiert: [RUN], [BALANCE], [LOOP], [PREQ], etc.

BANNED METHODS — NIEMALS VERWENDEN:
  ❌ playstealth launch
  ❌ webauto-nodriver — ABSOLUT BANNED
  ❌ cua-driver click (raw index)
  ❌ --remote-allow-origins=* (ohne Quotes)
  ❌ Hardcoded PIDs
  ❌ pkill -f "Google Chrome"
  ❌ killall Google Chrome
"""

import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

# ── Log Directory ──────────────────────────────────────

LOGS_DIR = Path(__file__).parent.parent.parent / "logs"


def _ensure_logs():
    """Ensure logs directory exists."""
    LOGS_DIR.mkdir(parents=True, exist_ok=True)


def _daily_file(name: str) -> Path:
    """Get daily log file path for structured logs."""
    date = datetime.now().strftime("%Y-%m-%d")
    return LOGS_DIR / f"{name}-{date}.jsonl"


# ── Console Colors ─────────────────────────────────────

class _Colors:
    RESET = "\033[0m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    BOLD = "\033[1m"

    @classmethod
    def disable(cls):
        cls.RESET = cls.GREEN = cls.RED = cls.YELLOW = cls.BLUE = cls.CYAN = cls.BOLD = ""


# ── Module-level Logger ─────────────────────────────────

_module_logger: Optional["StructuredLogger"] = None


def get_logger(verbose: bool = False, survey_id: str = "",
              provider: str = "") -> "StructuredLogger":
    """Get or create the module-level StructuredLogger.

    Args:
        verbose: Enable console output (controlled by RunnerConfig.debug)
        survey_id: Current survey ID (empty for session-level logs)
        provider: Current provider name
    """
    global _module_logger
    if _module_logger is None:
        _module_logger = StructuredLogger(verbose=verbose)
    _module_logger.configure(verbose=verbose, survey_id=survey_id, provider=provider)
    return _module_logger


def reset_logger():
    """Reset module logger (for testing)."""
    global _module_logger
    _module_logger = None


# ── StructuredLogger ────────────────────────────────────

class StructuredLogger:
    """Structured JSONL logger with optional console output.

    Writes all events to JSONL files (append-only). Optionally prints
    formatted messages to console in debug mode.

    Usage:
        logger = get_logger(verbose=True, survey_id="abc123", provider="qualtrics")
        logger.info("Survey started")
        logger.iteration(iteration=1, elements=12, provider="qualtrics")
        logger.balance(before=1.50, after=2.00, earned=0.50)
        logger.error("Survey stuck", context="nemo_loop")
        logger.survey_end(status="completed", earned=0.50, duration_s=45.2)
    """

    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.survey_id = ""
        self.provider = ""
        self._iteration_count = 0

    def configure(self, verbose: Optional[bool] = None,
                  survey_id: str = "", provider: str = ""):
        """Reconfigure logger for current survey context."""
        if verbose is not None:
            self.verbose = verbose
        self.survey_id = survey_id
        self.provider = provider
        self._iteration_count = 0

    def _jsonl(self, tag: str, event_type: str, data: Dict[str, Any]):
        """Write structured JSONL entry + optional console output."""
        _ensure_logs()
        entry = {
            "ts": datetime.now().isoformat(),
            "unix_ts": time.time(),
            "type": event_type,
            "tag": tag,
            "survey_id": self.survey_id,
            "provider": self.provider,
            **data,
        }
        fp = _daily_file("iterations")
        with open(fp, "a") as f:
            f.write(json.dumps(entry) + "\n")

    def _console(self, tag: str, msg: str, color: str = ""):
        """Print to console if verbose enabled."""
        if self.verbose:
            c = color
            r = _Colors.RESET if color else ""
            print(f"{c}[{tag}]{r} {msg}", flush=True)

    # ── Public API ─────────────────────────────────────────

    def info(self, msg: str, **kwargs):
        """Log info event."""
        self._jsonl("INFO", "info", {"message": msg, **kwargs})
        self._console("INFO", msg)

    def warn(self, msg: str, **kwargs):
        """Log warning event."""
        self._jsonl("WARN", "warn", {"message": msg, **kwargs})
        self._console("WARN", msg, _Colors.YELLOW)

    def error(self, msg: str, context: str = "", **kwargs):
        """Log error event."""
        self._jsonl("ERROR", "error", {"message": msg, "context": context, **kwargs})
        self._console("ERROR", msg, _Colors.RED)

    def iteration(self, iteration: int, elements: int, actions: int = 0,
                  dom_hash: str = "", provider: str = ""):
        """Log NEMO loop iteration."""
        self._iteration_count = iteration
        self._jsonl("ITER", "iteration", {
            "iteration": iteration,
            "elements": elements,
            "actions_executed": actions,
            "dom_hash": dom_hash,
            "provider": provider or self.provider,
        })
        prov = provider or self.provider
        self._console("ITER", f"iter {iteration} | {prov} | {elements} el | {actions} actions")

    def survey_start(self, survey_id: str, provider: str, url: str = "",
                     balance_before: float = 0.0):
        """Log survey run start."""
        self.survey_id = survey_id
        self.provider = provider
        self._iteration_count = 0
        self._jsonl("RUN", "survey_start", {
            "survey_id": survey_id,
            "provider": provider,
            "url": url[:80],
            "balance_before": balance_before,
        })
        self._console("RUN", f"{survey_id} → {provider} ({url[:60]})",
                      _Colors.BOLD + _Colors.CYAN)

    def survey_end(self, status: str, earned: float = 0.0,
                   duration_s: float = 0.0, error: str = ""):
        """Log survey run end."""
        self._jsonl("RESULT", "survey_end", {
            "status": status,
            "earned_eur": earned,
            "duration_s": round(duration_s, 1),
            "error": error,
            "iterations": self._iteration_count,
        })
        if status == "completed":
            self._console("RESULT", f"{status} +{earned}€ ({self.provider}, "
                             f"{self._iteration_count} iter, {duration_s:.0f}s)",
                          _Colors.GREEN + _Colors.BOLD)
        elif status == "screen_out":
            self._console("RESULT", f"{status} | no payout ({self.provider})",
                          _Colors.YELLOW)
        else:
            color = _Colors.RED if status == "error" else _Colors.YELLOW
            err_msg = f" | {error[:40]}" if error else ""
            self._console("RESULT", f"{status}{err_msg}", color)

    def prequal(self, survey_id: str, question: str = "",
                answered: bool = True, result_url: str = ""):
        """Log pre-qualifier handling."""
        self._jsonl("PREQ", "prequal", {
            "survey_id": survey_id,
            "question_preview": question[:60],
            "answered": answered,
            "result_url": result_url[:80],
        })
        if answered:
            self._console("PREQ", f"answered → {result_url[:60]}" if result_url else "answered",
                          _Colors.BLUE)
        else:
            self._console("PREQ", "failed → skipping", _Colors.YELLOW)

    def balance(self, before: float, after: float, earned: float = 0.0):
        """Log balance change."""
        self._jsonl("BALANCE", "balance", {
            "balance_before": before,
            "balance_after": after,
            "earned": earned,
        })
        if earned > 0:
            self._console("BALANCE", f"Before: {before:.2f}€ | After: {after:.2f}€ | "
                             f"Earned: +{earned:.2f}€", _Colors.GREEN)
        else:
            self._console("BALANCE", f"Before: {before:.2f}€ | After: {after:.2f}€ | "
                             f"Earned: {earned:.2f}€")

    def loop_summary(self, attempted: int, completed: int, total_earned: float,
                     failed: int = 0, screen_out: int = 0):
        """Log run_loop summary."""
        self._jsonl("LOOP", "loop_summary", {
            "attempted": attempted,
            "completed": completed,
            "failed": failed,
            "screen_out": screen_out,
            "total_earned": total_earned,
        })
        self._console("LOOP", f"{completed}/{attempted} surveys | "
                         f"+{total_earned:.2f}€ earned | {failed} failed | {screen_out} screen-out",
                      _Colors.BOLD)

    def cleanup(self, tabs_before: int, tabs_after: int, zombie_tabs: int = 0):
        """Log tab cleanup."""
        self._jsonl("CLEANUP", "cleanup", {
            "tabs_before": tabs_before,
            "tabs_after": tabs_after,
            "zombie_tabs": zombie_tabs,
        })
        self._console("CLEANUP", f"Closed {tabs_before - tabs_after} zombie tabs")

    def completion(self, tab_url: str = "", detected: bool = True):
        """Log completion detection."""
        self._jsonl("COMPLETION", "completion", {
            "tab_url": tab_url[:80],
            "detected": detected,
        })
        if detected:
            self._console("COMPLETION", f"Detected on tab {tab_url[:60]}",
                          _Colors.GREEN)

    def rate(self, success: bool = True):
        """Log survey rating attempt."""
        self._jsonl("RATE", "rate", {"success": success})
        if success:
            self._console("RATE", "Rating clicked (+0.01€ bonus)", _Colors.GREEN)
        else:
            self._console("RATE", "Rating failed", _Colors.YELLOW)

    def cash_out(self, triggered: bool = True, balance: float = 0.0):
        """Log cash-out trigger."""
        self._jsonl("CASH", "cash_out", {
            "triggered": triggered,
            "balance": balance,
        })
        if triggered:
            self._console("CASH", f"Auszahlung clicked (balance: {balance:.2f}€)",
                          _Colors.GREEN)
        else:
            self._console("CASH", "Trigger failed", _Colors.YELLOW)

    def tab_switch(self, tab_id: str, reason: str = ""):
        """Log tab switch/new tab detection."""
        self._jsonl("TAB", "tab_switch", {
            "tab_id": tab_id[:8],
            "reason": reason,
        })
        self._console("TAB", f"New tab {tab_id[:8]} ({reason})", _Colors.BLUE)