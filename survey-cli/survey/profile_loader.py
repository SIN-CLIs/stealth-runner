"""ProfileLoader — load persona profile with dynamic age calculation.

WARUM: runner.py hatte ~40 Zeilen Profil-Laden mit Fallback-Daten.
ProfileLoader isoliert ALLES was mit "Wer ist der Survey-Teilnehmer?" zu tun hat.

BANNED METHODS — NIEMALS VERWENDEN:
  ❌ playstealth launch
  ❌ webauto-nodriver — ABSOLUT BANNED
"""

import json
import os
from datetime import date
from typing import Dict, Any


class ProfileLoader:
    """Load persona profile from JSON files with dynamic age calculation."""

    DEFAULT_PROFILE = {
        "name": "Jeremy Schulze",
        "date_of_birth": "1993-11-13",
        "gender": "male",
        "gender_label": "Männlich",
        "city": "Berlin",
        "state": "Berlin",
        "zip": "10785",
        "household_size": 3,
        "marital_status": "married",
        "education": "abitur",
        "employment": "employed_fulltime",
        "employment_label": "Angestellte",
        "household_income": "3000-4000",
        "personal_income": "1000-2000",
        "nationality": "Deutsch",
        "language": "Deutsch",
    }

    @classmethod
    def load_profile(cls, module_dir: str = "") -> Dict[str, Any]:
        """Load profile from JSON or return default with calculated age.

        Args:
            module_dir: Directory to search for profiles/ subdirectory

        Returns:
            Profile dict with guaranteed "age" key.
        """
        paths = [
            os.path.join(module_dir, "profiles", "jeremy_schulze.json"),
            os.path.join(os.path.dirname(module_dir), "config", "profiles", "jeremy_schulze.json"),
        ]

        profile = None
        for path in paths:
            if os.path.exists(path):
                try:
                    with open(path) as f:
                        profile = json.load(f)
                    break
                except Exception:
                    pass

        if not profile:
            profile = dict(cls.DEFAULT_PROFILE)

        # Dynamically calculate age from date_of_birth
        if "date_of_birth" in profile and "age" not in profile:
            try:
                dob = profile["date_of_birth"]
                born = date.fromisoformat(dob)
                today = date.today()
                profile["age"] = today.year - born.year - (
                    (today.month, today.day) < (born.month, born.day)
                )
            except (ValueError, TypeError):
                profile["age"] = 32

        return profile
