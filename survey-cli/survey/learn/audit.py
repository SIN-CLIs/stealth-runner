"""SR-109 #109 — read-only audit-log dashboard fuer apply-side records.

================================================================================
ZWECK
================================================================================

``survey learn status`` (SR-104 #104) zeigt die Inbox-Seite: was wartet noch?
Dieses Modul ist die symmetrische Apply-Seite: **was wurde schon angewendet
(oder verworfen), mit welcher Entscheidung, von welcher Source, ueber welches
Modell?**

``apply.py`` schreibt jeden Run in ``logs/learn-applied-{YYYYmmddTHHMMSSZ}.jsonl``.
Pro Inbox-Eintrag wird genau ein audit-record geschrieben mit einer von vier
``decision``-werten:

  - ``applied``               — keyword wurde in FIELD_PATTERNS eingebaut
  - ``rejected_by_gate``      — confidence < gate / source-typ-policy
  - ``rejected_by_reviewer``  — Mensch hat ``r`` gewaehlt (interactive mode)
  - ``rejected_by_ast``       — AST-Mutation failed (z.B. duplicate keyword)

Felder-schema (verifiziert in ``apply.py:595-655``):

  - **applied**:               ``decision``, ``family``, ``keyword``,
                               ``source``, ``confidence``, ``model``,
                               ``prompt_hash``, ``timestamp``
  - **rejected_by_gate**:      ``decision``, ``reason``, ``entry``
                               (= ``InboxEntry.__dict__``)
  - **rejected_by_reviewer**:  ``decision``, ``entry``
  - **rejected_by_ast**:       ``decision``, ``reason``, ``entry``

Reject-records haben **kein** top-level ``source``/``family``/``timestamp``;
diese muessen aus ``entry`` extrahiert werden. Die Normalizer unten erledigen
das defensiv.

================================================================================
ARCHITEKTUR-ENTSCHEIDUNGEN
================================================================================

A) **Strict read-only.** Dieses Modul importiert weder ``apply`` noch
   ``aggregator`` noch ``status``. Der AuditReport ist ein passiver
   dataclass-snapshot. CLI macht alle file-I/O.

B) **Defensive field-extraction.** Reject-records haben source/family/
   timestamp NUR in ``entry``-dict. ``_normalize_*`` Helper folgen einer
   fallback-Kette (top-level -> entry -> default). Spiegelt das Pattern
   aus ``status.py:_normalize_source``.

C) **Top-N truncation passiert spaet.** ``summarize_audit`` haelt alle
   Counter-objects vollstaendig; ``format_*`` Helpers schneiden nach top-N.
   Macht Tests trivial (vollstaendige counts verifizierbar).

D) **Filter-Reihenfolge: decision -> source -> family -> since.** AND-
   kombiniert. Identisch zur ``status.py``-Konvention.

E) **``--since`` filtert auf per-record ``timestamp``.** Applied-records
   haben top-level ``timestamp`` (ISO-string). Reject-records haben kein
   timestamp -- wir fallback auf ``entry.first_seen`` / ``entry.created_at``
   / ``entry.ts`` (gleiche Priority wie ``status.py``). Records ohne
   irgendeinen timestamp passieren den ``--since``-Filter NICHT (defensive:
   kein false-positive in time-range scans).

F) **``by_model`` ist neu vs. SR-104.** Zaehlt NUR applied-records mit
   nicht-leerem ``model``. Gibt einem Operator Einsicht ob die
   LLM-Phase-2 (#56) tatsaechlich Beitrag liefert vs. nur substring.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Iterable, List, Literal, Optional


# -- Types -------------------------------------------------------------------


DecisionFilter = Literal[
    "all",
    "applied",
    "rejected_by_gate",
    "rejected_by_reviewer",
    "rejected_by_ast",
]
SourceFilter = Literal["all", "substring", "llm"]


@dataclass(frozen=True)
class AuditFilters:
    """User-facing filter selectors fuer ``summarize_audit``.

    Alle defaulten auf ``"all"`` / None; combination ist AND. ``since`` ist
    eine tz-aware ``datetime`` (oder None = kein time-filter). Family ist
    case-sensitive exakter Match.
    """

    decision: DecisionFilter = "all"
    source: SourceFilter = "all"
    family: Optional[str] = None
    since: Optional[datetime] = None


@dataclass
class AuditReport:
    """Aggregate snapshot ueber (gefilterte) audit-record-Liste.

    Counter-objects sind vollstaendig (kein top-N hier; Formatter schneiden).
    ``first_applied_iso`` / ``last_applied_iso`` werden NUR aus applied-
    records gezogen (Operator interessiert die Tracking-Range der
    angewandten Aenderungen, nicht die der rejects).
    """

    total_records: int = 0
    files_scanned: int = 0
    by_decision: Counter = field(default_factory=Counter)
    # Folgende drei zaehlen NUR applied-records:
    by_source_applied: Counter = field(default_factory=Counter)
    families_applied: Counter = field(default_factory=Counter)
    labels_applied: Counter = field(default_factory=Counter)  # key=(role,label)
    by_model: Counter = field(default_factory=Counter)
    first_applied_iso: Optional[str] = None
    last_applied_iso: Optional[str] = None

    def has_applied(self) -> bool:
        """True iff at least one record passed filters AND decision=applied."""
        return self.by_decision.get("applied", 0) > 0


# -- Normalizers (defensive against schema-drift between record types) ------


def _normalize_decision(record: dict) -> str:
    """Default to "applied" fuer records ohne decision-Feld.

    ``apply.py`` schreibt ``decision`` immer; dieser default ist defensive
    fuer hypothetische legacy-records (die nicht existieren sollten).
    """
    return str(record.get("decision") or "applied")


def _normalize_source(record: dict) -> str:
    """Source-fallback-Kette: top-level -> entry.source -> "substring".

    Spiegelt ``status.py:_normalize_source`` UND ``review.py:normalize_source``
    -- alle drei Module nehmen denselben default. Reject-records haben
    source nur in ``entry``.
    """
    src = record.get("source")
    if src:
        return str(src)
    entry = record.get("entry") or {}
    return str(entry.get("source") or "substring")


def _normalize_family(record: dict) -> Optional[str]:
    """Family-fallback: top-level family -> entry.suggested_family -> None.

    Returns None bei records ohne family. NICHT ``"<NEW>"`` wie in status.py --
    audit-records ohne family sind by-design (rejects ohne suggestion).
    """
    fam = record.get("family")
    if fam:
        return str(fam)
    entry = record.get("entry") or {}
    fam2 = entry.get("suggested_family")
    return str(fam2) if fam2 else None


def _normalize_label(record: dict) -> Optional[tuple]:
    """(role, label) tuple fuer applied/reject records, oder None.

    Applied: top-level ``keyword`` (no role; we synthesize role from entry
    if present, else empty-string).
    Rejects: aus ``entry`` (role + normalized_label).
    """
    entry = record.get("entry") or {}
    if "keyword" in record:
        # applied-record: keyword direkt, role aus entry falls vorhanden
        role = str(entry.get("role") or "")
        label = str(record["keyword"])
        return (role, label)
    role = str(entry.get("role") or "")
    label = str(entry.get("normalized_label") or "")
    if not label:
        return None
    return (role, label)


def _parse_iso(raw) -> Optional[datetime]:
    """Tolerantes ISO-parsing. Akzeptiert ``Z``-suffix und datetime-instances."""
    if isinstance(raw, datetime):
        return raw if raw.tzinfo else raw.replace(tzinfo=timezone.utc)
    try:
        dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return None


def _extract_timestamp(record: dict) -> Optional[datetime]:
    """tz-aware datetime fuer ``--since``-filter.

    Priority:
      1. ``record["timestamp"]``             (applied records, set by apply.py)
      2. ``record["entry"]["first_seen"]``   (rejected records, from InboxEntry)
      3. ``record["entry"]["created_at"]``
      4. ``record["entry"]["ts"]``

    Return None wenn nirgendwo ein parseable ISO-string steht. Pure
    defensive: Records ohne timestamp werden vom ``--since``-Filter
    AUSGESCHLOSSEN (kein false-positive).
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


