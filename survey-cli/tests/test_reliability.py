"""
Unit tests for SR-152 reliability primitives.

Tests cover: retry policy, DLQ, contradiction detector, webhook, integration.
22+ tests total.
"""
from __future__ import annotations

import asyncio
import json
import os
import sqlite3
import tempfile
import time
import unittest
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from threading import Thread
from unittest.mock import patch, MagicMock, AsyncMock

from survey.reliability.retry_policy import (
    RetryPolicy,
    Retryability,
    TransientError,
    PermanentError,
    FatalError,
    default_classify,
    RetryContext,
)
from survey.reliability.dlq import DLQ, DLQRecord
from survey.reliability.contradiction import (
    ContradictionDetector,
    Contradiction,
    PinnedAnswer,
    IdentityCategory,
)


# =============================================================================
# Retry Policy Tests (6)
# =============================================================================

class TestRetryPolicy(unittest.TestCase):
    """Tests for retry_policy.py"""
    
    def test_success_no_retry(self):
        """Success on first attempt — no retries needed."""
        policy = RetryPolicy(max_attempts=3)
        call_count = 0
        
        async def succeeds():
            nonlocal call_count
            call_count += 1
            return "success"
        
        result = asyncio.get_event_loop().run_until_complete(
            policy.run(succeeds)
        )
        
        self.assertEqual(result, "success")
        self.assertEqual(call_count, 1)
    
    def test_transient_retry_then_success(self):
        """Transient error retried, then succeeds."""
        policy = RetryPolicy(max_attempts=3, base_delay=0.01)
        call_count = 0
        
        async def fails_twice_then_succeeds():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise TimeoutError("transient")
            return "success"
        
        result = asyncio.get_event_loop().run_until_complete(
            policy.run(fails_twice_then_succeeds)
        )
        
        self.assertEqual(result, "success")
        self.assertEqual(call_count, 3)
    
    def test_permanent_no_retry(self):
        """Permanent error not retried."""
        policy = RetryPolicy(max_attempts=3)
        call_count = 0
        
        async def fails_permanent():
            nonlocal call_count
            call_count += 1
            raise PermanentError("account banned")
        
        with self.assertRaises(PermanentError):
            asyncio.get_event_loop().run_until_complete(
                policy.run(fails_permanent)
            )
        
        self.assertEqual(call_count, 1)
    
    def test_max_attempts_exceeded(self):
        """All retries exhausted raises last error."""
        policy = RetryPolicy(max_attempts=3, base_delay=0.01)
        call_count = 0
        
        async def always_transient():
            nonlocal call_count
            call_count += 1
            raise TransientError("always fails")
        
        with self.assertRaises(TransientError):
            asyncio.get_event_loop().run_until_complete(
                policy.run(always_transient)
            )
        
        self.assertEqual(call_count, 3)
    
    def test_backoff_respects_max_delay(self):
        """Backoff delay capped at max_delay."""
        policy = RetryPolicy(max_attempts=5, base_delay=10.0, max_delay=0.5)
        
        # Attempt 3 would be 10 * 2^3 = 80s without cap
        delay = policy._calculate_delay(3)
        
        # Should be capped at 0.5 + some jitter (max 0.25)
        self.assertLess(delay, 1.0)
    
    def test_classify_fn_override(self):
        """Custom classify function is used."""
        policy = RetryPolicy(max_attempts=3, base_delay=0.01)
        call_count = 0
        
        def custom_classify(e):
            # Treat everything as transient
            return Retryability.TRANSIENT
        
        async def fails_with_value_error():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ValueError("normally permanent")
            return "success"
        
        result = asyncio.get_event_loop().run_until_complete(
            policy.run(fails_with_value_error, classify_fn=custom_classify)
        )
        
        self.assertEqual(result, "success")
        self.assertEqual(call_count, 2)


