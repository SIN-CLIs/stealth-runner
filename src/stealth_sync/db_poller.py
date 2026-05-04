import asyncio
import sqlite3
import time
from pathlib import Path
from typing import Optional, List, Dict, Any
import structlog

logger = structlog.get_logger(__name__)


class OpenCodeDBPoller:

    def __init__(self, db_path: Optional[str] = None):
        """Initialize the database poller with the OpenCode DB path.
        
        Args:
            db_path: Path to opencode.db (default: ~/.local/share/opencode/opencode.db)
        """
        # Expand user path for default OpenCode DB location
        self.db_path = Path(db_path or "~/.local/share/opencode/opencode.db").expanduser()
        # Track last poll time for incremental fetching
        self.last_check: Optional[float] = None
        logger.info("Initialized DB poller", db_path=str(self.db_path))

    def _get_connection(self) -> sqlite3.Connection:
        """Create a new SQLite connection with Row factory.
        
        Returns a new connection to the OpenCode DB. Each call creates
        a fresh connection since SQLite connections are not thread-safe.
        
        Returns:
            SQLite connection with row_factory set to sqlite3.Row
            
        Raises:
            FileNotFoundError: If the database file doesn't exist
        """
        if not self.db_path.exists():
            raise FileNotFoundError(f"OpenCode DB not found: {self.db_path}")
        conn = sqlite3.connect(str(self.db_path))
        # Use Row factory for dict-like access to columns
        conn.row_factory = sqlite3.Row
        return conn

    def get_new_sessions(self) -> List[Dict[str, Any]]:
        """Fetch sessions created since the last poll.
        
        If last_check is None (first poll), returns the 10 most recent sessions.
        Otherwise, returns sessions created after last_check timestamp.
        
        The timestamp format in OpenCode DB is milliseconds since epoch.
        All timestamps in the DB are stored as INTEGER in milliseconds.
        
        Returns:
            List of session dictionaries with all session table columns
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            if self.last_check:
                # Incremental fetch: only new sessions since last check
                cursor.execute(
                    "SELECT * FROM sessions WHERE created_at > ? ORDER BY created_at",
                    (self.last_check,),
                )
            else:
                # First run: get 10 most recent sessions
                cursor.execute("SELECT * FROM sessions ORDER BY created_at DESC LIMIT 10")
            rows = cursor.fetchall()
            # Update last_check to current time for next poll
            self.last_check = time.time() * 1000  # Convert to milliseconds
            return [dict(row) for row in rows]
        finally:
            # Always close connection to prevent locks
            conn.close()

    def get_session_messages(self, session_id: str) -> List[Dict[str, Any]]:
        """Get all messages for a specific session.
        
        Retrieves all messages belonging to the given session, ordered
        by creation time. Each message includes the JSON data field
        which contains role, content, model info, tokens, etc.
        
        Args:
            session_id: The OpenCode session ID (e.g., ses_XYZ)
            
        Returns:
            List of message dictionaries with all message table columns
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            # Fetch all messages for this session, oldest first
            cursor.execute(
                "SELECT * FROM messages WHERE session_id = ? ORDER BY timestamp",
                (session_id,),
            )
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def get_session_status(self, session_id: str) -> Optional[str]:
        """Get current status of a session.
        
        Queries the session table to get the current status field.
        Status values include: 'active', 'idle', 'completed', etc.
        
        Args:
            session_id: The OpenCode session ID
            
        Returns:
            Status string if session exists, None otherwise
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT status FROM sessions WHERE id = ?", (session_id,)
            )
            row = cursor.fetchone()
            return row["status"] if row else None
        finally:
            conn.close()
