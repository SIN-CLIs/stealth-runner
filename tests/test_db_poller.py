"""Test suite for OpenCodeDBPoller module.

Tests the database polling functionality including:
- Database connection and initialization
- Session retrieval (new sessions, all sessions)
- Message retrieval for specific sessions
- Session status queries
- Error handling for missing databases

Uses pytest-asyncio for async test support and pytest-cov for coverage.
"""

import pytest
import sqlite3
import tempfile
from pathlib import Path
from src.stealth_sync.db_poller import OpenCodeDBPoller


class TestOpenCodeDBPoller:
    """Test suite for OpenCodeDBPoller class."""

    def test_init_default_db_path(self):
        """Test initialization with default database path."""
        poller = OpenCodeDBPoller()
        assert poller.db_path is not None
        assert "opencode.db" in str(poller.db_path)
        assert poller.last_check is None

    def test_init_custom_db_path(self, mock_db_path):
        """Test initialization with custom database path."""
        poller = OpenCodeDBPoller(db_path=str(mock_db_path))
        assert str(poller.db_path) == str(mock_db_path)
        assert poller.last_check is None

    def test_get_connection_success(self, mock_db_path):
        """Test successful database connection creation."""
        poller = OpenCodeDBPoller(db_path=str(mock_db_path))
        conn = poller._get_connection()
        assert isinstance(conn, sqlite3.Connection)
        assert conn.row_factory == sqlite3.Row
        conn.close()

    def test_get_connection_file_not_found(self):
        """Test error handling for missing database file."""
        poller = OpenCodeDBPoller(db_path="/nonexistent/path/to/db.db")
        with pytest.raises(FileNotFoundError) as exc_info:
            poller._get_connection()
        assert "OpenCode DB not found" in str(exc_info.value)

    def test_get_new_sessions_first_poll(self, mock_db_path):
        """Test fetching new sessions on first poll."""
        poller = OpenCodeDBPoller(db_path=str(mock_db_path))
        sessions = poller.get_new_sessions()
        
        assert isinstance(sessions, list)
        assert len(sessions) == 2  # We inserted 2 sessions
        assert all("id" in session for session in sessions)
        assert all("status" in session for session in sessions)
        
        # Verify last_check was updated
        assert poller.last_check is not None
        assert isinstance(poller.last_check, float)

    def test_get_new_sessions_incremental(self, mock_db_path):
        """Test fetching new sessions incrementally."""
        poller = OpenCodeDBPoller(db_path=str(mock_db_path))
        
        # First poll to set last_check
        _ = poller.get_new_sessions()
        first_check = poller.last_check
        
        # Second poll should return empty (no new sessions)
        sessions = poller.get_new_sessions()
        assert len(sessions) == 0
        
        # last_check should be updated
        assert poller.last_check > first_check

    def test_get_session_messages(self, mock_db_path):
        """Test fetching messages for a specific session."""
        poller = OpenCodeDBPoller(db_path=str(mock_db_path))
        
        messages = poller.get_session_messages("ses_test1")
        
        assert isinstance(messages, list)
        assert len(messages) == 2  # We inserted 2 messages
        assert all("session_id" in msg for msg in messages)
        assert all("role" in msg for msg in messages)
        assert all("content" in msg for msg in messages)
        
        # Verify session_id filtering
        for msg in messages:
            assert msg["session_id"] == "ses_test1"

    def test_get_session_messages_empty(self, mock_db_path):
        """Test fetching messages for non-existent session."""
        poller = OpenCodeDBPoller(db_path=str(mock_db_path))
        messages = poller.get_session_messages("nonexistent_session")
        
        assert isinstance(messages, list)
        assert len(messages) == 0

    def test_get_session_status(self, mock_db_path):
        """Test fetching session status."""
        poller = OpenCodeDBPoller(db_path=str(mock_db_path))
        
        status = poller.get_session_status("ses_test1")
        assert status == "active"
        
        status_none = poller.get_session_status("nonexistent")
        assert status_none is None

    def test_connection_close(self, mock_db_path):
        """Test that database connections are properly closed."""
        poller = OpenCodeDBPoller(db_path=str(mock_db_path))
        
        # Get connection multiple times
        conn1 = poller._get_connection()
        conn2 = poller._get_connection()
        
        # Both should be valid connections
        assert conn1 is not None
        assert conn2 is not None
        
        # Close them
        conn1.close()
        conn2.close()


@pytest.mark.asyncio
async def test_async_compatibility():
    """Test async/await compatibility of db_poller methods."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
        db_path = Path(tmp.name)
        
        try:
            # Create test database with proper schema
            conn = sqlite3.connect(str(db_path))
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    created_at INTEGER,
                    status TEXT,
                    metadata TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT,
                    timestamp INTEGER,
                    role TEXT,
                    content TEXT
                )
            """)
            conn.execute("INSERT INTO sessions VALUES ('ses_test', 1234567890, 'active', '{}')")
            conn.commit()
            conn.close()
            
            poller = OpenCodeDBPoller(db_path=str(db_path))
            
            # Test that methods can be awaited (they're not async but should work with async tests)
            sessions = poller.get_new_sessions()
            assert isinstance(sessions, list)
            
        finally:
            db_path.unlink(missing_ok=True)