class TestDefaultClassify(unittest.TestCase):
    """Tests for default_classify function."""
    
    def test_timeout_is_transient(self):
        self.assertEqual(default_classify(TimeoutError()), Retryability.TRANSIENT)
    
    def test_connection_is_transient(self):
        self.assertEqual(default_classify(ConnectionError()), Retryability.TRANSIENT)
    
    def test_assertion_is_fatal(self):
        self.assertEqual(default_classify(AssertionError()), Retryability.FATAL)
    
    def test_account_banned_is_permanent(self):
        self.assertEqual(
            default_classify(Exception("account banned")),
            Retryability.PERMANENT
        )
    
    def test_503_is_transient(self):
        self.assertEqual(
            default_classify(Exception("HTTP 503 Service Unavailable")),
            Retryability.TRANSIENT
        )


# =============================================================================
# DLQ Tests (6)
# =============================================================================

class TestDLQ(unittest.TestCase):
    """Tests for dlq.py"""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.dlq = DLQ(dlq_path=self.temp_dir)
    
    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_push_creates_record(self):
        """Push creates a DLQ record with correct fields."""
        dlq_id = self.dlq.push(
            survey_id="test-survey-123",
            persona_id="anna_meyer",
            provider="lucid",
            url="https://example.com/survey",
            error=ValueError("test error"),
            attempt_count=3,
            context={"last_question": "What is your age?"},
        )
        
        self.assertTrue(dlq_id.startswith("dlq-"))
        
        record = self.dlq.get(dlq_id)
        self.assertIsNotNone(record)
        self.assertEqual(record.survey_id, "test-survey-123")
        self.assertEqual(record.persona_id, "anna_meyer")
        self.assertEqual(record.status, "pending")
    
    def test_list_pending(self):
        """List pending returns only pending records."""
        self.dlq.push("s1", "p1", "provider", "url", Exception("e1"), 1)
        id2 = self.dlq.push("s2", "p2", "provider", "url", Exception("e2"), 1)
        self.dlq.push("s3", "p3", "provider", "url", Exception("e3"), 1)
        
        self.dlq.mark_replayed(id2)
        
        pending = self.dlq.list_pending()
        self.assertEqual(len(pending), 2)
    
    def test_mark_replayed(self):
        """Mark replayed updates status."""
        dlq_id = self.dlq.push("s1", "p1", "provider", "url", Exception("e"), 1)
        
        self.assertTrue(self.dlq.mark_replayed(dlq_id))
        
        record = self.dlq.get(dlq_id)
        self.assertEqual(record.status, "replayed")
    
    def test_mark_discarded(self):
        """Mark discarded updates status."""
        dlq_id = self.dlq.push("s1", "p1", "provider", "url", Exception("e"), 1)
        
        self.assertTrue(self.dlq.mark_discarded(dlq_id))
        
        record = self.dlq.get(dlq_id)
        self.assertEqual(record.status, "discarded")
    
    def test_jsonl_format(self):
        """DLQ writes valid JSONL format."""
        self.dlq.push("s1", "p1", "provider", "url", Exception("e"), 1)
        self.dlq.push("s2", "p2", "provider", "url", Exception("e"), 2)
        
        # Read raw file
        dlq_files = list(Path(self.temp_dir).glob("dlq-*.jsonl"))
        self.assertEqual(len(dlq_files), 1)
        
        with open(dlq_files[0]) as f:
            lines = f.readlines()
        
        self.assertEqual(len(lines), 2)
        
        for line in lines:
            record = json.loads(line)
            self.assertIn("id", record)
            self.assertIn("ts", record)
            self.assertIn("status", record)
    
    def test_daily_rotation(self):
        """DLQ files are named with current date."""
        from datetime import datetime
        
        self.dlq.push("s1", "p1", "provider", "url", Exception("e"), 1)
        
        date_str = datetime.now().strftime("%Y-%m-%d")
        expected_file = Path(self.temp_dir) / f"dlq-{date_str}.jsonl"
        
        self.assertTrue(expected_file.exists())


# =============================================================================
# Contradiction Detector Tests (6)
# =============================================================================

