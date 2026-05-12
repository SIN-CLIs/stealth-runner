#!/usr/bin/env python3
# =============================================================================
# SR-113: Schema validator for audit-logs (learn-applied-*.jsonl).
#
# WHY THIS FILE EXISTS
# --------------------
# apply.py (#51) writes audit-records to logs/learn-applied-{ISO}.jsonl with
# 4 different decision-types (applied/rejected_by_*), each with distinct
# required/optional fields. When apply.py gets patched and the schema silently
# drifts (new required field, renamed field, etc.), ALL downstream tools
# (audit, explain, triage, future tooling) silently break.
#
# This script is the SCHEMA-GUARD: runs as CI-step or cron, validates every
# record against the spec, exits non-zero if drift detected.
#
# CONTRACT
# --------
# - Reads only. NEVER writes to disk, NEVER mutates input files.
# - Default mode: print violations, exit 0 always (read-only diagnostic).
# - `--exit-non-zero-on-violation`: exit 1 iff violations > 0 (CI/alert mode).
# - `--json`: machine-parseable JSON output to stdout.
#
# DESIGN
# ------
# Standalone — does NOT import `from survey.learn import ...`. The scripts/
# tree is sys-admin/hygiene territory and must run without the survey-cli
# package installed. JSONL parsing is trivial; no code-reuse needed.
#
# SCHEMA SPEC (frozen, from Issue #113)
# --------
# **Top-level required** (every record):
#   - decision: string, one of ["applied", "rejected_by_gate",
#                                "rejected_by_reviewer", "rejected_by_ast"]
#
# **If decision == "applied"** (additionally required):
#   - family:      string, non-empty
#   - keyword:     string, non-empty
#   - source:      string, one of ["substring", "llm"]
#   - confidence:  number, 0.0 <= x <= 1.0
#   - timestamp:   string, ISO-format parseable
#
# **If decision == "applied"** (optional):
#   - model:       string OR null (should be set if source=="llm")
#   - details:     string OR null
#   - note:        string OR null
#
# **If decision == "rejected_by_*"** (optional):
#   - reason:      string OR null
#   - model:       string OR null
#   - note:        string OR null
#
# FILE SELECTION
# - Globs learn-applied-*.jsonl in the logs dir.
# =============================================================================
"""scripts/check_audit_log_schema.py — validate audit-log record schema.

CLI:
    python scripts/check_audit_log_schema.py
        [--logs DIR]                   # default: survey-cli/logs
        [--exit-non-zero-on-violation] # rc=1 if violations > 0
        [--json]                       # JSON output to stdout

Closes #113 (schema-guard for audit-logs).
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

# Public helpers (also imported by tests).
__all__ = [
    "iter_records",
    "parse_timestamp",
    "validate_record",
    "check_logs",
    "format_human",
    "format_json",
    "main",
]


# -- Constants ---------------------------------------------------------------

DEFAULT_LOGS_DIR = "survey-cli/logs"
INPUT_GLOB = "learn-applied-*.jsonl"

# Valid decision types
VALID_DECISIONS = {"applied", "rejected_by_gate", "rejected_by_reviewer", "rejected_by_ast"}
VALID_SOURCES = {"substring", "llm"}


# -- Pure helpers ------------------------------------------------------------


def parse_timestamp(value: Any) -> bool:
    """Check if value is a valid ISO8601-ish timestamp.

    Returns True if parseable, False otherwise. We accept trailing 'Z' for UTC.
    Naive datetimes are assumed UTC.
    """
    if not value or not isinstance(value, str):
        return False
    s = value.strip()
    if not s:
        return False
    # Normalize trailing "Z" -> "+00:00" for fromisoformat.
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        datetime.fromisoformat(s)
        return True
    except (ValueError, TypeError):
        return False


def validate_record(
    record: Dict[str, Any], file_path: str, line_num: int
) -> Optional[Dict[str, Any]]:
    """Validate a single audit-log record against the schema spec.

    Returns None if valid, or a violation dict if invalid.
    """
    errors = []

    # === Top-level required fields ===
    if "decision" not in record:
        errors.append("missing required field 'decision'")
    elif not isinstance(record["decision"], str):
        errors.append(f"'decision' must be string, got {type(record['decision']).__name__}")
    elif record["decision"] not in VALID_DECISIONS:
        errors.append(f"'decision' must be one of {VALID_DECISIONS}, got '{record['decision']}'")

    decision = record.get("decision")

    # === Conditionally required fields (if decision == "applied") ===
    if decision == "applied":
        # family: required, non-empty string
        if "family" not in record:
            errors.append("missing required field 'family' (for decision='applied')")
        elif not isinstance(record["family"], str):
            errors.append(
                f"'family' must be string, got {type(record['family']).__name__} (for decision='applied')"
            )
        elif not record["family"].strip():
            errors.append("'family' must be non-empty (for decision='applied')")

        # keyword: required, non-empty string
        if "keyword" not in record:
            errors.append("missing required field 'keyword' (for decision='applied')")
        elif not isinstance(record["keyword"], str):
            errors.append(
                f"'keyword' must be string, got {type(record['keyword']).__name__} (for decision='applied')"
            )
        elif not record["keyword"].strip():
            errors.append("'keyword' must be non-empty (for decision='applied')")

        # source: required, must be substring or llm
        if "source" not in record:
            errors.append("missing required field 'source' (for decision='applied')")
        elif not isinstance(record["source"], str):
            errors.append(
                f"'source' must be string, got {type(record['source']).__name__} (for decision='applied')"
            )
        elif record["source"] not in VALID_SOURCES:
            errors.append(
                f"'source' must be one of {VALID_SOURCES}, got '{record['source']}' (for decision='applied')"
            )

        # confidence: required, 0.0 <= x <= 1.0
        if "confidence" not in record:
            errors.append("missing required field 'confidence' (for decision='applied')")
        elif not isinstance(record["confidence"], (int, float)):
            errors.append(
                f"'confidence' must be numeric, got {type(record['confidence']).__name__} (for decision='applied')"
            )
        elif not (0.0 <= record["confidence"] <= 1.0):
            errors.append(
                f"'confidence' must be in range [0.0, 1.0], got {record['confidence']} (for decision='applied')"
            )

        # timestamp: required, ISO-format parseable
        if "timestamp" not in record:
            errors.append("missing required field 'timestamp' (for decision='applied')")
        elif not parse_timestamp(record.get("timestamp")):
            errors.append(
                f"'timestamp' must be ISO8601-parseable, got '{record.get('timestamp')}' (for decision='applied')"
            )

        # Optional fields for applied:
        # - model: string or null (should be set if source=="llm" but not required)
        # - details: string or null
        # - note: string or null
        # (We just check they're not bizarre types if present; no coercion.)

    # === Conditionally optional fields (for all decisions, but only check presence/type) ===
    # reason, model, details, note: if present, must be string or null
    for opt_field in ["reason", "model", "details", "note"]:
        if opt_field in record:
            val = record[opt_field]
            if not isinstance(val, (str, type(None))):
                errors.append(
                    f"'{opt_field}' must be string or null, got {type(val).__name__}"
                )

    if errors:
        return {
            "file": file_path,
            "line": line_num,
            "record": record,
            "errors": errors,
        }
    return None


def iter_records(file_path: str) -> Tuple[Dict[str, Any], int, Optional[str]]:
    """Iterate over JSONL records in a file.

    Yields tuples of (record, line_number, error_msg).
    If error_msg is not None, record will be None.
    """
    try:
        with open(file_path, "r") as f:
            for line_num, line in enumerate(f, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                    yield record, line_num, None
                except json.JSONDecodeError as e:
                    yield None, line_num, f"JSON parse error: {e}"
    except OSError as e:
        # File doesn't exist or can't be read; don't crash.
        pass


def check_logs(logs_dir: str) -> Tuple[List[Dict[str, Any]], int, int]:
    """Check all learn-applied-*.jsonl files in logs_dir.

    Returns (violations, total_records, total_files).
    """
    violations = []
    total_records = 0
    total_files = 0

    pattern = os.path.join(logs_dir, INPUT_GLOB)
    files = sorted(glob.glob(pattern))

    for file_path in files:
        total_files += 1
        for record, line_num, parse_err in iter_records(file_path):
            if parse_err:
                violations.append(
                    {
                        "file": file_path,
                        "line": line_num,
                        "error": parse_err,
                    }
                )
                continue

            total_records += 1
            violation = validate_record(record, file_path, line_num)
            if violation:
                violations.append(violation)

    return violations, total_records, total_files


def format_human(violations: List[Dict[str, Any]], total_records: int, total_files: int) -> str:
    """Format violations as human-readable text."""
    lines = []
    if not violations:
        lines.append(f"✓ All {total_records} records across {total_files} file(s) are valid.")
    else:
        lines.append(f"✗ Found {len(violations)} violation(s) across {total_records} records in {total_files} file(s):\n")
        for v in violations:
            lines.append(f"  {v['file']}:{v['line']}")
            if "error" in v:
                lines.append(f"    Parse error: {v['error']}")
            else:
                for err_msg in v.get("errors", []):
                    lines.append(f"    - {err_msg}")
            lines.append("")
    return "\n".join(lines)


def format_json(
    violations: List[Dict[str, Any]], total_records: int, total_files: int
) -> str:
    """Format violations as JSON."""
    return json.dumps(
        {
            "valid": len(violations) == 0,
            "violation_count": len(violations),
            "total_records": total_records,
            "total_files": total_files,
            "violations": violations,
        },
        indent=2,
    )


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Validate audit-log schema (learn-applied-*.jsonl records)."
    )
    parser.add_argument(
        "--logs",
        default=DEFAULT_LOGS_DIR,
        help=f"Path to logs directory (default: {DEFAULT_LOGS_DIR})",
    )
    parser.add_argument(
        "--exit-non-zero-on-violation",
        action="store_true",
        help="Exit with code 1 if violations found (default: always exit 0)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output JSON instead of human-readable text",
    )
    args = parser.parse_args()

    violations, total_records, total_files = check_logs(args.logs)

    if args.json:
        output = format_json(violations, total_records, total_files)
    else:
        output = format_human(violations, total_records, total_files)

    print(output)

    if args.exit_non_zero_on_violation and violations:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
