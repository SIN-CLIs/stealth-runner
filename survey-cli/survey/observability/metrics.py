"""SurveyMetrics — in-memory counters + periodic JSONL persistence.

WARUM: Phase 5 von ULTIMATE-PLAN.md — "SurveyMetrics und Health Snapshot
einfuehren". Metriken muessen gemessen werden, nicht erraten.

ARCHITEKTUR:
  - SurveyMetrics Singleton: in-memory counters, persisted to JSONL
  - Zaehlt attempted/completed/screen_out/error/earned
  - Latenz-Tracking: NIM calls, batch execution, loop duration
  - Tagesweise JSONL in logs/metrics-{date}.jsonl

BANNED METHODS — NIEMALS VERWENDEN:
  ❌ playstealth launch
  ❌ webauto-nodriver — ABSOLUT BANNED
  ❌ Hardcoded PIDs
  ❌ pkill -f "Google Chrome"
  ❌ killall Google Chrome
"""

import json
import time
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Any, Dict, Optional

# ── Log Directory ──────────────────────────────────────

LOGS_DIR = Path(__file__).parent.parent.parent / "logs"


def _ensure_logs():
    LOGS_DIR.mkdir(parents=True, exist_ok=True)


def _daily_file(name: str) -> Path:
    date = datetime.now().strftime("%Y-%m-%d")
    return LOGS_DIR / f"{name}-{date}.jsonl"


# ── Singleton ────────────────────────────────────────────

class _SurveyMetrics:
    """Thread-safe in-memory metrics singleton with JSONL persistence."""

    def __init__(self):
        self._lock = Lock()
        self._counters: Dict[str, Any] = {
            "surveys_attempted": 0,
            "surveys_completed": 0,
            "surveys_screen_out": 0,
            "surveys_error": 0,
            "surveys_blocked": 0,
            "total_earned_eur": 0.0,
            "nim_calls": 0,
            "nim_errors": 0,
            "batch_calls": 0,
            "batch_errors": 0,
            "prequal_answered": 0,
            "prequal_failed": 0,
            "loops_completed": 0,
        }
        self._nim_latency_ms: list = []
        self._batch_latency_ms: list = []
        self._survey_durations_s: list = []
        self._session_start = time.time()

    def survey_attempted(self):
        with self._lock:
            self._counters["surveys_attempted"] += 1

    def survey_completed(self, earned: float = 0.0, duration_s: float = 0.0):
        with self._lock:
            self._counters["surveys_completed"] += 1
            if earned > 0:
                self._counters["total_earned_eur"] += earned
            self._survey_durations_s.append(duration_s)

    def survey_screen_out(self):
        with self._lock:
            self._counters["surveys_screen_out"] += 1

    def survey_error(self):
        with self._lock:
            self._counters["surveys_error"] += 1

    def survey_blocked(self):
        with self._lock:
            self._counters["surveys_blocked"] += 1

    def prequal_answered(self):
        with self._lock:
            self._counters["prequal_answered"] += 1

    def prequal_failed(self):
        with self._lock:
            self._counters["prequal_failed"] += 1

    def nim_call(self, latency_ms: float, error: bool = False):
        with self._lock:
            self._counters["nim_calls"] += 1
            if error:
                self._counters["nim_errors"] += 1
            self._nim_latency_ms.append(latency_ms)

    def batch_call(self, latency_ms: float, error: bool = False):
        with self._lock:
            self._counters["batch_calls"] += 1
            if error:
                self._counters["batch_errors"] += 1
            self._batch_latency_ms.append(latency_ms)

    def loop_completed(self):
        with self._lock:
            self._counters["loops_completed"] += 1

    def snapshot(self) -> Dict[str, Any]:
        """Return current metrics snapshot."""
        with self._lock:
            nims = self._nim_latency_ms
            batches = self._batch_latency_ms
            durations = self._survey_durations_s
            return {
                **self._counters,
                "nim_avg_latency_ms": (sum(nims) / len(nims)) if nims else 0,
                "nim_p95_latency_ms": sorted(nims)[int(len(nims) * 0.95)] if len(nims) > 1 else (nims[0] if nims else 0),
                "batch_avg_latency_ms": (sum(batches) / len(batches)) if batches else 0,
                "survey_avg_duration_s": (sum(durations) / len(durations)) if durations else 0,
                "session_duration_s": round(time.time() - self._session_start, 1),
            }

    def persist(self):
        """Write current snapshot to JSONL."""
        _ensure_logs()
        entry = {
            "ts": datetime.now().isoformat(),
            "unix_ts": time.time(),
            "type": "metrics_snapshot",
            **self.snapshot(),
        }
        fp = _daily_file("metrics")
        with open(fp, "a") as f:
            f.write(json.dumps(entry) + "\n")

    def reset(self):
        """Reset all counters (for testing)."""
        with self._lock:
            self._counters = {k: 0 if isinstance(v, float) else v
                              for k, v in self._counters.items()}
            self._nim_latency_ms.clear()
            self._batch_latency_ms.clear()
            self._survey_durations_s.clear()
            self._session_start = time.time()


# ── Public Singleton ──────────────────────────────────────

_metrics: Optional[_SurveyMetrics] = None


def SurveyMetrics() -> _SurveyMetrics:
    global _metrics
    if _metrics is None:
        _metrics = _SurveyMetrics()
    return _metrics


def reset_metrics():
    """Reset metrics singleton (for testing)."""
    global _metrics
    _metrics = None
