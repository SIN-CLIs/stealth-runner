"""Test suite for StealthSyncDaemon module.

Tests the daemon functionality including:
- Daemon initialization
- Start/stop operations
- Signal handling
- Polling and processing cycles
- Session processing workflow
- Error handling

Uses pytest-asyncio for async test support.
"""

import pytest
import time
import signal
from unittest.mock import Mock, MagicMock, patch
from pathlib import Path
from src.stealth_sync.daemon import StealthSyncDaemon


class TestStealthSyncDaemon:
    """Test suite for StealthSyncDaemon class."""

    def test_init_default_parameters(self, tmp_path):
        """Test daemon initialization with default parameters."""
        db_path = tmp_path / "test.db"
        output_dir = tmp_path / "output"
        logbook_path = tmp_path / "logbook.yaml"
        
        daemon = StealthSyncDaemon(
            db_path=str(db_path),
            poll_interval=5,
            output_dir=str(output_dir),
            logbook_path=str(logbook_path)
        )
        
        assert daemon.db_poller is not None
        assert daemon.analyzer is not None
        assert daemon.generator is not None
        assert daemon.poll_interval == 5
        assert daemon.logbook_path == str(logbook_path)
        assert daemon.running is False
        assert daemon.scheduler is not None

    def test_init_custom_parameters(self, tmp_path):
        """Test daemon initialization with custom parameters."""
        db_path = tmp_path / "custom.db"
        output_dir = tmp_path / "custom_output"
        logbook_path = tmp_path / "custom_logbook.yaml"
        
        daemon = StealthSyncDaemon(
            db_path=str(db_path),
            poll_interval=15,
            output_dir=str(output_dir),
            logbook_path=str(logbook_path)
        )
        
        assert daemon.poll_interval == 15
        assert daemon.logbook_path == str(logbook_path)

    def test_init_components_initialized(self, tmp_path):
        """Test that all components are properly initialized."""
        db_path = tmp_path / "test.db"
        
        daemon = StealthSyncDaemon(db_path=str(db_path))
        
        # Check that all main components exist
        assert daemon.db_poller is not None
        assert daemon.analyzer is not None
        assert daemon.generator is not None
        assert daemon.scheduler is not None

    def test_start_sets_running_flag(self, tmp_path):
        """Test that start sets the running flag."""
        db_path = tmp_path / "test.db"
        daemon = StealthSyncDaemon(db_path=str(db_path))
        
        # Mock the scheduler to prevent actual start
        daemon.scheduler.start = Mock()
        
        # Start the daemon
        daemon.start()
        
        assert daemon.running is True

    def test_stop_sets_running_flag(self, tmp_path):
        """Test that stop clears the running flag."""
        db_path = tmp_path / "test.db"
        daemon = StealthSyncDaemon(db_path=str(db_path))
        
        # Manually set running to True
        daemon.running = True
        daemon.scheduler.running = True
        
        # Stop the daemon
        daemon.stop()
        
        assert daemon.running is False

    def test_stop_shuts_down_scheduler(self, tmp_path):
        """Test that stop shuts down the scheduler."""
        db_path = tmp_path / "test.db"
        daemon = StealthSyncDaemon(db_path=str(db_path))
        
        daemon.running = True
        daemon.scheduler.running = True
        daemon.scheduler.shutdown = Mock()
        
        daemon.stop()
        
        daemon.scheduler.shutdown.assert_called_once_with(wait=True)

    def test_signal_handler(self, tmp_path):
        """Test signal handler sets running to False."""
        db_path = tmp_path / "test.db"
        daemon = StealthSyncDaemon(db_path=str(db_path))
        
        # Manually set running to True
        daemon.running = True
        
        # Call signal handler
        daemon._signal_handler(signal.SIGTERM, None)
        
        assert daemon.running is False

    def test_poll_and_process_no_new_sessions(self, tmp_path):
        """Test polling when no new sessions exist."""
        db_path = tmp_path / "empty.db"
        
        # Create empty database
        import sqlite3
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE sessions (id TEXT PRIMARY KEY)")
        conn.commit()
        conn.close()
        
        daemon = StealthSyncDaemon(db_path=str(db_path))
        
        # Mock the logger to avoid output
        with patch.object(daemon.db_poller, 'get_new_sessions', return_value=[]):
            daemon._poll_and_process()
            
            # Should not raise any errors

    def test_poll_and_process_with_sessions(self, tmp_path, sample_session, sample_messages):
        """Test polling when new sessions exist."""
        db_path = tmp_path / "test.db"
        
        # Create database with test data
        import sqlite3
        conn = sqlite3.connect(str(db_path))
        conn.execute("""
            CREATE TABLE sessions (
                id TEXT PRIMARY KEY,
                created_at INTEGER,
                status TEXT,
                metadata TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                timestamp INTEGER,
                role TEXT,
                content TEXT
            )
        """)
        conn.execute(
            "INSERT INTO sessions VALUES (?, ?, ?, ?)",
            (sample_session["id"], 1234567890, "active", '{"type": "fix"}')
        )
        for msg in sample_messages:
            conn.execute(
                "INSERT INTO messages VALUES (?, ?, ?, ?, ?)",
                (msg["id"], msg["session_id"], msg["timestamp"], msg["role"], msg["content"])
            )
        conn.commit()
        conn.close()
        
        daemon = StealthSyncDaemon(db_path=str(db_path))
        
        # Mock the processing to avoid actual API calls
        with patch.object(daemon, '_process_session') as mock_process:
            with patch.object(daemon.db_poller, 'get_new_sessions', return_value=[sample_session]):
                daemon._poll_and_process()
                
                mock_process.assert_called_once_with(sample_session)

    def test_process_session_missing_id(self, tmp_path):
        """Test processing a session without an ID."""
        db_path = tmp_path / "test.db"
        daemon = StealthSyncDaemon(db_path=str(db_path))
        
        session_without_id = {"status": "active"}
        
        # Should not raise an error
        daemon._process_session(session_without_id)

    def test_process_session_with_messages(self, tmp_path, sample_session, sample_messages):
        """Test processing a session with messages."""
        db_path = tmp_path / "test.db"
        
        # Create database with test data
        import sqlite3
        conn = sqlite3.connect(str(db_path))
        conn.execute("""
            CREATE TABLE sessions (
                id TEXT PRIMARY KEY,
                created_at INTEGER,
                status TEXT,
                metadata TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                timestamp INTEGER,
                role TEXT,
                content TEXT
            )
        """)
        conn.execute(
            "INSERT INTO sessions VALUES (?, ?, ?, ?)",
            (sample_session["id"], 1234567890, "active", '{"type": "fix"}')
        )
        for msg in sample_messages:
            conn.execute(
                "INSERT INTO messages VALUES (?, ?, ?, ?, ?)",
                (msg["id"], msg["session_id"], msg["timestamp"], msg["role"], msg["content"])
            )
        conn.commit()
        conn.close()
        
        daemon = StealthSyncDaemon(db_path=str(db_path))
        
        # Mock the analyzer and generator
        mock_classification = {"category": "fix", "confidence": 0.95}
        
        with patch.object(daemon.analyzer, 'classify_session', return_value=mock_classification):
            with patch.object(daemon.analyzer, 'generate_doc_unit', return_value={
                "session_id": sample_session["id"],
                "classification": mock_classification,
                "message_count": len(sample_messages),
                "summary": "Test summary"
            }):
                with patch.object(daemon.generator, 'generate_yaml'):
                    with patch.object(daemon.generator, 'generate_json'):
                        with patch.object(daemon.generator, 'update_changelog'):
                            with patch.object(daemon.generator, 'update_logbook'):
                                daemon._process_session(sample_session)
                                
                                # Verify all methods were called
                                daemon.analyzer.classify_session.assert_called_once()
                                daemon.generator.generate_yaml.assert_called_once()
                                daemon.generator.generate_json.assert_called_once()

    def test_process_session_no_messages(self, tmp_path, sample_session):
        """Test processing a session with no messages."""
        db_path = tmp_path / "test.db"
        
        # Create database with session but no messages
        import sqlite3
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE sessions (id TEXT PRIMARY KEY)")
        conn.execute("INSERT INTO sessions VALUES (?)", (sample_session["id"],))
        conn.commit()
        conn.close()
        
        daemon = StealthSyncDaemon(db_path=str(db_path))
        
        with patch.object(daemon.db_poller, 'get_session_messages', return_value=[]):
            daemon._process_session(sample_session)
            
            # Should not raise errors

    def test_process_session_error_handling(self, tmp_path, sample_session):
        """Test error handling during session processing."""
        db_path = tmp_path / "test.db"
        daemon = StealthSyncDaemon(db_path=str(db_path))
        
        # Mock a method to raise an exception
        with patch.object(daemon.db_poller, 'get_session_messages', side_effect=Exception("DB error")):
            daemon._process_session(sample_session)
            
            # Should not raise the exception

    def test_scheduler_initialized_with_job(self, tmp_path):
        """Test that scheduler is initialized with a polling job."""
        db_path = tmp_path / "test.db"
        daemon = StealthSyncDaemon(db_path=str(db_path), poll_interval=10)
        
        # Check that job was added
        jobs = daemon.scheduler.get_jobs()
        assert len(jobs) > 0
        assert jobs[0].id == "opencode_poll"
        assert jobs[0].name == "OpenCode Session Poller"


@pytest.mark.asyncio
async def test_async_compatibility():
    """Test async/await compatibility of daemon methods."""
    import tempfile
    
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = Path(tmp_dir) / "test.db"
        
        # Create empty database
        import sqlite3
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE sessions (id TEXT PRIMARY KEY)")
        conn.commit()
        conn.close()
        
        daemon = StealthSyncDaemon(db_path=str(db_path))
        
        # Test that methods can be awaited
        assert daemon.running is False
        
        # Start should work (will block, so we won't actually call it in async test)
        # Just verify the method exists and is callable
        assert callable(daemon.start)
        assert callable(daemon.stop)
        assert callable(daemon._poll_and_process)
        assert callable(daemon._process_session)
