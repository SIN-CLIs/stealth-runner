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

from .aggregator import (
    aggregate_misses,
    default_suggestions_path,
    write_suggestions,
)


# ── HARTCODIERT FALSE — niemals aendern ohne §12 Update + Review ────────────
_AUTO_APPLY = False


def _logs_dir() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.normpath(os.path.join(here, "..", "..", "logs"))


def cmd_aggregate(args: argparse.Namespace) -> int:
    log_dir = args.logs or _logs_dir()
    suggestions = aggregate_misses(
        log_dir=log_dir, min_count=args.min_count, persona=args.persona,
    )
    out_path = args.out or default_suggestions_path(log_dir)
    write_suggestions(out_path, suggestions)
    print(f"[learn] read miss_labels from {log_dir}/matcher-telemetry-*.jsonl")
    print(f"[learn] wrote {len(suggestions)} suggestions to {out_path}")
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

    n_acc = 0
    n_rej = 0
    n_skip = 0
    try:
        for i, item in enumerate(items, start=1):
            print()
            print(f"[{i}/{len(items)}] "
                  f"role={item.get('role', '?')} "
                  f"label={item.get('normalized_label', '?')!r} "
                  f"count={item.get('count', 0)}")
            family = item.get("suggested_family")
            conf = item.get("confidence", 0.0)
            matched = item.get("matched_tokens", [])
            if family:
                print(f"        suggested: {family}  "
                      f"(confidence={conf:.2f}, matched={matched})")
            else:
                print(f"        suggested: <NEW family needed>  "
                      f"(confidence={conf:.2f}, label_tokens="
                      f"{item.get('label_tokens', [])})")
            samples = item.get("sample_labels", [])
            if samples:
                print(f"        sample labels: {samples}")

            if args.dry_run:
                continue

            choice = _interactive_choice(
                "        Action [a]ccept / [r]eject / [s]kip / [q]uit: "
            )
            if choice == "a" and accepted_f is not None:
                item["status"] = "accepted"
                accepted_f.write(json.dumps(item, ensure_ascii=False) + "\n")
                accepted_f.flush()
                n_acc += 1
            elif choice == "r" and rejected_f is not None:
                item["status"] = "rejected"
                rejected_f.write(json.dumps(item, ensure_ascii=False) + "\n")
                rejected_f.flush()
                n_rej += 1
            elif choice == "q":
                print("[learn] quit by user.")
                break
            else:
                n_skip += 1
    finally:
        if accepted_f is not None:
            accepted_f.close()
        if rejected_f is not None:
            rejected_f.close()

    print()
    print(f"[learn] review done: accepted={n_acc} rejected={n_rej} "
          f"skipped={n_skip}")
    if not _AUTO_APPLY and n_acc:
        print(f"[learn] NEXT STEP (manual): open {accepted_path}, "
              "uebernimm die Patterns in survey/profile_loader.py")
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
    p_agg.set_defaults(func=cmd_aggregate)

    p_rev = sub.add_parser("review",
                           help="Interaktive Sichtung der Vorschlaege")
    p_rev.add_argument("--logs", type=str, default="",
                      help="Pfad zu logs/")
    p_rev.add_argument("--input", type=str, default="",
                      help="Vorschlags-JSONL (default: heutiges aggregate)")
    p_rev.add_argument("--dry-run", action="store_true",
                      help="Nur anzeigen, nichts schreiben")
    p_rev.set_defaults(func=cmd_review)

    return p


def main(argv: List[str] | None = None) -> int:
    parser = build_argparser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
