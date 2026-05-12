#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
smoke_match_field.py — Synthetischer E2E-Smoke fuer ProfileLoader.match_field
=============================================================================

KONTEXT (Issue #49 / SR-51)
---------------------------
Die §13-Unit-Tests sind alle gruen, aber sie testen IDEALE Labels
("Postleitzahl"). Echte Surveys mischen Label-Varianten:

  - Leading/Trailing-Whitespace      ("  PLZ  ")
  - Pflichtfeld-Marker ``*``         ("Vorname *")
  - Trailing-Doppelpunkt             ("E-Mail:")
  - Pre-/Suffixe                     ("Bitte geben Sie Ihre PLZ ein")
  - DE/EN-Mischformen                ("Your Stadt")
  - HTML-Artefakte aus innerText     ("Vorname\n(required)")
  - Provider-spezifische Phrasen     ("In welcher Stadt wohnen Sie?")
  - Kombinierte Labels               ("PLZ und Ort")
  - Englische Variationen            ("Zip code", "Year of birth")

Statt einer echten Survey (Login, Tokens, Brittleness) generieren wir
einen synthetischen Korpus aus genau diesen Variationen. Damit wird
schnell sichtbar, ob die Patterns realweltlich greifen.

USAGE
-----
::

    cd survey-cli
    python tools/smoke_match_field.py [--out logs/smoke-{date}.jsonl] \\
                                       [--profile jeremy_schulze] \\
                                       [--threshold 0.70]

Output:
  - stdout-Summary (Hit-Rate gesamt, Top-N Miss-Labels)
  - JSONL ein Record pro Probe in ``--out``

Exit-Code:
  0  Hit-Rate >= threshold
  1  Hit-Rate <  threshold (CI-tauglich)

Pflicht-Kontext:
  - survey-cli/survey/profile_loader.py FIELD_PATTERNS
  - AGENTS.md §13.3 / §13.8
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PARENT = os.path.dirname(HERE)
if PARENT not in sys.path:
    sys.path.insert(0, PARENT)

from survey.profile_loader import ProfileLoader  # noqa: E402


# ---------------------------------------------------------------------------
# CORPUS — (role, label, placeholder, erwartete_familie)
# erwartete_familie ist nur ein Marker fuer den Auswerter, der Matcher
# bekommt nur (role, label, placeholder).
# ---------------------------------------------------------------------------

# Schema: (role, label, placeholder, expected_key)
CORPUS: list[tuple[str, str, str, str]] = [
    # First name
    ("textbox", "Vorname", "", "first_name"),
    ("textbox", "Vorname *", "", "first_name"),
    ("textbox", "Vorname (Pflichtfeld)", "", "first_name"),
    ("textbox", "  Vorname:  ", "", "first_name"),
    ("textbox", "First name", "", "first_name"),
    ("textbox", "Given name", "Your first name", "first_name"),
    ("textbox", "Forename", "", "first_name"),
    # Last name
    ("textbox", "Nachname", "", "last_name"),
    ("textbox", "Last name *", "", "last_name"),
    ("textbox", "Surname", "", "last_name"),
    ("textbox", "Family name", "", "last_name"),
    # Email
    ("textbox", "E-Mail", "", "email"),
    ("textbox", "E-Mail-Adresse *", "", "email"),
    ("textbox", "Email", "", "email"),
    ("textbox", "Email address", "you@example.com", "email"),
    ("textbox", "Mailadresse", "", "email"),
    ("textbox", "Ihre E-Mail:", "", "email"),
    # Postal code
    ("textbox", "PLZ", "", "postal_code"),
    ("textbox", "Postleitzahl *", "", "postal_code"),
    ("textbox", "Zip", "", "postal_code"),
    ("textbox", "ZIP code", "", "postal_code"),
    ("textbox", "Postal code", "", "postal_code"),
    ("textbox", "Postcode", "", "postal_code"),
    ("spinbutton", "PLZ", "", "postal_code"),
    ("textbox", "Bitte geben Sie Ihre PLZ ein", "", "postal_code"),
    # City
    ("textbox", "Stadt", "", "city"),
    ("textbox", "Stadt *", "", "city"),
    ("textbox", "Wohnort", "", "city"),
    ("textbox", "Ort", "", "city"),
    ("textbox", "City", "", "city"),
    ("textbox", "Town", "", "city"),
    ("textbox", "In welcher Stadt wohnen Sie?", "", "city"),
    # State / region
    ("textbox", "Bundesland", "", "state_region"),
    ("textbox", "Region", "", "state_region"),
    ("textbox", "State", "", "state_region"),
    ("textbox", "Province", "", "state_region"),
    # Country
    ("textbox", "Land", "", "country"),
    ("textbox", "Wohnsitzland", "", "country"),
    ("textbox", "Country", "", "country"),
    ("textbox", "Country of residence", "", "country"),
    ("combobox", "In welchem Land wohnen Sie?", "", "country"),
    # Street
    ("textbox", "Straße", "", "street"),
    ("textbox", "Strasse und Hausnummer", "", "street"),
    ("textbox", "Address", "", "street"),
    ("textbox", "Street", "", "street"),
    ("textbox", "Adresse *", "", "street"),
    # Birth year
    ("textbox", "Geburtsjahr", "", "birth_year"),
    ("spinbutton", "Geburtsjahr *", "", "birth_year"),
    ("textbox", "Jahrgang", "", "birth_year"),
    ("textbox", "Year of birth", "YYYY", "birth_year"),
    ("textbox", "Birth year", "", "birth_year"),
    ("textbox", "What year were you born?", "", "birth_year"),
    # Age
    ("spinbutton", "Alter", "", "age"),
    ("textbox", "Wie alt sind Sie?", "", "age"),
    ("spinbutton", "Age", "", "age"),
    ("textbox", "Your age", "", "age"),
    # Gender
    ("textbox", "Geschlecht", "", "gender"),
    ("textbox", "Gender", "", "gender"),
    ("textbox", "Sex", "", "gender"),
    # Household size
    ("spinbutton", "Haushaltsgröße", "", "household_size"),
    ("spinbutton", "Personen im Haushalt", "", "household_size"),
    ("spinbutton", "Household size", "", "household_size"),
    ("spinbutton", "People in household", "", "household_size"),
    ("spinbutton", "Wie viele Personen leben in Ihrem Haushalt?", "", "household_size"),
    # Personal income
    ("textbox", "Einkommen", "", "income"),
    ("textbox", "Gehalt", "", "income"),
    ("textbox", "Salary", "", "income"),
    ("textbox", "Personal income", "", "income"),
    # Household income
    ("textbox", "Haushaltseinkommen", "", "hh_income"),
    ("textbox", "Household income", "", "hh_income"),
    ("textbox", "Familieneinkommen", "", "hh_income"),
    # Phone
    ("textbox", "Telefonnummer", "", "phone"),
    ("textbox", "Handy", "", "phone"),
    ("textbox", "Mobilnummer", "", "phone"),
    ("textbox", "Phone", "", "phone"),
    ("textbox", "Phone number", "+49 ...", "phone"),
    # Job / industry
    ("textbox", "Beruf", "", "job_title"),
    ("textbox", "Job title", "", "job_title"),
    ("textbox", "Branche", "", "industry"),
    ("textbox", "Industry", "", "industry"),
    # Nationality / language
    ("textbox", "Nationalität", "", "nationality"),
    ("textbox", "Staatsangehörigkeit", "", "nationality"),
    ("textbox", "Muttersprache", "", "language"),
    ("textbox", "Sprache", "", "language"),
    ("textbox", "Language", "", "language"),
    # Full name (vorsichtig — kommt nach first/last in Patterns)
    ("textbox", "Vollständiger Name", "", "full_name"),
    ("textbox", "Full name", "", "full_name"),
    # NEGATIV-FAELLE: matcht hoffentlich NICHTS
    ("textbox", "Lieblingsfarbe?", "", None),
    ("textbox", "Hobby", "", None),
    ("textbox", "Wie zufrieden waren Sie?", "", None),
    ("button", "Weiter", "", None),
    ("radio", "Ja", "", None),
]


def expected_value(profile: dict, expected_key: str | None) -> str | None:
    """Hilfsfunktion: was haette die richtige Familie geliefert?"""
    if expected_key is None:
        return None
    return ProfileLoader._resolve_value(expected_key, profile)


class SmokeResult:
    """Aggregierte Smoke-Statistik — als Plain-Python-Objekt fuer Test-Asserts."""

    def __init__(self) -> None:
        self.records: list[dict] = []
        self.n_pos = 0
        self.n_neg = 0
        self.hits = 0
        self.wrong_family = 0
        self.misses: list[tuple[str, str, str]] = []
        self.false_positives: list[tuple[str, str, str]] = []

    @property
    def hit_rate(self) -> float:
        """Hit-Rate fuer positive Faelle in **Prozent** (0..100)."""
        return (self.hits / self.n_pos * 100.0) if self.n_pos else 0.0

    @property
    def false_positive_rate(self) -> float:
        """FP-Rate fuer negative Faelle in **Prozent** (0..100)."""
        return (len(self.false_positives) / self.n_neg * 100.0) if self.n_neg else 0.0


def run_smoke(
    profile_name: str = "jeremy_schulze",
    write_jsonl: bool = False,
    out_path: str = "",
) -> SmokeResult:
    """Run the smoke evaluation in-process and return a SmokeResult.

    Diese Funktion ist die importierbare API fuer Tests
    (siehe tests/test_smoke_match_field.py). ``main()`` ist ein duenner
    CLI-Wrapper drumherum.
    """
    profile = ProfileLoader.load_profile(profile_name=profile_name)
    profile["_loader_name"] = profile_name

    res = SmokeResult()
    res.n_pos = sum(1 for c in CORPUS if c[3] is not None)
    res.n_neg = sum(1 for c in CORPUS if c[3] is None)

    for role, label, placeholder, expected_key in CORPUS:
        actual = ProfileLoader.match_field(role, label, profile, placeholder)
        exp_val = expected_value(profile, expected_key)
        rec = {
            "role": role,
            "label": label,
            "placeholder": placeholder,
            "expected_key": expected_key,
            "expected_value": exp_val,
            "actual_value": actual,
        }
        if expected_key is None:
            if actual is not None:
                rec["status"] = "FALSE_POSITIVE"
                res.false_positives.append((role, label, str(actual)))
            else:
                rec["status"] = "CORRECT_REJECT"
        else:
            if actual is None:
                rec["status"] = "MISS"
                res.misses.append((role, label, expected_key))
            elif exp_val is not None and str(actual) == str(exp_val):
                rec["status"] = "HIT"
                res.hits += 1
            else:
                rec["status"] = "WRONG_FAMILY"
                res.wrong_family += 1
        res.records.append(rec)

    if write_jsonl:
        if not out_path:
            today = datetime.date.today().isoformat()
            log_dir = os.path.join(PARENT, "logs")
            os.makedirs(log_dir, exist_ok=True)
            out_path = os.path.join(log_dir, f"smoke-{today}.jsonl")
        try:
            with open(out_path, "w") as f:
                for rec in res.records:
                    f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            print(f"  records geschrieben: {out_path}")
        except Exception as exc:
            print(f"  WARN: JSONL write failed: {exc}")

    return res


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Smoke-Test ProfileLoader.match_field gegen synth. Korpus"
    )
    parser.add_argument("--profile", default="jeremy_schulze", help="Persona-Basename")
    parser.add_argument("--out", default="", help="JSONL-Output (default: logs/smoke-{date}.jsonl)")
    parser.add_argument(
        "--threshold", type=float, default=0.70, help="Mindest-Hit-Rate fuer positive Faelle"
    )
    args = parser.parse_args()

    res = run_smoke(args.profile, write_jsonl=True, out_path=args.out)

    print("=" * 70)
    print(f"  SMOKE: match_field gegen synth. Korpus ({args.profile})")
    print("=" * 70)
    print(f"  positive Faelle:  {res.n_pos}")
    print(f"  negative Faelle:  {res.n_neg}")
    print(f"  HITS (richtig):   {res.hits}  → hit-rate {res.hit_rate:.1f}%")
    print(f"  WRONG_FAMILY:     {res.wrong_family}")
    print(f"  MISSES:           {len(res.misses)}")
    print(
        f"  FALSE_POSITIVES:  {len(res.false_positives)}  → fp-rate {res.false_positive_rate:.1f}%"
    )
    print()
    if res.misses:
        print("  Top MISS-Labels:")
        for role, label, key in res.misses[:10]:
            print(f"    [{role}]  expected={key:14s}  label={label!r}")
        print()
    if res.false_positives:
        print("  FALSE_POSITIVE-Labels (haben gematcht obwohl nichts erwartet war):")
        for role, label, actual in res.false_positives[:10]:
            print(f"    [{role}]  label={label!r}  -> {actual!r}")
        print()

    threshold_pct = args.threshold * 100.0
    print()
    if res.hit_rate < threshold_pct:
        print(f"  FAIL: hit-rate {res.hit_rate:.1f}% < threshold {threshold_pct:.1f}%")
        return 1
    print(f"  OK:   hit-rate {res.hit_rate:.1f}% >= threshold {threshold_pct:.1f}%")
    return 0


if __name__ == "__main__":
    sys.exit(main())
