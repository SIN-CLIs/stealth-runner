"""================================================================================
PERSONAS QUARANTINE — File-based store for drifted-persona isolation (SR-170 PR1)
================================================================================

MODUL-KONZEPT (SR-170, 2026-05-13)
-----------------------------------

WARUM ÜBERHAUPT?
    `trajectory_judge.py` liefert nach jedem Run eine `JudgeScoreCard`
    mit 4 Scores. Wenn `min(scores) < quarantine_threshold`, sollte die
    betroffene Persona NICHT für den nächsten Run wiederverwendet
    werden — sie braucht entweder manuelles Review oder ein Re-Train.

    Dieser Store ist der einfachst-mögliche Mechanismus dafür: eine
    JSON-Datei pro quarantänisierter Persona, geordnet unter
    `runs/quarantine/<persona_id>.json`. Beim nächsten Run-Start fragt
    der Persona-Selector über `is_quarantined(persona_id)` ab und
    skippt den Eintrag.

WARUM DATEI-BASIERT?
    • Keine externe Abhängigkeit (SQLite, Redis, Postgres) für eine
      Operation, die typisch < 100 Einträge produziert pro Tag.
    • Atomarität via `os.replace()` — POSIX-rename ist auf gleicher
      FS-Partition atomar, also keine half-written JSONs.
    • Auditbar: `git diff` der `runs/quarantine/` reicht für ein
      menschliches Review, kein SQL nötig.
    • Test-Determinismus: `tmp_path`-Fixture, kein Mock-DB-Tooling.

NICHT-ZIELE
-----------
    Dieses Modul macht KEIN:
      • Persona-Selection-Logic (wo wird die Quarantine konsultiert?
        → das ist Aufgabe des Caller-Codes, z. B. `persona_picker.py`).
      • Persona-Definitionen (siehe Brief-Constraint: nur `persona_id:
        str`-zentriert, keine Persona-Modelle).

TTL / AUTO-RELEASE (SR-247, 2026-05-17)
---------------------------------------
    PR #224 hat TTL/auto-release explizit als out-of-scope deferred:

        > TTL/auto-release policy for quarantine entries; currently every
        > release is manual.

    SR-247 schließt diesen Punkt mit einem opt-in TTL-Feld:

      • quarantine(ttl_seconds=86400) lässt den Eintrag nach 24h ablaufen.
      • is_quarantined() / list_active() behandeln expired Einträge bereits
        als released (read-only — keine Writes auf dem Hot-Path).
      • sweep_expired() ist der explizite Reaper: schreibt Release-Records
        mit reason="ttl_expired:auto" für den Audit-Trail.
      • ttl_seconds=None (default) = altes Verhalten, kein Auto-Release.

    Backward-compatible: alte JSONs ohne ttl_seconds laden weiterhin sauber,
    schema_version bumpt 1→2, from_dict() füllt Default ein.

PUBLIC API
----------
    QuarantineEntry        — frozen dataclass mit Eintrag-Metadaten
    QuarantineError        — Basisklasse für Fehler
    PersonaNotQuarantined  — release() auf non-quarantined ID
    quarantine             — Eintrag anlegen / updaten (optional ttl_seconds)
    is_quarantined         — Bool-Check (TTL-aware)
    list_active            — alle aktiven Einträge (TTL-aware)
    release                — Eintrag schließen (mit Audit-Reason)
    get                    — einzelnen Eintrag lesen (incl. released/expired)
    sweep_expired          — TTL-Reaper: schreibt released_at auf abgelaufene

ADD-HERE-TOO CHECKLIST (when extending this module)
----------------------------------------------------
    [ ] New field on QuarantineEntry?       → update to_dict/from_dict
        AND the JSON schema-version constant AND the migration logic in
        from_dict for old files.
    [ ] New error type?                     → also extend tests.
    [x] Auto-release / TTL?                 → SR-247: opt-in via
        ttl_seconds field; sweep_expired() is the explicit reaper.
        Effective expiry timestamp = quarantined_at + ttl_seconds. Read
        paths (is_quarantined / list_active) treat expired as released
        WITHOUT writing — only sweep_expired() persists the release.

Module Status: NEW (SR-170 Phase PR1, 2026-05-13)
================================================================================
"""

