import json, os, time, random
from datetime import datetime, timezone

class AuditLog:
    def __init__(self, path=None):
        self.path = path or f"/tmp/stealth_runner_{int(time.time())}.jsonl"
        self.entries = []

    def log(self, event, **kwargs):
        entry = {"timestamp": datetime.now(timezone.utc).isoformat(), "event": event}
        entry.update(kwargs)
        self.entries.append(entry)
        with open(self.path, "a") as f:
            f.write(json.dumps(entry) + "\n")

    def get_summary(self):
        return {"total_events": len(self.entries), "path": self.path}