class TestContradictionDetector(unittest.TestCase):
    """Tests for contradiction.py"""
    
    def setUp(self):
        self.temp_db = tempfile.mktemp(suffix=".db")
        self._setup_db()
        self.detector = ContradictionDetector(db_path=self.temp_db)
    
    def _setup_db(self):
        """Create answer_history table with test data."""
        conn = sqlite3.connect(self.temp_db)
        conn.execute("""
            CREATE TABLE answer_history (
                id INTEGER PRIMARY KEY,
                question_hash TEXT,
                question_text TEXT,
                answer_value TEXT,
                persona_hash TEXT,
                created_at TEXT,
                identity_category TEXT
            )
        """)
        conn.commit()
        conn.close()
    
    def tearDown(self):
        if os.path.exists(self.temp_db):
            os.remove(self.temp_db)
    
    def test_categorize_german(self):
        """Categorize detects German keywords."""
        self.assertEqual(
            self.detector.categorize("Wie alt sind Sie?"),
            IdentityCategory.AGE
        )
        self.assertEqual(
            self.detector.categorize("Was ist Ihr Geschlecht?"),
            IdentityCategory.GENDER
        )
        self.assertEqual(
            self.detector.categorize("Ihr monatliches Einkommen?"),
            IdentityCategory.INCOME
        )
    
    def test_categorize_english(self):
        """Categorize detects English keywords."""
        self.assertEqual(
            self.detector.categorize("What is your age?"),
            IdentityCategory.AGE
        )
        self.assertEqual(
            self.detector.categorize("Select your gender"),
            IdentityCategory.GENDER
        )
        self.assertEqual(
            self.detector.categorize("What is your annual household income?"),
            IdentityCategory.INCOME
        )
    
    def test_check_no_prior(self):
        """Check returns None when no prior answers exist."""
        result = self.detector.check("unknown_persona", "What is your age?")
        self.assertIsNone(result)
    
    def test_check_with_prior(self):
        """Check returns pinned answer when prior exists."""
        # Insert prior answers
        conn = sqlite3.connect(self.temp_db)
        for _ in range(5):
            conn.execute("""
                INSERT INTO answer_history 
                (question_hash, answer_value, persona_hash, identity_category)
                VALUES (?, ?, ?, ?)
            """, ("hash1", "25-34", "test_persona", "AGE"))
        conn.commit()
        conn.close()
        
        result = self.detector.check("test_persona", "How old are you?")
        
        self.assertIsNotNone(result)
        self.assertEqual(result.category, IdentityCategory.AGE)
        self.assertEqual(result.value, "25-34")
        self.assertIn("SR-152", result.reasoning)
    
    def test_scan_no_conflicts(self):
        """Scan reports consistent answers correctly."""
        conn = sqlite3.connect(self.temp_db)
        for _ in range(10):
            conn.execute("""
                INSERT INTO answer_history 
                (question_hash, answer_value, persona_hash, identity_category)
                VALUES (?, ?, ?, ?)
            """, ("hash1", "female", "consistent_persona", "GENDER"))
        conn.commit()
        conn.close()
        
        results = self.detector.scan("consistent_persona")
        
        self.assertIn("GENDER", results)
        self.assertFalse(results["GENDER"].is_contradicted)
        self.assertEqual(results["GENDER"].most_frequent, "female")
    
    def test_scan_with_conflicts(self):
        """Scan detects contradictions correctly."""
        conn = sqlite3.connect(self.temp_db)
        # 8 answers for "25-34", 2 for "35-44"
        for _ in range(8):
            conn.execute("""
                INSERT INTO answer_history 
                (question_hash, answer_value, persona_hash, identity_category)
                VALUES (?, ?, ?, ?)
            """, ("hash1", "25-34", "conflict_persona", "AGE"))
        for _ in range(2):
            conn.execute("""
                INSERT INTO answer_history 
                (question_hash, answer_value, persona_hash, identity_category)
                VALUES (?, ?, ?, ?)
            """, ("hash2", "35-44", "conflict_persona", "AGE"))
        conn.commit()
        conn.close()
        
        results = self.detector.scan("conflict_persona")
        
        self.assertIn("AGE", results)
        self.assertTrue(results["AGE"].is_contradicted)
        self.assertEqual(results["AGE"].most_frequent, "25-34")
        self.assertEqual(results["AGE"].most_frequent_count, 8)


