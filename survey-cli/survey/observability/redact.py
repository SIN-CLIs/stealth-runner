"""================================================================================
LOG REDACTION — Best-effort PII/secret scrubbing for log payloads (SR-250)
================================================================================

MODUL-KONZEPT (SR-250, follow-up auf SR-173 + SR-198 Logger-Hygiene)
--------------------------------------------------------------------

Im Repo gibt es structlog/JSONL-Logging an mehreren Stellen
(`observability/logger.py`, jsonl-Telemetry, `qualification-blocks-*.jsonl`),
aber KEINE zentrale Redaction-Util. Ohne sie leakt jeder neue Logger
potenziell:

  - Persona-PII (E-Mail, Geburtsdaten, Adressen)
  - API-Keys aus environment-spread (OpenAI, NIM, 2captcha)
  - JWT/Bearer-Tokens aus URL-Query-Strings (`?auth=...`, `?session=...`)
  - Login-Cookies aus heypiggy / Survey-Provider

Dieses Modul liefert ein **pure-Python**, **dependency-frei**, **regex-basiertes**
Best-Effort-Scrubbing fuer dict-Payloads. Es ist NICHT als Security-Boundary
gedacht — der Anspruch ist "in einem normal aufgesetzten Logger-Pipeline
verhindern wir die haeufigsten Leak-Klassen".

PUBLIC API
----------
    REDACTED                       — Sentinel string '[REDACTED]'
    DEFAULT_SECRET_KEY_PATTERNS    — tuple of regex strings, key-name match
    DEFAULT_VALUE_PATTERNS         — tuple of regex strings, value match
    redact(payload, *,
           secret_key_patterns,
           value_patterns,
           max_depth)              — top-level entry-point, returns deep-copy

DESIGN CHOICES
--------------

1. **Returns a deep-copy.** Caller's payload is never mutated. Logger
   pipelines often share dicts across handlers, so in-place mutation
   would be a foot-gun.

2. **Two pattern sets.**
   - `secret_key_patterns`: match against KEY names → entire VALUE replaced
     with REDACTED. Catches `{"api_key": "sk-..."}`, `{"password": "..."}`.
   - `value_patterns`: match against string VALUES → matching SUBSTRING
     replaced with REDACTED. Catches JWTs / bearer-tokens / e-mails that
     are embedded in larger strings (e.g. URL query strings).

3. **Recursion-safe.**
   - `max_depth` (default 8) prevents stack-overflow on cyclic dicts.
   - Sets/tuples become lists (JSON-friendliness; structlog typically
     normalizes anyway).
   - Non-JSON values (bytes, datetime, custom objects) are left alone —
     redaction only applies to str/dict/list/tuple/set values.

4. **Default patterns are conservative.**
   - Key patterns are word-bounded to avoid false-positives on harmless
     keys (e.g. `{"password_strength_score": 0.8}` is matched, but that's
     desirable — the field name screams "security").
   - Value patterns target high-confidence shapes only (Bearer-prefix,
     JWT-shape, sk-/sk_-prefixed API keys, e-mail RFC-5322 simplified).

5. **Customizable.**
   - Caller can override or extend both pattern lists at call time.
   - `add_secret_key_pattern()` / `add_value_pattern()` mutate the module
     defaults — explicitly NOT used internally so unit tests don't
     accidentally pollute each other.

USAGE
-----

    >>> from survey.observability.redact import redact
    >>> raw = {
    ...     "event": "login_attempt",
    ...     "user_email": "alice@example.com",
    ...     "api_key": "sk-proj-abc123",
    ...     "url": "https://heypiggy.com/cb?session=eyJhbGciOi...",
    ... }
    >>> redact(raw)
    {
      "event": "login_attempt",
      "user_email": "[REDACTED]",
      "api_key": "[REDACTED]",
      "url": "https://heypiggy.com/cb?session=[REDACTED]",
    }

WHAT THIS MODULE DELIBERATELY DOES NOT
--------------------------------------

- No automatic logger-handler wireup. A separate PR can plug this into
  StructuredLogger as a processor step. SR-250 ships the primitive only.
- No persona-database lookup ("redact every value that equals
  persona.email"). That requires a stable Persona import path which
  doesn't exist yet (cf. SR-170 deliberation).
- No multi-line / file-content redaction (logs are dict-shaped today).
- Not a replacement for proper secret management — secrets should be
  in env-vars and never reach a log payload to begin with.

Module Status: NEW (SR-250, follow-up to SR-173 logger hygiene)
================================================================================
"""

