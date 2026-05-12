"""FCTC-ES Lernschleife (AGENTS.md §12) — Phase 1: Matcher-Pattern-Vorschlaege.

================================================================================
ZWECK
================================================================================

Wenn ProfileLoader.match_field() ein Label NICHT trifft, ist das ein
**Lern-Signal**: entweder ist die Persona unvollstaendig (REQUIRED_KEYS,
siehe SR-53), oder das Label gehoert zu einer Familie, die noch kein
FIELD_PATTERNS-Eintrag abdeckt.

Diese Lernschleife sammelt Miss-Labels aus ProfileLoader.telemetry()
und schlaegt vor, welche bestehende Familie um welches Keyword erweitert
werden sollte.

================================================================================
PIPELINE (Phase 1, manual review)
================================================================================

  1. ``aggregator.aggregate_misses(telemetry_path)``
     → liest matcher-telemetry-*.jsonl, normalisiert Labels, gruppiert
       per (role, normalized_label) und zaehlt Frequenz.

  2. ``suggester.suggest_family(normalized_label) -> SuggestedFamily``
     → vergleicht Token-Set des Labels mit den Keyword-Sets der bekannten
       FIELD_PATTERNS-Familien (rein heuristisch, KEINE LLM-Dependency).
     → confidence in [0..1], suggested_family kann None sein.

  3. ``aggregator.write_suggestions(out_path, suggestions)``
     → schreibt JSONL Datei ``pattern-suggestions-{date}.jsonl``.

  4. CLI ``python -m survey learn review``
     → zeigt offene Vorschlaege tabellarisch, fragt nach
       ACCEPT / REJECT / SKIP (interaktiv).
     → akzeptierte Vorschlaege landen in
       ``logs/pattern-suggestions-accepted.jsonl`` als To-Do fuer den
       naechsten ProfileLoader-Update — KEIN Auto-Apply!

NIEMALS Auto-Apply:
  Patterns sind sicherheitsrelevant (falsche Familie -> falscher Wert ->
  Screen-Out). Mensch entscheidet, bis Phase 2 ein Eval-Harness hat.
"""

from __future__ import annotations

from .aggregator import (
    aggregate_misses,
    write_suggestions,
    normalize_label,
)
from .suggester import (
    SuggestedFamily,
    suggest_family,
    FAMILY_TOKENS,
    LLMSuggestion,
    suggest_via_llm,
)
from .apply import (
    InboxEntry,
    ApplyResult,
    apply_inbox,
    apply_keyword_to_family,
    compute_diff,
)
from .llm_client import (
    LLMResponse,
    call_llm,
    is_available as llm_is_available,
    prompt_hash,
)
# SR-102 #102 — source-aware batch-review pure functions
from .review import (
    ReviewRules,
    ReviewSummary,
    plan_action,
    apply_status,
    format_display_line,
    partition_records,
    normalize_source,
)

__all__ = [
    "aggregate_misses",
    "write_suggestions",
    "normalize_label",
    "SuggestedFamily",
    "suggest_family",
    "FAMILY_TOKENS",
    # SR-58 #57
    "InboxEntry",
    "ApplyResult",
    "apply_inbox",
    "apply_keyword_to_family",
    "compute_diff",
    # SR-57 #56 (FCTC-ES Phase 2)
    "LLMSuggestion",
    "suggest_via_llm",
    "LLMResponse",
    "call_llm",
    "llm_is_available",
    "prompt_hash",
    # SR-102 #102
    "ReviewRules",
    "ReviewSummary",
    "plan_action",
    "apply_status",
    "format_display_line",
    "partition_records",
    "normalize_source",
]