# =============================================================================
# Webhook Tests (2)
# =============================================================================

class WebhookHandler(BaseHTTPRequestHandler):
    """Simple webhook handler for testing."""
    received_payloads = []
    
    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length)
        WebhookHandler.received_payloads.append(json.loads(body))
        self.send_response(200)
        self.end_headers()
    
    def log_message(self, format, *args):
        pass  # Suppress logging


class TestWebhook(unittest.TestCase):
    """Tests for webhook alerting."""
    
    def test_webhook_env_set_fires(self):
        """Webhook fires when RELIABILITY_WEBHOOK_URL is set."""
        WebhookHandler.received_payloads = []
        
        # Start test server
        server = HTTPServer(('127.0.0.1', 0), WebhookHandler)
        port = server.server_address[1]
        thread = Thread(target=server.handle_request)
        thread.start()
        
        try:
            temp_dir = tempfile.mkdtemp()
            dlq = DLQ(
                dlq_path=temp_dir,
                webhook_url=f"http://127.0.0.1:{port}/webhook"
            )
            
            dlq.push("s1", "p1", "provider", "url", Exception("test"), 1)
            
            thread.join(timeout=2)
            
            self.assertEqual(len(WebhookHandler.received_payloads), 1)
            self.assertIn("text", WebhookHandler.received_payloads[0])
            self.assertIn("details", WebhookHandler.received_payloads[0])
        finally:
            server.server_close()
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)
    
    def test_webhook_env_unset_skipped(self):
        """No webhook call when URL not set."""
        temp_dir = tempfile.mkdtemp()
        dlq = DLQ(dlq_path=temp_dir, webhook_url=None)
        
        # Should not raise, should not call webhook
        dlq_id = dlq.push("s1", "p1", "provider", "url", Exception("test"), 1)
        
        self.assertIsNotNone(dlq_id)
        
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)


# =============================================================================
# Integration Tests (2)
# =============================================================================

class TestIntegration(unittest.TestCase):
    """Integration tests for reliability primitives."""
    
    def test_retry_context_tracks_errors(self):
        """RetryContext correctly tracks error history."""
        policy = RetryPolicy(max_attempts=3)
        ctx = RetryContext(policy)
        
        ctx.record_error(TimeoutError("e1"), Retryability.TRANSIENT)
        ctx.record_error(ConnectionError("e2"), Retryability.TRANSIENT)
        ctx.record_error(PermanentError("e3"), Retryability.PERMANENT)
        
        self.assertEqual(ctx.total_attempts, 3)
        self.assertIsInstance(ctx.last_error, PermanentError)
        
        ctx_dict = ctx.to_dict()
        self.assertEqual(len(ctx_dict["errors"]), 3)
    
    def test_dlq_record_serialization(self):
        """DLQRecord serializes and deserializes correctly."""
        record = DLQRecord(
            id="dlq-test123",
            ts="2026-05-12T15:30:00Z",
            survey_id="survey-abc",
            persona_id="anna_meyer",
            provider="lucid",
            url="https://example.com",
            error_class="ValueError",
            error_message="test error",
            attempt_count=3,
            context={"key": "value"},
            status="pending",
        )
        
        # Serialize
        data = record.to_dict()
        json_str = json.dumps(data)
        
        # Deserialize
        loaded = json.loads(json_str)
        restored = DLQRecord.from_dict(loaded)
        
        self.assertEqual(restored.id, record.id)
        self.assertEqual(restored.survey_id, record.survey_id)
        self.assertEqual(restored.context, record.context)


if __name__ == "__main__":
    unittest.main()
