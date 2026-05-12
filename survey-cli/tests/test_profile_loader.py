"""Tests for ProfileLoader — persona loading with dynamic age calculation.

WARUM: Jede Code-Datei braucht Tests. ProfileLoader ist NEU.
"""

import unittest
import json
import tempfile
import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from survey.profile_loader import ProfileLoader


class TestProfileLoader(unittest.TestCase):
    """Test ProfileLoader.load_profile() with file and fallback scenarios."""

    def test_default_profile_has_age(self):
        profile = ProfileLoader.load_profile()
        self.assertIn("age", profile)
        self.assertIsInstance(profile["age"], int)
        # Age for 1993-11-13 should be around 32-33 depending on current date
        self.assertGreaterEqual(profile["age"], 30)
        self.assertLessEqual(profile["age"], 35)

    def test_default_profile_structure(self):
        profile = ProfileLoader.load_profile()
        self.assertEqual(profile["name"], "Jeremy Schulze")
        self.assertEqual(profile["city"], "Berlin")
        self.assertEqual(profile["gender"], "male")
        self.assertEqual(profile["language"], "Deutsch")

    def test_loads_from_json_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            profile_path = os.path.join(tmp, "profiles", "jeremy_schulze.json")
            os.makedirs(os.path.dirname(profile_path), exist_ok=True)
            custom = {
                "name": "Test User",
                "date_of_birth": "2000-01-01",
                "gender": "female",
            }
            with open(profile_path, "w") as f:
                json.dump(custom, f)

            profile = ProfileLoader.load_profile(tmp)
            self.assertEqual(profile["name"], "Test User")
            self.assertEqual(profile["gender"], "female")
            # Age should be calculated
            expected_age = date.today().year - 2000
            if (date.today().month, date.today().day) < (1, 1):
                expected_age -= 1
            self.assertEqual(profile["age"], expected_age)

    def test_calculates_age_correctly(self):
        profile = ProfileLoader.load_profile()
        dob = date.fromisoformat(profile["date_of_birth"])
        today = date.today()
        expected = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
        self.assertEqual(profile["age"], expected)

    def test_invalid_dob_falls_back_to_32(self):
        with tempfile.TemporaryDirectory() as tmp:
            profile_path = os.path.join(tmp, "profiles", "jeremy_schulze.json")
            os.makedirs(os.path.dirname(profile_path), exist_ok=True)
            with open(profile_path, "w") as f:
                json.dump({"date_of_birth": "invalid-date"}, f)

            profile = ProfileLoader.load_profile(tmp)
            self.assertEqual(profile["age"], 32)

    def test_preserves_explicit_age(self):
        with tempfile.TemporaryDirectory() as tmp:
            profile_path = os.path.join(tmp, "profiles", "jeremy_schulze.json")
            os.makedirs(os.path.dirname(profile_path), exist_ok=True)
            with open(profile_path, "w") as f:
                json.dump({"date_of_birth": "1993-11-13", "age": 99}, f)

            profile = ProfileLoader.load_profile(tmp)
            self.assertEqual(profile["age"], 99)


if __name__ == "__main__":
    unittest.main()
