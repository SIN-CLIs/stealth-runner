"""
Dead-Letter Queue v2 — fcntl locking, async webhook, idempotency claims (SR-157).

Improvements over SR-152:
    - fcntl.flock for atomic concurrent writes
    - Async webhook via loop.run_in_executor (non-blocking event loop)
    - Webhook delivery retry with exponential backoff
    - Claim mechanism for distributed replay safety
    - Idempotency keys to prevent double-replay
"""

from __future__ import annotations

import asyncio
import contextlib
import errno
import json
import logging
import os
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

logger = logging.getLogger(__name__)

# Optional fcntl (POSIX only). On Windows we degrade gracefully.
try:
    import fcntl

    HAS_FCNTL = True
except ImportError:
    HAS_FCNTL = False

DEFAULT_DLQ_PATH = Path("~/.survey_agent/logs").expanduser()
WEBHOOK_TIMEOUT = 5.0
WEBHOOK_MAX_RETRIES = 3
CLAIM_TTL_SECONDS = 300  # 5 minutes


# =============================================================================
# File locking helper
# =============================================================================


@contextlib.contextmanager
def file_lock(path: Path, exclusive: bool = True):
    """
    Cross-platform-ish file lock via fcntl.flock (POSIX).

    On Windows (no fcntl), falls back to lockfile sentinels.
    """
    lock_path = path.with_suffix(path.suffix + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)

    if HAS_FCNTL:
        lock_file = open(lock_path, "w")
        try:
            fcntl.flock(
                lock_file.fileno(),
                fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH,
            )
            yield
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
            lock_file.close()
    else:
        # Windows / no-fcntl: spin on exclusive lockfile creation
        deadline = time.monotonic() + 10.0
        while True:
            try:
                fd = os.open(
                    str(lock_path),
                    os.O_CREAT | os.O_EXCL | os.O_RDWR,
                )
                break
            except OSError as e:
                if e.errno != errno.EEXIST:
                    raise
                if time.monotonic() >= deadline:
                    raise TimeoutError(f"Could not acquire lock on {lock_path}")
                time.sleep(0.05)
        try:
            yield
        finally:
            os.close(fd)
            try:
                lock_path.unlink()
            except FileNotFoundError:
                pass


# =============================================================================
# Records
# =============================================================================


@dataclass
class DLQRecord:
    """A single DLQ entry."""

    id: str
    ts: str
    survey_id: str
    persona_id: str
    provider: str
    url: str
    error_class: str
    error_message: str
    attempt_count: int
    context: dict[str, Any]
    status: str = "pending"  # pending | claimed | replayed | discarded | escalated
    # Idempotency / claim metadata
    idempotency_key: str = ""
    claim_owner: str = ""
    claim_expires_at: float = 0.0
    replay_attempts: int = 0
    escalated: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DLQRecord":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


# =============================================================================
# Webhook (async + retry)
# =============================================================================


async def _deliver_webhook(
    webhook_url: str,
    payload: dict[str, Any],
    timeout: float = WEBHOOK_TIMEOUT,
    max_retries: int = WEBHOOK_MAX_RETRIES,
) -> bool:
    """
    Deliver webhook asynchronously with exponential backoff.

    Uses run_in_executor to avoid blocking the event loop with urllib.
    """
    loop = asyncio.get_event_loop()
    data = json.dumps(payload).encode("utf-8")

    def _blocking_post() -> int:
        req = urllib.request.Request(
            webhook_url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status

    for attempt in range(max_retries):
        try:
            status = await loop.run_in_executor(None, _blocking_post)
            if 200 <= status < 300:
                logger.debug(f"Webhook delivered (attempt {attempt + 1})")
                return True
            logger.warning(f"Webhook returned status {status}")
        except urllib.error.URLError as e:
            logger.warning(f"Webhook attempt {attempt + 1} failed: {e}")
        except Exception as e:
            logger.warning(f"Webhook attempt {attempt + 1} error: {e}")

        # Backoff before retry (full jitter)
        if attempt + 1 < max_retries:
            import random

            delay = random.uniform(0, min(2**attempt, 8))
            await asyncio.sleep(delay)

    logger.error(f"Webhook delivery failed after {max_retries} attempts")
    return False


def _fire_webhook_background(webhook_url: str, payload: dict[str, Any]) -> None:
    """
    Fire-and-forget webhook from sync context.

    Schedules delivery on the running loop if present, else runs a one-shot loop.
    """
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_deliver_webhook(webhook_url, payload))
    except RuntimeError:
        # No running loop — spawn a thread with its own loop
        import threading

        def _runner():
            asyncio.run(_deliver_webhook(webhook_url, payload))

        threading.Thread(target=_runner, daemon=True).start()


