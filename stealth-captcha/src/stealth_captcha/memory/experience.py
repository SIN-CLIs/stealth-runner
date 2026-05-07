"""Episodic experience memory: caches successful trajectories per (host, captcha-type, delta_x).

WARUM: CAPTCHA-Engines lernen. Ein frischer Bezier-Pfad funktioniert
auf derselben Seite nicht immer wieder (zufällige Verzögerung, veränderte
Gap-Größe). Agent-S3 Pattern (CAPTCHA-X Research): erfolgreiche Trajektorien
werden gespeichert und mit frischem Noise wiederverwendet.
Nach 5 erfolgreichen Lösungen auf derselben Domain ist die Trajektorie
auf das spezifische Widget (Gap-Size, Sensitivität) kalibriert.

ARCHITEKTUR: Keyed by (host, captcha_type, delta_x). SQLite-Backend
mit JSON-Serialisierung. Trajektorien werden mit Gaussian-Noise
leicht variiert (Replay ≠ 1:1 Copy). TTL-basiertes Expiry für alte
Einträge. Thread-safe via sqlite3 WAL mode.

BANNED METHODS — NIEMALS VERWENDEN:
❌ playstealth launch
❌ webauto-nodriver — ABSOLUT BANNED
❌ cua-driver click (raw index)
❌ --remote-allow-origins=* (ohne Quotes)
❌ /tmp/heypiggy-bot (fixed profile)
❌ Hardcoded PIDs
❌ pkill -f "Google Chrome"
❌ killall Google Chrome
❌ skylight-cli click --element-index
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import aiosqlite

from stealth_captcha.config import MemorySettings
from stealth_captcha.telemetry import get_logger

log = get_logger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS trajectories (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    host        TEXT NOT NULL,
    captcha_type TEXT NOT NULL,
    delta_x     REAL NOT NULL,
    delta_y     REAL NOT NULL,
    duration_ms REAL NOT NULL,
    sample_count INTEGER NOT NULL,
    points_json TEXT NOT NULL,
    success     INTEGER NOT NULL DEFAULT 1,
    created_at  INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_traj_lookup
    ON trajectories(host, captcha_type, success, delta_x);
"""


@dataclass(slots=True, frozen=True)
class TrajectoryRecord:
    """A stored trajectory from a solved captcha.

    Attributes:
        host: The domain (e.g., "survey.example.com").
        captcha_type: "slide", "drag_drop", etc.
        delta_x: Horizontal gap in pixels.
        delta_y: Vertical gap in pixels.
        duration_ms: Total duration of the drag in ms.
        sample_count: Number of trajectory points.
        points: [(t_ms, x, y), ...] trajectory data.
        success: Whether this solve was successful.
        created_at: Unix timestamp.
    """

    host: str
    captcha_type: str
    delta_x: float
    delta_y: float
    duration_ms: float
    sample_count: int
    points: list[tuple[float, float, float]]
    success: bool = True
    created_at: int | None = None


@dataclass(slots=True)
class ExperienceMemory:
    """Episodic memory backed by SQLite (WAL mode for concurrent access).

    Usage:
        mem = ExperienceMemory(settings.memory)
        await mem.init()
        await mem.record(trajectory_record)
        similar = await mem.find_similar(host="example.com", ...)
    """

    settings: MemorySettings
    _db: aiosqlite.Connection | None = None

    @property
    def db_path(self) -> Path:
        return self.settings.db_path

    async def init(self) -> None:
        """Initialize the database and create tables if needed."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._db = await aiosqlite.connect(str(self.db_path))
        self._db.row_factory = aiosqlite.Row
        await self._db.execute("PRAGMA journal_mode=WAL;")
        await self._db.execute("PRAGMA synchronous=NORMAL;")
        await self._db.executescript(_SCHEMA)
        await self._db.commit()
        log.info("experience_memory_ready", path=str(self.db_path))

    async def record(self, record: TrajectoryRecord) -> None:
        """Store a trajectory in the experience database.

        Args:
            record: The trajectory to persist.
        """
        db = self._db
        if db is None:
            raise RuntimeError("ExperienceMemory not initialized — call init() first")

        now = record.created_at or int(time.time())
        await db.execute(
            "INSERT INTO trajectories "
            "(host, captcha_type, delta_x, delta_y, duration_ms, sample_count, "
            "points_json, success, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                record.host,
                record.captcha_type,
                record.delta_x,
                record.delta_y,
                record.duration_ms,
                record.sample_count,
                json.dumps(record.points),
                int(record.success),
                now,
            ),
        )
        # Prune old entries beyond max_entries
        await db.execute(
            "DELETE FROM trajectories WHERE id IN ("
            "  SELECT id FROM trajectories ORDER BY created_at DESC "
            "  LIMIT -1 OFFSET ?"
            ")",
            (self.settings.max_entries,),
        )
        await db.commit()
        log.info(
            "experience_recorded",
            host=record.host,
            dx=round(record.delta_x, 1),
            points=record.sample_count,
        )

    async def find_similar(
        self,
        host: str,
        captcha_type: str,
        delta_x: float,
        *,
        tolerance_px: float | None = None,
        limit: int = 16,
    ) -> list[TrajectoryRecord]:
        """Find successful trajectories with similar gap distance.

        Args:
            host: Domain to match.
            captcha_type: Type of captcha.
            delta_x: The gap distance to match against.
            tolerance_px: How close the gap must be (default: from settings).
            limit: Maximum number of results.

        Returns:
            List of matching TrajectoryRecord, newest first.
        """
        db = self._db
        if db is None:
            return []

        tol = tolerance_px if tolerance_px is not None else self.settings.similarity_threshold_px
        cursor = await db.execute(
            "SELECT * FROM trajectories WHERE host=? AND captcha_type=? "
            "AND success=1 AND ABS(delta_x - ?) <= ? "
            "ORDER BY created_at DESC LIMIT ?",
            (host, captcha_type, delta_x, tol, limit),
        )
        rows: list[Any] = await cursor.fetchall()
        return [
            TrajectoryRecord(
                host=r["host"],
                captcha_type=r["captcha_type"],
                delta_x=r["delta_x"],
                delta_y=r["delta_y"],
                duration_ms=r["duration_ms"],
                sample_count=r["sample_count"],
                points=json.loads(r["points_json"]),
                success=bool(r["success"]),
                created_at=r["created_at"],
            )
            for r in rows
        ]

    async def stats(self) -> dict[str, Any]:
        """Get memory statistics."""
        db = self._db
        if db is None:
            return {"status": "uninitialized"}
        cursor = await db.execute(
            "SELECT host, captcha_type, COUNT(*) as count, "
            "AVG(delta_x) as avg_dx "
            "FROM trajectories WHERE success=1 "
            "GROUP BY host, captcha_type ORDER BY count DESC"
        )
        rows = await cursor.fetchall()
        return {
            "status": "ready",
            "total_entries": sum(r["count"] for r in rows),
            "per_domain": [dict(r) for r in rows],
        }

    async def close(self) -> None:
        """Close the database connection."""
        if self._db:
            await self._db.close()
            self._db = None

    async def __aenter__(self) -> ExperienceMemory:
        await self.init()
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.close()

    @staticmethod
    def now() -> int:
        return int(time.time())