# -- Filtering ---------------------------------------------------------------


def passes_filters(record: dict, filters: AuditFilters) -> bool:
    """AND-combine decision + source + family + since filter.

    Reihenfolge: decision -> source -> family -> since (cheapest first).
    Pure predicate; kein Side-effect.
    """
    if filters.decision != "all":
        if _normalize_decision(record) != filters.decision:
            return False
    if filters.source != "all":
        if _normalize_source(record) != filters.source:
            return False
    if filters.family is not None:
        if _normalize_family(record) != filters.family:
            return False
    if filters.since is not None:
        ts = _extract_timestamp(record)
        if ts is None or ts < filters.since:
            return False
    return True


# -- Core summarization ------------------------------------------------------


def summarize_audit(
    records: Iterable[dict],
    filters: AuditFilters = AuditFilters(),
    files_scanned: int = 0,
) -> AuditReport:
    """Build ``AuditReport`` aus einer (potenziell gefilterten) Record-Liste.

    Args:
        records:        Iterable von audit-records (aus ``learn-applied-*.jsonl``).
        filters:        AND-filters auf decision/source/family/since.
        files_scanned:  Caller passt diesen counter durch (nur fuer Anzeige).

    Returns:
        ``AuditReport`` dataclass mit vollstaendigen Counter-objects. Top-N
        wird in formatter angewandt (consistent with status.py).
    """
    report = AuditReport(files_scanned=files_scanned)

    first_dt: Optional[datetime] = None
    last_dt: Optional[datetime] = None

    for rec in records:
        if not passes_filters(rec, filters):
            continue
        report.total_records += 1

        decision = _normalize_decision(rec)
        report.by_decision[decision] += 1

        if decision == "applied":
            report.by_source_applied[_normalize_source(rec)] += 1
            fam = _normalize_family(rec)
            if fam:
                report.families_applied[fam] += 1
            lbl = _normalize_label(rec)
            if lbl is not None:
                report.labels_applied[lbl] += 1
            model = rec.get("model")
            if model:
                report.by_model[str(model)] += 1
            ts = _extract_timestamp(rec)
            if ts is not None:
                if first_dt is None or ts < first_dt:
                    first_dt = ts
                if last_dt is None or ts > last_dt:
                    last_dt = ts

    if first_dt is not None:
        report.first_applied_iso = first_dt.isoformat()
    if last_dt is not None:
        report.last_applied_iso = last_dt.isoformat()

    return report


