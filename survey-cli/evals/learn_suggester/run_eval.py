"""SR-101: FCTC-ES Suggester Eval-Harness.

================================================================================
PURPOSE
================================================================================

Measure how well ``survey.learn.suggester.suggest_family`` (Phase 1, token-
overlap heuristic) and ``suggest_via_llm`` (Phase 2, LLM classification)
classify unmatched survey-question labels into one of the 20 known
``FAMILY_TOKENS`` families.

This harness exists because:
  1. We don't currently know Phase-1 accuracy — we just trust unit tests.
  2. We don't know whether Phase-2 actually improves over Phase-1.
  3. A token-set tweak in ``FAMILY_TOKENS`` could silently regress
     real-world accuracy while passing all unit tests.

The harness reads a FROZEN golden set (``labels.golden.jsonl``), runs each
record through the suggester(s), and emits a structured report with
per-family precision/recall, confusion-pairs and a threshold-gate.

================================================================================
DESIGN DECISIONS
================================================================================

A) **Frozen golden set.** Updates only via manual PR. No auto-update path.
   Rationale: if the eval can amend its own ground-truth, it stops being an
   eval. Golden-set changes need human review.

B) **--mock mode for Phase 2.** Deterministic regex-driven engine that
   patches ``survey.learn.suggester.call_llm``. Allows running on CI (and on
   PRs from forks) without ``AI_GATEWAY_API_KEY``. NOT a quality measurement
   of the real LLM — only validates the pipeline wiring (response parsing,
   source-tagging, threshold gates).

C) **--live mode for Phase 2.** Real API calls. Only allowed via
   ``workflow_dispatch`` — never on PRs/push (cost risk).

D) **Exit codes.** 0 = OK, 1 = threshold-gate failed (regression),
   2 = config/IO error. CI uses ``--exit-non-zero-on-threshold-miss`` to
   distinguish "eval ran but heuristic regressed" from "eval crashed".

E) **No new deps.** stdlib only. ``unittest.mock.patch`` for the Phase-2
   mock-engine injection.

================================================================================
USAGE
================================================================================

Run from ``survey-cli/`` directory::

    # Phase 1 only (no API key needed):
    python -m evals.learn_suggester.run_eval --phase 1

    # Phase 2 with mock engine (no API key, deterministic):
    python -m evals.learn_suggester.run_eval --phase 2 --mock

    # Phase 2 live (workflow_dispatch only, costs API calls):
    python -m evals.learn_suggester.run_eval --phase 2 --live

Output:
  - stdout: human-readable summary
  - ``evals/learn_suggester/last-report.json``: full JSON report

Closes #101.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import sys
from collections import Counter, defaultdict
from typing import Any, Dict, List, Optional, Tuple
from unittest import mock

# Allow running both as ``python -m evals.learn_suggester.run_eval``
# (recommended) and as ``python evals/learn_suggester/run_eval.py``
# (developer convenience). In the latter case sys.path needs survey-cli/.
_HERE = os.path.dirname(os.path.abspath(__file__))
_SURVEY_CLI_DIR = os.path.dirname(os.path.dirname(_HERE))
if _SURVEY_CLI_DIR not in sys.path:
    sys.path.insert(0, _SURVEY_CLI_DIR)

from survey.learn.suggester import (  # noqa: E402
    FAMILY_TOKENS,
    LLMSuggestion,
    suggest_family,
    suggest_via_llm,
)
from survey.learn.llm_client import LLMResponse  # noqa: E402

# ── Paths and constants ──────────────────────────────────────────────────────

DEFAULT_GOLDEN = os.path.join(_HERE, "labels.golden.jsonl")
DEFAULT_REPORT = os.path.join(_HERE, "last-report.json")
DEFAULT_MIN_PHASE1_ACCURACY = 0.65

ALLOWED_FAMILIES = sorted(FAMILY_TOKENS.keys())

# ── Mock engine for Phase-2 ─────────────────────────────────────────────────

# Hand-curated hints simulating a "good enough" LLM. Includes a few German
# synonyms that Phase 1 misses through phrasing variation. NOT a real quality
# measurement — purpose is to validate pipeline wiring AND demonstrate that an
# LLM-style classifier CAN beat the heuristic on phrasing variants.
_MOCK_HINTS: Dict[str, List[str]] = {
    "email":          ["email", "e-mail", "mail-adresse", "mailadresse"],
    "phone":          ["phone", "telefon", "handy", "mobil", "nummer", "tel"],
    "birth_year":     ["geburtsjahr", "year of birth", "jahrgang", "born in"],
    "postal_code":    ["plz", "postleitzahl", "zip", "postal"],
    "hh_income":      ["haushaltseinkommen", "household income",
                       "familieneinkommen"],
    "income":         ["nettoeinkommen", "salary", "gehalt",
                       "personal income", "monthly salary"],
    "first_name":     ["vorname", "first name", "given name"],
    "last_name":      ["nachname", "surname", "last name", "family name"],
    "street":         ["strasse", "straße", "street", "anschrift"],
    "city":           ["stadt", "wohnort", "city", "town"],
    "country":        ["land", "country", "nation", "in welchem land"],
    "state_region":   ["bundesland", "state", "province", "kanton"],
    "household_size": ["personen", "wie viele personen",
                       "household size", "people in your household"],
    "age":            ["wie alt", "your age", "ihr alter"],
    "job_title":      ["beruf", "job title", "berufsbezeichnung"],
    "industry":       ["branche", "industry", "wirtschaftszweig"],
    "nationality":    ["staatsangeh", "nationality", "nationalit"],
    "language":       ["muttersprache", "native language", "sprache"],
    "gender":         ["geschlecht", "gender", "sex"],
    "full_name":      ["vollstaendiger name", "vollständiger name",
                       "full name"],
}


_PROMPT_LABEL_RE = re.compile(r"Label: '(.+?)'\n", re.DOTALL)


def _mock_call_llm(
    prompt: str,
    *,
    model: Optional[str] = None,
    timeout: float = 20.0,
) -> LLMResponse:
    """Deterministic mock for ``survey.learn.suggester.call_llm``.

    Extracts the label from the prompt, iterates families in SORTED order,
    and returns the first family whose hint-list has a substring match in
    the label. Returns family=null if nothing matches.

    Deterministic: same prompt -> same response. No randomness, no I/O.
    """
    # Extract the label from the prompt format produced by _build_llm_prompt:
    #   "Label: 'foo bar'\n"
    m = _PROMPT_LABEL_RE.search(prompt)
    label = (m.group(1) if m else "").lower()

    # Longest-match wins. Iterating families in sorted() order for stable
    # tie-breaks. The longest-hint heuristic prevents short-substring false
    # positives like "land" in "bundesland" outranking the more specific
    # "bundesland" hint of the state_region family. This is a deliberately
    # simple proxy for what a real LLM does ("pick the most specific
    # matching family"), and it suffices to demonstrate phase-2 lift in
    # the mock pipeline.
    best_family: Optional[str] = None
    best_hint_len: int = 0
    for fam in sorted(_MOCK_HINTS.keys()):
        for hint in _MOCK_HINTS[fam]:
            h_lower = hint.lower()
            if h_lower in label and len(h_lower) > best_hint_len:
                best_family = fam
                best_hint_len = len(h_lower)
    chosen_family = best_family

    if chosen_family is None:
        content = json.dumps({
            "family": None, "confidence": 0.0, "reason": "mock no-match",
        })
    else:
        content = json.dumps({
            "family": chosen_family,
            "confidence": 0.9,
            "reason": "mock substring-hint match",
        })

    return LLMResponse(
        content=content,
        model=model or "mock/deterministic",
        prompt_hash="mockhash0000",
        error=None,
        latency_ms=0,
    )


# ── Golden-set loading + validation ──────────────────────────────────────────


def load_golden(path: str) -> List[Dict[str, Any]]:
    """Read JSONL records from ``path``.

    Raises FileNotFoundError if missing, json.JSONDecodeError on parse error.
    """
    records: List[Dict[str, Any]] = []
    with open(path, encoding="utf-8") as f:
        for line_num, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError as e:
                raise json.JSONDecodeError(
                    f"{path}:{line_num}: {e.msg}", e.doc, e.pos)
            records.append(rec)
    return records


def validate_golden(records: List[Dict[str, Any]]) -> List[str]:
    """Validate every record. Returns list of error messages (empty = OK)."""
    errors: List[str] = []
    REQUIRED = {"label", "role", "expected_family", "lang", "notes"}
    for i, rec in enumerate(records):
        missing = REQUIRED - set(rec.keys())
        if missing:
            errors.append(
                f"record[{i}] missing fields: {sorted(missing)}")
            continue
        if not isinstance(rec["label"], str) or not rec["label"].strip():
            errors.append(f"record[{i}] label must be non-empty str")
        if rec["expected_family"] is not None:
            if rec["expected_family"] not in FAMILY_TOKENS:
                errors.append(
                    f"record[{i}] expected_family "
                    f"{rec['expected_family']!r} not in FAMILY_TOKENS"
                )
        if rec.get("lang") not in {"de", "en"}:
            errors.append(
                f"record[{i}] lang must be 'de' or 'en', got {rec.get('lang')!r}")
    return errors


# ── Eval execution ───────────────────────────────────────────────────────────


def _phase1_prediction(label: str) -> Tuple[Optional[str], float]:
    """Phase 1: heuristic suggest_family."""
    r = suggest_family(label)
    return r.family, r.confidence


def _phase2_prediction(
    label: str, *, use_mock: bool,
) -> Tuple[Optional[str], float, Optional[str]]:
    """Phase 2: LLM suggest_via_llm. Returns (family, confidence, error_or_None).

    Caller must wrap in mock-patch context if use_mock=True.
    """
    r: LLMSuggestion = suggest_via_llm(
        label, allowed_families=ALLOWED_FAMILIES,
    )
    return r.family, r.confidence, r.error


def evaluate(
    records: List[Dict[str, Any]],
    *,
    phase: int,
    use_mock: bool,
) -> Dict[str, Any]:
    """Run records through phase-1 (and optionally phase-2).

    Returns a structured report dict.
    """
    items: List[Dict[str, Any]] = []
    confusion_p1: Counter = Counter()
    confusion_p2: Counter = Counter()

    # Always compute Phase-1 — even in phase=2 we want lift comparison.
    for rec in records:
        label = rec["label"]
        expected = rec["expected_family"]

        p1_fam, p1_conf = _phase1_prediction(label)
        p1_correct = (p1_fam == expected)
        if not p1_correct:
            confusion_p1[(str(expected), str(p1_fam))] += 1

        item: Dict[str, Any] = {
            "label": label,
            "role": rec["role"],
            "lang": rec["lang"],
            "expected": expected,
            "p1_pred": p1_fam,
            "p1_conf": round(p1_conf, 4),
            "p1_correct": p1_correct,
        }
        items.append(item)

    if phase == 2:
        ctx = (
            mock.patch("survey.learn.suggester.call_llm",
                       side_effect=_mock_call_llm)
            if use_mock else _NullCM()
        )
        with ctx:
            for item, rec in zip(items, records):
                p2_fam, p2_conf, p2_err = _phase2_prediction(
                    rec["label"], use_mock=use_mock)
                item["p2_pred"] = p2_fam
                item["p2_conf"] = round(p2_conf, 4)
                item["p2_correct"] = (p2_fam == rec["expected_family"])
                item["p2_error"] = p2_err
                if not item["p2_correct"]:
                    confusion_p2[(
                        str(rec["expected_family"]), str(p2_fam))] += 1

    return _build_report(items, confusion_p1, confusion_p2, phase, use_mock)


class _NullCM:
    """No-op context manager for the not-mocked branch."""

    def __enter__(self):
        return None

    def __exit__(self, *_):
        return False


# ── Report building ──────────────────────────────────────────────────────────


def _per_family_stats(items: List[Dict[str, Any]], phase: int) -> Dict[str, Dict]:
    """Compute precision / recall / F1 per family (including None=negative)."""
    # Stringify so we can sort. ``None`` is the "no family" / true-negative
    # bucket and sorts as the literal string "None".
    expected_set = {str(it["expected"]) for it in items}
    pred_set = {str(it[f"p{phase}_pred"]) for it in items}
    fams = sorted(expected_set | pred_set)
    stats: Dict[str, Dict[str, Any]] = {}
    for fam in fams:
        tp = sum(
            1 for it in items
            if str(it["expected"]) == fam
            and str(it[f"p{phase}_pred"]) == fam)
        fp = sum(
            1 for it in items
            if str(it["expected"]) != fam
            and str(it[f"p{phase}_pred"]) == fam)
        fn = sum(
            1 for it in items
            if str(it["expected"]) == fam
            and str(it[f"p{phase}_pred"]) != fam)
        n = tp + fn
        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = (2 * precision * recall / (precision + recall)
              if (precision + recall) else 0.0)
        stats[str(fam)] = {
            "n": n,
            "tp": tp, "fp": fp, "fn": fn,
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
        }
    return stats


def _build_report(
    items: List[Dict[str, Any]],
    confusion_p1: Counter,
    confusion_p2: Counter,
    phase: int,
    use_mock: bool,
) -> Dict[str, Any]:
    total = len(items)
    p1_correct = sum(1 for it in items if it["p1_correct"])
    p1_acc = p1_correct / total if total else 0.0

    report: Dict[str, Any] = {
        "schema_version": "1.0",
        "phase": phase,
        "mode": ("mock" if use_mock else "live") if phase == 2 else "heuristic",
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "total": total,
        "phase1_correct": p1_correct,
        "phase1_accuracy": round(p1_acc, 4),
        "phase1_per_family": _per_family_stats(items, 1),
        "phase1_confusion_top5": [
            {"expected": e, "actual": a, "count": c}
            for (e, a), c in confusion_p1.most_common(5)
        ],
    }

    if phase == 2:
        p2_correct = sum(1 for it in items if it.get("p2_correct"))
        p2_acc = p2_correct / total if total else 0.0
        report["phase2_correct"] = p2_correct
        report["phase2_accuracy"] = round(p2_acc, 4)
        report["phase2_lift"] = round(p2_acc - p1_acc, 4)
        report["phase2_per_family"] = _per_family_stats(items, 2)
        report["phase2_confusion_top5"] = [
            {"expected": e, "actual": a, "count": c}
            for (e, a), c in confusion_p2.most_common(5)
        ]

    report["items"] = items
    return report


# ── Output ───────────────────────────────────────────────────────────────────


def write_report(path: str, report: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)


def format_summary(report: Dict[str, Any]) -> str:
    """Compact human-readable summary string."""
    lines = [
        f"SR-101 Eval — phase={report['phase']}  mode={report['mode']}",
        f"  records: {report['total']}",
        f"  phase1_accuracy: {report['phase1_accuracy']:.3f}  "
        f"({report['phase1_correct']}/{report['total']})",
    ]
    if report["phase"] == 2:
        lines.append(
            f"  phase2_accuracy: {report['phase2_accuracy']:.3f}  "
            f"({report['phase2_correct']}/{report['total']})")
        lines.append(f"  phase2_lift:     {report['phase2_lift']:+.3f}")
    if report["phase1_confusion_top5"]:
        lines.append("  phase1 confusion (top5):")
        for c in report["phase1_confusion_top5"]:
            lines.append(
                f"    expected={c['expected']:<14} "
                f"actual={c['actual']:<14} n={c['count']}")
    return "\n".join(lines)


# ── CLI ──────────────────────────────────────────────────────────────────────


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="SR-101 FCTC-ES Suggester Eval-Harness.",
    )
    p.add_argument("--phase", type=int, choices=[1, 2], default=1,
                   help="Eval phase (1=heuristic only, 2=LLM)")
    grp = p.add_mutually_exclusive_group()
    grp.add_argument("--mock", action="store_true",
                     help="Phase-2: use deterministic mock LLM (no API key)")
    grp.add_argument("--live", action="store_true",
                     help="Phase-2: real API call (costs money)")
    p.add_argument("--golden", default=DEFAULT_GOLDEN,
                   help="Path to golden-set JSONL")
    p.add_argument("--report", default=DEFAULT_REPORT,
                   help="Path to write JSON report to")
    p.add_argument("--min-phase1-accuracy",
                   type=float, default=DEFAULT_MIN_PHASE1_ACCURACY,
                   help="Threshold gate for Phase-1 accuracy")
    p.add_argument("--exit-non-zero-on-threshold-miss",
                   action="store_true",
                   help="Exit 1 if phase1_accuracy below threshold "
                        "(CI/cron gate mode)")
    p.add_argument("--quiet", action="store_true",
                   help="Suppress stdout summary")
    return p.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)

    # Phase 2 requires explicit mode choice
    if args.phase == 2 and not (args.mock or args.live):
        print("ERROR: --phase 2 requires either --mock or --live",
              file=sys.stderr)
        return 2

    # Load + validate golden set
    try:
        records = load_golden(args.golden)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"ERROR loading golden set: {e}", file=sys.stderr)
        return 2

    errs = validate_golden(records)
    if errs:
        print("ERROR validating golden set:", file=sys.stderr)
        for e in errs:
            print(f"  {e}", file=sys.stderr)
        return 2

    # Run eval
    report = evaluate(records, phase=args.phase, use_mock=args.mock)

    # Write report
    try:
        write_report(args.report, report)
    except OSError as e:
        print(f"ERROR writing report: {e}", file=sys.stderr)
        return 2

    # Stdout summary
    if not args.quiet:
        print(format_summary(report))
        print(f"\nFull report: {args.report}")

    # Threshold gate
    if report["phase1_accuracy"] < args.min_phase1_accuracy:
        msg = (
            f"THRESHOLD MISS: phase1_accuracy "
            f"{report['phase1_accuracy']:.3f} < "
            f"{args.min_phase1_accuracy:.3f}"
        )
        print(msg, file=sys.stderr)
        if args.exit_non_zero_on_threshold_miss:
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