from __future__ import annotations

import re
from typing import Any, Final, Iterable

REDACTED: Final[str] = "[REDACTED]"


# ── DEFAULT PATTERNS ─────────────────────────────────────────────────────────

# Key-name patterns: match against dict-key strings (case-insensitive).
# When matched → entire VALUE for that key is replaced with REDACTED.
DEFAULT_SECRET_KEY_PATTERNS: Final[tuple[str, ...]] = (
    # Generic security/auth keywords
    r"(?i)\b(?:secret|password|passwd|pwd|token|auth|authorization)\b",
    r"(?i)\b(?:api[_-]?key|access[_-]?key|private[_-]?key|client[_-]?secret)\b",
    r"(?i)\b(?:bearer|session[_-]?id|refresh[_-]?token)\b",
    # Cookie / session artefacts
    r"(?i)\bcookie\b",
    r"(?i)\bcsrf[_-]?token\b",
    # PII keys
    r"(?i)\b(?:email|e[_-]?mail|phone|ssn|tax[_-]?id|date[_-]?of[_-]?birth|dob)\b",
    r"(?i)\b(?:credit[_-]?card|card[_-]?number|cvv)\b",
    # Provider-specific
    r"(?i)\b(?:openai[_-]?api[_-]?key|nim[_-]?api[_-]?key|captcha[_-]?api[_-]?key)\b",
    # SR-260: Vercel AI Gateway is the only sanctioned LLM backend.
    r"(?i)\b(?:ai[_-]?gateway[_-]?api[_-]?key|ai[_-]?gateway[_-]?key)\b",
)

# Value patterns: match against string VALUES. Matching SUBSTRING
# is replaced with REDACTED (not the whole string), so URL hosts /
# surrounding context survive in logs while the secret is scrubbed.
DEFAULT_VALUE_PATTERNS: Final[tuple[str, ...]] = (
    # Bearer / Authorization headers
    r"(?i)Bearer\s+[A-Za-z0-9._\-+/=]+",
    # JWT (three base64url segments separated by dots)
    r"\beyJ[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+\b",
    # OpenAI-style keys (sk-..., sk_proj_..., sk-ant-...)
    r"\bsk[-_][A-Za-z0-9_\-]{20,}\b",
    # NVIDIA / NIM keys (nvapi-...)
    r"\bnvapi-[A-Za-z0-9_\-]{20,}\b",
    # Generic long hex / base64 secret-shape (32+ chars contiguous)
    r"\b[A-Fa-f0-9]{32,}\b",
    # E-mail (simplified RFC-5322)
    r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b",
    # URL query-string sensitive params: ?session=... / ?token=... / ?auth=...
    r"(?i)([?&](?:session|token|auth|access[_-]?token|api[_-]?key)=)[^&\s]+",
)

# Default safety limit for recursion. Cyclic / very deep payloads get
# truncated rather than blowing the stack. 8 is generous for realistic
# log shapes (typically 2-3).
_DEFAULT_MAX_DEPTH: Final[int] = 8


# ── INTERNAL HELPERS ─────────────────────────────────────────────────────────


def _compile_patterns(patterns: Iterable[str]) -> list[re.Pattern[str]]:
    """Compile a tuple/list of regex strings. Bad regexes are skipped
    silently — we never want a custom-pattern bug to crash a log call.
    """
    compiled: list[re.Pattern[str]] = []
    for p in patterns:
        try:
            compiled.append(re.compile(p))
        except re.error:
            continue
    return compiled


def _key_matches(key: str, compiled: list[re.Pattern[str]]) -> bool:
    return any(p.search(key) for p in compiled)


def _scrub_string(value: str, compiled: list[re.Pattern[str]]) -> str:
    """Replace every match of any value-pattern with REDACTED.

    For patterns with capture groups (e.g. URL query-key prefix), we
    preserve group(1) when present and replace only the rest.
    """
    out = value
    for p in compiled:
        if p.groups >= 1:
            out = p.sub(lambda m: (m.group(1) or "") + REDACTED, out)
        else:
            out = p.sub(REDACTED, out)
    return out


