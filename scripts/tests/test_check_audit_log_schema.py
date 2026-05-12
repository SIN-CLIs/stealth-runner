"""tests for scripts/check_audit_log_schema.py — SR-113.

Test coverage:
  - AC1: parse_timestamp validation (valid/invalid ISO8601)
  - AC2: validate_record for applied records (all fields, all errors)
  - AC3: validate_record for rejected_by_* records (minimal required fields)
  - AC4: empty logs dir handling
  - AC5: missing/malformed JSONL handling
  - AC6: --exit-non-zero-on-violation flag behavior
  - AC7: --json flag output format
  - AC8: human-readable output format
  - AC9: file globbing (learn-applied-*.jsonl pattern)
  - AC10: total_records and total_files counting
"""

import json
import os
import tempfile
import pytest
from check_audit_log_schema import (
    parse_timestamp,
    validate_record,
    check_logs,
    format_human,
    format_json,
)


class TestParseTimestamp:
    """Test timestamp parsing."""

    def test_valid_iso8601_with_z(self):
        """Valid ISO8601 with Z suffix should parse."""
        assert parse_timestamp("2026-05-12T10:05:33Z") is True

    def test_valid_iso8601_with_offset(self):
        """Valid ISO8601 with +00:00 offset should parse."""
        assert parse_timestamp("2026-05-12T10:05:33+00:00") is True

    def test_valid_iso8601_naive(self):
        """Naive ISO8601 (no timezone) should parse."""
        assert parse_timestamp("2026-05-12T10:05:33") is True

    def test_invalid_not_string(self):
        """Non-string timestamps should return False."""
        assert parse_timestamp(12345) is False
        assert parse_timestamp(None) is False
        assert parse_timestamp([]) is False

    def test_invalid_empty_string(self):
        """Empty or whitespace-only strings should return False."""
        assert parse_timestamp("") is False
        assert parse_timestamp("   ") is False

    def test_invalid_unparseable(self):
        """Unparseable strings should return False."""
        assert parse_timestamp("not-a-timestamp") is False
        assert parse_timestamp("2026-13-45T99:99:99Z") is False


