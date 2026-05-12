"""SR-104 #104 — read-only inbox dashboard fuer pattern-suggestions.

================================================================================
ZWECK
================================================================================

Nach Merge von #56 (Phase 2 LLM-Suggester) und #102 (source-aware batch-
review) hat ein Operator eine ``pattern-suggestions-*.jsonl``-Inbox mit
drei Status (``open``/``accepted``/``rejected``) und zwei Source-Tags
(``substring``/``llm``). Dieses Modul liefert ein read-only Dashboard.

Pure-function-Layer:

  - ``summarize_inbox(records, filters)``       -> ``StatusReport``
  - ``format_human_report(report)``             -> ``str``
  - ``report_to_json(report)``                  -> ``dict`` (JSON-serializable)
  - Defensive normalizers fuer pre-#56-records (kein source field) und
    pre-#102-records (kein status field).

I/O bleibt in ``cli.py:cmd_status`` — dieses Modul **schreibt nichts** und
oeffnet nichts.

================================================================================
ARCHITEKTUR-ENTSCHEIDUNGEN
================================================================================

A) **Strict read-only.** ``status.py`` importiert weder ``apply`` noch
   ``aggregator``. Der StatusReport ist ein passiver dataclass-snapshot.

B) **Defensive field-defaults.** Records aus pre-#56-Aggregator-Laeufen
   haben kein source-Feld -> default ``"substring"`` (spiegelt
   ``review.py:normalize_source``). Records aus pre-#102-Laeufen koennen
   kein status-Feld haben -> default ``"open"``.

C) **Top-N truncation passiert spaet.** ``summarize_inbox`` haelt alle
   counts in vollstaendigen Counter-objects; ``format_*`` Helpers
   schneiden nach top-N. Das macht Tests trivial (vollstaendige counts
   verifizieren) und gibt der CLI Flexibilitaet (verschiedene N).

D) **Filter-Reihenfolge identisch zu review.py.** Erst status-Filter
   (idempotenz-Gate), dann source-Filter, dann family-Aggregation. Stellt
   sicher dass ``--filter-status open --filter-source llm`` dasselbe Set
   liefert wie der entsprechende review-Lauf gesehen haette.

E) **oldest_open_age basiert auf field-priority.** ``first_seen`` >
   ``created_at`` > ``ts`` > None. Aggregator-Output ist gerade beim
   Migrieren -- wir akzeptieren alle drei Aliase. Wenn KEIN Feld
   vorhanden, ``oldest_open_iso`` bleibt None (kein file-mtime-fallback,
   weil Records via CLI multi-source kommen koennen).
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Iterable, List, Literal, Optional


# -- Types -------------------------------------------------------------------


SourceFilter = Literal["all", "substring", "llm"]
StatusFilter = Literal["all", "open", "accepted", "rejected"]


@dataclass(frozen=True)
class StatusFilters:
    """User-facing filter selectors fuer ``summarize_inbox``.

    Both default to ``"all"``; combination is AND. Identical filter-Logik
    wie ``review.py:ReviewRules`` damit ``status`` und ``review`` dasselbe
    set sehen.
    """

    source: SourceFilter = "all"
    status: StatusFilter = "all"


@dataclass
class StatusReport:
    """Aggregate snapshot ueber eine (gefilterte) Record-Liste.

    Felder sind alle public read-only views; Formatting-Helpers consumieren
    direkt. ``Counter``-objects bleiben unsorted im Report -- Top-N happens
    in formatter."""

    total_records: int = 0
    files_scanned: int = 0
    by_status: Counter = field(default_factory=Counter)
    by_source_open: Counter = field(default_factory=Counter)
    families_open: Counter = field(default_factory=Counter)
    labels_open: Counter = field(default_factory=Counter)  # key=(role,label)
    oldest_open_iso: Optional[str] = None
    oldest_open_age_days: Optional[int] = None

    def has_open(self) -> bool:
        """True iff at least one record passed filters AND status=open."""
        return self.by_status.get("open", 0) > 0


# -- Normalizers (defensive against schema-drift) ----------------------------


def _normalize_status(record: dict) -> str:
    """Default to "open" fuer pre-#102 records ohne status-Feld."""
    return str(record.get("status") or "open")


def _normalize_source(record: dict) -> str:
    """Default to "substring" fuer pre-#56 records ohne source-Feld.

    Spiegelt ``review.py:normalize_source`` und ``apply.py:InboxEntry.
    from_dict`` -- alle drei Module nehmen denselben default.
    """
    return str(record.get("source") or "substring")


def _normalize_family(record: dict) -> str:
    """Records ohne ``suggested_family`` bekommen den ``<NEW>`` bucket.

    Das passiert wenn der suggester kein FAMILY_TOKENS-Match findet UND
    LLM-Phase deaktiviert war (oder auch keine Family vorgeschlagen hat).
    Der Operator muss dann manuell eine neue Family im Profile anlegen.
    """
    fam = record.get("suggested_family")
    return fam if fam else "<NEW>"


def _extract_timestamp(record: dict) -> Optional[datetime]:
    """Try first_seen -> created_at -> ts; return tz-aware datetime or None.

    Aggregator-Output ist gerade beim Migrieren (kein einheitliches
    timestamp-Feld). Wir akzeptieren ISO-strings in allen drei Aliasen.
    Wenn parsing fehlschlaegt -> None (defensive)."""
    for key in ("first_seen", "created_at", "ts"):
        raw = record.get(key)
        if not raw:
            continue
        if isinstance(raw, datetime):
            return raw if raw.tzinfo else raw.replace(tzinfo=timezone.utc)
        try:
            dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            continue
    return None


