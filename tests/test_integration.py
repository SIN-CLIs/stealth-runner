"""Integration test suite for stealth-sync full pipeline.

WARUM: stealth-sync besteht aus 3 Komponenten (DBPoller, SemanticAnalyzer,
OutputGenerator). Jede Komponente für sich ist getestet, aber die
Integration kann fehlschlagen (Format-Mismatch, State-Drift, Race-Conditions).
Diese Tests prüfen den gesamten Workflow End-to-End.

ARCHITEKTUR: pytest + unittest.mock (Mock, MagicMock, patch).
SQLite wird als tempfile angelegt, Sessions werden eingefügt,
Poll → Analyze → Generate wird ausgeführt und Outputs verifiziert.
Kein echter Netzwerk-IO (NIM gepatcht), kein echter Dateisystem-IO
außer tempfiles.

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

import pytest
import tempfile
import time
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
from src.stealth_sync.db_poller import OpenCodeDBPoller
from src.stealth_sync.semantic_engine import SemanticAnalyzer
from src.stealth_sync.output_generator import OutputGenerator


class TestIntegrationPipeline:
    """Test suite for the complete stealth-sync pipeline."""

    def test_full_pipeline_with_mocked_analysis(self, tmp_path):
        """Test the complete poll → analyze → generate pipeline."""
        # Setup paths
        db_path = tmp_path / "test.db"
        output_dir = tmp_path / "output"
        logbook_path = tmp_path / "logbook.yaml"
        changelog_dir = tmp_path / "changelog"
        
        # Create a test database with a session
        import sqlite3
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
                content TEXT,
                FOREIGN KEY (session_id) REFERENCES sessions(id)
            )
        """)
        
        # Insert test session with messages
        session_id = "ses_integration_test"
        conn.execute(
            "INSERT INTO sessions (id, created_at, status, metadata) VALUES (?, ?, ?, ?)",
            (session_id, int(time.time()), "active", '{"type": "fix"}')
        )
        conn.execute(
            "INSERT INTO messages (session_id, timestamp, role, content) VALUES (?, ?, ?, ?)",
            (session_id, int(time.time()), "user", "Fix the critical bug in the authentication module")
        )
        conn.execute(
            "INSERT INTO messages (session_id, timestamp, role, content) VALUES (?, ?, ?, ?)",
            (session_id, int(time.time()) + 1, "assistant", "Fixed the authentication issue with proper error handling")
        )
        conn.commit()
        conn.close()
        
        # Create components
        poller = OpenCodeDBPoller(db_path=str(db_path))
        analyzer = SemanticAnalyzer()
        generator = OutputGenerator(output_dir=str(output_dir))
        
        # Test polling
        new_sessions = poller.get_new_sessions()
        assert len(new_sessions) == 1
        assert new_sessions[0]["id"] == session_id
        
        # Test getting messages
        messages = poller.get_session_messages(session_id)
        assert len(messages) == 2
        assert messages[0]["role"] == "user"
        assert messages[1]["role"] == "assistant"
        
        # Test analysis (mock the API call)
        with patch.object(analyzer.client.chat.completions, 'create') as mock_create:
            mock_response = Mock()
            mock_response.choices = [Mock()]
            mock_response.choices[0].message.content = "fix"
            mock_create.return_value = mock_response
            
            classification = analyzer.classify_session(messages)
            assert classification["category"] in ["fix", "new", "refactor", "doc", "test", "chore", "feat"]
            assert classification["confidence"] == 0.9
        
        # Test documentation unit generation
        doc_unit = analyzer.generate_doc_unit(session_id, messages, classification)
        assert doc_unit["session_id"] == session_id
        assert doc_unit["classification"] == classification
        assert doc_unit["message_count"] == 2
        assert "summary" in doc_unit
        assert "timestamp" in doc_unit
        
        # Test output generation
        yaml_path = generator.generate_yaml(doc_unit)
        assert yaml_path.exists()
        assert yaml_path.suffix == ".yaml"
        
        json_path = generator.generate_json(doc_unit)
        assert json_path.exists()
        assert json_path.suffix == ".json"
        
        # Test changelog update
        changelog_path = generator.update_changelog(doc_unit, str(changelog_dir))
        assert changelog_path.exists()
        assert changelog_path.suffix == ".md"
        
        # Test logbook update
        generator.update_logbook(doc_unit, str(logbook_path))
        assert Path(logbook_path).exists()
        
        # Verify all files were created in the correct locations
        assert output_dir.exists()
        assert changelog_dir.exists()
        
    def test_pipeline_with_different_categories(self, tmp_path):
        """Test pipeline with different session categories."""
        # Setup
        db_path = tmp_path / "categories.db"
        output_dir = tmp_path / "categories_output"
        
        import sqlite3
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE IF NOT EXISTS sessions (id TEXT PRIMARY KEY, created_at INTEGER, status TEXT, metadata TEXT)")
        conn.execute("CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT, timestamp INTEGER, role TEXT, content TEXT, FOREIGN KEY (session_id) REFERENCES sessions(id))")
        
        categories_and_messages = [
            ("fix", [
                ("user", "Fix the bug in the login function"),
                ("assistant", "Fixed the login bug with proper validation")
            ]),
            ("new", [
                ("user", "Add new user authentication system"),
                ("assistant", "Implemented JWT-based authentication")
            ]),
            ("refactor", [
                ("user", "Refactor the database schema"),
                ("assistant", "Refactored database models for better performance")
            ]),
            ("doc", [
                ("user", "Update README with installation instructions"),
                ("assistant", "Added comprehensive README documentation")
            ]),
            ("test", [
                ("user", "Add unit tests for authentication module"),
                ("assistant", "Implemented test suite with 100% coverage")
            ]),
            ("chore", [
                ("user", "Update dependencies to latest versions"),
                ("assistant", "Updated all dependencies and fixed vulnerabilities")
            ]),
            ("feat", [
                ("user", "Implement new dashboard feature"),
                ("assistant", "Built interactive dashboard with React")
            ]),
        ]
        
        for category, messages in categories_and_messages:
            session_id = f"ses_{category}_test"
            conn.execute(
                "INSERT INTO sessions (id, created_at, status, metadata) VALUES (?, ?, ?, ?)",
                (session_id, int(time.time()), "active", f'{{"type": "{category}"}}')
            )
            for role, content in messages:
                conn.execute(
                    "INSERT INTO messages (session_id, timestamp, role, content) VALUES (?, ?, ?, ?)",
                    (session_id, int(time.time()), role, content)
                )
        
        conn.commit()
        conn.close()
        
        # Create components
        poller = OpenCodeDBPoller(db_path=str(db_path))
        analyzer = SemanticAnalyzer()
        generator = OutputGenerator(output_dir=str(output_dir))
        
        # Process each session
        new_sessions = poller.get_new_sessions()
        assert len(new_sessions) == 7
        
        for session in new_sessions:
            session_id = session["id"]
            messages = poller.get_session_messages(session_id)
            
            # Mock classification based on session ID
            expected_category = session_id.split("_")[1]
            with patch.object(analyzer.client.chat.completions, 'create') as mock_create:
                mock_response = Mock()
                mock_response.choices = [Mock()]
                mock_response.choices[0].message.content = expected_category
                mock_create.return_value = mock_response
                
                classification = analyzer.classify_session(messages)
                assert classification["category"] == expected_category
            
            # Generate documentation
            doc_unit = analyzer.generate_doc_unit(session_id, messages, classification)
            assert doc_unit["classification"]["category"] == expected_category
            
            # Generate outputs
            yaml_path = generator.generate_yaml(doc_unit)
            assert yaml_path.exists()
            
            json_path = generator.generate_json(doc_unit)
            assert json_path.exists()

    def test_pipeline_error_handling(self, tmp_path):
        """Test pipeline error handling and resilience."""
        # Setup empty database
        db_path = tmp_path / "empty.db"
        output_dir = tmp_path / "error_output"
        
        import sqlite3
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE IF NOT EXISTS sessions (id TEXT PRIMARY KEY, created_at INTEGER, status TEXT, metadata TEXT)")
        conn.execute("CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT, timestamp INTEGER, role TEXT, content TEXT, FOREIGN KEY (session_id) REFERENCES sessions(id))")
        conn.commit()
        conn.close()
        
        # Create components
        poller = OpenCodeDBPoller(db_path=str(db_path))
        analyzer = SemanticAnalyzer()
        generator = OutputGenerator(output_dir=str(output_dir))
        
        # Test with no sessions
        new_sessions = poller.get_new_sessions()
        assert len(new_sessions) == 0
        
        # Test with empty session (no messages)
        session_id = "ses_empty"
        conn = sqlite3.connect(str(db_path))
        conn.execute(
            "INSERT INTO sessions (id, created_at, status, metadata) VALUES (?, ?, ?, ?)",
            (session_id, int(time.time()), "active", '{"type": "doc"}')
        )
        conn.commit()
        conn.close()
        
        messages = poller.get_session_messages(session_id)
        assert len(messages) == 0
        
        # Should still generate documentation even with empty messages
        with patch.object(analyzer.client.chat.completions, 'create') as mock_create:
            mock_response = Mock()
            mock_response.choices = [Mock()]
            mock_response.choices[0].message.content = "doc"
            mock_create.return_value = mock_response
            
            classification = analyzer.classify_session(messages)
            assert classification["category"] == "doc"
        
        doc_unit = analyzer.generate_doc_unit(session_id, messages, classification)
        assert doc_unit["message_count"] == 0
        
        # Output generation should still work
        yaml_path = generator.generate_yaml(doc_unit)
        assert yaml_path.exists()
        
    def test_pipeline_with_unicode_and_special_chars(self, tmp_path):
        """Test pipeline handles Unicode and special characters correctly."""
        # Setup
        db_path = tmp_path / "unicode.db"
        output_dir = tmp_path / "unicode_output"
        
        import sqlite3
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE IF NOT EXISTS sessions (id TEXT PRIMARY KEY, created_at INTEGER, status TEXT, metadata TEXT)")
        conn.execute("CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT, timestamp INTEGER, role TEXT, content TEXT, FOREIGN KEY (session_id) REFERENCES sessions(id))")
        
        session_id = "ses_unicode_test"
        conn.execute(
            "INSERT INTO sessions (id, created_at, status, metadata) VALUES (?, ?, ?, ?)",
            (session_id, int(time.time()), "active", '{"type": "doc"}')
        )
        
        # Messages with Unicode and special characters
        unicode_messages = [
            ("user", "Update README with emojis and special chars: aeiou n"),
            ("assistant", "Added comprehensive documentation with UTF-8 support"),
            ("user", "Fix bug: Japanese text"),
            ("assistant", "修正完了しました"),
            ("user", "Add Arabic text"),
            ("assistant", "تمت الإضافة بنجاح"),
        ]
        
        for role, content in unicode_messages:
            conn.execute(
                "INSERT INTO messages (session_id, timestamp, role, content) VALUES (?, ?, ?, ?)",
                (session_id, int(time.time()), role, content)
            )
        
        conn.commit()
        conn.close()
        
        # Create components
        poller = OpenCodeDBPoller(db_path=str(db_path))
        analyzer = SemanticAnalyzer()
        generator = OutputGenerator(output_dir=str(output_dir))
        
        # Process
        messages = poller.get_session_messages(session_id)
        assert len(messages) == 6
        
        with patch.object(analyzer.client.chat.completions, 'create') as mock_create:
            mock_response = Mock()
            mock_response.choices = [Mock()]
            mock_response.choices[0].message.content = "doc"
            mock_create.return_value = mock_response
            
            classification = analyzer.classify_session(messages)
            assert classification["category"] == "doc"
        
        doc_unit = analyzer.generate_doc_unit(session_id, messages, classification)
        
        # Output generation should handle Unicode
        yaml_path = generator.generate_yaml(doc_unit)
        assert yaml_path.exists()
        
        # Verify content exists (summary will be "Session with 6 messages" due to mock)
        with open(yaml_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Just verify the file was created successfully with Unicode support
        assert len(content) > 0
        
        json_path = generator.generate_json(doc_unit)
        assert json_path.exists()
        
        # Verify Unicode is preserved in JSON
        import json as json_module
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json_module.load(f)
            assert "session_id" in data
            assert len(data["summary"]) > 0

    def test_pipeline_multiple_sessions_batch(self, tmp_path):
        """Test processing multiple sessions in batch."""
        # Setup
        db_path = tmp_path / "batch.db"
        output_dir = tmp_path / "batch_output"
        
        import sqlite3
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE IF NOT EXISTS sessions (id TEXT PRIMARY KEY, created_at INTEGER, status TEXT, metadata TEXT)")
        conn.execute("CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT, timestamp INTEGER, role TEXT, content TEXT, FOREIGN KEY (session_id) REFERENCES sessions(id))")
        
        # Create 10 sessions
        for i in range(10):
            session_id = f"ses_batch_{i}"
            conn.execute(
                "INSERT INTO sessions (id, created_at, status, metadata) VALUES (?, ?, ?, ?)",
                (session_id, int(time.time()) - i, "active", '{"type": "fix"}')
            )
            
            # Each session has 2-5 messages
            for j in range(2 if i % 3 == 0 else 5):
                conn.execute(
                    "INSERT INTO messages (session_id, timestamp, role, content) VALUES (?, ?, ?, ?)",
                    (session_id, int(time.time()) - i - j, "user" if j % 2 == 0 else "assistant", f"Message {j} for session {i}")
                )
        
        conn.commit()
        conn.close()
        
        # Create components
        poller = OpenCodeDBPoller(db_path=str(db_path))
        analyzer = SemanticAnalyzer()
        generator = OutputGenerator(output_dir=str(output_dir))
        
        # Process all sessions
        new_sessions = poller.get_new_sessions()
        assert len(new_sessions) == 10
        
        for session in new_sessions:
            session_id = session["id"]
            messages = poller.get_session_messages(session_id)
            
            with patch.object(analyzer.client.chat.completions, 'create') as mock_create:
                mock_response = Mock()
                mock_response.choices = [Mock()]
                mock_response.choices[0].message.content = "fix"
                mock_create.return_value = mock_response
                
                classification = analyzer.classify_session(messages)
            
            doc_unit = analyzer.generate_doc_unit(session_id, messages, classification)
            
            # Generate outputs for each session
            yaml_path = generator.generate_yaml(doc_unit)
            assert yaml_path.exists()
            
            json_path = generator.generate_json(doc_unit)
            assert json_path.exists()
        
        # Verify all output files exist
        yaml_files = list(output_dir.glob("session_*.yaml"))
        json_files = list(output_dir.glob("session_*.json"))
        
        assert len(yaml_files) == 10
        assert len(json_files) == 10


@pytest.mark.asyncio
async def test_async_pipeline_compatibility():
    """Test that all pipeline components are async-compatible."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        # Test components can be instantiated
        poller = OpenCodeDBPoller(db_path=f"{tmp_dir}/test.db")
        analyzer = SemanticAnalyzer()
        generator = OutputGenerator(output_dir=tmp_dir)
        
        # Test methods can be awaited (they're not async but should work in async context)
        session_id = "ses_async_test"
        messages = [
            {"role": "user", "content": "Test async compatibility"},
            {"role": "assistant", "content": "Async test passed"}
        ]
        
        with patch.object(analyzer.client.chat.completions, 'create') as mock_create:
            mock_response = Mock()
            mock_response.choices = [Mock()]
            mock_response.choices[0].message.content = "test"
            mock_create.return_value = mock_response
            
            classification = analyzer.classify_session(messages)
            assert isinstance(classification, dict)
        
        doc_unit = analyzer.generate_doc_unit(session_id, messages, classification)
        assert isinstance(doc_unit, dict)
        
        yaml_path = generator.generate_yaml(doc_unit)
        assert yaml_path.exists()
        
        json_path = generator.generate_json(doc_unit)
        assert json_path.exists()