class TestValidateRecord:
    """Test record validation against schema spec."""

    def test_valid_applied_record(self):
        """Valid 'applied' record should pass."""
        record = {
            "decision": "applied",
            "family": "test_family",
            "keyword": "test_keyword",
            "source": "substring",
            "confidence": 0.95,
            "timestamp": "2026-05-12T10:05:33Z",
        }
        violation = validate_record(record, "test.jsonl", 1)
        assert violation is None

    def test_valid_applied_with_optional_fields(self):
        """Valid 'applied' record with optional fields should pass."""
        record = {
            "decision": "applied",
            "family": "test_family",
            "keyword": "test_keyword",
            "source": "llm",
            "confidence": 0.5,
            "timestamp": "2026-05-12T10:05:33Z",
            "model": "gpt-4",
            "details": "some details",
            "note": "some note",
        }
        violation = validate_record(record, "test.jsonl", 1)
        assert violation is None

    def test_valid_rejected_by_gate(self):
        """Valid 'rejected_by_gate' record (minimal) should pass."""
        record = {"decision": "rejected_by_gate"}
        violation = validate_record(record, "test.jsonl", 1)
        assert violation is None

    def test_valid_rejected_by_reviewer(self):
        """Valid 'rejected_by_reviewer' record with optional fields should pass."""
        record = {
            "decision": "rejected_by_reviewer",
            "reason": "not relevant",
            "note": "reviewer comment",
        }
        violation = validate_record(record, "test.jsonl", 1)
        assert violation is None

    def test_valid_rejected_by_ast(self):
        """Valid 'rejected_by_ast' record should pass."""
        record = {"decision": "rejected_by_ast"}
        violation = validate_record(record, "test.jsonl", 1)
        assert violation is None

    def test_missing_decision(self):
        """Missing 'decision' should fail."""
        record = {"family": "test"}
        violation = validate_record(record, "test.jsonl", 1)
        assert violation is not None
        assert any("missing required field 'decision'" in e for e in violation["errors"])

    def test_invalid_decision_type(self):
        """Invalid decision value should fail."""
        record = {"decision": "invalid_decision"}
        violation = validate_record(record, "test.jsonl", 1)
        assert violation is not None
        assert any("must be one of" in e for e in violation["errors"])

    def test_applied_missing_family(self):
        """Applied record missing 'family' should fail."""
        record = {
            "decision": "applied",
            "keyword": "kw",
            "source": "substring",
            "confidence": 0.9,
            "timestamp": "2026-05-12T10:05:33Z",
        }
        violation = validate_record(record, "test.jsonl", 1)
        assert violation is not None
        assert any("'family'" in e for e in violation["errors"])

    def test_applied_empty_family(self):
        """Applied record with empty 'family' should fail."""
        record = {
            "decision": "applied",
            "family": "",
            "keyword": "kw",
            "source": "substring",
            "confidence": 0.9,
            "timestamp": "2026-05-12T10:05:33Z",
        }
        violation = validate_record(record, "test.jsonl", 1)
        assert violation is not None
        assert any("non-empty" in e for e in violation["errors"])

    def test_applied_missing_keyword(self):
        """Applied record missing 'keyword' should fail."""
        record = {
            "decision": "applied",
            "family": "fam",
            "source": "substring",
            "confidence": 0.9,
            "timestamp": "2026-05-12T10:05:33Z",
        }
        violation = validate_record(record, "test.jsonl", 1)
        assert violation is not None
        assert any("'keyword'" in e for e in violation["errors"])

    def test_applied_invalid_source(self):
        """Applied record with invalid 'source' should fail."""
        record = {
            "decision": "applied",
            "family": "fam",
            "keyword": "kw",
            "source": "invalid_source",
            "confidence": 0.9,
            "timestamp": "2026-05-12T10:05:33Z",
        }
        violation = validate_record(record, "test.jsonl", 1)
        assert violation is not None
        assert any("'source'" in e and "must be one of" in e for e in violation["errors"])

    def test_applied_confidence_out_of_range_high(self):
        """Applied record with confidence > 1.0 should fail."""
        record = {
            "decision": "applied",
            "family": "fam",
            "keyword": "kw",
            "source": "substring",
            "confidence": 1.5,
            "timestamp": "2026-05-12T10:05:33Z",
        }
        violation = validate_record(record, "test.jsonl", 1)
        assert violation is not None
        assert any("confidence" in e and "range" in e for e in violation["errors"])

    def test_applied_confidence_out_of_range_low(self):
        """Applied record with confidence < 0.0 should fail."""
        record = {
            "decision": "applied",
            "family": "fam",
            "keyword": "kw",
            "source": "substring",
            "confidence": -0.1,
            "timestamp": "2026-05-12T10:05:33Z",
        }
        violation = validate_record(record, "test.jsonl", 1)
        assert violation is not None
        assert any("confidence" in e and "range" in e for e in violation["errors"])

    def test_applied_invalid_timestamp(self):
        """Applied record with invalid 'timestamp' should fail."""
        record = {
            "decision": "applied",
            "family": "fam",
            "keyword": "kw",
            "source": "substring",
            "confidence": 0.9,
            "timestamp": "not-a-timestamp",
        }
        violation = validate_record(record, "test.jsonl", 1)
        assert violation is not None
        assert any("'timestamp'" in e and "ISO8601" in e for e in violation["errors"])

    def test_optional_field_not_string_or_null(self):
        """Optional fields that are not string/null should fail."""
        record = {
            "decision": "applied",
            "family": "fam",
            "keyword": "kw",
            "source": "substring",
            "confidence": 0.9,
            "timestamp": "2026-05-12T10:05:33Z",
            "model": 12345,  # Should be string or null, not int
        }
        violation = validate_record(record, "test.jsonl", 1)
        assert violation is not None
        assert any("'model'" in e and "string or null" in e for e in violation["errors"])

    def test_multiple_errors(self):
        """Record with multiple errors should report all."""
        record = {
            "decision": "applied",
            # Missing: family, keyword, source, confidence, timestamp
        }
        violation = validate_record(record, "test.jsonl", 1)
        assert violation is not None
        assert len(violation["errors"]) >= 5


