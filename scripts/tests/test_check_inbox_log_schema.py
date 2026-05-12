"""tests for scripts/check_inbox_log_schema.py — SR-117.

Coverage (15+ tests required):
  T01  valid minimal record (required fields only)
  T02  valid record with all optional fields
  T03  missing required field: role
  T04  missing required field: normalized_label
  T05  missing required field: confidence
  T06  missing required field: source
  T07  empty role string
  T08  empty normalized_label string
  T09  confidence below 0.0
  T10  confidence above 1.0
  T11  confidence exactly at boundary 0.0 and 1.0 (valid)
  T12  invalid source enum value
  T13  llm source without model -> warning (not violation)
  T14  llm source WITH model -> no warning
  T15  optional count negative -> violation
  T16  optional sample_labels contains non-string element
  T17  optional matched_tokens not a list
  T18  optional model wrong type (not str/null)
  T19  optional prompt_hash wrong type
  T20  malformed JSON line -> parse error as violation
  T21  empty file -> 0 records, 0 violations
  T22  no files matching glob -> 0 records, 0 files
  T23  multi-file aggregation: violations summed across files
  T24  multiple errors in one record reported together
  T25  format_human: clean output string
  T26  format_json_output: structure and fields
  T27  --strict promotes warnings to rc=1 (via check_logs directly)
"""

import json
import os
import tempfile

import pytest

from check_inbox_log_schema import (
    check_logs,
    format_human,
    format_json_output,
    validate_record,
)

# ── Helpers ───────────────────────────────────────────────────────────────────

VALID = {
    "role": "software_engineer",
    "normalized_label": "backend",
    "confidence": 0.85,
    "source": "substring",
}


def mk(overrides=None, omit=None):
    """Build a test record from VALID base, applying overrides/omissions."""
    r = dict(VALID)
    if omit:
        for k in omit:
            r.pop(k, None)
    if overrides:
        r.update(overrides)
    return r


def write_jsonl(path, records):
    with open(path, "w") as f:
        for rec in records:
            f.write(json.dumps(rec) + "\n")


# ── T01-T02: Valid records ────────────────────────────────────────────────────


class TestValidRecords:
    def test_T01_valid_minimal(self):
        viol, warn = validate_record(mk(), "f.jsonl", 1)
        assert viol is None
        assert warn is None

    def test_T02_valid_all_optional_fields(self):
        rec = mk({
            "suggested_family": "engineering",
            "count": 5,
            "sample_labels": ["backend dev", "swe"],
            "matched_tokens": ["backend"],
            "model": "gpt-4",
            "prompt_hash": "abc123",
            "source": "llm",
        })
        viol, warn = validate_record(rec, "f.jsonl", 1)
        assert viol is None
        assert warn is None  # model is set, so no warning


# ── T03-T08: Missing / empty required fields ─────────────────────────────────


class TestRequiredFields:
    def test_T03_missing_role(self):
        viol, _ = validate_record(mk(omit=["role"]), "f.jsonl", 1)
        assert viol is not None
        assert any("role" in e for e in viol["errors"])

    def test_T04_missing_normalized_label(self):
        viol, _ = validate_record(mk(omit=["normalized_label"]), "f.jsonl", 1)
        assert viol is not None
        assert any("normalized_label" in e for e in viol["errors"])

    def test_T05_missing_confidence(self):
        viol, _ = validate_record(mk(omit=["confidence"]), "f.jsonl", 1)
        assert viol is not None
        assert any("confidence" in e for e in viol["errors"])

    def test_T06_missing_source(self):
        viol, _ = validate_record(mk(omit=["source"]), "f.jsonl", 1)
        assert viol is not None
        assert any("source" in e for e in viol["errors"])

    def test_T07_empty_role(self):
        viol, _ = validate_record(mk({"role": "   "}), "f.jsonl", 1)
        assert viol is not None
        assert any("non-empty" in e for e in viol["errors"])

    def test_T08_empty_normalized_label(self):
        viol, _ = validate_record(
            mk({"normalized_label": ""}), "f.jsonl", 1
        )
        assert viol is not None
        assert any("non-empty" in e for e in viol["errors"])


# ── T09-T11: Confidence range ─────────────────────────────────────────────────


class TestConfidence:
    def test_T09_confidence_below_zero(self):
        viol, _ = validate_record(mk({"confidence": -0.01}), "f.jsonl", 1)
        assert viol is not None
        assert any("[0.0, 1.0]" in e for e in viol["errors"])

    def test_T10_confidence_above_one(self):
        viol, _ = validate_record(mk({"confidence": 1.001}), "f.jsonl", 1)
        assert viol is not None
        assert any("[0.0, 1.0]" in e for e in viol["errors"])

    def test_T11_confidence_at_boundaries(self):
        for val in (0.0, 1.0):
            viol, _ = validate_record(mk({"confidence": val}), "f.jsonl", 1)
            assert viol is None, f"confidence={val} should be valid"


# ── T12: Source enum ──────────────────────────────────────────────────────────


class TestSource:
    def test_T12_invalid_source(self):
        viol, _ = validate_record(mk({"source": "magic"}), "f.jsonl", 1)
        assert viol is not None
        assert any("source" in e and "must be one of" in e for e in viol["errors"])


# ── T13-T14: Cross-field llm/model warning ────────────────────────────────────