# -- Formatters --------------------------------------------------------------


def _percent(part: int, total: int) -> str:
    if total <= 0:
        return "  0.0%"
    return f"{(100.0 * part / total):5.1f}%"


def format_human_report(report: AuditReport, top: int = 10) -> str:
    """Render report als human-readable text-Block.

    Sektionen sind alle optional -- leere Counter werden ausgelassen.
    Identisches Layout-Vertrag wie status.py.
    """
    if top < 1:
        top = 1
    lines: List[str] = []

    lines.append(
        f"[learn] audit summary  ({report.files_scanned} file(s), {report.total_records} record(s))"
    )

    if report.by_decision:
        lines.append("")
        lines.append("By decision:")
        total = report.total_records
        # Stable order: applied first, dann reject-gruppen
        for decision in (
            "applied",
            "rejected_by_gate",
            "rejected_by_reviewer",
            "rejected_by_ast",
        ):
            n = report.by_decision.get(decision, 0)
            if n > 0:
                lines.append(f"  {decision:<22} {n:>4}   {_percent(n, total)}")

    if report.by_source_applied:
        lines.append("")
        lines.append("By source (applied only):")
        applied_total = sum(report.by_source_applied.values())
        for source, n in report.by_source_applied.most_common():
            lines.append(f"  {source:<10} {n:>4}   {_percent(n, applied_total)}")

    if report.families_applied:
        lines.append("")
        lines.append("Top families (applied):")
        for family, n in report.families_applied.most_common(top):
            lines.append(f"  {family:<20} {n:>4}")

    if report.labels_applied:
        lines.append("")
        lines.append("Top labels (applied, by frequency):")
        for (role, label), n in report.labels_applied.most_common(top):
            lines.append(f"  {role:<10} {label!r:<40} applied={n}x")

    if report.by_model:
        lines.append("")
        lines.append("Top LLM models used (applied):")
        for model, n in report.by_model.most_common(top):
            lines.append(f"  {model:<30} {n:>4}x")

    if report.first_applied_iso or report.last_applied_iso:
        lines.append("")
        lines.append("Time-range (applied records):")
        if report.first_applied_iso:
            lines.append(f"  first applied: {report.first_applied_iso}")
        if report.last_applied_iso:
            lines.append(f"  last applied:  {report.last_applied_iso}")

    return "\n".join(lines)


def report_to_json(report: AuditReport, top: int = 10) -> dict:
    """Pure JSON-serializable view des reports.

    Counter-objects werden zu lists-of-dicts (stable ordering via
    most_common). Top-N wird hier angewandt (consistent mit human-formatter).
    """
    if top < 1:
        top = 1
    return {
        "total_records": report.total_records,
        "files_scanned": report.files_scanned,
        "by_decision": dict(report.by_decision),
        "by_source_applied": dict(report.by_source_applied),
        "top_families_applied": [
            {"family": fam, "count": n} for fam, n in report.families_applied.most_common(top)
        ],
        "top_labels_applied": [
            {"role": role, "label": label, "count": n}
            for (role, label), n in report.labels_applied.most_common(top)
        ],
        "by_model": dict(report.by_model),
        "first_applied_iso": report.first_applied_iso,
        "last_applied_iso": report.last_applied_iso,
    }
