"""================================================================================
WIREUPS — Integration helpers that connect Welle-3 primitives to callers (SR-258)
================================================================================

Each function in this module is a standalone helper that a single call-site
imports and invokes. They exist so that the wireup-PR is a 1-2 line edit per
call-site rather than a 30-line inline block.

All functions are best-effort: a crash in any wireup must NEVER break the
calling path. They catch all exceptions internally and log/skip.

Module Status: NEW (SR-258, wireup batch)
================================================================================
"""

from __future__ import annotations

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)


# ── 1. TokenBucket-guarded DLQ replay ───────────────────────────────────────

_dlq_replay_bucket: Optional["TokenBucket"] = None


def get_dlq_replay_bucket() -> "TokenBucket":
    """Lazy-init a module-level TokenBucket for DLQ replay throttling.

    Default: 5 replays per minute with burst-5. Override via env:
        DLQ_REPLAY_RATE=5       (tokens per minute)
        DLQ_REPLAY_BURST=5      (max burst)
    """
    global _dlq_replay_bucket
    if _dlq_replay_bucket is None:
        from survey.reliability.rate_limit import TokenBucket

        rate_per_min = int(os.environ.get("DLQ_REPLAY_RATE", "5"))
        burst = int(os.environ.get("DLQ_REPLAY_BURST", "5"))
        _dlq_replay_bucket = TokenBucket(
            capacity=burst,
            refill_rate=rate_per_min / 60,
            name="dlq_replay",
        )
    return _dlq_replay_bucket


def replay_pending_with_budget(
    max_items: int = 20,
    callback=None,
) -> dict:
    """Replay pending DLQ items, throttled by the module-level TokenBucket.

    Args:
        max_items:  Max items to attempt this batch.
        callback:   Optional (DLQRecord) -> bool function that performs
                    the actual replay. Returns True on success. If None,
                    items are only marked_replayed (dry-run).

    Returns:
        {"attempted": int, "replayed": int, "rate_limited": int, "errors": int}
    """
    try:
        from survey.reliability.dlq import DLQ

        dlq = DLQ()
        bucket = get_dlq_replay_bucket()
        pending = dlq.list_pending(limit=max_items)

        stats = {"attempted": 0, "replayed": 0, "rate_limited": 0, "errors": 0}

        for record in pending:
            if not bucket.try_acquire():
                stats["rate_limited"] += 1
                continue
            stats["attempted"] += 1
            try:
                if callback is not None:
                    success = callback(record)
                else:
                    success = True  # dry-run
                if success:
                    dlq.mark_replayed(record.id)
                    stats["replayed"] += 1
            except Exception as exc:
                logger.debug("replay_pending_with_budget: %s failed: %s", record.id, exc)
                stats["errors"] += 1

        return stats
    except Exception as exc:
        logger.warning("replay_pending_with_budget: fatal: %s", exc)
        return {"attempted": 0, "replayed": 0, "rate_limited": 0, "errors": 1}


# ── 2. sweep_expired on daemon startup ──────────────────────────────────────


def sweep_expired_personas() -> int:
    """Run persona-quarantine TTL sweep. Returns count of swept entries.

    Best-effort — never raises. Intended to be called once at daemon
    startup and optionally on a periodic timer.
    """
    try:
        from survey.reliability.personas_quarantine import sweep_expired

        swept = sweep_expired()
        if swept:
            logger.info("sweep_expired_personas: released %d TTL-expired entries", len(swept))
        return len(swept)
    except Exception as exc:
        logger.warning("sweep_expired_personas: %s", exc)
        return 0


# ── 3. dlq_health for health endpoint ───────────────────────────────────────


def get_dlq_health_snapshot() -> dict:
    """Compute DLQ health for inclusion in /health JSON response.

    Returns a plain dict (JSON-safe). Never raises.
    """
    try:
        from survey.observability.dlq_health import aggregate_health
        from survey.reliability.dlq import DLQ

        dlq = DLQ()
        records = dlq.list_all(limit=10_000)
        health = aggregate_health(records)
        return health.to_dict()
    except Exception as exc:
        logger.warning("get_dlq_health_snapshot: %s", exc)
        return {"error": str(exc)}


# ── 4. full_stability pre-click gate ────────────────────────────────────────


async def wait_for_full_stability_safe(
    hasher,
    tracker,
    provider: Optional[str] = None,
) -> Optional[dict]:
    """Best-effort full_stability gate. Returns metric_dict on success,
    None on any failure (so caller proceeds without blocking).

    Args:
        hasher:   async () -> str, the subtree-hash callable
        tracker:  attached CdpNetworkTracker instance
        provider: provider name for tuning lookup
    """
    try:
        from survey.reliability.full_stability import wait_for_full_stability

        report = await wait_for_full_stability(
            hasher=hasher,
            tracker=tracker,
            provider=provider,
        )
        return report.metric_dict()
    except Exception as exc:
        logger.debug("wait_for_full_stability_safe: %s", exc)
        return None


__all__ = [
    "get_dlq_health_snapshot",
    "get_dlq_replay_bucket",
    "replay_pending_with_budget",
    "sweep_expired_personas",
    "wait_for_full_stability_safe",
]
