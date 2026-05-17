"""================================================================================
DLQ HEALTH — Operator-friendly aggregation over DLQ records (SR-248)
================================================================================

MODUL-KONZEPT (SR-248, follow-up auf SR-152)
--------------------------------------------

Der DLQ (`survey/reliability/dlq.py`, SR-152) speichert pro fehlgeschlagener
Survey-Session einen JSONL-Record mit error_class, attempt_count, status,
provider, ts. Bisher verfügbare Aggregation: nur `count_by_status()`. Für
einen Operator (`/doctor`-Command, Dashboard, Alerting) reicht das nicht:

    "Wie viele DLQ-Einträge sind älter als 24h und noch pending?"
    "Welche error_class dominiert?"
    "Welche provider produzieren die meisten Failures?"
    "p50/p95-Alter der pending-Backlog?"

Dieses Modul liefert **eine** pure-Python Aggregations-Funktion, die diese
Fragen aus einer Liste von DLQRecord (oder einer Live-DLQ-Instanz)
beantwortet — ohne neue Storage, ohne Dependencies, ohne Hot-Path-Impact.

KEINE NEUEN ABHÄNGIGKEITEN
--------------------------
- Liest nichts vom Filesystem direkt. Caller passt entweder eine
  DLQ-Instanz (lookup via `_read_all_records()`) oder eine bereits
  gefilterte `list[DLQRecord]` rein. Test-deterministisch ohne tmp_path.
- Keine I/O. Keine Webhooks. Keine print()s.
- Numerisch deterministisch: Quantile per Linear-Interpolation
  (NumPy-kompatibel, aber ohne NumPy-Dep).

PUBLIC API
----------
    DlqHealth          — frozen dataclass mit allen aggregierten Metriken
    aggregate_health   — pure function: list[DLQRecord], now → DlqHealth

USAGE PATTERN (typischer Operator-Endpoint)
-------------------------------------------

    >>> from survey.reliability.dlq import DLQ
    >>> from survey.observability.dlq_health import aggregate_health
    >>>
    >>> dlq = DLQ()
    >>> records = dlq.list_all(limit=10_000)
    >>> health = aggregate_health(records)
    >>> print(json.dumps(health.to_dict(), indent=2))
    {
      "total": 142,
      "by_status": {"pending": 12, "replayed": 118, "discarded": 12},
      "by_error_class": {"SelectorTimeout": 89, "BalanceCheckError": 31, ...},
      "by_provider": {"pollfish": 67, "cint": 42, ...},
      "pending": {
        "count": 12,
        "p50_age_seconds": 1834,
        "p95_age_seconds": 86412,
        "older_than_24h": 3,
        "newest_age_seconds": 47,
        "oldest_age_seconds": 432101
      },
      "attempt_buckets": {"1": 12, "2": 47, "3": 78, "4+": 5}
    }

    Operator-Triage:
      health.is_healthy(threshold_pending=20, threshold_oldest_h=48)
      → False, with .alarm_reasons listing what's wrong.

OBSERVABILITY-KONTRAKT
----------------------
- DlqHealth ist serializable (to_dict() liefert plain dict).
- Alle Felder sind JSON-safe (keine Path/datetime-Objekte).
- Felder dürfen ausschließlich erweitert werden (additive API). Bestehende
  Keys / Typen werden niemals geändert ohne Schema-Bump.

Module Status: NEW (SR-248, follow-up to SR-152)
================================================================================
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Iterable, Optional

from survey.reliability.dlq import DLQRecord


# ── DEFAULT THRESHOLDS ───────────────────────────────────────────────────────


_DEFAULT_PENDING_THRESHOLD: int = 20
"""Pending-backlog count above which is_healthy() flags an alarm."""

_DEFAULT_OLDEST_PENDING_HOURS: int = 48
"""If oldest pending record is older than this, is_healthy() flags."""


# ── DATACLASSES ──────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class PendingAgeStats:
    """Age-distribution statistics for the *pending* sub-set only.

    Ages are measured in seconds, against a caller-supplied `now`
    (defaults to `datetime.now(timezone.utc)`). Age can never be negative
    — records with parsable timestamps strictly in the future are clamped
    to 0 seconds so the histogram stays sane during clock skew.
    """

    count: int
    p50_age_seconds: int
    p95_age_seconds: int
    newest_age_seconds: int
    oldest_age_seconds: int
    older_than_24h: int

    def to_dict(self) -> dict[str, int]:
        return {
            "count": self.count,
            "p50_age_seconds": self.p50_age_seconds,
            "p95_age_seconds": self.p95_age_seconds,
            "newest_age_seconds": self.newest_age_seconds,
            "oldest_age_seconds": self.oldest_age_seconds,
            "older_than_24h": self.older_than_24h,
        }


@dataclass(frozen=True)
class DlqHealth:
    """Snapshot of DLQ health at one moment in time.

    Fields:
        total:            number of records in scope
        by_status:        counts per status string
        by_error_class:   counts per error_class
        by_provider:      counts per provider
        attempt_buckets:  '1', '2', '3', '4+' -> count
        pending:          PendingAgeStats over pending records only
        alarm_reasons:    free-form list of human-readable reasons why
                          is_healthy() returned False; empty if healthy
    """

    total: int
    by_status: dict[str, int]
    by_error_class: dict[str, int]
    by_provider: dict[str, int]
    attempt_buckets: dict[str, int]
    pending: PendingAgeStats
    alarm_reasons: list[str] = field(default_factory=list)

    def is_healthy(self) -> bool:
        """True iff alarm_reasons is empty.

        The list is computed at construction time by `aggregate_health`
        using the threshold kwargs. Re-evaluate by calling
        `aggregate_health(...)` again with new thresholds.
        """
        return len(self.alarm_reasons) == 0

    def to_dict(self) -> dict[str, object]:
        return {
            "total": self.total,
            "by_status": dict(self.by_status),
            "by_error_class": dict(self.by_error_class),
            "by_provider": dict(self.by_provider),
            "attempt_buckets": dict(self.attempt_buckets),
            "pending": self.pending.to_dict(),
            "alarm_reasons": list(self.alarm_reasons),
            "is_healthy": self.is_healthy(),
        }


# ── INTERNAL HELPERS ─────────────────────────────────────────────────────────


def _parse_iso_ts(ts: str) -> Optional[datetime]:
    """Parse the DLQ timestamp format. Returns None on parse failure.

    DLQRecord.ts is written as `datetime.now(timezone.utc).isoformat() + "Z"`
    in dlq.py (SR-152 + SR-187). Python's fromisoformat accepts the
    `+00:00` form natively but not the trailing `Z` until 3.11+; we
    strip a trailing `Z` defensively to support both shapes and any
    future format drift.
    """
    if not ts:
        return None
    candidate = ts
    if candidate.endswith("Z"):
        candidate = candidate[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(candidate)
    except (ValueError, TypeError):
        return None
    # Make the result tz-aware (assume UTC if missing) so callers
    # don't accidentally compare naive against aware.
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _quantile(sorted_values: list[int], q: float) -> int:
    """Linear-interpolation quantile, NumPy-compatible.

    Empty input → 0. q clamped to [0, 1]. Returns int (rounded).
    """
    if not sorted_values:
        return 0
    q = max(0.0, min(1.0, q))
    if len(sorted_values) == 1:
        return int(sorted_values[0])
    # Position in [0, n-1].
    pos = q * (len(sorted_values) - 1)
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return int(sorted_values[lo])
    frac = pos - lo
    return int(round(sorted_values[lo] + frac * (sorted_values[hi] - sorted_values[lo])))


def _attempt_bucket(n: int) -> str:
    """Bucket an attempt count into one of '1', '2', '3', '4+'."""
    if n <= 1:
        return "1"
    if n == 2:
        return "2"
    if n == 3:
        return "3"
    return "4+"


# ── PUBLIC ENTRY POINT ───────────────────────────────────────────────────────


def aggregate_health(
    records: Iterable[DLQRecord],
    *,
    now: Optional[datetime] = None,
    pending_threshold: int = _DEFAULT_PENDING_THRESHOLD,
    oldest_pending_hours: int = _DEFAULT_OLDEST_PENDING_HOURS,
) -> DlqHealth:
    """Aggregate a collection of DLQRecords into a DlqHealth snapshot.

    Pure function: identical inputs always produce identical outputs
    (when `now` is supplied). Safe to call from any thread.

    Args:
        records:                Any iterable of DLQRecord instances.
        now:                    Reference timestamp for age computation.
                                Default = datetime.now(timezone.utc).
                                Test-determinism via explicit injection.
        pending_threshold:      Pending-count above which is_healthy()
                                returns False with a 'pending_backlog'
                                alarm. Default 20.
        oldest_pending_hours:   If the oldest pending record is older
                                than this, is_healthy() returns False
                                with an 'oldest_pending' alarm. Default 48.

    Returns:
        DlqHealth with all aggregated counters + .alarm_reasons populated
        per the threshold checks.
    """
    record_list = list(records)
    now_dt = now if now is not None else datetime.now(timezone.utc)
    # Normalize to tz-aware UTC if caller passed a naive datetime.
    if now_dt.tzinfo is None:
        now_dt = now_dt.replace(tzinfo=timezone.utc)

    by_status: dict[str, int] = {}
    by_error_class: dict[str, int] = {}
    by_provider: dict[str, int] = {}
    attempt_buckets: dict[str, int] = {"1": 0, "2": 0, "3": 0, "4+": 0}

    pending_ages_s: list[int] = []
    older_than_24h = 0

    for r in record_list:
        # by_status
        by_status[r.status] = by_status.get(r.status, 0) + 1
        # by_error_class
        ec = r.error_class or "_unknown"
        by_error_class[ec] = by_error_class.get(ec, 0) + 1
        # by_provider
        prov = r.provider or "_unknown"
        by_provider[prov] = by_provider.get(prov, 0) + 1
        # attempt buckets
        bucket = _attempt_bucket(int(r.attempt_count))
        attempt_buckets[bucket] = attempt_buckets.get(bucket, 0) + 1

        # pending-only age stats
        if r.status == "pending":
            ts_dt = _parse_iso_ts(r.ts)
            if ts_dt is None:
                # Unparseable timestamp → contribute 0 age so the count
                # is still honest, but no skew on quantiles.
                pending_ages_s.append(0)
                continue
            age_s = int((now_dt - ts_dt).total_seconds())
            if age_s < 0:
                age_s = 0  # clock skew guard
            pending_ages_s.append(age_s)
            if age_s > 24 * 3600:
                older_than_24h += 1

    pending_ages_s.sort()
    pending_stats = PendingAgeStats(
        count=len(pending_ages_s),
        p50_age_seconds=_quantile(pending_ages_s, 0.50),
        p95_age_seconds=_quantile(pending_ages_s, 0.95),
        newest_age_seconds=pending_ages_s[0] if pending_ages_s else 0,
        oldest_age_seconds=pending_ages_s[-1] if pending_ages_s else 0,
        older_than_24h=older_than_24h,
    )

    # ── Alarm rules ──────────────────────────────────────────────────────────
    alarm_reasons: list[str] = []
    if pending_stats.count > pending_threshold:
        alarm_reasons.append(
            f"pending_backlog: {pending_stats.count} pending records "
            f"exceeds threshold {pending_threshold}"
        )
    oldest_threshold_s = oldest_pending_hours * 3600
    if pending_stats.oldest_age_seconds > oldest_threshold_s:
        alarm_reasons.append(
            f"oldest_pending: oldest pending record is "
            f"{pending_stats.oldest_age_seconds // 3600}h old "
            f"(threshold {oldest_pending_hours}h)"
        )

    return DlqHealth(
        total=len(record_list),
        by_status=by_status,
        by_error_class=by_error_class,
        by_provider=by_provider,
        attempt_buckets=attempt_buckets,
        pending=pending_stats,
        alarm_reasons=alarm_reasons,
    )


__all__ = [
    "DlqHealth",
    "PendingAgeStats",
    "aggregate_health",
]