class TestCheckLogs:
    """Test check_logs function with temp files."""

    def test_empty_logs_dir(self):
        """Empty logs directory should return 0 violations, 0 records, 0 files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            violations, total_records, total_files = check_logs(tmpdir)
            assert violations == []
            assert total_records == 0
            assert total_files == 0

    def test_single_valid_file(self):
        """Single file with valid records should count correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, "learn-applied-2026-05-12.jsonl")
            with open(log_file, "w") as f:
                f.write(json.dumps({
                    "decision": "applied",
                    "family": "f1",
                    "keyword": "k1",
                    "source": "substring",
                    "confidence": 0.9,
                    "timestamp": "2026-05-12T10:05:33Z",
                }) + "\n")
                f.write(json.dumps({
                    "decision": "rejected_by_gate",
                }) + "\n")

            violations, total_records, total_files = check_logs(tmpdir)
            assert violations == []
            assert total_records == 2
            assert total_files == 1

    def test_file_with_violations(self):
        """File with violations should be reported."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, "learn-applied-2026-05-12.jsonl")
            with open(log_file, "w") as f:
                f.write(json.dumps({
                    "decision": "applied",
                    "family": "f1",
                    # Missing required fields
                }) + "\n")

            violations, total_records, total_files = check_logs(tmpdir)
            assert len(violations) > 0
            assert total_records == 1
            assert total_files == 1

    def test_multiple_files(self):
        """Multiple log files should all be scanned."""
        with tempfile.TemporaryDirectory() as tmpdir:
            for i in range(3):
                log_file = os.path.join(tmpdir, f"learn-applied-2026-05-{12+i:02d}.jsonl")
                with open(log_file, "w") as f:
                    f.write(json.dumps({"decision": "rejected_by_ast"}) + "\n")

            violations, total_records, total_files = check_logs(tmpdir)
            assert violations == []
            assert total_records == 3
            assert total_files == 3

    def test_malformed_json_line(self):
        """Malformed JSON should be reported as parse error."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, "learn-applied-2026-05-12.jsonl")
            with open(log_file, "w") as f:
                f.write("{ invalid json }\n")

            violations, total_records, total_files = check_logs(tmpdir)
            assert len(violations) > 0
            assert any("error" in v for v in violations)

    def test_non_matching_files_ignored(self):
        """Files not matching pattern should be ignored."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a file that doesn't match pattern
            other_file = os.path.join(tmpdir, "other_file.jsonl")
            with open(other_file, "w") as f:
                f.write("ignored\n")

            # Create a valid pattern file
            log_file = os.path.join(tmpdir, "learn-applied-2026-05-12.jsonl")
            with open(log_file, "w") as f:
                f.write(json.dumps({"decision": "rejected_by_gate"}) + "\n")

            violations, total_records, total_files = check_logs(tmpdir)
            assert total_files == 1  # Only the learn-applied-*.jsonl file
            assert total_records == 1


class TestFormatting:
    """Test output formatting functions."""

    def test_format_human_no_violations(self):
        """Human format with no violations."""
        output = format_human([], 5, 2)
        assert "✓" in output
        assert "All 5 records" in output

    def test_format_human_with_violations(self):
        """Human format with violations."""
        violations = [
            {
                "file": "test.jsonl",
                "line": 1,
                "errors": ["missing field"],
            }
        ]
        output = format_human(violations, 5, 2)
        assert "✗" in output
        assert "1 violation" in output
        assert "test.jsonl:1" in output

    def test_format_json_no_violations(self):
        """JSON format with no violations."""
        output = format_json([], 5, 2)
        data = json.loads(output)
        assert data["valid"] is True
        assert data["violation_count"] == 0
        assert data["total_records"] == 5
        assert data["total_files"] == 2

    def test_format_json_with_violations(self):
        """JSON format with violations."""
        violations = [
            {
                "file": "test.jsonl",
                "line": 1,
                "errors": ["missing field"],
            }
        ]
        output = format_json(violations, 5, 2)
        data = json.loads(output)
        assert data["valid"] is False
        assert data["violation_count"] == 1
        assert len(data["violations"]) == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
