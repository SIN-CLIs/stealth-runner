"""Thread-sichere Survey-Queue (SQLite + FileLock)."""
from __future__ import annotations
import sqlite3, uuid
from datetime import datetime, timezone
from filelock import FileLock

class SurveyQueue:
    def __init__(self, db_path: str = "surveys.db") -> None:
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("CREATE TABLE IF NOT EXISTS tasks (id TEXT PRIMARY KEY, url TEXT NOT NULL, status TEXT DEFAULT 'pending', pid INTEGER, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
        self.conn.commit()
        self.lock = FileLock(f"{db_path}.lock")

    def enqueue(self, url: str) -> str:
        tid = uuid.uuid4().hex[:16]
        with self.lock: self.conn.execute("INSERT INTO tasks (id, url) VALUES (?,?)", (tid, url)); self.conn.commit()
        return tid

    def claim_task(self, pid: int) -> dict | None:
        with self.lock:
            cur = self.conn.execute("UPDATE tasks SET status='running', pid=?, updated_at=? WHERE status='pending' RETURNING id, url", (pid, datetime.now(timezone.utc).isoformat()))
            row = cur.fetchone(); self.conn.commit()
        return {"id": row["id"], "url": row["url"]} if row else None

    def mark_done(self, task_id: str) -> None:
        with self.lock: self.conn.execute("UPDATE tasks SET status='done', updated_at=? WHERE id=?", (datetime.now(timezone.utc).isoformat(), task_id)); self.conn.commit()

    def mark_failed(self, task_id: str, error: str) -> None:
        with self.lock: self.conn.execute("UPDATE tasks SET status='failed', updated_at=? WHERE id=?", (f"{datetime.now(timezone.utc).isoformat()} error={error}", task_id)); self.conn.commit()
