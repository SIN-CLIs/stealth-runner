"""AuditLog – Thread-safe JSONL trace mit Batched Writes."""
from __future__ import annotations
import json, threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

class AuditLog:
    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path or (Path.home() / ".stealth_runner" / "traces.jsonl"))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._buffer: list[dict[str, Any]] = []
        self._total_events = 0

    def log(self, event: str, **kwargs: Any) -> None:
        entry = {"timestamp": datetime.now(timezone.utc).isoformat(), "event": event, **kwargs}
        with self._lock:
            self._buffer.append(entry)
            self._total_events += 1
            if len(self._buffer) >= 10:
                self._flush_locked()

    def flush(self) -> None:
        with self._lock:
            self._flush_locked()

    def _flush_locked(self) -> None:
        if not self._buffer: return
        with open(self.path, "a") as f:
            for entry in self._buffer:
                f.write(json.dumps(entry, default=str) + "\n")
        self._buffer.clear()

    def get_summary(self) -> dict[str, Any]:
        return {"total_events": self._total_events, "path": str(self.path)}

    def close(self) -> None:
        self.flush()
