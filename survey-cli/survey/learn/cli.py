"""CLI entry: ``python -m survey learn <action>``.

Actions:
  aggregate   - Liest matcher-telemetry-*.jsonl, schreibt
                pattern-suggestions-{date}.jsonl.
  review      - Interaktive Sichtung. Pro Vorschlag: ACCEPT / REJECT / SKIP.
                Akzeptierte landen in pattern-suggestions-accepted.jsonl.
                Abgelehnte landen in pattern-suggestions-rejected.jsonl.
                NIEMALS Auto-Apply!

Beispiel-Workflow:
  $ python -m survey learn aggregate
    [learn] read 12 miss_labels from logs/matcher-telemetry-*.jsonl
    [learn] wrote 4 suggestions to logs/pattern-suggestions-2026-05-11.jsonl

  $ python -m survey learn review
    [1/4] role=textbox label='mobilnummer' count=3
          suggested: phone (confidence=0.50, matched=['mobil', 'nummer'])
          Action [a]ccept / [r]eject / [s]kip / [q]uit: a
    ...

Sicherheitsgurt: AUTO_APPLY ist hartcodiert FALSE. Akzeptierte Vorschlaege
landen in einer Sammeldatei, die ein Mensch lesen + manuell in
profile_loader.py FIELD_PATTERNS einarbeiten muss.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import List

from .review import (
    ReviewRules, ReviewSummary,
    plan_action, apply_status, format_display_line,
)
from .status import (
    StatusFilters,
    format_human_report,
    report_to_json,
    summarize_inbox,
)
# SR-109 #109: audit-log dashboard (apply-side complement to status)
from .audit import (
    AuditFilters,
    format_human_report as format_audit_report,
    report_to_json as audit_report_to_json,
    summarize_audit,
)
from .aggregator import (
    aggregate_misses,
    default_suggestions_path,
    write_suggestions,
)
from .apply import apply_inbox  # SR-58 #57


# ── HARTCODIERT FALSE — niemals aendern ohne §12 Update + Review ────────────
_AUTO_APPLY = False


def _logs_dir() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.normpath(os.path.join(here, "..", "..", "logs"))


def cmd_aggregate(args: argparse.Namespace) -> int:
    log_dir = args.logs or _logs_dir()
    suggestions = aggregate_misses(
        log_dir=log_dir, min_count=args.min_count, persona=args.persona,
        # SR-57 #56: optional Phase-2 LLM-fallback.
        use_llm=args.llm,
        llm_model=args.llm_model or None,
    )
    out_path = args.out or default_suggestions_path(log_dir)
    write_suggestions(out_path, suggestions)
    print(f"[learn] read miss_labels from {log_dir}/matcher-telemetry-*.jsonl")
    print(f"[learn] wrote {len(suggestions)} suggestions to {out_path}")
    if args.llm:
        n_llm = sum(1 for s in suggestions if s.get("source") == "llm")
        n_substr = sum(1 for s in suggestions
                       if s.get("source") == "substring")
        print(f"[learn] sources: substring={n_substr} llm={n_llm}")
    if not suggestions:
        print("[learn] (no misses with count >= "
              f"{args.min_count} — nothing to suggest)")
    return 0


def _interactive_choice(prompt: str) -> str:
    """Fragt nach a/r/s/q. Bei nicht-tty (CI / Pipe) → SKIP-Default."""
    if not sys.stdin.isatty():
        return "s"
    while True:
        choice = input(prompt).strip().lower()
        if choice in ("a", "r", "s", "q"):
            return choice
        print("  bitte 'a' (accept), 'r' (reject), 's' (skip) oder 'q' (quit)")


def cmd_review(args: argparse.Namespace) -> int:
    """SR-102 #102: source-aware batch-review.

    Drei Modi koexistieren ohne sich zu stoeren:
      - auto-rules (--auto-accept-substring-above / --auto-reject-llm-below)
        greifen pro record FIRST
      - --filter-source schaltet records aus, die das Auto-Regelwerk gar
        nicht erreichen sollen
      - alles uebrige geht in interaktiven a/r/s/q flow (oder wird unter
        --non-interactive einfach uebersprungen)
    Records werden idempotent via "status" field gemerkt — re-run skippt
    bereits prozessierte.
    """
    log_dir = args.logs or _logs_dir()
    suggestions_path = args.input or default_suggestions_path(log_dir)
    if not os.path.exists(suggestions_path):
        print(f"[learn] no suggestions file at {suggestions_path} — "
              "run 'aggregate' first.")
        return 1

    items: List[dict] = []
    with open(suggestions_path) as f:
        for line in f:
            line = line.strip()
            if line:
                items.append(json.loads(line))

    rules = ReviewRules(
        auto_accept_substring_above=(
            args.auto_accept_substring_above
            if args.auto_accept_substring_above >= 0 else None),
        auto_reject_llm_below=(
            args.auto_reject_llm_below
            if args.auto_reject_llm_below >= 0 else None),
        filter_source=args.filter_source,
        non_interactive=args.non_interactive,
        filter_open_only=True,
    )

    accepted_path = os.path.join(log_dir, "pattern-suggestions-accepted.jsonl")
    rejected_path = os.path.join(log_dir, "pattern-suggestions-rejected.jsonl")
    # In dry-run NICHT oeffnen — Tests pruefen explizit dass keine
    # accepted/rejected-Datei angelegt wird.
    if args.dry_run:
        accepted_f = None
        rejected_f = None
    else:
        accepted_f = open(accepted_path, "a")
        rejected_f = open(rejected_path, "a")

    summary = ReviewSummary()
    quit_requested = False

    try:
        for i, item in enumerate(items, start=1):
            action = plan_action(item, rules)
            src = item.get("source") or "substring"

            # already_done + filtered: silent skip, kein output
            if action in ("already_done", "filtered"):
                summary.bump(action, src)
                continue

            # accept/reject via auto-rule: log + write + status-flip
            if action in ("accept", "reject"):
                flipped = apply_status(item, action)
                items[i - 1] = flipped  # in-place so input-file gets updated
                if not args.dry_run:
                    target = accepted_f if action == "accept" else rejected_f
                    assert target is not None
                    target.write(
                        json.dumps(flipped, ensure_ascii=False) + "\n")
                    target.flush()
                summary.bump(action, src)
                print(f"[{i}/{len(items)}] auto-{action}: "
                      f"{format_display_line(flipped)}")
                continue

            # action == "ask"
            print()
            print(f"[{i}/{len(items)}] "
                  f"role={item.get('role', '?')} "
                  f"label={item.get('normalized_label', '?')!r} "
                  f"count={item.get('count', 0)}")
            print(f"        {format_display_line(item)}")
            matched = item.get("matched_tokens", [])
            if matched:
                print(f"        matched_tokens: {matched}")
            samples = item.get("sample_labels", [])
            if samples:
                print(f"        sample labels: {samples}")

            if args.dry_run:
                summary.bump("ask", src)
                continue

            choice = _interactive_choice(
                "        Action [a]ccept / [r]eject / [s]kip / [q]uit: "
            )
            if choice == "a" and accepted_f is not None:
                flipped = apply_status(item, "accept")
                items[i - 1] = flipped
                accepted_f.write(json.dumps(flipped, ensure_ascii=False) + "\n")
                accepted_f.flush()
                summary.bump("accept", src)
            elif choice == "r" and rejected_f is not None:
                flipped = apply_status(item, "reject")
                items[i - 1] = flipped
                rejected_f.write(json.dumps(flipped, ensure_ascii=False) + "\n")
                rejected_f.flush()
                summary.bump("reject", src)
            elif choice == "q":
                print("[learn] quit by user.")
                quit_requested = True
                break
            else:
                summary.bump("ask", src)
    finally:
        if accepted_f is not None:
            accepted_f.close()
        if rejected_f is not None:
            rejected_f.close()

    # Write back status-flipped input (idempotency). Only when NOT dry-run.
    # Skip rewrite if quit-requested too — partial state would be confusing.
    if not args.dry_run and not quit_requested:
        with open(suggestions_path, "w") as f:
            for rec in items:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    print()
    print(f"[learn] review done: accepted={summary.accepted} "
          f"rejected={summary.rejected} skipped={summary.asked} "
          f"filtered={summary.filtered} already_done={summary.already_done}")
    if summary.by_source:
        bs = ", ".join(f"{k}={v}" for k, v in
                       sorted(summary.by_source.items()))
        print(f"[learn] by_source: {bs}")
    if not _AUTO_APPLY and summary.accepted:
        print(f"[learn] NEXT STEP (manual): open {accepted_path}, "
              "uebernimm die Patterns in survey/profile_loader.py")
    return 0

def cmd_apply(args: argparse.Namespace) -> int:
    """SR-58 #57 — manueller, auditierter Apply von Inbox-Eintraegen.

    Workflow:
      1. Lese accepted-Inbox JSONL.
      2. Confidence-Gate (substring >= 0.7, llm >= 0.85).
      3. Pro Eintrag: prompt (interactive) ODER auto-accept (--approve-all)
         ODER skip-und-Diff-zeigen (--dry-run).
      4. AST-Roundtrip auf survey/profile_loader.py::FIELD_PATTERNS.
      5. Smoke-Tests; bei Failure: byte-genauer Rollback.
      6. Audit-Log: logs/learn-applied-{ISO8601}.jsonl

    Exit codes:
      0  = OK (auch bei "nothing applied" + dry-run).
      1  = pre/post Test-Fail mit Rollback, oder Inbox-IO-Fehler.
      2  = inkompatibler Flag-Mix (sollte argparse abfangen).
    """
    if args.approve_all and args.interactive:
        print("[learn-apply] --approve-all und --interactive sind exklusiv.",
              file=sys.stderr)
        return 2
    if args.approve_all:
        mode = "approve-all"
    elif args.dry_run:
        mode = "dry-run"
    else:
        mode = "interactive"

    result = apply_inbox(
        inbox_path=args.inbox,
        mode=mode,
        skip_tests=args.skip_tests,
    )

    if result.error:
        print(f"[learn-apply] ERROR: {result.error}", file=sys.stderr)
        if result.rolled_back:
            print("[learn-apply] rollback successful — profile_loader.py "
                  "is back to pre-apply state.", file=sys.stderr)
        return 1

    print(f"[learn-apply] mode={mode}")
    print(f"[learn-apply] accepted={result.accepted} "
          f"rejected={result.rejected} skipped={result.skipped}")
    for fam, kw in result.applied_keywords:
        print(f"[learn-apply]   + {fam}: {kw}")
    if result.audit_log_path:
        print(f"[learn-apply] audit log: {result.audit_log_path}")
    elif mode == "dry-run":
        if not result.applied_keywords:
            print("[learn-apply] (dry-run: no candidate above confidence gate)")
        else:
            print(f"[learn-apply] (dry-run: {len(result.applied_keywords)} "
                  "candidate(s) above gate — diff printed above, "
                  "no files written)")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    """SR-104 #104: read-only inbox dashboard.

    Default: scan all ``pattern-suggestions-*.jsonl`` in ``--logs`` dir,
    aggregate counts by status/source/family, print human report.
    With ``--json`` emit machine-readable JSON instead.
    With ``--require-empty`` exit 1 if any open records remain (CI gate).

    Strict read-only: opens files with ``"r"`` ONLY; never creates
    accepted/rejected/audit log outputs.
    """
    import glob
    log_dir = args.logs or _logs_dir()

    if args.input:
        input_paths = [args.input] if os.path.exists(args.input) else []
    else:
        input_paths = sorted(glob.glob(
            os.path.join(log_dir, "pattern-suggestions-*.jsonl")))
        # Skip accepted/rejected derived files -- nur die roh-inbox.
        input_paths = [p for p in input_paths
                       if not (p.endswith("-accepted.jsonl")
                               or p.endswith("-rejected.jsonl"))]

    if not input_paths:
        print(f"[learn] no pattern-suggestions-*.jsonl found "
              f"(searched {log_dir})")
        return 0 if not args.require_empty else 1

    records = []
    for path in input_paths:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if line:
                    records.append(json.loads(line))

    filters = StatusFilters(
        source=args.filter_source,
        status=args.filter_status,
    )
    report = summarize_inbox(
        records,
        filters=filters,
        files_scanned=len(input_paths),
    )

    if args.json:
        print(json.dumps(report_to_json(report, top=args.top),
                         indent=2, ensure_ascii=False))
    else:
        print(format_human_report(report, top=args.top))

    if args.require_empty and report.has_open():
        # Stderr-Erklaerung, damit CI-Diff lesbar bleibt.
        sys.stderr.write(
            f"[learn] --require-empty: "
            f"{report.by_status.get('open', 0)} open record(s) remain.\n"
        )
        return 1
    return 0



def cmd_audit(args: argparse.Namespace) -> int:
    """SR-109 #109: read-only audit-log dashboard.

    Default: scan all ``learn-applied-*.jsonl`` in ``--logs`` dir,
    aggregate counts by decision/source/family/model, print human report.
    With ``--json`` emit machine-readable JSON instead.

    Strict read-only: opens files with ``"r"`` ONLY; never creates new
    audit-log outputs nor modifies existing ones. Mirrors ``cmd_status``
    in spirit and constraints.
    """
    import glob
    from datetime import datetime, timezone

    log_dir = args.logs or _logs_dir()

    if args.input:
        input_paths = [args.input] if os.path.exists(args.input) else []
    else:
        input_paths = sorted(glob.glob(
            os.path.join(log_dir, "learn-applied-*.jsonl")))

    if not input_paths:
        print(f"[learn] no learn-applied-*.jsonl found "
              f"(searched {log_dir})")
        return 0

    records = []
    for path in input_paths:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if line:
                    records.append(json.loads(line))

    # Parse --since (optional)
    since_dt = None
    if args.since:
        try:
            since_dt = datetime.fromisoformat(
                str(args.since).replace("Z", "+00:00"))
            if since_dt.tzinfo is None:
                since_dt = since_dt.replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            sys.stderr.write(
                f"[learn] --since: cannot parse ISO timestamp "
                f"{args.since!r} -- ignored.\n"
            )
            since_dt = None

    filters = AuditFilters(
        decision=args.filter_decision,
        source=args.filter_source,
        family=args.filter_family or None,
        since=since_dt,
    )
    report = summarize_audit(
        records,
        filters=filters,
        files_scanned=len(input_paths),
    )

    if args.json:
        print(json.dumps(audit_report_to_json(report, top=args.top),
                         indent=2, ensure_ascii=False))
    else:
        print(format_audit_report(report, top=args.top))

    return 0


def build_argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="survey learn")
    sub = p.add_subparsers(dest="action", required=True)

    p_agg = sub.add_parser("aggregate",
                           help="Aggregate matcher-telemetry misses")
    p_agg.add_argument("--logs", type=str, default="",
                      help="Pfad zu logs/ (default: survey/../logs)")
    p_agg.add_argument("--min-count", type=int, default=1,
                      help="Mindest-Frequenz (default: 1)")
    p_agg.add_argument("--persona", type=str, default=None,
                      help="Nur Misses dieser Persona")
    p_agg.add_argument("--out", type=str, default="",
                      help="Output-Pfad (default: pattern-suggestions-{date})")
    # SR-57 #56: FCTC-ES Phase 2 (LLM fallback). Opt-in via --llm.
    p_agg.add_argument("--llm", action="store_true",
                      help="Phase-2: ruft LLM-Suggester fuer Misses, die "
                           "die Heuristik nicht entscheidet (family=None "
                           "oder confidence<0.20). Erfordert "
                           "AI_GATEWAY_API_KEY.")
    p_agg.add_argument("--llm-model", type=str, default="",
                      help="Override fuer LLM model id "
                           "(default: openai/gpt-5-mini)")
    p_agg.set_defaults(func=cmd_aggregate)

    p_rev = sub.add_parser("review",
                           help="Interaktive Sichtung der Vorschlaege")
    p_rev.add_argument("--logs", type=str, default="",
                      help="Pfad zu logs/")
    p_rev.add_argument("--input", type=str, default="",
                      help="Vorschlags-JSONL (default: heutiges aggregate)")
    p_rev.add_argument("--dry-run", action="store_true",
                      help="Nur anzeigen, nichts schreiben")
    # SR-102 #102: source-aware batch-review flags.
    p_rev.add_argument(
        "--auto-accept-substring-above", type=float, default=-1.0,
        metavar="CONF",
        help="Auto-accept records mit source=substring UND "
             "confidence >= CONF (e.g. 0.9). Default: disabled.")
    p_rev.add_argument(
        "--auto-reject-llm-below", type=float, default=-1.0,
        metavar="CONF",
        help="Auto-reject records mit source=llm UND "
             "confidence < CONF (e.g. 0.85). Default: disabled.")
    p_rev.add_argument(
        "--filter-source", choices=["all", "substring", "llm"],
        default="all",
        help="Nur records dieser source verarbeiten. Default: all.")
    p_rev.add_argument(
        "--non-interactive", action="store_true",
        help="Kein stdin-prompt; records ohne auto-rule-match werden "
             "uebersprungen (status bleibt open).")
    p_rev.set_defaults(func=cmd_review)

    # SR-58 #57: apply ──────────────────────────────────────────────────────
    p_app = sub.add_parser(
        "apply",
        help="Apply accepted suggestions to FIELD_PATTERNS (AST roundtrip)")
    p_app.add_argument("inbox", type=str,
                       help="Pfad zur accepted-Inbox JSONL "
                            "(z.B. logs/pattern-suggestions-accepted.jsonl)")
    p_app.add_argument("--dry-run", action="store_true",
                       help="Diff anzeigen, NICHTS schreiben")
    grp = p_app.add_mutually_exclusive_group()
    grp.add_argument("--approve-all", action="store_true",
                     help="Alle Eintraege oberhalb Confidence-Gate uebernehmen")
    grp.add_argument("--interactive", action="store_true",
                     help="Pro Eintrag fragen [a/r/s/q] (default)")
    p_app.add_argument("--skip-tests", action="store_true",
                       help="DEV-FLAG: pytest-Gate ueberspringen "
                            "(nur fuer Tests, nicht in CI)")
    p_app.set_defaults(func=cmd_apply)

    # SR-104 #104: read-only inbox dashboard.
    p_sts = sub.add_parser(
        "status",
        help="Read-only Inbox-Dashboard: counts by status/source/family")
    p_sts.add_argument("--logs", default=None,
                       help="Logs-Verzeichnis (default: survey-cli/logs)")
    p_sts.add_argument("--input", default=None,
                       help="Statt multi-file scan, eine einzelne JSONL lesen")
    p_sts.add_argument("--filter-source",
                       choices=["all", "substring", "llm"], default="all",
                       help="Filter auf source field. Default: all.")
    p_sts.add_argument("--filter-status",
                       choices=["all", "open", "accepted", "rejected"],
                       default="all",
                       help="Filter auf status field. Default: all.")
    p_sts.add_argument("--top", type=int, default=10, metavar="N",
                       help="Limit fuer top-N family/label-Listen. Default: 10.")
    p_sts.add_argument("--json", action="store_true",
                       help="JSON statt human-readable Output")
    p_sts.add_argument("--require-empty", action="store_true",
                       help="Exit 1 wenn open-count > 0 (CI smoke-gate). "
                            "Read-only -- modifiziert nichts.")
    p_sts.set_defaults(func=cmd_status)

    # SR-109 #109: read-only audit-log dashboard (apply-side).
    p_aud = sub.add_parser(
        "audit",
        help="Read-only Audit-Dashboard: counts by decision/source/family")
    p_aud.add_argument("--logs", default=None,
                       help="Logs-Verzeichnis (default: survey-cli/logs)")
    p_aud.add_argument("--input", default=None,
                       help="Statt multi-file scan, eine einzelne JSONL lesen")
    p_aud.add_argument(
        "--filter-decision",
        choices=["all", "applied", "rejected_by_gate",
                 "rejected_by_reviewer", "rejected_by_ast"],
        default="all",
        help="Filter auf decision field. Default: all.")
    p_aud.add_argument("--filter-source",
                       choices=["all", "substring", "llm"], default="all",
                       help="Filter auf source field. Default: all.")
    p_aud.add_argument("--filter-family", default=None,
                       help="Filter auf family (exakter Match). Default: alle.")
    p_aud.add_argument("--since", default=None, metavar="ISO",
                       help="Nur records mit timestamp >= ISO (z.B. "
                            "2026-05-01T00:00:00Z). Records ohne timestamp "
                            "werden ausgeschlossen.")
    p_aud.add_argument("--top", type=int, default=10, metavar="N",
                       help="Limit fuer top-N family/label/model-Listen. "
                            "Default: 10.")
    p_aud.add_argument("--json", action="store_true",
                       help="JSON statt human-readable Output")
    p_aud.set_defaults(func=cmd_audit)

    return p


def main(argv: List[str] | None = None) -> int:
    parser = build_argparser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
