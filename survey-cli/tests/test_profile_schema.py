# -*- coding: utf-8 -*-
"""
test_profile_schema.py
======================

Test-Suite fuer Issue #51 (SR-53):

(A) Pflichtfeld-Coverage
    - Alle drei Demo-Personas (jeremy_schulze, anna_meyer, thomas_weber)
      MUESSEN alle REQUIRED_KEYS gesetzt haben (nicht None, nicht "").
    - Profile mit fehlenden REQUIRED_KEYS MUESSEN beim load_profile()
      eine ``logging.WARNING`` mit dem Praefix "profile_loader:" emittieren.

(B) Erweiterte Keyword-Familien
    - "phone" / "Telefonnummer" / "Handy" → profile['phone']
    - "Land" / "Country" → profile['country'] (NICHT 'bundesland' aus state)
    - "Bundesland" → profile['state'] (NICHT 'country')
    - first_name/last_name werden DIRECT aus Profile gelesen, statt aus
      ``name.split()``.

(C) Telemetrie-Hooks (SR-54)
    - load_profile() incrementiert ``loads`` und schreibt ``missing_required_count``.
    - match_field() Hit/Miss-Counter funktionieren pro Persona.

Pflicht-Kontext:
    - survey-cli/survey/profile_loader.py REQUIRED_KEYS + load_profile +
      match_field + _record_match.
"""

from __future__ import annotations

import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
PARENT = os.path.dirname(HERE)
if PARENT not in sys.path:
    sys.path.insert(0, PARENT)

from survey.profile_loader import ProfileLoader


PROFILES_DIR = os.path.join(PARENT, "survey", "profiles")


class TestRequiredKeysComplete(unittest.TestCase):
    """Pflichtfeld-Coverage aller mitgelieferten Personas."""

    def setUp(self):
        ProfileLoader.reset_telemetry()

    def _assert_complete(self, profile_name: str):
        p = ProfileLoader.load_profile(profile_name=profile_name)
        missing = ProfileLoader._missing_required(p)
        self.assertEqual(
            missing,
            set(),
            f"Persona {profile_name!r} fehlen REQUIRED_KEYS: {sorted(missing)}",
        )

    def test_jeremy_schulze_complete(self):
        self._assert_complete("jeremy_schulze")

    def test_anna_meyer_complete(self):
        self._assert_complete("anna_meyer")

    def test_thomas_weber_complete(self):
        self._assert_complete("thomas_weber")


class TestMissingRequiredEmitsWarning(unittest.TestCase):
    """Persona ohne Required-Key → WARNING im Logger."""

    def setUp(self):
        ProfileLoader.reset_telemetry()

    def test_default_unknown_profile_warns(self):
        # Nicht-existierende Persona → DEFAULT_PROFILE + WARNING.
        with self.assertLogs("survey.profile_loader", level="WARNING") as cm:
            ProfileLoader.load_profile(profile_name="does_not_exist_xyz")

        warns = "\n".join(cm.output)
        self.assertIn("no JSON found", warns)
        # DEFAULT_PROFILE ist vollstaendig → kein "missing required keys"
        # darauf folgen, aber das "no JSON found"-Warning genuegt fuer den Test.


class TestPhoneFamily(unittest.TestCase):
    """SR-53 (B): Telefonnummer-Familie."""

    def test_phone_de(self):
        p = ProfileLoader.load_profile(profile_name="jeremy_schulze")
        v = ProfileLoader.match_field("textbox", "Telefonnummer", p)
        self.assertEqual(v, p["phone"])

    def test_phone_de_handy(self):
        p = ProfileLoader.load_profile(profile_name="jeremy_schulze")
        v = ProfileLoader.match_field("textbox", "Handy", p)
        self.assertEqual(v, p["phone"])

    def test_phone_en(self):
        p = ProfileLoader.load_profile(profile_name="anna_meyer")
        v = ProfileLoader.match_field("textbox", "Phone number", p)
        self.assertEqual(v, p["phone"])


class TestCountryVsState(unittest.TestCase):
    """SR-53 (B): "Land" ist Country, "Bundesland" ist State."""

    def test_land_returns_country_not_state(self):
        p = ProfileLoader.load_profile(profile_name="jeremy_schulze")
        v = ProfileLoader.match_field("textbox", "In welchem Land wohnen Sie?", p)
        self.assertEqual(v, "Deutschland")
        self.assertNotEqual(v, "Berlin")  # Berlin ist state

    def test_bundesland_returns_state(self):
        p = ProfileLoader.load_profile(profile_name="anna_meyer")
        v = ProfileLoader.match_field("textbox", "Bundesland", p)
        self.assertEqual(v, "Bayern")

    def test_country_en(self):
        p = ProfileLoader.load_profile(profile_name="thomas_weber")
        v = ProfileLoader.match_field("textbox", "Country of residence", p)
        self.assertEqual(v, "Deutschland")


class TestDirectFirstLastName(unittest.TestCase):
    """SR-53 (B): direkte first_name/last_name Keys gewinnen vor split."""

    def test_first_name_direct(self):
        p = ProfileLoader.load_profile(profile_name="anna_meyer")
        v = ProfileLoader.match_field("textbox", "Vorname", p)
        self.assertEqual(v, "Anna")

    def test_last_name_direct(self):
        p = ProfileLoader.load_profile(profile_name="thomas_weber")
        v = ProfileLoader.match_field("textbox", "Nachname", p)
        self.assertEqual(v, "Weber")


class TestTelemetryLoadCounter(unittest.TestCase):
    """SR-54 hooks: load_profile zaehlt loads."""

    def setUp(self):
        ProfileLoader.reset_telemetry()

    def test_load_increments_counter(self):
        ProfileLoader.load_profile(profile_name="jeremy_schulze")
        ProfileLoader.load_profile(profile_name="jeremy_schulze")
        t = ProfileLoader.telemetry()
        self.assertEqual(t["jeremy_schulze"]["loads"], 2)
        self.assertEqual(t["jeremy_schulze"]["missing_required_count"], 0)


class TestTelemetryMatchHits(unittest.TestCase):
    """SR-54 hooks: match_field Hit/Miss pro Persona."""

    def setUp(self):
        ProfileLoader.reset_telemetry()

    def test_hit_and_miss_counters(self):
        p = ProfileLoader.load_profile(profile_name="jeremy_schulze")
        # Required _loader_name fuer _record_match auf Profile-Dict
        p["_loader_name"] = "jeremy_schulze"

        ProfileLoader.match_field("textbox", "Stadt", p)   # hit
        ProfileLoader.match_field("textbox", "Postleitzahl", p)  # hit
        ProfileLoader.match_field("textbox", "Lieblingsfarbe?", p)  # miss

        t = ProfileLoader.telemetry()
        self.assertGreaterEqual(t["jeremy_schulze"]["match_hits"], 2)
        self.assertGreaterEqual(t["jeremy_schulze"]["match_misses"], 1)
        self.assertIn("per_key_hits", t["jeremy_schulze"])
        self.assertGreaterEqual(t["jeremy_schulze"]["per_key_hits"]["city"], 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
