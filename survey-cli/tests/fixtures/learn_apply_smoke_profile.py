"""Minimal ProfileLoader stub for learn-apply smoke tests.

This file mirrors the AST shape of survey/profile_loader.py::FIELD_PATTERNS
(list of (family_str, re.compile(...)) tuples) WITHOUT the full 20+ families.
Purpose: CI smoke can run apply against this stub without touching production
profile_loader.py, and the AST locator will find the same structure.

DO NOT use this file for anything except smoke tests. The real FIELD_PATTERNS
live in survey/profile_loader.py and are tested via test_profile_match_field.py.
"""

from __future__ import annotations

import re
from typing import List, Tuple


class ProfileLoader:
    """Minimal stub for smoke testing learn apply AST injection."""

    # ── FIELD_PATTERNS — same AST shape as production ──────────────────────
    # Format: (logical_key, compiled_regex)
    # The smoke test will inject "|mobilnummer" into the phone pattern.
    FIELD_PATTERNS: List[Tuple[str, "re.Pattern[str]"]] = [
        # Email — single pattern for smoke.
        ("email", re.compile(r"(e[\s\-]?mail|mailadresse)", re.I)),

        # Phone — the smoke test injects "|mobilnummer" here.
        ("phone", re.compile(
            r"(telefon|handy|phone)",
            re.I,
        )),
    ]
