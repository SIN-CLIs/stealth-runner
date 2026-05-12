# -*- coding: utf-8 -*-
"""
test_profile_miss_labels.py
============================

Test-Suite fuer Issue #58 (SR-59):
Persistente, semantisch getaggte ``miss_labels`` in der Matcher-Telemetrie.

Akzeptanzkriterien aus dem Issue-Body:
  1. ``_record_match(hit=False)`` schreibt einen Dict mit allen Pflichtfeldern.
  2. ``user_value_provided`` ist IMMER ein Boolean — niemals der echte Wert.
  3. JSONL-Roundtrip (write → read → schema unverändert).
  4. ``cluster_miss_labels()`` gruppiert per Token-Jaccard ≥ 0.6.
  5. ``_guess_candidate_keys()`` liefert plausible logical_keys fuer
     near-miss Labels (z.B. "Mobilnummer" → ``phone``).

WARUM separat von test_profile_dump_cli.py?
  test_profile_dump_cli.py prueft Counter-Korrektheit (loads/hits/misses) —
  also das SR-54-Telemetrie-Schema. Dieses Modul prueft das SR-59-Schema-
  Delta (miss_labels-Reichhaltigkeit). Trennt die Verantwortlichkeit klar
  und macht ein Schema-Regression auf einen Blick sichtbar.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
PARENT = os.path.dirname(HERE)
if PARENT not in sys.path:
    sys.path.insert(0, PARENT)

from survey.profile_loader import ProfileLoader
from survey.learn.aggregator import cluster_miss_labels


# Pflichtfelder pro miss_label-Record (SR-59 #58 Schema).
REQUIRED_FIELDS = {
    "role", "label",                       # backward-compat
    "ts", "question_text", "page_url",
    "snapshot_hash", "candidate_keys", "user_value_provided",
}


def _force_miss(label: str, profile_name: str = "jeremy_schulze",
                role: str = "textbox", page_url: str = None) -> dict:
    """Trigger one matcher miss + return the bucket for inspection."""
    profile = ProfileLoader.load_profile(profile_name=profile_name)
    profile["_loader_name"] = profile_name
    if page_url is not None:
        profile["_page_url"] = page_url
    # Label that definitely won't match any FIELD_PATTERN.
    ProfileLoader.match_field(role, label, profile)
    return ProfileLoader.telemetry().get(profile_name, {})


class TestMissLabelSchema(unittest.TestCase):
    """Akzeptanzkriterium 1: alle Pflichtfelder vorhanden."""

    def setUp(self):
        ProfileLoader.reset_telemetry()

    def test_record_has_all_required_fields(self):
        bucket = _force_miss("Lieblings-Pizza Belag?")
        mls = bucket.get("miss_labels", [])
        self.assertEqual(len(mls), 1, f"expected 1 miss_label, got {len(mls)}")
        record = mls[0]
        self.assertEqual(
            set(record.keys()) & REQUIRED_FIELDS, REQUIRED_FIELDS,
            f"missing fields: {REQUIRED_FIELDS - set(record.keys())}",
        )

    def test_ts_is_iso_format(self):
        bucket = _force_miss("Lieblings-Auto-Marke?")
        record = bucket["miss_labels"][0]
        # ISO 8601 mit timezone — fromisoformat akzeptiert "+00:00".
        from datetime import datetime
        parsed = datetime.fromisoformat(record["ts"])
        self.assertIsNotNone(parsed.tzinfo,
                             f"ts must carry timezone: {record['ts']!r}")

    def test_snapshot_hash_is_stable(self):
        """Gleiches Label → gleicher snapshot_hash (12 Hex-Zeichen)."""
        bucket1 = _force_miss("Hobby?")
        h1 = bucket1["miss_labels"][0]["snapshot_hash"]
        ProfileLoader.reset_telemetry()
        bucket2 = _force_miss("Hobby?")
        h2 = bucket2["miss_labels"][0]["snapshot_hash"]
        self.assertEqual(h1, h2, "snapshot_hash unstable across runs")
        self.assertEqual(len(h1), 12)
        self.assertTrue(all(c in "0123456789abcdef" for c in h1),
                        f"non-hex chars in hash: {h1!r}")

    def test_page_url_forwarded_from_profile(self):
        bucket = _force_miss("Was magst du?",
                             page_url="https://example.com/survey/q1")
        self.assertEqual(bucket["miss_labels"][0]["page_url"],
                         "https://example.com/survey/q1")

    def test_page_url_defaults_to_none(self):
        bucket = _force_miss("Lieblingstier?")
        self.assertIsNone(bucket["miss_labels"][0]["page_url"])


class TestPrivacyInvariant(unittest.TestCase):
    """Akzeptanzkriterium 2: ``user_value_provided`` ist nur Boolean."""

    def setUp(self):
        ProfileLoader.reset_telemetry()

    def test_user_value_provided_is_boolean(self):
        bucket = _force_miss("Lieblings-Wein?")
        record = bucket["miss_labels"][0]
        self.assertIsInstance(record["user_value_provided"], bool,
                              "user_value_provided MUSS bool sein (PII-Schutz)")
        # Default-Wert ist False — kein User-Eingriff bei Miss.
        self.assertFalse(record["user_value_provided"])

    def test_no_user_value_keys_leak_into_record(self):
        """Sanity: kein Feld wie 'user_value' / 'value' / 'input' im Record."""
        bucket = _force_miss("Geheimes Lieblingswort?")
        record = bucket["miss_labels"][0]
        for forbidden in ("user_value", "value", "user_input", "input"):
            self.assertNotIn(forbidden, record,
                             f"PII-leak risk: '{forbidden}' in miss_label")


class TestCandidateKeys(unittest.TestCase):
    """Akzeptanzkriterium 5: _guess_candidate_keys liefert near-miss hints."""

    def setUp(self):
        ProfileLoader.reset_telemetry()

    def test_phone_hint_for_mobilnummer_variant(self):
        # "Mobilnummer" matched FIELD_PATTERNS — also kein Miss.
        # Wir testen direkt die Hilfsfunktion mit einem Label, das KEIN
        # Pattern matcht, aber semantisch verwandt ist: "Mobile Phone Carrier"
        cands = ProfileLoader._guess_candidate_keys("Welcher Mobile Carrier?")
        self.assertIn("phone", cands)

    def test_no_candidates_for_truly_unknown(self):
        cands = ProfileLoader._guess_candidate_keys("xyzzy lieblings 123")
        self.assertEqual(cands, [])

    def test_max_k_respected(self):
        # Label mit MEHREREN Familie-Hints → max_k limitiert.
        cands = ProfileLoader._guess_candidate_keys(
            "Email Telefon Stadt Strasse Land", max_k=2)
        self.assertLessEqual(len(cands), 2)

    def test_empty_text_returns_empty(self):
        self.assertEqual(ProfileLoader._guess_candidate_keys(""), [])
        self.assertEqual(ProfileLoader._guess_candidate_keys(None or ""), [])


class TestJsonlRoundtrip(unittest.TestCase):
    """Akzeptanzkriterium 3: write → read → schema unverändert."""

    def setUp(self):
        ProfileLoader.reset_telemetry()

    def test_roundtrip_preserves_schema(self):
        # Erzeuge 2 Misses
        _force_miss("Lieblingstier?", page_url="https://x.example/q1")
        _force_miss("Lieblingsband?")

        telem = ProfileLoader.telemetry()
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "matcher-telemetry-test.jsonl")
            with open(path, "w") as f:
                for persona, bucket in telem.items():
                    line = json.dumps(
                        {"persona": persona, **bucket}, ensure_ascii=False,
                    )
                    f.write(line + "\n")

            with open(path) as f:
                recs = [json.loads(ln) for ln in f if ln.strip()]

        self.assertEqual(len(recs), 1)
        mls = recs[0].get("miss_labels", [])
        self.assertGreaterEqual(len(mls), 2)
        for ml in mls:
            self.assertEqual(set(ml.keys()) & REQUIRED_FIELDS,
                             REQUIRED_FIELDS,
                             f"roundtrip dropped fields: {ml.keys()}")


class TestClusterMissLabels(unittest.TestCase):
    """Akzeptanzkriterium 4: Token-Jaccard-Clustering >= 0.6."""

    def test_jaccard_groups_paraphrases(self):
        ml = [
            {"question_text": "Postleitzahl angeben"},
            {"question_text": "Bitte Postleitzahl angeben"},
            {"question_text": "Lieblings Pizza Belag"},
        ]
        clusters = cluster_miss_labels(ml, threshold=0.5)
        # Erwartet: 2 Cluster — PLZ-Variante + Pizza
        self.assertEqual(len(clusters), 2,
                         f"expected 2 clusters, got {list(clusters.keys())}")
        sizes = sorted(len(v) for v in clusters.values())
        self.assertEqual(sizes, [1, 2])

    def test_legacy_label_field_still_works(self):
        # Backward-compat: aggregator soll auch alte Records (nur ``label``)
        # clustern koennen.
        ml = [{"label": "Stadt"}, {"label": "Stadt"}, {"label": "Beruf"}]
        clusters = cluster_miss_labels(ml, threshold=0.5)
        self.assertEqual(len(clusters), 2)

    def test_empty_input(self):
        self.assertEqual(cluster_miss_labels([]), {})

    def test_threshold_strictness(self):
        # Zwei voellig unaehnliche Labels → 2 Cluster bei threshold 0.9
        ml = [{"question_text": "Postleitzahl Berlin"},
              {"question_text": "Lieblings Pizza Belag"}]
        self.assertEqual(len(cluster_miss_labels(ml, threshold=0.9)), 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