from __future__ import annotations

import json
import os
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional


# ── ERRORS ───────────────────────────────────────────────────────────────────


class QuarantineError(Exception):
    """Base class for all quarantine-store failures."""


class PersonaNotQuarantined(QuarantineError):
    """release() / get() called for a persona_id that has no entry."""


# ── SCHEMA VERSION ───────────────────────────────────────────────────────────


_SCHEMA_VERSION: int = 2
"""
Bump this when QuarantineEntry's on-disk shape changes incompatibly.
The from_dict() loader keeps backward compatibility via the version
field on each JSON file.

Version history:
    1 — initial (SR-170)
    2 — added ttl_seconds field (SR-247)
"""


# ── DATA SHAPE ───────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class QuarantineEntry:
    """
    One quarantine record, on-disk under `<store_root>/<persona_id>.json`.

    Fields:
        persona_id:        opaque caller-chosen identifier (string).
        reason:            free-form why-it-was-quarantined.
        judge_scores:      the JudgeScoreCard.to_dict() that triggered
                           the quarantine. Optional: empty dict if the
                           quarantine was manual.
        quarantined_at:    UNIX epoch seconds (int) when first quarantined.
        released_at:       UNIX epoch seconds (int) when released, or None
                           if still active.
        release_reason:    free-form why-it-was-released, or empty.
        ttl_seconds:       optional integer seconds for auto-release. None
                           (default) = no TTL, behaves exactly like SR-170
                           pre-247. When set, expiry is computed lazily as
                           quarantined_at + ttl_seconds.
        schema_version:    on-disk schema version, see _SCHEMA_VERSION.
    """

    persona_id: str
    reason: str
    judge_scores: dict[str, Any] = field(default_factory=dict)
    quarantined_at: int = 0
    released_at: Optional[int] = None
    release_reason: str = ""
    ttl_seconds: Optional[int] = None
    schema_version: int = _SCHEMA_VERSION

    def is_active(self) -> bool:
        """True iff the entry has not been released yet (TTL-unaware).

        For TTL-aware activity use ``is_active_at(now)``. The legacy
        ``is_active()`` is kept as the historical "released_at is None"
        check so that get() callers and audit tools can distinguish a
        TTL-expired-but-not-yet-swept entry from a manually-released one.
        """
        return self.released_at is None

    def expires_at(self) -> Optional[int]:
        """Return the absolute epoch-seconds at which this entry expires,
        or None if there is no TTL."""
        if self.ttl_seconds is None:
            return None
        return self.quarantined_at + self.ttl_seconds

    def is_active_at(self, now: int) -> bool:
        """True iff the entry is active at wall-clock ``now``.

        Two ways an entry can be inactive:
          1) released_at was explicitly set (manual release, prior sweep).
          2) ttl_seconds is set and quarantined_at + ttl_seconds <= now.

        Read-path callers (is_quarantined, list_active) use this to filter
        TTL-expired entries WITHOUT writing to disk. The actual release
        record is only persisted by sweep_expired().
        """
        if self.released_at is not None:
            return False
        expiry = self.expires_at()
        if expiry is not None and now >= expiry:
            return False
        return True

    def to_dict(self) -> dict[str, Any]:
        """JSON-safe dict; ordered fields for readable git diffs."""
        return {
            "persona_id": self.persona_id,
            "reason": self.reason,
            "judge_scores": dict(self.judge_scores),
            "quarantined_at": self.quarantined_at,
            "released_at": self.released_at,
            "release_reason": self.release_reason,
            "ttl_seconds": self.ttl_seconds,
            "schema_version": self.schema_version,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> QuarantineEntry:
        """
        Reconstruct from on-disk JSON. Tolerates older schema versions
        by filling missing fields with safe defaults.

        Schema-1 files (pre-SR-247) lack ``ttl_seconds`` and are loaded
        with ttl_seconds=None — their behaviour is unchanged.
        """
        ttl_raw = data.get("ttl_seconds")
        ttl_value: Optional[int]
        if ttl_raw is None:
            ttl_value = None
        else:
            ttl_value = int(ttl_raw)
            if ttl_value <= 0:
                # Defensive: reject silly values from corrupted manifests.
                ttl_value = None
        return cls(
            persona_id=str(data["persona_id"]),
            reason=str(data.get("reason", "")),
            judge_scores=dict(data.get("judge_scores", {})),
            quarantined_at=int(data.get("quarantined_at", 0)),
            released_at=(
                int(data["released_at"]) if data.get("released_at") is not None else None
            ),
            release_reason=str(data.get("release_reason", "")),
            ttl_seconds=ttl_value,
            schema_version=int(data.get("schema_version", 0)),
        )


# ── STORE ROOT (DEFAULT) ─────────────────────────────────────────────────────


_DEFAULT_STORE_RELPATH: str = "runs/quarantine"
"""Relative to repo-root / $STEALTH_RUNNER_ROOT / cwd."""


def _resolve_store_root(store_root: Optional[Path]) -> Path:
    """
    Decide where the quarantine JSONs live.

    Order:
        1. Explicit `store_root` arg.
        2. $STEALTH_RUNNER_ROOT env var (joined with default subdir).
        3. CWD / default subdir.

    Auto-creates the directory.
    """
    if store_root is not None:
        resolved = Path(store_root)
    else:
        env_root = os.environ.get("STEALTH_RUNNER_ROOT")
        base = Path(env_root) if env_root else Path.cwd()
        resolved = base / _DEFAULT_STORE_RELPATH
    resolved.mkdir(parents=True, exist_ok=True)
    return resolved


def _entry_path(store_root: Path, persona_id: str) -> Path:
    """
    Build the on-disk path for one persona_id.

    Sanitization: replace any character that is not [A-Za-z0-9._-] with
    '_'. We keep this minimal — the caller controls persona_id and is
    expected to use opaque tokens, not user input.
    """
    safe = "".join(c if (c.isalnum() or c in "._-") else "_" for c in persona_id)
    if not safe or safe.startswith("."):
        raise ValueError(
            f"persona_id sanitizes to empty/hidden filename: {persona_id!r}"
        )
    return store_root / f"{safe}.json"


# ── ATOMIC WRITE ─────────────────────────────────────────────────────────────


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    """
    Write JSON via `tmp + os.replace()`. On POSIX, replace() is atomic
    within one filesystem, so a reader either sees the old file or the
    new file — never a half-written one.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    # NamedTemporaryFile in the same directory ensures replace() is
    # cross-link compatible (same FS partition).
    fd, tmp_path_str = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
    )
    tmp_path = Path(tmp_path_str)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2, sort_keys=False)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp_path, path)
    except Exception:
        # Best-effort cleanup; we never want stale .tmp files hanging around.
        try:
            tmp_path.unlink(missing_ok=True)
        except Exception:
            pass
        raise


# ── PUBLIC API ───────────────────────────────────────────────────────────────


def quarantine(
    persona_id: str,
    reason: str,
    judge_scores: Optional[dict[str, Any]] = None,
    *,
    ttl_seconds: Optional[int] = None,
    store_root: Optional[Path] = None,
    now: Optional[int] = None,
) -> QuarantineEntry:
    """
    Quarantine a persona, or re-quarantine an already-active one.

    Semantics:
      • If `persona_id` is not quarantined yet:        create new active entry.
      • If `persona_id` IS already active:             update reason/scores,
                                                       keep original
                                                       quarantined_at.
                                                       ttl_seconds, if given,
                                                       overrides the prior
                                                       value. Pass None
                                                       explicitly to clear it.
      • If `persona_id` was previously released:       create a new active
                                                       entry, with a fresh
                                                       quarantined_at (i.e.,
                                                       the release record is
                                                       overwritten — caller
                                                       should grep audit log
                                                       if the history matters).

    Args:
        persona_id:    opaque identifier; must sanitize to a non-empty filename.
        reason:        free-form. Will be persisted verbatim.
        judge_scores:  optional dict (e.g. JudgeScoreCard.to_dict()).
        ttl_seconds:   optional integer seconds for auto-release. Must be > 0
                       if not None. Default None = no TTL (legacy behaviour).
        store_root:    optional path override; default = repo-rooted runs/quarantine.
        now:           optional epoch-seconds injection for test determinism.

    Returns:
        The QuarantineEntry as written.

    Raises:
        ValueError: if ttl_seconds is not None and not a positive integer.
    """
    if ttl_seconds is not None and ttl_seconds <= 0:
        raise ValueError(
            f"ttl_seconds must be positive int or None; got {ttl_seconds!r}"
        )

    root = _resolve_store_root(store_root)
    path = _entry_path(root, persona_id)
    timestamp = int(now if now is not None else time.time())

    # If an active entry exists, preserve its `quarantined_at` for audit.
    quarantined_at = timestamp
    if path.is_file():
        try:
            existing = QuarantineEntry.from_dict(json.loads(path.read_text("utf-8")))
            if existing.is_active():
                quarantined_at = existing.quarantined_at or timestamp
        except (json.JSONDecodeError, KeyError, ValueError):
            # Corrupt file → overwrite with fresh entry. Don't crash the caller.
            pass

    entry = QuarantineEntry(
        persona_id=persona_id,
        reason=reason,
        judge_scores=dict(judge_scores or {}),
        quarantined_at=quarantined_at,
        released_at=None,
        release_reason="",
        ttl_seconds=ttl_seconds,
        schema_version=_SCHEMA_VERSION,
    )
    _atomic_write_json(path, entry.to_dict())
    return entry


def is_quarantined(
    persona_id: str,
    *,
    store_root: Optional[Path] = None,
    now: Optional[int] = None,
) -> bool:
    """
    True iff there is an active (un-released, un-expired) quarantine
    for this persona_id.

    Released entries return False — they are kept on disk for audit but
    do not block the persona from being re-used.

    TTL-expired entries (SR-247): also return False. The on-disk file is
    NOT mutated by this read-path call — it stays in the "lazy expired"
    state until sweep_expired() persists the release record.

    Args:
        now: optional epoch-seconds injection for test determinism. Used
             to evaluate TTL expiry. Default = wall-clock time.
    """
    root = _resolve_store_root(store_root)
    path = _entry_path(root, persona_id)
    if not path.is_file():
        return False
    try:
        entry = QuarantineEntry.from_dict(json.loads(path.read_text("utf-8")))
    except (json.JSONDecodeError, KeyError, ValueError):
        # Corrupt file → fail-safe: treat as quarantined so the caller
        # surfaces the corruption instead of silently using the persona.
        return True
    timestamp = int(now if now is not None else time.time())
    return entry.is_active_at(timestamp)


def list_active(
    *,
    store_root: Optional[Path] = None,
    now: Optional[int] = None,
) -> list[QuarantineEntry]:
    """
    Return every currently-active quarantine, ordered by quarantined_at ASC.

    Released entries are NOT included. TTL-expired entries are NOT included
    (filtered via is_active_at(now), no writes). Corrupt files are skipped
    silently (use ``get(persona_id)`` for diagnostics on a specific id).
    """
    root = _resolve_store_root(store_root)
    timestamp = int(now if now is not None else time.time())
    entries: list[QuarantineEntry] = []
    for path in sorted(root.glob("*.json")):
        try:
            entry = QuarantineEntry.from_dict(json.loads(path.read_text("utf-8")))
        except (json.JSONDecodeError, KeyError, ValueError):
            continue
        if entry.is_active_at(timestamp):
            entries.append(entry)
    entries.sort(key=lambda e: e.quarantined_at)
    return entries


def release(
    persona_id: str,
    override_reason: str,
    *,
    store_root: Optional[Path] = None,
    now: Optional[int] = None,
) -> QuarantineEntry:
    """
    Mark an active quarantine as released.

    The on-disk file is REWRITTEN with `released_at` and `release_reason`
    set; it is NOT deleted, so audit greps still find the history.

    Args:
        persona_id:       must currently be active.
        override_reason:  free-form justification, e.g. "false positive,
                          manual review confirmed persona OK".
        store_root:       optional override.
        now:              optional epoch-seconds for test determinism.

    Returns:
        The QuarantineEntry as written (now in released state).

    Raises:
        PersonaNotQuarantined: if the persona is not currently quarantined
                               (either no entry, or entry already released).
    """
    root = _resolve_store_root(store_root)
    path = _entry_path(root, persona_id)
    if not path.is_file():
        raise PersonaNotQuarantined(
            f"persona_id {persona_id!r} has no quarantine entry to release."
        )
    try:
        existing = QuarantineEntry.from_dict(json.loads(path.read_text("utf-8")))
    except (json.JSONDecodeError, KeyError, ValueError) as exc:
        raise QuarantineError(
            f"Quarantine file for {persona_id!r} is corrupt: {exc!s}"
        ) from exc

    if not existing.is_active():
        raise PersonaNotQuarantined(
            f"persona_id {persona_id!r} is already released "
            f"(at epoch {existing.released_at})."
        )

    timestamp = int(now if now is not None else time.time())
    released = QuarantineEntry(
        persona_id=existing.persona_id,
        reason=existing.reason,
        judge_scores=existing.judge_scores,
        quarantined_at=existing.quarantined_at,
        released_at=timestamp,
        release_reason=override_reason,
        ttl_seconds=existing.ttl_seconds,
        schema_version=_SCHEMA_VERSION,
    )
    _atomic_write_json(path, released.to_dict())
    return released


def sweep_expired(
    *,
    store_root: Optional[Path] = None,
    now: Optional[int] = None,
    release_reason: str = "ttl_expired:auto",
) -> list[QuarantineEntry]:
    """
    Persist release records for every TTL-expired entry. SR-247 reaper.

    Walks the store, finds entries that satisfy ``not is_active() but
    quarantined_at + ttl_seconds <= now AND released_at is None``, and
    writes a release record (released_at=now, release_reason given) to
    each. Entries without a TTL, already-released, or not-yet-expired
    entries are skipped.

    This is the ONLY write path that is intended to be triggered on a
    schedule (cron / startup hook). Read paths (is_quarantined,
    list_active) deliberately do NOT mutate the store — that keeps the
    hot path I/O-cheap and the sweep auditable as a single batch.

    Args:
        store_root:     optional path override.
        now:            optional epoch-seconds for test determinism.
        release_reason: text to store in release_reason. Default is the
                        canonical "ttl_expired:auto" so audit greps can
                        distinguish auto from manual releases.

    Returns:
        List of QuarantineEntry records that were swept (after writing).
        Ordered by quarantined_at ASC. Empty list if nothing to do.
    """
    root = _resolve_store_root(store_root)
    timestamp = int(now if now is not None else time.time())
    swept: list[QuarantineEntry] = []
    for path in sorted(root.glob("*.json")):
        try:
            entry = QuarantineEntry.from_dict(json.loads(path.read_text("utf-8")))
        except (json.JSONDecodeError, KeyError, ValueError):
            continue
        if entry.released_at is not None:
            continue
        expiry = entry.expires_at()
        if expiry is None or timestamp < expiry:
            continue
        # Eligible — write release record.
        released = QuarantineEntry(
            persona_id=entry.persona_id,
            reason=entry.reason,
            judge_scores=entry.judge_scores,
            quarantined_at=entry.quarantined_at,
            released_at=timestamp,
            release_reason=release_reason,
            ttl_seconds=entry.ttl_seconds,
            schema_version=_SCHEMA_VERSION,
        )
        _atomic_write_json(path, released.to_dict())
        swept.append(released)
    swept.sort(key=lambda e: e.quarantined_at)
    return swept


def get(
    persona_id: str,
    *,
    store_root: Optional[Path] = None,
) -> QuarantineEntry:
    """
    Read one entry (active or released) for diagnostics.

    Raises PersonaNotQuarantined if no entry exists at all. Distinct
    from is_quarantined() which is a fast boolean; this returns the
    full record incl. history.
    """
    root = _resolve_store_root(store_root)
    path = _entry_path(root, persona_id)
    if not path.is_file():
        raise PersonaNotQuarantined(
            f"persona_id {persona_id!r} has no quarantine entry."
        )
    try:
        return QuarantineEntry.from_dict(json.loads(path.read_text("utf-8")))
    except (json.JSONDecodeError, KeyError, ValueError) as exc:
        raise QuarantineError(
            f"Quarantine file for {persona_id!r} is corrupt: {exc!s}"
        ) from exc


# ── PUBLIC RE-EXPORTS ────────────────────────────────────────────────────────


__all__ = [
    "PersonaNotQuarantined",
    "QuarantineEntry",
    "QuarantineError",
    "get",
    "is_quarantined",
    "list_active",
    "quarantine",
    "release",
    "sweep_expired",
]
