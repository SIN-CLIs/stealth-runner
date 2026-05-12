"""SR-112 #112 — read-only per-keyword inverse-lookup fuer audit-records.

================================================================================
ZWECK
================================================================================

Die learn-Pipeline hat aktuell zwei aggregierende read-only Views:

  - ``status``  (#104) — Inbox-side: was wartet noch?
  - ``audit``   (#109 / PR #111) — Apply-side aggregate: was wurde global
                                    angewandt / verworfen?

Dieses Modul ergaenzt die **dritte Perspektive**: Apply-side **per-keyword
inverse-lookup**. Use-cases:

  1. Reviewer findet einen verdaechtigen ``FIELD_PATTERNS``-Eintrag und
     will dessen Provenance verifizieren — bevor er rueckwaerts editiert.
  2. LLM (Phase 2, #56) hat einen Fehler gemacht — Operator will den
     genauen ``prompt_hash`` + ``model`` finden um den Fall zu
     reproduzieren.
  3. Audit-trail: "Welche records haben ``phone`` in den letzten 30 Tagen
     applied?" — granular pro-keyword statt aggregiert.

================================================================================
DATEN-QUELLE
================================================================================

Liest dieselbe Datei wie ``audit`` — ``logs/learn-applied-{ISO}.jsonl`` aus
``apply.py:audit_records``. Schema verifiziert in ``apply.py:595-655``:

  applied:                {decision, family, keyword, source, confidence,
                           model, prompt_hash, timestamp}
  rejected_by_gate:       {decision, reason, entry}
  rejected_by_reviewer:   {decision, entry}
  rejected_by_ast:        {decision, reason, entry}

Reject-records haben source/family/timestamp nur in ``entry`` — defensive
fallback-Kette in den ``_normalize_*`` Helpern unten.

================================================================================
ARCHITEKTUR-ENTSCHEIDUNGEN
================================================================================

A) **Strict read-only.** Modul importiert weder ``apply`` noch
   ``aggregator`` noch ``status``/``audit``. ``find_explanations`` ist
   eine pure-function-Pipeline. CLI macht alle file-I/O.

B) **Self-contained normalizers** (NICHT shared mit audit.py).
   Audit.py wurde in PR #111 eingefuehrt, ist aber zum Zeitpunkt der
   #112-Implementation noch nicht auf main gemerged. Defensive
   Duplikation der ~30 LOC Helpern statt Soft-Dependency auf un-merged
   PR. Nach beiden Merges kann ein Follow-up sie konsolidieren.

C) **Auto-detect match-mode.** Query mit ``:`` -> ``label`` (role:label
   tuple). Sonst Default ``keyword`` (substring match gegen ``keyword``
   field bei applied UND gegen ``entry.normalized_label`` bei rejects).
   ``--by`` overridet auto-detect.

D) **Case-insensitive substring** — Operator typt schnell. Exact-match
   waere zu strikt fuer eine Diagnostik-Funktion.

E) **Sortierung: newest first.** Records ohne timestamp sortieren ans
   Ende (defensiv — sortable=False rang).

F) **Reject-records sind opt-in.** Default applied-only (80%-Use-case:
   "was hat es ins Pattern geschafft?"). ``--include-rejects`` schaltet
   sie zu fuer "warum NICHT applied"-Diagnose.

G) **File-origin als ``__file__`` key.** CLI attached pro Record ein
   internes Marker-Feld (``__file__``: basename des origin jsonl); die
   pure-functions geben es via ``Explanation.log_file`` weiter. Internes
   Feld mit dunder-Prefix damit es nicht mit echten Schema-Feldern
   kollidiert.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, List, Literal, Optional, Tuple


MatchMode = Literal["auto", "keyword", "family", "label"]


# -- Public types ------------------------------------------------------------


@dataclass(frozen=True)
class Explanation:
    """Ein einzelner audit-record als reviewer-friendly snapshot.

    Felder spiegeln das applied-record-Schema mit defensiv-defaultierten
    Werten fuer rejects (z.B. confidence=None wenn nicht im record).
    ``log_file`` ist der basename der jsonl-Datei aus der dieser record
    gelesen wurde (None wenn caller keine origin-info attached hat).
    """

    decision: str
    family: Optional[str]
    keyword: Optional[str]
    role: Optional[str]
    label: Optional[str]  # normalized_label aus entry (reject) oder None
    source: str
    confidence: Optional[float]
    model: Optional[str]
    prompt_hash: Optional[str]
    timestamp_iso: Optional[str]
    log_file: Optional[str]
    reason: Optional[str]  # nur fuer rejects


# -- Normalizers (self-contained; duplicate-by-design vs audit.py #111) ----


def _normalize_decision(record: dict) -> str:
    """Default ``"applied"`` fuer records ohne decision-Feld (defensive)."""
    return str(record.get("decision") or "applied")


def _normalize_source(record: dict) -> str:
    """Source fallback: top-level -> entry.source -> ``"substring"``."""
    src = record.get("source")
    if src:
        return str(src)
    entry = record.get("entry") or {}
    return str(entry.get("source") or "substring")


def _normalize_family(record: dict) -> Optional[str]:
    """Family fallback: top-level -> entry.suggested_family -> None.

    None means "kein family bucket" (rejects ohne suggestion).
    """
    fam = record.get("family")
    if fam:
        return str(fam)
    entry = record.get("entry") or {}
    fam2 = entry.get("suggested_family")
    return str(fam2) if fam2 else None


def _normalize_role(record: dict) -> Optional[str]:
    """Role kommt fuer applied UND rejects aus ``entry.role`` (falls vorh).

    Applied-records haben keine eigene role; nur wenn der record auch
    ein entry-dict mitschleppt (z.B. aus debug-mode), wird sie sichtbar.
    """
    entry = record.get("entry") or {}
    role = entry.get("role")
    return str(role) if role else None


def _normalize_label(record: dict) -> Tuple[Optional[str], Optional[str]]:
    """(role, label) tuple fuer matching/anzeige.

    Applied:    role aus entry (oft leer), label = top-level keyword
    Rejected:   role aus entry, label = entry.normalized_label
    Return (None, None) wenn nichts extrahierbar.
    """
    entry = record.get("entry") or {}
    role = entry.get("role")
    role_str = str(role) if role else None

    if "keyword" in record and record["keyword"]:
        return (role_str, str(record["keyword"]))

    nl = entry.get("normalized_label")
    if nl:
        return (role_str, str(nl))

    return (role_str, None)


def _parse_iso(raw) -> Optional[datetime]:
    """Tolerantes ISO-parsing. Akzeptiert ``Z``-suffix + naive datetimes."""
    if isinstance(raw, datetime):
        return raw if raw.tzinfo else raw.replace(tzinfo=timezone.utc)
    try:
        dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return None


def _extract_timestamp(record: dict) -> Optional[datetime]:
    """Priority: top-level timestamp -> entry.first_seen -> entry.created_at -> entry.ts.

    Return None wenn nirgendwo parseable.
    """
    raw = record.get("timestamp")
    if raw:
        dt = _parse_iso(raw)
        if dt is not None:
            return dt
    entry = record.get("entry") or {}
    for key in ("first_seen", "created_at", "ts"):
        raw = entry.get(key)
        if not raw:
            continue
        dt = _parse_iso(raw)
        if dt is not None:
            return dt
    return None


# -- Match logic -------------------------------------------------------------


def detect_match_mode(query: str) -> MatchMode:
    """Auto-detect mode from query content.

    ``role:label`` syntax (with colon) -> ``label`` mode.
    Default fallback -> ``keyword`` (most common operator query).

    Family-only matching nie auto-detected -- Operator muss ``--by family``
    explizit setzen, sonst koennte ``"phone"`` versehentlich auf keywords
    wie ``"phone_number"`` matchen (was meistens gewollt ist).
    """
    if ":" in query:
        return "label"
    return "keyword"


def _matches_keyword(record: dict, query_lower: str) -> bool:
    """Case-insensitive substring against keyword OR entry.normalized_label."""
    kw = record.get("keyword")
    if kw and query_lower in str(kw).lower():
        return True
    entry = record.get("entry") or {}
    nl = entry.get("normalized_label")
    if nl and query_lower in str(nl).lower():
        return True
    return False


def _matches_family(record: dict, query_lower: str) -> bool:
    """Case-insensitive substring against family (top-level or entry)."""
    fam = _normalize_family(record)
    return fam is not None and query_lower in fam.lower()


def _matches_label(record: dict, query: str) -> bool:
    """Match ``role:label`` tuple, case-insensitive. Substring on both halves.

    If query has no ``:``, treat whole string as label-part (role = wildcard).
    """
    if ":" in query:
        role_q, label_q = query.split(":", 1)
        role_q = role_q.strip().lower()
        label_q = label_q.strip().lower()
    else:
        role_q = ""
        label_q = query.strip().lower()

    role, label = _normalize_label(record)
    if label_q:
        if not label or label_q not in label.lower():
            return False
    if role_q:
        if not role or role_q not in role.lower():
            return False
    return True


def record_matches(record: dict, query: str, mode: MatchMode) -> bool:
    """Dispatch matcher based on mode. ``auto`` resolves via detect_match_mode."""
    if mode == "auto":
        mode = detect_match_mode(query)
    q_lower = query.lower()
    if mode == "keyword":
        return _matches_keyword(record, q_lower)
    if mode == "family":
        return _matches_family(record, q_lower)
    if mode == "label":
        return _matches_label(record, query)
    # Unknown mode -> no match (defensive)
    return False


# -- Core pipeline -----------------------------------------------------------


def _to_explanation(record: dict) -> Explanation:
    """Lift a raw record into the Explanation snapshot dataclass."""
    role, label = _normalize_label(record)
    ts = _extract_timestamp(record)
    ts_iso = ts.isoformat() if ts is not None else None

    return Explanation(
        decision=_normalize_decision(record),
        family=_normalize_family(record),
        keyword=(str(record["keyword"])
                 if record.get("keyword") else None),
        role=role,
        label=label,
        source=_normalize_source(record),
        confidence=(float(record["confidence"])
                    if record.get("confidence") is not None else None),
        model=(str(record["model"]) if record.get("model") else None),
        prompt_hash=(str(record["prompt_hash"])
                     if record.get("prompt_hash") else None),
        timestamp_iso=ts_iso,
        log_file=(str(record["__file__"])
                  if record.get("__file__") else None),
        reason=(str(record["reason"]) if record.get("reason") else None),
    )


def find_explanations(
    records: Iterable[dict],
    query: str,
    mode: MatchMode = "auto",
    limit: int = 5,
    include_rejects: bool = False,
) -> List[Explanation]:
    """Filter + sort + limit pipeline.

    Args:
        records:          Iterable of raw audit-records. CLI attached
                          ``__file__`` key per record (optional).
        query:            User query string. Case-insensitive substring.
        mode:             ``"auto" | "keyword" | "family" | "label"``.
        limit:            Max number of explanations returned.
        include_rejects:  If False (default), only applied-records are
                          considered. If True, rejects are included.

    Returns:
        List of Explanation objects, newest first. Records without a
        parseable timestamp sort to the end (stable within the group).
    """
    matched: List[Explanation] = []
    for rec in records:
        decision = _normalize_decision(rec)
        if not include_rejects and decision != "applied":
            continue
        if not record_matches(rec, query, mode):
            continue
        matched.append(_to_explanation(rec))

    # Sort: newest first, records without timestamp go to end.
    # We use a tuple key (has_timestamp_bool_inverted, -timestamp) so that
    # records with timestamps sort first by (False, ...) tuple-prefix, and
    # records without sort last by (True, ...).
    def sort_key(e: Explanation):
        if e.timestamp_iso is None:
            return (1, "")  # ans Ende
        return (0, e.timestamp_iso)  # ISO strings sortieren chronologisch

    matched.sort(key=sort_key, reverse=False)
    # Within "has timestamp" group we want newest first -> reverse twice
    # logic: easier to split, sort each, concat.
    with_ts = [e for e in matched if e.timestamp_iso is not None]
    no_ts = [e for e in matched if e.timestamp_iso is None]
    with_ts.sort(key=lambda e: e.timestamp_iso or "", reverse=True)
    result = with_ts + no_ts

    if limit > 0:
        result = result[:limit]
    return result


# -- Formatters --------------------------------------------------------------


def _fmt_value(value, fallback: str = "(n/a)") -> str:
    if value is None or value == "":
        return fallback
    return str(value)


def format_human_report(
    explanations: List[Explanation],
    query: str,
    match_mode: MatchMode,
    limit: int,
    include_rejects: bool,
    reject_count_excluded: int = 0,
) -> str:
    """Human-readable rendering. Header + per-explanation block.

    ``reject_count_excluded``: caller computes how many rejects matched
    the query but were excluded by ``--include-rejects``-being-off; this
    becomes a hint at the bottom ("0 reject records matched; use
    --include-rejects to include them").
    """
    if match_mode == "auto":
        # Resolve for display
        match_mode = detect_match_mode(query)

    lines: List[str] = []
    lines.append(
        f"[learn] explain query: {query!r}  "
        f"(matched as {match_mode})"
    )
    lines.append("")

    if not explanations:
        lines.append(
            f"No audit-record matched query {query!r} "
            f"in mode={match_mode!r}."
        )
        if not include_rejects and reject_count_excluded > 0:
            lines.append(
                f"({reject_count_excluded} reject record(s) matched but "
                f"are excluded; use --include-rejects to include them.)"
            )
        return "\n".join(lines)

    lines.append(
        f"Found {len(explanations)} audit-record(s) "
        f"(newest first), limit={limit}:"
    )
    lines.append("")

    for i, exp in enumerate(explanations, start=1):
        lines.append(
            f"[{i}] {_fmt_value(exp.timestamp_iso)}  {exp.decision}"
        )
        if exp.family:
            lines.append(f"    family:       {exp.family}")
        if exp.keyword:
            lines.append(f"    keyword:      {exp.keyword}")
        elif exp.label:
            lines.append(f"    label:        {exp.label}")
        if exp.role:
            lines.append(f"    role:         {exp.role}")
        lines.append(f"    source:       {exp.source}")
        if exp.confidence is not None:
            lines.append(f"    confidence:   {exp.confidence:.2f}")
        lines.append(f"    model:        {_fmt_value(exp.model)}")
        if exp.prompt_hash:
            lines.append(f"    prompt_hash:  {exp.prompt_hash}")
        if exp.reason:
            lines.append(f"    reason:       {exp.reason}")
        if exp.log_file:
            lines.append(f"    log-file:     {exp.log_file}")
        lines.append("")

    if not include_rejects and reject_count_excluded > 0:
        lines.append(
            f"({reject_count_excluded} reject record(s) also matched but "
            f"are excluded; use --include-rejects to include them.)"
        )

    return "\n".join(lines).rstrip()


def report_to_json(
    explanations: List[Explanation],
    query: str,
    match_mode: MatchMode,
    limit: int,
    include_rejects: bool,
    total_matches: Optional[int] = None,
) -> dict:
    """Machine-readable JSON-serializable view.

    ``total_matches`` defaults to ``len(explanations)`` if not given.
    """
    if match_mode == "auto":
        match_mode = detect_match_mode(query)

    return {
        "query": query,
        "match_mode": match_mode,
        "limit": limit,
        "include_rejects": include_rejects,
        "total_matches": (total_matches if total_matches is not None
                          else len(explanations)),
        "explanations": [
            {
                "decision": e.decision,
                "family": e.family,
                "keyword": e.keyword,
                "role": e.role,
                "label": e.label,
                "source": e.source,
                "confidence": e.confidence,
                "model": e.model,
                "prompt_hash": e.prompt_hash,
                "timestamp": e.timestamp_iso,
                "log_file": e.log_file,
                "reason": e.reason,
            }
            for e in explanations
        ],
    }
