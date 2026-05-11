#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
eval_match_field.py — Automatisierte Eval-Harness für ProfileLoader Pattern-Matching
================================================================================

LATEST HIT-RATE SNAPSHOT (2026-05-11)
-------------------------------------
Precision: 0.94  |  Recall: 0.91  |  F1: 0.925
Corpus: 152 cases (128 positive, 24 negative)
Threshold: 0.92 (CI fail-closed)

KONTEXT (Issue #55 / SR-56)
---------------------------
Eval-Harness die bei jeder PR Precision/Recall gegen einen Gold-Korpus
misst und CI bei Regression failen lässt.

EVALUIERT: Direkt die FIELD_PATTERNS Regex-Matches, NICHT die match_field()-
Funktion die VALUES zurückgibt. So können wir KEY-Korrektheit testen.

USAGE
-----
::

    cd survey-cli
    python tools/eval_match_field.py [--corpus tests/fixtures/match_field_corpus.jsonl] \
                                     [--threshold 0.92] \
                                     [--verbose]

Exit-Code:
  0  F1 >= threshold
  1  F1 <  threshold (CI-fail)

Pflicht-Kontext:
  - survey-cli/survey/profile_loader.py FIELD_PATTERNS
  - survey-cli/tests/fixtures/match_field_corpus.jsonl
  - AGENTS.md §13.8 FCTC-ES Phase 1
================================================================================
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

HERE = Path(__file__).parent
PARENT = HERE.parent
if str(PARENT) not in sys.path:
    sys.path.insert(0, str(PARENT))

from survey.profile_loader import ProfileLoader  # noqa: E402


@dataclass
class EvalResult:
    """Ergebnis der Evaluation."""
    total: int
    true_positives: int
    false_positives: int
    false_negatives: int
    true_negatives: int
    
    @property
    def precision(self) -> float:
        denom = self.true_positives + self.false_positives
        return self.true_positives / denom if denom > 0 else 0.0
    
    @property
    def recall(self) -> float:
        denom = self.true_positives + self.false_negatives
        return self.true_positives / denom if denom > 0 else 0.0
    
    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return 2 * p * r / (p + r) if (p + r) > 0 else 0.0


def load_corpus(corpus_path: Path) -> list[dict]:
    """Lädt Gold-Korpus aus JSONL-Datei.
    
    Format pro Zeile:
    {
        "role": "textbox",
        "label": "Vorname *",
        "placeholder": "",
        "expected_key": "first_name"  # oder null für negative cases
    }
    """
    cases = []
    with open(corpus_path, "r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                case = json.loads(line)
                cases.append(case)
            except json.JSONDecodeError as e:
                print(f"[WARN] Line {line_no}: Invalid JSON: {e}", file=sys.stderr)
    return cases


def match_pattern_key(label: str, placeholder: str = "") -> Optional[str]:
    """Direkter Pattern-Match auf FIELD_PATTERNS, gibt logical_key zurück.
    
    Dies testet die Pattern-Logik direkt, unabhängig von match_field()
    die auch role-Filtering und value-resolution macht.
    """
    combined = (label + " " + (placeholder or "")).strip().lower()
    
    for logical_key, pattern in ProfileLoader.FIELD_PATTERNS:
        if pattern.search(combined):
            return logical_key
    
    return None


def evaluate(corpus: list[dict], verbose: bool = False) -> EvalResult:
    """Evaluiert FIELD_PATTERNS Pattern-Matching gegen den Gold-Korpus.
    
    Testet direkt die Regex-Pattern, nicht die match_field() Funktion.
    """
    tp = fp = fn = tn = 0
    misses = []
    
    for case in corpus:
        role = case.get("role", "textbox")
        label = case.get("label", "")
        placeholder = case.get("placeholder", "")
        expected_key = case.get("expected_key")  # None für negative cases
        
        # Pattern-Match
        predicted_key = match_pattern_key(label, placeholder)
        
        # Klassifizierung
        if expected_key is not None:  # Positive case (erwarten Match)
            if predicted_key == expected_key:
                tp += 1
                if verbose:
                    print(f"[TP] '{label}' -> '{predicted_key}'")
            elif predicted_key is not None:
                fp += 1
                misses.append({
                    "type": "FP",
                    "label": label,
                    "expected": expected_key,
                    "predicted": predicted_key
                })
                if verbose:
                    print(f"[FP] '{label}' -> predicted '{predicted_key}', expected '{expected_key}'")
            else:
                fn += 1
                misses.append({
                    "type": "FN",
                    "label": label,
                    "expected": expected_key,
                    "predicted": None
                })
                if verbose:
                    print(f"[FN] '{label}' -> NO MATCH, expected '{expected_key}'")
        else:  # Negative case (erwarten kein Match)
            if predicted_key is None:
                tn += 1
                if verbose:
                    print(f"[TN] '{label}' -> NO MATCH (correct)")
            else:
                fp += 1
                misses.append({
                    "type": "FP_NEG",
                    "label": label,
                    "expected": None,
                    "predicted": predicted_key
                })
                if verbose:
                    print(f"[FP] '{label}' -> predicted '{predicted_key}', expected NO MATCH")
    
    if verbose and misses:
        print("\n=== MISSES ===")
        for m in misses:
            print(f"  {m['type']}: '{m['label']}' expected={m['expected']} got={m['predicted']}")
    
    return EvalResult(
        total=len(corpus),
        true_positives=tp,
        false_positives=fp,
        false_negatives=fn,
        true_negatives=tn
    )


def main():
    parser = argparse.ArgumentParser(
        description="Eval-Harness für ProfileLoader.FIELD_PATTERNS"
    )
    parser.add_argument(
        "--corpus",
        type=Path,
        default=PARENT / "tests" / "fixtures" / "match_field_corpus.jsonl",
        help="Pfad zum Gold-Korpus (JSONL)"
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.92,
        help="Minimum F1-Score für CI-Pass (default: 0.92)"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Zeige jeden Test-Case"
    )
    args = parser.parse_args()
    
    # Corpus laden
    if not args.corpus.exists():
        print(f"[ERROR] Corpus nicht gefunden: {args.corpus}", file=sys.stderr)
        print("[HINT] Erstelle survey-cli/tests/fixtures/match_field_corpus.jsonl", file=sys.stderr)
        sys.exit(1)
    
    corpus = load_corpus(args.corpus)
    if not corpus:
        print("[ERROR] Leerer Corpus", file=sys.stderr)
        sys.exit(1)
    
    print(f"[EVAL] Corpus: {len(corpus)} cases")
    print(f"[EVAL] Threshold: F1 >= {args.threshold}")
    print()
    
    # Evaluation
    result = evaluate(corpus, verbose=args.verbose)
    
    # Report
    print("=" * 60)
    print("EVAL RESULTS")
    print("=" * 60)
    print(f"Total Cases:      {result.total}")
    print(f"True Positives:   {result.true_positives}")
    print(f"False Positives:  {result.false_positives}")
    print(f"False Negatives:  {result.false_negatives}")
    print(f"True Negatives:   {result.true_negatives}")
    print("-" * 60)
    print(f"Precision:        {result.precision:.4f}")
    print(f"Recall:           {result.recall:.4f}")
    print(f"F1 Score:         {result.f1:.4f}")
    print("=" * 60)
    
    # Threshold Check
    if result.f1 >= args.threshold:
        print(f"\n[PASS] F1 {result.f1:.4f} >= threshold {args.threshold}")
        sys.exit(0)
    else:
        print(f"\n[FAIL] F1 {result.f1:.4f} < threshold {args.threshold}")
        sys.exit(1)


if __name__ == "__main__":
    main()
