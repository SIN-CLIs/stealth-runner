#!/usr/bin/env python3
# =============================================================================
# SR-117: Schema validator for inbox suggestion-logs
#         (logs/pattern-suggestions-*.jsonl).
#
# WHY THIS FILE EXISTS
# --------------------
# survey learn apply/review reads inbox records from
# logs/pattern-suggestions-*.jsonl via InboxEntry.from_dict() (apply.py:77).
# from_dict() silently falls back to defaults when fields are missing
# (e.g. confidence=0.0). A corrupt record can therefore be silently applied
# at default confidence instead of being rejected.  This script is the
# INBOX-SCHEMA-GUARD: runs as CI-step or pre-apply hook, validates every
# record against the InboxEntry spec, exits non-zero if drift detected.
#
# CONTRACT
# --------
# - Reads only. NEVER writes to disk, NEVER mutates input files.
# - Default mode (no flags): print human-readable report, exit 0 always.
# - --exit-non-zero-on-violation: exit 1 if violations > 0 (CI / alert mode).
# - --strict: also exit 1 if warnings > 0
#             (e.g. llm-source records missing model field).
# - --json:  machine-parseable JSON to stdout.
# - --quiet: suppress output, use only exit code.
#
# DESIGN
# ------
# Standalone — does NOT import `from survey.learn import ...`.
# The scripts/ tree is sys-admin/hygiene territory and must run without the
# survey-cli package installed.
#
# SCHEMA SPEC (frozen, from Issue #117 / apply.py:77-105 InboxEntry)
# -------------------------------------------------------------------
# Required fields (every record):
#   role              : str, non-empty
#   normalized_label  : str, non-empty
#   confidence        : float,  0.0 <= x <= 1.0
#   source            : str, one of {"substring", "llm", "manual"}
#
# Optional fields (if present, must be correctly typed):
#   suggested_family  : str | null
#   count             : int >= 0
#   sample_labels     : list[str]
#   matched_tokens    : list[str]
#   model             : str | null
#   prompt_hash       : str | null
#
# Cross-field WARNING (not error):
#   source == "llm" AND model is None
#       -> "llm-source record missing model field — pre-SR-57 legacy?"
#
# FILE SELECTION
#   Glob: logs/pattern-suggestions-*.jsonl
# =============================================================================
"""scripts/check_inbox_log_schema.py — validate inbox suggestion-log schema.

CLI:
    python scripts/check_inbox_log_schema.py
        [--logs DIR]                    # default: survey-cli/logs
        [--exit-non-zero-on-violation]  # rc=1 if violations > 0
        [--strict]                      # rc=1 if warnings > 0 too
        [--json]                        # JSON output to stdout
        [--quiet]                       # suppress output (exit code only)

Closes #117
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import sys
from typing import Any

__all__ = [
    "validate_record",
    "iter_records",
    "check_logs",
    "format_human",
    "format_json_output",
    "main",
]

# ── Constants ─────────────────────────────────────────────────────────────────

DEFAULT_LOGS_DIR = "survey-cli/logs"
INPUT_GLOB = "pattern-suggestions-*.jsonl"

VALID_SOURCES = {"substring", "llm", "manual"}

# ── Core validation ──────────────────────────────────────────────────────────


def validate_record(
    record: dict[str, Any],
    file_path: str,
    line_num: int,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """Validate one inbox record against the InboxEntry schema spec.

    Returns (violation, warning) — each is None if not applicable.
    violation : dict with keys file, line, record, errors
    warning   : dict with keys file, line, record, message
    """
    errors: list[str] = []
    warning: dict[str, Any] | None = None

    # ── Required: role ────────────────────────────────────────────────────────
    if "role" not in record:
        errors.append("missing required field 'role'")
    elif not isinstance(record["role"], str):
        errors.append(f"'role' must be str, got {type(record['role']).__name__}")
    elif not record["role"].strip():
        errors.append("'role' must be non-empty")

    # ── Required: normalized_label ────────────────────────────────────────────
    if "normalized_label" not in record:
        errors.append("missing required field 'normalized_label'")
    elif not isinstance(record["normalized_label"], str):
        errors.append(
            f"'normalized_label' must be str, got {type(record['normalized_label']).__name__}"
        )
    elif not record["normalized_label"].strip():
        errors.append("'normalized_label' must be non-empty")

    # ── Required: confidence ─────────────────────────────────────────────────
    if "confidence" not in record:
        errors.append("missing required field 'confidence'")
    elif not isinstance(record["confidence"], int | float):
        errors.append(f"'confidence' must be numeric, got {type(record['confidence']).__name__}")
    elif not (0.0 <= record["confidence"] <= 1.0):
        errors.append(f"'confidence' must be in [0.0, 1.0], got {record['confidence']}")

    # ── Required: source ─────────────────────────────────────────────────────
    source = record.get("source")
    if "source" not in record:
        errors.append("missing required field 'source'")
    elif not isinstance(source, str):
        errors.append(f"'source' must be str, got {type(source).__name__}")
    elif source not in VALID_SOURCES:
        errors.append(f"'source' must be one of {sorted(VALID_SOURCES)}, got '{source}'")

    # ── Optional: suggested_family ───────────────────────────────────────────
    if "suggested_family" in record:
        v = record["suggested_family"]
        if not isinstance(v, str | type(None)):
            errors.append(f"'suggested_family' must be str or null, got {type(v).__name__}")

    # ── Optional: count ───────────────────────────────────────────────────────
    if "count" in record:
        v = record["count"]
        if not isinstance(v, int):
            errors.append(f"'count' must be int, got {type(v).__name__}")
        elif v < 0:
            errors.append(f"'count' must be >= 0, got {v}")

    # ── Optional: sample_labels ───────────────────────────────────────────────
    if "sample_labels" in record:
        v = record["sample_labels"]
        if not isinstance(v, list):
            errors.append(f"'sample_labels' must be list, got {type(v).__name__}")
        else:
            for i, item in enumerate(v):
                if not isinstance(item, str):
                    errors.append(f"'sample_labels[{i}]' must be str, got {type(item).__name__}")

    # ── Optional: matched_tokens ──────────────────────────────────────────────
    if "matched_tokens" in record:
        v = record["matched_tokens"]
        if not isinstance(v, list):
            errors.append(f"'matched_tokens' must be list, got {type(v).__name__}")
        else:
            for i, item in enumerate(v):
                if not isinstance(item, str):
                    errors.append(f"'matched_tokens[{i}]' must be str, got {type(item).__name__}")

    # ── Optional: model ───────────────────────────────────────────────────────
    if "model" in record:
        v = record["model"]
        if not isinstance(v, str | type(None)):
            errors.append(f"'model' must be str or null, got {type(v).__name__}")

    # ── Optional: prompt_hash ─────────────────────────────────────────────────
    if "prompt_hash" in record:
        v = record["prompt_hash"]
        if not isinstance(v, str | type(None)):
            errors.append(f"'prompt_hash' must be str or null, got {type(v).__name__}")

    # ── Cross-field warning: llm without model ────────────────────────────────
    if isinstance(source, str) and source == "llm" and record.get("model") is None and not errors:
        warning = {
            "file": file_path,
            "line": line_num,
            "record": record,
            "message": ("llm-source record missing model field — pre-SR-57 legacy? (#56)"),
        }

    violation = (
        {
            "file": file_path,
            "line": line_num,
            "record": record,
            "errors": errors,
        }
        if errors
        else None
    )
    return violation, warning


def iter_records(
    file_path: str,
) -> tuple[dict[str, Any] | None, int, str | None]:
    """Yield (record_or_None, line_num, parse_error_or_None) for each line."""
    try:
        with open(file_path) as fh:
            for line_num, raw in enumerate(fh, start=1):
                line = raw.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line), line_num, None
                except json.JSONDecodeError as exc:
                    yield None, line_num, f"JSON parse error: {exc}"
    except OSError:
        pass  # unreadable file: skip silently


def check_logs(
    logs_dir: str,
) -> tuple[list[dict], list[dict], int, int]:
    """Scan all pattern-suggestions-*.jsonl files in logs_dir.

    Returns (violations, warnings, total_records, total_files).
    """
    violations: list[dict] = []
    warnings: list[dict] = []
    total_records = 0
    total_files = 0

    pattern = os.path.join(logs_dir, INPUT_GLOB)
    for file_path in sorted(glob.glob(pattern)):
        total_files += 1
        for record, line_num, parse_err in iter_records(file_path):
            if parse_err is not None:
                violations.append({"file": file_path, "line": line_num, "error": parse_err})
                continue
            total_records += 1
            viol, warn = validate_record(record, file_path, line_num)
            if viol:
                violations.append(viol)
            if warn:
                warnings.append(warn)

    return violations, warnings, total_records, total_files


# ── Formatting ────────────────────────────────────────────────────────────────


def format_human(
    violations: list[dict],
    warnings: list[dict],
    total_records: int,
    total_files: int,
) -> str:
    """Return a human-readable validation report."""
    lines: list[str] = []

    if not violations and not warnings:
        lines.append(f"OK  {total_records} record(s) across {total_files} file(s) are valid.")
        return "\n".join(lines)

    header = (
        f"Found {total_records} record(s) across {total_files} file(s) — "
        f"{len(violations)} violation(s), {len(warnings)} warning(s)."
    )
    lines.append(header)

    if violations:
        lines.append("")
        lines.append("VIOLATIONS:")
        for v in violations:
            lines.append(f"  {v['file']}:{v['line']}")
            if "error" in v:
                lines.append(f"    parse: {v['error']}")
            else:
                for msg in v.get("errors", []):
                    lines.append(f"    - {msg}")

    if warnings:
        lines.append("")
        lines.append("WARNINGS:")
        for w in warnings:
            lines.append(f"  {w['file']}:{w['line']}: {w['message']}")

    return "\n".join(lines)


def format_json_output(
    violations: list[dict],
    warnings: list[dict],
    total_records: int,
    total_files: int,
) -> str:
    """Return machine-parseable JSON output."""
    return json.dumps(
        {
            "clean": len(violations) == 0,
            "violations": violations,
            "warnings": warnings,
            "files_scanned": total_files,
            "records_validated": total_records,
        },
        indent=2,
    )


# ── CLI ───────────────────────────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser(
        description=("Validate inbox suggestion-log schema (pattern-suggestions-*.jsonl records).")
    )
    parser.add_argument(
        "--logs",
        default=DEFAULT_LOGS_DIR,
        metavar="DIR",
        help=f"Path to logs directory (default: {DEFAULT_LOGS_DIR})",
    )
    parser.add_argument(
        "--exit-non-zero-on-violation",
        action="store_true",
        help="Exit with code 1 if violations found.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Also exit with code 1 if warnings found.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output JSON instead of human-readable text.",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress all output; use exit code only.",
    )
    args = parser.parse_args()

    violations, warnings, total_records, total_files = check_logs(args.logs)

    if not args.quiet:
        if args.json:
            print(format_json_output(violations, warnings, total_records, total_files))
        else:
            print(format_human(violations, warnings, total_records, total_files))

    has_violations = len(violations) > 0
    has_warnings = len(warnings) > 0

    if args.exit_non_zero_on_violation and has_violations:
        return 1
    if args.strict and (has_violations or has_warnings):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
