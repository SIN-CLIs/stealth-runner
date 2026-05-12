"""
Dead-Letter Queue (DLQ) — JSONL-based persistence for failed surveys.

SR-152: Production-grade DLQ for the survey daemon.

Features:
    - Append-only JSONL storage, daily-rotated
    - Optional webhook alerting (Slack/Discord compatible)
    - Status tracking: pending | replayed | discarded
"""
from __future__ import annotations

import json
import logging
import os
import urllib.request
import urllib.error
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

logger = logging.getLogger(__name__)

DEFAULT_DLQ_PATH = Path("~/.survey_agent/logs").expanduser()
WEBHOOK_TIMEOUT = 5  # seconds


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
    status: str = "pending"  # pending | replayed | discarded
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DLQRecord":
        """Create DLQRecord from dictionary."""
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


class DLQ:
    """
    Dead-Letter Queue for failed surveys.
    
    Usage:
        dlq = DLQ()
        dlq_id = dlq.push(survey_id="abc", ...)
        pending = dlq.list_pending()
        dlq.mark_replayed(dlq_id)
    """
    
    def __init__(
        self,
        dlq_path: Path | str = DEFAULT_DLQ_PATH,
        webhook_url: str | None = None,
    ):
        """
        Initialize DLQ.
        
        Args:
            dlq_path: Directory for DLQ files
            webhook_url: Optional webhook URL for alerts (overrides env var)
        """
        self.dlq_path = Path(dlq_path).expanduser()
        self.dlq_path.mkdir(parents=True, exist_ok=True)
        
        # Webhook URL from param or env var
        self.webhook_url = webhook_url or os.environ.get("RELIABILITY_WEBHOOK_URL")
    
    def _get_current_file(self) -> Path:
        """Get current DLQ file path (daily rotation)."""
        date_str = datetime.now().strftime("%Y-%m-%d")
        return self.dlq_path / f"dlq-{date_str}.jsonl"
    
    def _fire_webhook(self, record: DLQRecord) -> None:
        """
        Fire webhook alert for DLQ push (fire-and-forget).
        
        Args:
            record: The DLQ record to alert about
        """
        if not self.webhook_url:
            return
        
        try:
            payload = {
                "text": (
                    f"SR-152 alert: DLQ push {record.survey_id} for {record.persona_id}: "
                    f"{record.error_class}: {record.error_message}"
                ),
                "details": record.to_dict(),
            }
            
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                self.webhook_url,
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            
            urllib.request.urlopen(req, timeout=WEBHOOK_TIMEOUT)
            logger.debug(f"Webhook fired for DLQ record {record.id}")
            
        except urllib.error.URLError as e:
            logger.warning(f"Webhook failed (timeout or network): {e}")
        except Exception as e:
            logger.warning(f"Webhook failed: {e}")
    
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
        Push a failed survey to the DLQ.
        
        Args:
            survey_id: Unique survey identifier
            persona_id: Persona used for the survey
            provider: Survey provider (e.g. "lucid", "toluna")
            url: Survey URL
            error: The exception that caused the failure
            attempt_count: Number of attempts made
            context: Additional context (last_question, page_html_b64, etc.)
            
        Returns:
            DLQ record ID
        """
        record = DLQRecord(
            id=f"dlq-{uuid4().hex[:12]}",
            ts=datetime.utcnow().isoformat() + "Z",
            survey_id=survey_id,
            persona_id=persona_id,
            provider=provider,
            url=url,
            error_class=type(error).__name__,
            error_message=str(error)[:500],  # Truncate long messages
            attempt_count=attempt_count,
            context=context or {},
            status="pending",
        )
        
        # Write to JSONL file
        dlq_file = self._get_current_file()
        with open(dlq_file, "a") as f:
            f.write(json.dumps(record.to_dict()) + "\n")
        
        logger.info(f"Pushed to DLQ: {record.id} ({record.error_class})")
        
        # Fire webhook (non-blocking, fire-and-forget)
        self._fire_webhook(record)
        
        return record.id
    
    def _read_all_files(self) -> list[Path]:
        """Get all DLQ files sorted by date (newest first)."""
        files = list(self.dlq_path.glob("dlq-*.jsonl"))
        files.sort(reverse=True)
        return files
    
    def _read_all_records(self) -> list[DLQRecord]:
        """Read all records from all DLQ files."""
        records = []
        for file_path in self._read_all_files():
            try:
                with open(file_path) as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            data = json.loads(line)
                            records.append(DLQRecord.from_dict(data))
            except Exception as e:
                logger.warning(f"Error reading DLQ file {file_path}: {e}")
        return records
    
    def list_pending(self, limit: int = 100) -> list[DLQRecord]:
        """
        List pending DLQ records.
        
        Args:
            limit: Maximum number of records to return
            
        Returns:
            List of pending DLQ records
        """
        records = self._read_all_records()
        pending = [r for r in records if r.status == "pending"]
        return pending[:limit]
    
    def list_all(
        self,
        status: str | None = None,
        limit: int = 100,
    ) -> list[DLQRecord]:
        """
        List all DLQ records, optionally filtered by status.
        
        Args:
            status: Filter by status (pending, replayed, discarded)
            limit: Maximum number of records to return
            
        Returns:
            List of DLQ records
        """
        records = self._read_all_records()
        if status:
            records = [r for r in records if r.status == status]
        return records[:limit]
    
    def get(self, dlq_id: str) -> DLQRecord | None:
        """
        Get a specific DLQ record by ID.
        
        Args:
            dlq_id: DLQ record ID
            
        Returns:
            DLQ record or None if not found
        """
        records = self._read_all_records()
        for record in records:
            if record.id == dlq_id:
                return record
        return None
    
    def _update_status(self, dlq_id: str, new_status: str) -> bool:
        """
        Update status of a DLQ record.
        
        Args:
            dlq_id: DLQ record ID
            new_status: New status value
            
        Returns:
            True if updated, False if not found
        """
        updated = False
        
        for file_path in self._read_all_files():
            lines = []
            modified = False
            
            try:
                with open(file_path) as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        data = json.loads(line)
                        if data.get("id") == dlq_id:
                            data["status"] = new_status
                            modified = True
                            updated = True
                        lines.append(json.dumps(data))
                
                if modified:
                    with open(file_path, "w") as f:
                        f.write("\n".join(lines) + "\n")
                    break
                    
            except Exception as e:
                logger.warning(f"Error updating DLQ file {file_path}: {e}")
        
        return updated
    
    def mark_replayed(self, dlq_id: str) -> bool:
        """
        Mark a DLQ record as replayed (successfully retried).
        
        Args:
            dlq_id: DLQ record ID
            
        Returns:
            True if updated, False if not found
        """
        success = self._update_status(dlq_id, "replayed")
        if success:
            logger.info(f"Marked DLQ record as replayed: {dlq_id}")
        return success
    
    def mark_discarded(self, dlq_id: str) -> bool:
        """
        Mark a DLQ record as discarded (manually dismissed).
        
        Args:
            dlq_id: DLQ record ID
            
        Returns:
            True if updated, False if not found
        """
        success = self._update_status(dlq_id, "discarded")
        if success:
            logger.info(f"Marked DLQ record as discarded: {dlq_id}")
        return success
    
    def count_by_status(self) -> dict[str, int]:
        """
        Count records by status.
        
        Returns:
            Dictionary of status -> count
        """
        records = self._read_all_records()
        counts: dict[str, int] = {"pending": 0, "replayed": 0, "discarded": 0}
        for record in records:
            counts[record.status] = counts.get(record.status, 0) + 1
        return counts