# -- Filtering ---------------------------------------------------------------


def passes_filters(record: dict, filters: StatusFilters) -> bool:
    """AND-combine source + status filter. Read-only predicate."""
    if filters.status != "all" and _normalize_status(record) != filters.status:
        return False
    if filters.source != "all" and _normalize_source(record) != filters.source:
        return False
    return True


# -- Core summarization ------------------------------------------------------


def summarize_inbox(
    records: Iterable[dict],
    filters: StatusFilters = StatusFilters(),
    files_scanned: int = 0,
    now: Optional[datetime] = None,
) -> StatusReport:
    """Build ``StatusReport`` von einer (potentiell gefilterten) Record-Liste.

    Args:
        records:        Iterable von suggestion-records (any JSONL source).
        filters:        AND-filters auf source + status.
        files_scanned:  Caller passt diesen counter durch (nur fuer Anzeige
                        -- pure functions wissen nichts ueber filesystem).
        now:            datetime used als reference fuer ``age_days``-
                        Berechnung. Default: ``datetime.now(timezone.utc)``.
                        Tests injizieren festen ``now`` fuer determinism.

    Returns:
        ``StatusReport`` dataclass -- alle Counter sind vollstaendig
        (kein top-N hier; Formatting-Helpers schneiden).
    """
    if now is None:
        now = datetime.now(timezone.utc)

    report = StatusReport(files_scanned=files_scanned)

    oldest_dt: Optional[datetime] = None

    for rec in records:
        if not passes_filters(rec, filters):
            continue
        report.total_records += 1

        status = _normalize_status(rec)
        report.by_status[status] += 1

        if status == "open":
            report.by_source_open[_normalize_source(rec)] += 1
            report.families_open[_normalize_family(rec)] += 1
            role = str(rec.get("role") or "")
            label = str(rec.get("normalized_label") or "")
            count = int(rec.get("count") or 0)
            # Aggregator gibt den miss-count; wir summieren ihn, NICHT +1
            # per record. Multiple identical records komponieren ueber
            # Counter += sauber.
            report.labels_open[(role, label)] += count

            ts = _extract_timestamp(rec)
            if ts is not None and (oldest_dt is None or ts < oldest_dt):
                oldest_dt = ts

    if oldest_dt is not None:
        report.oldest_open_iso = oldest_dt.isoformat()
        delta = now - oldest_dt
        report.oldest_open_age_days = max(0, delta.days)

    return report


# -- Formatters --------------------------------------------------------------


def _percent(part: int, total: int) -> str:
    if total <= 0:
        return "  0.0%"
    return f"{(100.0 * part / total):5.1f}%"


def format_human_report(report: StatusReport, top: int = 10) -> str:
    """Render report als human-readable text-Block fuer stdout.

    Args:
        report: das, was ``summarize_inbox`` zurueckgibt.
        top:    Max items pro top-N list (families, labels). >=1.

    Layout-Vertrag: jede Sektion ist optional -- wenn die zugrundeliegende
    Counter leer ist, wird die Sektion komplett ausgelassen (kein
    ``"(none)"``-Geblubber). Macht den Output bei leerer Inbox aufgeraeumt.
    """
    if top < 1:
        top = 1
    lines: List[str] = []

    lines.append(
        f"[learn] inbox summary  ({report.files_scanned} file(s), "
        f"{report.total_records} record(s))"
    )

    if report.by_status:
        lines.append("")
        lines.append("By status:")
        total = report.total_records
        for status in ("open", "accepted", "rejected", "skipped"):
            n = report.by_status.get(status, 0)
            if n > 0:
                lines.append(
                    f"  {status:<10} {n:>4}   {_percent(n, total)}")

    if report.by_source_open:
        lines.append("")
        lines.append("By source (open records only):")
        open_total = sum(report.by_source_open.values())
        for source, n in report.by_source_open.most_common():
            lines.append(
                f"  {source:<10} {n:>4}   {_percent(n, open_total)}")

    if report.families_open:
        lines.append("")
        lines.append("Top families (open records):")
        for family, n in report.families_open.most_common(top):
            tag = "  (no family suggested)" if family == "<NEW>" else ""
            lines.append(f"  {family:<20} {n:>4}{tag}")

    if report.labels_open:
        lines.append("")
        lines.append("Top labels (open, by count):")
        for (role, label), n in report.labels_open.most_common(top):
            lines.append(f"  {role:<10} {label!r:<40} count={n}")

    if report.oldest_open_iso:
        lines.append("")
        lines.append(
            f"Oldest open record: {report.oldest_open_iso} "
            f"({report.oldest_open_age_days} day(s) ago)"
        )

    return "\n".join(lines)


def report_to_json(report: StatusReport, top: int = 10) -> dict:
    """Pure JSON-serializable view des reports.

    Counter-objects werden zu lists-of-dicts fuer stable ordering.
    Top-N wird hier auch angewandt (consistent mit human-formatter)."""
    if top < 1:
        top = 1
    return {
        "total_records": report.total_records,
        "files_scanned": report.files_scanned,
        "by_status": dict(report.by_status),
        "by_source_open": dict(report.by_source_open),
        "top_families_open": [
            {"family": fam, "count": n}
            for fam, n in report.families_open.most_common(top)
        ],
        "top_labels_open": [
            {"role": role, "label": label, "count": n}
            for (role, label), n in report.labels_open.most_common(top)
        ],
        "oldest_open_iso": report.oldest_open_iso,
        "oldest_open_age_days": report.oldest_open_age_days,
    }
