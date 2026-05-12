"""SR-55 — Tests fuer survey/learn (aggregator + suggester + cli).

Wir testen drei Schichten unabhaengig:

  1. ``suggester.suggest_family`` — gegen bekannte Komposita.
  2. ``aggregator.aggregate_misses`` — gegen ein fake matcher-telemetry-JSONL.
  3. CLI dry-run via ``learn.cli.main(['aggregate', ...])`` + ``review --dry-run``.

KEIN End-to-End mit echtem ProfileLoader — das deckt
``test_profile_match_field.py`` ab. Hier nur Lern-Pipeline-Mechanik.
"""

from __future__ import annotations

import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout

# Make survey-cli/ importable
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from survey.learn import (  # noqa: E402
    suggest_family,
    aggregate_misses,
    write_suggestions,
    normalize_label,
)
from survey.learn import cli as learn_cli  # noqa: E402


class SuggesterTest(unittest.TestCase):
    """Family-Vorschlag fuer typische DE-Komposita."""

    def test_kompositum_faxnummer_phone(self) -> None:
        r = suggest_family("faxnummer")
        self.assertEqual(r.family, "phone")
        self.assertGreater(r.confidence, 0.5)

    def test_kompositum_mobilfunknummer_phone(self) -> None:
        r = suggest_family("mobilfunknummer")
        self.assertEqual(r.family, "phone")

    def test_lieblingsfarbe_no_family(self) -> None:
        r = suggest_family("lieblingsfarbe")
        self.assertIsNone(r.family)
        self.assertEqual(r.label_tokens, ["lieblingsfarbe"])

    def test_email_address_email(self) -> None:
        r = suggest_family("email address")
        self.assertEqual(r.family, "email")

    def test_strasse_und_hausnummer(self) -> None:
        r = suggest_family("strasse und hausnummer")
        # "strasse" → street family (substring "strasse" in fam_tokens)
        self.assertEqual(r.family, "street")

    def test_empty_label(self) -> None:
        r = suggest_family("")
        self.assertIsNone(r.family)
        self.assertEqual(r.confidence, 0.0)


class NormalizeLabelTest(unittest.TestCase):
    def test_strip_required_marker(self) -> None:
        self.assertEqual(normalize_label("  Postleitzahl *  "), "postleitzahl")
        self.assertEqual(normalize_label("PLZ (Pflicht)"), "plz")
        self.assertEqual(normalize_label("Vorname (required)"), "vorname")

    def test_multi_whitespace(self) -> None:
        self.assertEqual(normalize_label("Erste\t\tStrasse"), "erste strasse")


class AggregatorTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.log_dir = self.tmp.name
        # Fake matcher-telemetry-*.jsonl mit miss_labels.
        path = os.path.join(self.log_dir, "matcher-telemetry-fake.jsonl")
        records = [
            {
                "persona": "jeremy_schulze",
                "loads": 1,
                "match_hits": 5,
                "match_misses": 4,
                "miss_labels": [
                    {"role": "textbox", "label": "Faxnummer"},
                    {"role": "textbox", "label": "  Faxnummer  *"},  # dup nach normalize
                    {"role": "textbox", "label": "Lieblingsfarbe"},
                    {"role": "textbox", "label": "Mobilfunknummer"},
                ],
            },
        ]
        with open(path, "w") as f:
            for r in records:
                f.write(json.dumps(r) + "\n")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_aggregate_groups_normalized_labels(self) -> None:
        sug = aggregate_misses(self.log_dir, min_count=1)
        # Faxnummer + "  Faxnummer  *" sollten via normalize_label gleich sein
        by_label = {s["normalized_label"]: s for s in sug}
        self.assertIn("faxnummer", by_label)
        self.assertEqual(by_label["faxnummer"]["count"], 2)
        self.assertEqual(by_label["faxnummer"]["suggested_family"], "phone")

    def test_min_count_filter(self) -> None:
        sug = aggregate_misses(self.log_dir, min_count=2)
        # Nur "faxnummer" hat count >= 2.
        self.assertEqual(len(sug), 1)
        self.assertEqual(sug[0]["normalized_label"], "faxnummer")

    def test_persona_filter(self) -> None:
        sug_match = aggregate_misses(self.log_dir, min_count=1, persona="jeremy_schulze")
        sug_none = aggregate_misses(self.log_dir, min_count=1, persona="does_not_exist")
        self.assertGreater(len(sug_match), 0)
        self.assertEqual(len(sug_none), 0)

    def test_write_suggestions_jsonl(self) -> None:
        sug = aggregate_misses(self.log_dir, min_count=1)
        out = os.path.join(self.log_dir, "out.jsonl")
        write_suggestions(out, sug)
        self.assertTrue(os.path.exists(out))
        with open(out) as f:
            lines = [json.loads(l) for l in f if l.strip()]
        self.assertEqual(len(lines), len(sug))


class CLITest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.log_dir = self.tmp.name
        path = os.path.join(self.log_dir, "matcher-telemetry-cli.jsonl")
        with open(path, "w") as f:
            f.write(
                json.dumps(
                    {
                        "persona": "jeremy_schulze",
                        "miss_labels": [
                            {"role": "textbox", "label": "Faxnummer"},
                            {"role": "textbox", "label": "Faxnummer"},
                        ],
                    }
                )
                + "\n"
            )

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_cmd_aggregate(self) -> None:
        out_path = os.path.join(self.log_dir, "suggestions.jsonl")
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = learn_cli.main(
                [
                    "aggregate",
                    "--logs",
                    self.log_dir,
                    "--out",
                    out_path,
                    "--min-count",
                    "1",
                ]
            )
        self.assertEqual(rc, 0)
        self.assertIn("wrote", buf.getvalue())
        self.assertTrue(os.path.exists(out_path))
        with open(out_path) as f:
            items = [json.loads(l) for l in f if l.strip()]
        self.assertGreaterEqual(len(items), 1)

    def test_cmd_review_dry_run(self) -> None:
        out_path = os.path.join(self.log_dir, "suggestions.jsonl")
        learn_cli.main(
            [
                "aggregate",
                "--logs",
                self.log_dir,
                "--out",
                out_path,
                "--min-count",
                "1",
            ]
        )
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = learn_cli.main(
                [
                    "review",
                    "--logs",
                    self.log_dir,
                    "--input",
                    out_path,
                    "--dry-run",
                ]
            )
        self.assertEqual(rc, 0)
        self.assertIn("review done", buf.getvalue())
        # dry-run schreibt KEINE accepted/rejected Files
        self.assertFalse(
            os.path.exists(os.path.join(self.log_dir, "pattern-suggestions-accepted.jsonl"))
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