# ── PUBLIC API ───────────────────────────────────────────────────────────────


def redact(
    payload: Any,
    *,
    secret_key_patterns: Iterable[str] | None = None,
    value_patterns: Iterable[str] | None = None,
    max_depth: int = _DEFAULT_MAX_DEPTH,
) -> Any:
    """Return a redacted DEEP COPY of ``payload``.

    Behaviour:
      - dict: each key checked against secret_key_patterns. Match → value
        replaced with REDACTED. No-match → recurse into the value.
      - list/tuple/set: recurse element-wise. Tuples and sets become
        lists in the output (JSON-friendly).
      - str: each value-pattern applied; matching substrings replaced.
      - All other types (int, float, bool, None, bytes, datetime, custom
        objects) returned unchanged.

    Args:
        payload:                The value to redact. May be any nested
                                Python structure.
        secret_key_patterns:    Override the module-default key patterns.
                                Pass None (default) to use defaults.
                                Pass () to disable key-based redaction.
        value_patterns:         Override the module-default value patterns.
                                Pass None (default) to use defaults.
                                Pass () to disable value-based redaction.
        max_depth:              Recursion safety cap. At depth >= max_depth,
                                the value is returned as-is (no further
                                recursion). Default 8.

    Returns:
        A new structure with redactions applied. The original is never
        mutated. Cyclic inputs are handled by the depth cap.

    Raises:
        Never (best-effort). Bad regexes in the override lists are
        silently dropped.
    """
    key_patterns = (
        DEFAULT_SECRET_KEY_PATTERNS
        if secret_key_patterns is None
        else tuple(secret_key_patterns)
    )
    val_patterns = (
        DEFAULT_VALUE_PATTERNS if value_patterns is None else tuple(value_patterns)
    )
    compiled_keys = _compile_patterns(key_patterns)
    compiled_vals = _compile_patterns(val_patterns)
    return _redact_inner(payload, compiled_keys, compiled_vals, max_depth)


def _redact_inner(
    value: Any,
    compiled_keys: list[re.Pattern[str]],
    compiled_vals: list[re.Pattern[str]],
    depth: int,
) -> Any:
    """Recursive worker. Splits on type."""
    if depth <= 0:
        # Safety cap: stop recursing. Return the value unchanged so
        # callers don't see surprise REDACTED tokens at depth.
        return value

    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for k, v in value.items():
            key_str = str(k)
            if _key_matches(key_str, compiled_keys):
                # Whole-value redaction. Even if the value itself is a
                # nested structure, we collapse it — that's the point.
                out[key_str] = REDACTED
            else:
                out[key_str] = _redact_inner(
                    v, compiled_keys, compiled_vals, depth - 1
                )
        return out

    if isinstance(value, str):
        if not compiled_vals:
            return value
        return _scrub_string(value, compiled_vals)

    if isinstance(value, (list, tuple, set)):
        return [
            _redact_inner(item, compiled_keys, compiled_vals, depth - 1)
            for item in value
        ]

    # int/float/bool/None/bytes/datetime/etc → unchanged
    return value


def add_secret_key_pattern(pattern: str) -> None:
    """Append ``pattern`` to the module-default secret-key list.

    Mutates module state — intended for callers that want the new
    pattern to apply to every subsequent ``redact()`` without an explicit
    override. Tests should NOT use this (use the override kwargs instead)
    to keep test isolation clean.
    """
    global DEFAULT_SECRET_KEY_PATTERNS  # noqa: PLW0603 — intentional module mutation
    DEFAULT_SECRET_KEY_PATTERNS = DEFAULT_SECRET_KEY_PATTERNS + (pattern,)


def add_value_pattern(pattern: str) -> None:
    """Append ``pattern`` to the module-default value-pattern list.

    See ``add_secret_key_pattern`` for the same caveats.
    """
    global DEFAULT_VALUE_PATTERNS  # noqa: PLW0603 — intentional module mutation
    DEFAULT_VALUE_PATTERNS = DEFAULT_VALUE_PATTERNS + (pattern,)


__all__ = [
    "DEFAULT_SECRET_KEY_PATTERNS",
    "DEFAULT_VALUE_PATTERNS",
    "REDACTED",
    "add_secret_key_pattern",
    "add_value_pattern",
    "redact",
]