class TestLlmModelWarning:
    def test_T13_llm_without_model_is_warning_not_violation(self):
        rec = mk({"source": "llm"})
        # model field absent entirely
        rec.pop("model", None)
        viol, warn = validate_record(rec, "f.jsonl", 1)
        assert viol is None, "should not be a violation"
        assert warn is not None
        assert "llm-source" in warn["message"]
        assert "model" in warn["message"]

    def test_T14_llm_with_model_no_warning(self):
        rec = mk({"source": "llm", "model": "gpt-4"})
        viol, warn = validate_record(rec, "f.jsonl", 1)
        assert viol is None
        assert warn is None


# ── T15-T19: Optional field type validation ───────────────────────────────────


class TestOptionalFields:
    def test_T15_count_negative(self):
        viol, _ = validate_record(mk({"count": -1}), "f.jsonl", 1)
        assert viol is not None
        assert any("count" in e and ">= 0" in e for e in viol["errors"])

    def test_T16_sample_labels_non_string_element(self):
        viol, _ = validate_record(
            mk({"sample_labels": ["ok", 42]}), "f.jsonl", 1
        )
        assert viol is not None
        assert any("sample_labels" in e for e in viol["errors"])

    def test_T17_matched_tokens_not_list(self):
        viol, _ = validate_record(
            mk({"matched_tokens": "oops"}), "f.jsonl", 1
        )
        assert viol is not None
        assert any("matched_tokens" in e and "list" in e for e in viol["errors"])

    def test_T18_model_wrong_type(self):
        viol, _ = validate_record(mk({"model": 12345}), "f.jsonl", 1)
        assert viol is not None
        assert any("model" in e and "str or null" in e for e in viol["errors"])

    def test_T19_prompt_hash_wrong_type(self):
        viol, _ = validate_record(mk({"prompt_hash": ["x"]}), "f.jsonl", 1)
        assert viol is not None
        assert any("prompt_hash" in e and "str or null" in e for e in viol["errors"])


# ── T20-T24: check_logs integration tests ────────────────────────────────────


class TestCheckLogs:
    def test_T20_malformed_json_line(self):
        with tempfile.TemporaryDirectory() as d:
            write_jsonl(
                os.path.join(d, "pattern-suggestions-20260512.jsonl"),
                []
            )
            p = os.path.join(d, "pattern-suggestions-20260512.jsonl")
            with open(p, "w") as f:
                f.write("{ not valid json \n")
            viols, warns, recs, files = check_logs(d)
            assert files == 1
            assert any("error" in v for v in viols)

    def test_T21_empty_file(self):
        with tempfile.TemporaryDirectory() as d:
            open(os.path.join(
                d, "pattern-suggestions-20260512.jsonl"
            ), "w").close()
            viols, warns, recs, files = check_logs(d)
            assert files == 1
            assert recs == 0
            assert viols == []

    def test_T22_no_matching_files(self):
        with tempfile.TemporaryDirectory() as d:
            # Create a file that does NOT match the glob
            with open(os.path.join(d, "unrelated.jsonl"), "w") as f:
                f.write(json.dumps(mk()) + "\n")
            viols, warns, recs, files = check_logs(d)
            assert files == 0
            assert recs == 0

    def test_T23_multi_file_aggregation(self):
        with tempfile.TemporaryDirectory() as d:
            for i in range(3):
                fname = f"pattern-suggestions-2026050{i+1}.jsonl"
                write_jsonl(
                    os.path.join(d, fname),
                    [mk(), mk(omit=["role"])]  # 1 valid, 1 invalid each
                )
            viols, warns, recs, files = check_logs(d)
            assert files == 3
            assert recs == 6        # all examined records (valid + invalid)
            assert len(viols) == 3  # 1 violation per file

    def test_T24_multiple_errors_in_one_record(self):
        rec = {
            "role": "",              # empty
            "normalized_label": "",  # empty
            "confidence": 2.0,       # out of range
            # source: missing
        }
        viol, _ = validate_record(rec, "f.jsonl", 1)
        assert viol is not None
        assert len(viol["errors"]) >= 4


# ── T25-T27: Formatting and strict mode ──────────────────────────────────────


class TestFormatting:
    def test_T25_format_human_clean(self):
        out = format_human([], [], 10, 2)
        assert "OK" in out
        assert "10" in out
        assert "2" in out

    def test_T26_format_json_structure(self):
        viols = [{"file": "f.jsonl", "line": 1, "errors": ["bad"]}]
        warns = [{"file": "f.jsonl", "line": 2, "message": "warn"}]
        out = json.loads(format_json_output(viols, warns, 5, 1))
        assert out["clean"] is False
        assert out["files_scanned"] == 1
        assert out["records_validated"] == 5
        assert len(out["violations"]) == 1
        assert len(out["warnings"]) == 1

    def test_T27_strict_mode_via_check_logs_warnings(self):
        with tempfile.TemporaryDirectory() as d:
            write_jsonl(
                os.path.join(d, "pattern-suggestions-20260512.jsonl"),
                [mk({"source": "llm"})],  # llm without model -> warning
            )
            viols, warns, recs, files = check_logs(d)
            # No violations, but there IS a warning
            assert viols == []
            assert len(warns) == 1
            # --strict would return rc=1 when warnings > 0
            has_violations = len(viols) > 0
            has_warnings   = len(warns) > 0
            strict_rc = 1 if (has_violations or has_warnings) else 0
            assert strict_rc == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
