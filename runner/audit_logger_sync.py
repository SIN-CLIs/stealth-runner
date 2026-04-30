"""Crash-sicheres JSONL Audit-Log mit O_SYNC + fcntl."""
from __future__ import annotations
import fcntl, json, os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

class AuditLoggerSync:
    def __init__(self, path: Path = Path("audit.jsonl")) -> None:
        self.path = Path(path); self.path.parent.mkdir(parents=True, exist_ok=True)
        self.fd = os.open(str(self.path), os.O_WRONLY | os.O_CREATE | os.O_APPEND | os.O_SYNC, 0o600)

    def log(self, state: str, action: dict[str, Any] | None = None, meta: dict[str, Any] | None = None) -> None:
        entry = {"ts": datetime.now(timezone.utc).isoformat(), "state": state, "action": action or {}, "meta": meta or {}}
        line = json.dumps(entry, ensure_ascii=False) + "\n"
        fcntl.flock(self.fd, fcntl.LOCK_EX)
        try: os.write(self.fd, line.encode())
        finally: fcntl.flock(self.fd, fcntl.LOCK_UN)

    def close(self) -> None:
        if hasattr(self, "fd"): os.close(self.fd)