# =============================================================================
# DLQ
# =============================================================================


class DLQ:
    """
    Dead-Letter Queue with file-locking and idempotency.

    Storage: JSONL files, daily-rotated, fcntl-locked.
    For higher concurrency, see SR-158 SQLite backend.
    """

    def __init__(
        self,
        dlq_path: Path | str = DEFAULT_DLQ_PATH,
        webhook_url: str | None = None,
        max_replay_attempts: int = 3,
        worker_id: str | None = None,
    ):
        self.dlq_path = Path(dlq_path).expanduser()
        self.dlq_path.mkdir(parents=True, exist_ok=True)
        self.webhook_url = webhook_url or os.environ.get("RELIABILITY_WEBHOOK_URL")
        self.max_replay_attempts = max_replay_attempts
        self.worker_id = worker_id or f"worker-{uuid4().hex[:8]}"

    def _current_file(self) -> Path:
        date_str = datetime.now().strftime("%Y-%m-%d")
        return self.dlq_path / f"dlq-{date_str}.jsonl"

    def _all_files(self) -> list[Path]:
        return sorted(self.dlq_path.glob("dlq-*.jsonl"), reverse=True)

    def _idempotency_key(
        self,
        survey_id: str,
        persona_id: str,
        url: str,
    ) -> str:
        """Stable key for deduplication."""
        import hashlib

        h = hashlib.sha256(f"{survey_id}|{persona_id}|{url}".encode()).hexdigest()
        return f"idmp-{h[:16]}"

    def push(
        self,
        survey_id: str,
        persona_id: str,
        provider: str,
        url: str,
        error: Exception,
        attempt_count: int,
        context: dict[str, Any] | None = None,
    ) -> str:
        """
        Push a failed survey to the DLQ (idempotent).

        If an identical (survey_id, persona_id, url) already exists as pending,
        returns its ID instead of creating a duplicate.
        """
        idmp_key = self._idempotency_key(survey_id, persona_id, url)

        # Dedup check
        existing = self._find_by_idempotency(idmp_key)
        if existing and existing.status == "pending":
            logger.info(f"DLQ idempotent push, returning existing {existing.id}")
            return existing.id

        record = DLQRecord(
            id=f"dlq-{uuid4().hex[:12]}",
            ts=datetime.utcnow().isoformat() + "Z",
            survey_id=survey_id,
            persona_id=persona_id,
            provider=provider,
            url=url,
            error_class=type(error).__name__,
            error_message=str(error)[:500],
            attempt_count=attempt_count,
            context=context or {},
            status="pending",
            idempotency_key=idmp_key,
        )

        dlq_file = self._current_file()
        with file_lock(dlq_file):
            with open(dlq_file, "a") as f:
                f.write(json.dumps(record.to_dict()) + "\n")

        logger.info(f"Pushed to DLQ: {record.id} ({record.error_class})")

        if self.webhook_url:
            _fire_webhook_background(
                self.webhook_url,
                {
                    "text": (
                        f"SR-157 alert: DLQ push {record.survey_id} "
                        f"for {record.persona_id}: {record.error_class}: {record.error_message}"
                    ),
                    "details": record.to_dict(),
                },
            )

        return record.id

    def _read_records(self) -> list[DLQRecord]:
        records: list[DLQRecord] = []
        for file_path in self._all_files():
            try:
                with file_lock(file_path, exclusive=False):
                    with open(file_path) as f:
                        for line in f:
                            line = line.strip()
                            if line:
                                records.append(DLQRecord.from_dict(json.loads(line)))
            except Exception as e:
                logger.warning(f"Error reading {file_path}: {e}")
        return records

    def _find_by_idempotency(self, idmp_key: str) -> DLQRecord | None:
        for record in self._read_records():
            if record.idempotency_key == idmp_key:
                return record
        return None

    def get(self, dlq_id: str) -> DLQRecord | None:
        for record in self._read_records():
            if record.id == dlq_id:
                return record
        return None

    def list_pending(self, limit: int = 100) -> list[DLQRecord]:
        records = self._read_records()
        # Skip records currently claimed by another worker (TTL valid)
        now = time.time()
        pending = [
            r
            for r in records
            if r.status == "pending" and (not r.claim_owner or r.claim_expires_at < now)
        ]
        return pending[:limit]

    def list_all(self, status: str | None = None, limit: int = 100) -> list[DLQRecord]:
        records = self._read_records()
        if status:
            records = [r for r in records if r.status == status]
        return records[:limit]

    def _update_record(
        self,
        dlq_id: str,
        updates: dict[str, Any],
        expected_status: str | None = None,
    ) -> bool:
        """
        Atomically update a record. Returns False if expected_status mismatch.

        TODO(SR-158): Replace with SQLite for O(1) updates.
        """
        updated = False

        for file_path in self._all_files():
            with file_lock(file_path):
                try:
                    with open(file_path) as f:
                        lines = f.readlines()
                except FileNotFoundError:
                    continue

                modified = False
                new_lines = []
                for line in lines:
                    line = line.strip()
                    if not line:
                        continue
                    data = json.loads(line)
                    if data.get("id") == dlq_id:
                        if expected_status and data.get("status") != expected_status:
                            return False
                        data.update(updates)
                        modified = True
                        updated = True
                    new_lines.append(json.dumps(data))

                if modified:
                    # Atomic rewrite via temp file + rename
                    tmp_path = file_path.with_suffix(file_path.suffix + ".tmp")
                    with open(tmp_path, "w") as f:
                        f.write("\n".join(new_lines) + "\n")
                    os.replace(tmp_path, file_path)
                    return True

        return updated

    def claim(self, dlq_id: str, ttl: int = CLAIM_TTL_SECONDS) -> bool:
        """
        Claim a DLQ record for exclusive replay.

        Returns True if claimed, False if already claimed by another worker
        (and claim still valid) or record not pending.
        """
        record = self.get(dlq_id)
        if not record:
            return False

        now = time.time()
        # Already claimed and not expired
        if (
            record.claim_owner
            and record.claim_owner != self.worker_id
            and record.claim_expires_at > now
        ):
            logger.info(
                f"DLQ {dlq_id} already claimed by {record.claim_owner} "
                f"(expires in {record.claim_expires_at - now:.0f}s)"
            )
            return False

        if record.status not in ("pending", "claimed"):
            return False

        return self._update_record(
            dlq_id,
            {
                "status": "claimed",
                "claim_owner": self.worker_id,
                "claim_expires_at": now + ttl,
            },
        )

    def release(self, dlq_id: str) -> bool:
        """Release a claim without marking replayed (e.g. on transient failure)."""
        record = self.get(dlq_id)
        if not record or record.claim_owner != self.worker_id:
            return False

        return self._update_record(
            dlq_id,
            {
                "status": "pending",
                "claim_owner": "",
                "claim_expires_at": 0.0,
            },
        )

    def mark_replayed(self, dlq_id: str) -> bool:
        """Mark replayed (release claim, increment counter)."""
        record = self.get(dlq_id)
        if not record:
            return False

        success = self._update_record(
            dlq_id,
            {
                "status": "replayed",
                "claim_owner": "",
                "claim_expires_at": 0.0,
                "replay_attempts": record.replay_attempts + 1,
            },
        )
        if success:
            logger.info(f"Marked DLQ replayed: {dlq_id}")
        return success

    def mark_failed_replay(self, dlq_id: str) -> bool:
        """
        Mark a replay as failed. After max_replay_attempts, escalate.
        """
        record = self.get(dlq_id)
        if not record:
            return False

        new_attempts = record.replay_attempts + 1
        if new_attempts >= self.max_replay_attempts:
            logger.warning(f"DLQ {dlq_id} exhausted {new_attempts} replay attempts — escalating")
            return self._update_record(
                dlq_id,
                {
                    "status": "escalated",
                    "claim_owner": "",
                    "claim_expires_at": 0.0,
                    "replay_attempts": new_attempts,
                    "escalated": True,
                },
            )
        return self._update_record(
            dlq_id,
            {
                "status": "pending",
                "claim_owner": "",
                "claim_expires_at": 0.0,
                "replay_attempts": new_attempts,
            },
        )

    def mark_discarded(self, dlq_id: str) -> bool:
        success = self._update_record(
            dlq_id,
            {"status": "discarded", "claim_owner": "", "claim_expires_at": 0.0},
        )
        if success:
            logger.info(f"Marked DLQ discarded: {dlq_id}")
        return success

    def count_by_status(self) -> dict[str, int]:
        counts: dict[str, int] = {
            "pending": 0,
            "claimed": 0,
            "replayed": 0,
            "discarded": 0,
            "escalated": 0,
        }
        for record in self._read_records():
            counts[record.status] = counts.get(record.status, 0) + 1
        return counts
