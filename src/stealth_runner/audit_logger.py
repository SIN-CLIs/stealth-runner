from __future__ import annotations
import os, json, fcntl, uuid
from pathlib import Path
from datetime import datetime, timezone
from typing import Any

class AuditLogger:
    def __init__(self, path: Path):
        self.path = path; self.fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_APPEND | os.O_SYNC, 0o600)
        self.session_id = uuid.uuid4().hex[:12]

    def log(self, state: str, action: dict[str, Any], meta: dict[str, Any] | None = None) -> None:
        entry = {"ts": datetime.now(timezone.utc).isoformat(), "session": self.session_id, "state": state, "action": action, "meta": meta or {}}
        line = json.dumps(entry, ensure_ascii=False) + "\n"
        fcntl.flock(self.fd, fcntl.LOCK_EX)
        try: os.write(self.fd, line.encode())
        finally: fcntl.flock(self.fd, fcntl.LOCK_UN)

    def close(self) -> None: os.close(self.fd)
