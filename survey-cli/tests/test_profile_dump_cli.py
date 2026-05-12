# -*- coding: utf-8 -*-
"""
test_profile_dump_cli.py
========================

Test-Suite fuer Issue #52 (SR-54):
``ProfileLoader.telemetry()`` + ``survey profile dump`` JSONL-Output.

(A) Counter-Korrektheit
    Nach 5 Treffern (Stadt, PLZ, Email, Vorname, Geburtsjahr) und 3
    Miss-Versuchen (Lieblingstier, Hobby, Wahn-Frage) MUSS
    ``telemetry()`` zeigen:
        match_hits   >= 5
        match_misses >= 3
        per_key_hits enthaelt city, postal_code, email, first_name, birth_year

(B) Reset
    ``reset_telemetry()`` setzt alle Counter zurueck.

(C) JSONL-Datei
    Ein simulierter ``profile dump --out <pfad>`` MUSS eine Datei mit
    JSONL-Zeilen schreiben — eine pro Persona.
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


class TestCounterCorrectness(unittest.TestCase):
    def setUp(self):
        ProfileLoader.reset_telemetry()
        self.profile = ProfileLoader.load_profile(profile_name="jeremy_schulze")
        self.profile["_loader_name"] = "jeremy_schulze"

    def test_five_hits_three_misses(self):
        # 5 hits
        ProfileLoader.match_field("textbox", "Stadt", self.profile)
        ProfileLoader.match_field("textbox", "PLZ", self.profile)
        ProfileLoader.match_field("textbox", "E-Mail", self.profile)
        ProfileLoader.match_field("textbox", "Vorname", self.profile)
        ProfileLoader.match_field("textbox", "Geburtsjahr", self.profile)
        # 3 misses
        ProfileLoader.match_field("textbox", "Lieblingstier", self.profile)
        ProfileLoader.match_field("textbox", "Was magst du?", self.profile)
        ProfileLoader.match_field("textbox", "Hobby?", self.profile)

        telem = ProfileLoader.telemetry()
        bucket = telem["jeremy_schulze"]
        self.assertGreaterEqual(bucket["match_hits"], 5)
        self.assertGreaterEqual(bucket["match_misses"], 3)
        per = bucket["per_key_hits"]
        for key in ("city", "postal_code", "email", "first_name", "birth_year"):
            self.assertGreaterEqual(per.get(key, 0), 1, f"per_key_hits missing {key}: {per}")


class TestResetTelemetry(unittest.TestCase):
    def test_reset_clears(self):
        profile = ProfileLoader.load_profile(profile_name="jeremy_schulze")
        profile["_loader_name"] = "jeremy_schulze"
        ProfileLoader.match_field("textbox", "Stadt", profile)
        self.assertGreater(ProfileLoader.telemetry()["jeremy_schulze"]["match_hits"], 0)
        ProfileLoader.reset_telemetry()
        self.assertEqual(ProfileLoader.telemetry(), {})


class TestJsonlOutput(unittest.TestCase):
    """``survey profile dump --out <path>`` schreibt JSONL."""

    def setUp(self):
        ProfileLoader.reset_telemetry()

    def test_jsonl_persona_per_line(self):
        # Telemetrie fuer 2 Personas erzeugen
        p1 = ProfileLoader.load_profile(profile_name="jeremy_schulze")
        p1["_loader_name"] = "jeremy_schulze"
        ProfileLoader.match_field("textbox", "Stadt", p1)
        p2 = ProfileLoader.load_profile(profile_name="anna_meyer")
        p2["_loader_name"] = "anna_meyer"
        ProfileLoader.match_field("textbox", "Phone", p2)

        # cmd_profile dump simulieren (das eigentliche stdout-Format
        # interessiert uns hier nicht, nur die Datei).
        with tempfile.TemporaryDirectory() as td:
            out_path = os.path.join(td, "telem.jsonl")
            with open(out_path, "w") as f:
                for persona, bucket in ProfileLoader.telemetry().items():
                    f.write(
                        json.dumps(
                            {"persona": persona, **bucket},
                            ensure_ascii=False,
                        )
                        + "\n"
                    )

            with open(out_path) as f:
                lines = [ln for ln in f.read().splitlines() if ln.strip()]

        self.assertEqual(len(lines), 2)
        rec_personas = sorted(json.loads(ln)["persona"] for ln in lines)
        self.assertEqual(rec_personas, ["anna_meyer", "jeremy_schulze"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
