"""SR-102 #102 — Source-aware batch-review fuer pattern-suggestions inbox.

================================================================================
ZWECK
================================================================================

Bisher (vor diesem Modul): ``cmd_review`` in ``cli.py`` war ein monolithischer
interaktiver stdin-Flow. Mit dem Merge von SR-57 #56 (Phase 2 LLM-Suggester)
gibt es jetzt zwei Quellen von Vorschlaegen mit unterschiedlichen
Konfidenz-Charakteristiken:

  - ``source=substring``  Heuristik, deterministisch, kostenlos
  - ``source=llm``        LLM-Klassifikation, kostet API-Calls, statistisch

Ein typischer Workflow ist:

  1. ``aggregate --llm`` → mixed inbox
  2. ``review`` mit auto-rules:
       - high-conf substring        → auto-accept
       - low-conf llm               → auto-reject
       - alles uebrige              → manuell sichten
  3. ``apply`` mit der akzeptierten Liste

Dieses Modul liefert die PURE-FUNCTION-Logik dafuer: ``plan_action`` und
``apply_status``. ``cli.py:cmd_review`` ruft sie auf — das I/O bleibt dort.

================================================================================
ARCHITEKTUR-ENTSCHEIDUNGEN
================================================================================

A) **Pure functions, kein I/O.** ``plan_action`` ist deterministisch und
   ohne Seiteneffekte. Das macht die Logik trivial unit-testbar (kein tmp-
   dir, kein stdin-mock) und cleant das CLI-Modul.

B) **Idempotenz via ``status``-Feld.** Aggregator emittiert
   ``status="open"``. Nach einem review-Lauf wird das im input-file zu
   ``"accepted" | "rejected" | "skipped"`` geflippt. Re-run kann mit
   ``filter_open_only=True`` alle non-open records skippen → idempotent.

C) **Filter-Rules sind orthogonal zu Auto-Rules.** ``filter_source`` schliesst
   records aus, bevor die auto-Rules greifen — d.h. ``--filter-source llm
   --auto-accept-substring-above 0.9`` macht nichts, auch wenn high-conf
   substring records da sind, weil die durch den Filter rausfallen.

D) **Source-Tag default = "substring".** SR-57 #56 fuegt das Feld neu hinzu;
   Records aus Pre-#56-Aggregator-Laeufen haben kein source-Feld. Wir
   normalisieren auf "substring" um Backwards-Compat zu garantieren.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, List, Literal, Optional


# ── Typed actions ────────────────────────────────────────────────────────────


Action = Literal["accept", "reject", "ask", "filtered", "already_done"]


@dataclass(frozen=True)
class ReviewRules:
    """Configuration fuer einen review-Lauf.

    Fields:
        auto_accept_substring_above:
            Wenn nicht None: source=="substring" UND confidence >= value
            → action="accept".
        auto_reject_llm_below:
            Wenn nicht None: source=="llm" UND confidence < value
            → action="reject".
        filter_source:
            "all" (default) | "substring" | "llm" — andere records werden
            mit action="filtered" markiert.
        non_interactive:
            True: action="ask" wird nicht erlaubt; alle Records die nicht
            durch eine auto-rule abgedeckt werden, werden uebersprungen
            (Caller sollte sie auf "skipped" tracken, aber nicht in
            accepted/rejected output).
        filter_open_only:
            True (default): records mit status != "open" werden mit
            action="already_done" markiert. Garantiert Idempotenz.
    """

    auto_accept_substring_above: Optional[float] = None
    auto_reject_llm_below: Optional[float] = None
    filter_source: Literal["all", "substring", "llm"] = "all"
    non_interactive: bool = False
    filter_open_only: bool = True


@dataclass
class ReviewSummary:
    """Aggregate counts returned by Caller (cli.cmd_review) zur User-Anzeige."""

    accepted: int = 0
    rejected: int = 0
    skipped: int = 0
    filtered: int = 0
    already_done: int = 0
    asked: int = 0
    by_source: dict = field(default_factory=dict)

    def total(self) -> int:
        return (self.accepted + self.rejected + self.skipped
                + self.filtered + self.already_done)

    def bump(self, action: Action, source: str) -> None:
        """In-place increment per (action, source)."""
        if action == "accept":
            self.accepted += 1
        elif action == "reject":
            self.rejected += 1
        elif action == "ask":
            self.asked += 1
        elif action == "filtered":
            self.filtered += 1
        elif action == "already_done":
            self.already_done += 1
        # source-grouping fuer "alle gesehenen" records (inkl. ask + filtered)
        key = source or "unknown"
        self.by_source[key] = self.by_source.get(key, 0) + 1


# ── Core decision function ───────────────────────────────────────────────────


def normalize_source(record: dict) -> str:
    """Default source = "substring" fuer pre-#56 Records.

    Pre-#56 aggregator-output hatte kein source-Feld. apply.py:InboxEntry.
    from_dict defaultet auf "substring" — wir spiegeln das hier, damit
    pure-function-Logik backwards-kompatibel bleibt."""
    return str(record.get("source") or "substring")


def plan_action(record: dict, rules: ReviewRules) -> Action:
    """Entscheidet die action fuer einen einzelnen suggestion-record.

    Logik-Reihenfolge (FIRST match wins):
      1. Wenn ``filter_open_only`` UND status != "open" → "already_done"
      2. Wenn ``filter_source`` != "all" UND source mismatch → "filtered"
      3. Wenn source=substring + auto_accept_substring_above gesetzt + conf hoch
         → "accept"
      4. Wenn source=llm + auto_reject_llm_below gesetzt + conf niedrig
         → "reject"
      5. Wenn ``non_interactive`` → "filtered" (faellt durch ohne Frage)
      6. Sonst → "ask" (Caller fragt User via stdin)

    Args:
        record: Ein Eintrag aus pattern-suggestions-*.jsonl.
        rules:  ReviewRules dataclass.

    Returns:
        Eine der Action-Literals.

    Examples:
        >>> r = {"source": "substring", "confidence": 0.95, "status": "open"}
        >>> plan_action(r, ReviewRules(auto_accept_substring_above=0.9))
        'accept'
        >>> r = {"source": "llm", "confidence": 0.5, "status": "open"}
        >>> plan_action(r, ReviewRules(auto_reject_llm_below=0.85))
        'reject'
        >>> r = {"source": "substring", "confidence": 0.95, "status": "accepted"}
        >>> plan_action(r, ReviewRules())
        'already_done'
    """
    # Rule 1: idempotency gate.
    status = str(record.get("status") or "open")
    if rules.filter_open_only and status != "open":
        return "already_done"

    src = normalize_source(record)

    # Rule 2: source filter.
    if rules.filter_source != "all" and src != rules.filter_source:
        return "filtered"

    conf = float(record.get("confidence") or 0.0)

    # Rule 3: auto-accept high-confidence substring.
    if (rules.auto_accept_substring_above is not None
            and src == "substring"
            and conf >= rules.auto_accept_substring_above):
        return "accept"

    # Rule 4: auto-reject low-confidence llm.
    if (rules.auto_reject_llm_below is not None
            and src == "llm"
            and conf < rules.auto_reject_llm_below):
        return "reject"

    # Rule 5: non-interactive fallthrough.
    if rules.non_interactive:
        return "filtered"

    # Rule 6: ask user.
    return "ask"


# ── Status helpers ───────────────────────────────────────────────────────────


def apply_status(record: dict, action: Action) -> dict:
    """Returns a COPY of record with updated status field.

    Mapping:
        accept       → status="accepted"
        reject       → status="rejected"
        ask          → unchanged (caller handles via interactive prompt)
        filtered     → unchanged (record is invisible to this run)
        already_done → unchanged (record already processed in prior run)
    """
    out = dict(record)
    if action == "accept":
        out["status"] = "accepted"
    elif action == "reject":
        out["status"] = "rejected"
    return out


def format_display_line(record: dict) -> str:
    """Format a record fuer den interactive-display.

    Zeigt source/model/prompt_hash explizit fuer LLM-records — das war der
    Haupt-Gap pre-#102 (cmd_review zeigte diese Felder gar nicht an).

    Examples:
        >>> r = {"source": "llm", "model": "openai/gpt-5-mini",
        ...      "prompt_hash": "abc123def456", "confidence": 0.91,
        ...      "suggested_family": "household_size"}
        >>> "openai/gpt-5-mini" in format_display_line(r)
        True
    """
    src = normalize_source(record)
    fam = record.get("suggested_family") or "<NEW family needed>"
    conf = float(record.get("confidence") or 0.0)
    parts = [f"family={fam}", f"conf={conf:.2f}", f"source={src}"]
    if src == "llm":
        model = record.get("model") or "?"
        # Truncate model id — manche provider-prefixes sind sehr lang.
        if len(model) > 30:
            model = model[:27] + "..."
        parts.append(f"model={model}")
        ph = record.get("prompt_hash")
        if ph:
            parts.append(f"hash={ph[:8]}")
    return "  ".join(parts)


def partition_records(
    records: Iterable[dict], rules: ReviewRules,
) -> List[tuple]:
    """Vorab-Partitionierung aller records → Liste von (record, action) Tupeln.

    Nuetzlich fuer ``--dry-run``: der Caller kann das Resultat anzeigen
    OHNE den interaktiven Loop zu starten. Records mit action="ask" werden
    NICHT umgewandelt — der Caller muss selbst entscheiden, ob der die
    Frage stellt oder das record skippt (z.B. bei --dry-run).
    """
    return [(rec, plan_action(rec, rules)) for rec in records]
