"""Tests fuer ProfileLoader.match_field() — Form-Field → Profil-Wert Mapping.

WARUM: Heuristik 2b in decide_node hat frueher BLIND ``profile["city"]``
in jedes leere Textfeld geschrieben. Das hat "Berlin" in E-Mail- und
PLZ-Felder gepflanzt → sofortiger Screen-Out. Diese Tests sichern die
Keyword-Familien-Erkennung gegen Regression ab.

ARCHITEKTUR:
  Pro Keyword-Familie mindestens 1 DE-Test, 1 EN-Test, sowie Reihenfolge-
  und Role-Negativ-Tests. Profile-Dict wird inline gebaut um isoliert vom
  echten jeremy_schulze.json zu testen.

KEYWORD-FAMILIEN (siehe profile_loader.py FIELD_PATTERNS):
  email, birth_year, age, postal_code, city, state_region, street,
  first_name, last_name, full_name, household_size, income, hh_income,
  job_title, industry, nationality, language, gender.

PFLICHT-KONTEXT VOR ERWEITERUNG:
  Wer eine neue Keyword-Familie hinzufuegt MUSS:
   1. FIELD_PATTERNS in profile_loader.py ergaenzen (an der richtigen Stelle
      — spezifischer-zuerst).
   2. _resolve_value() um den logical_key erweitern, falls nicht 1:1.
   3. Hier einen Test pro Sprache hinzufuegen.
   4. AGENTS.md → "PROFIL-MAPPING ERWEITERUNG (2026-05-11)" Tabelle aktualisieren.

BANNED:
  ❌ Hartkodierte Fallbacks ("Berlin", "32", "test@test.de") in match_field
  ❌ Pattern ohne re.I (Surveys mixen Klein-/Grossschreibung beliebig)
  ❌ Tests, die ECHTES Profil-File lesen — alle Profile inline halten.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from survey.profile_loader import ProfileLoader


# Reichhaltiges Test-Profile, deckt alle logical_keys ab.
PROFILE = {
    "name": "Jeremy Schulze",
    "date_of_birth": "1993-11-13",
    "age": 32,
    "gender": "male",
    "gender_label": "Männlich",
    "city": "Berlin",
    "state": "Berlin",
    "zip": "10785",
    "street": "Kurfürstenstraße 124",
    "email": "jeremy@example.com",
    "household_size": 3,
    "household_income": "3000-4000",
    "personal_income": "1000-2000",
    "job_title": "Meister",
    "industry": "Handwerk",
    "nationality": "Deutsch",
    "language": "Deutsch",
}


# =============================================================================
# Per-Familie Tests — DE + EN
# =============================================================================


class TestEmailMatch(unittest.TestCase):
    def test_de_label_emailadresse(self):
        self.assertEqual(
            ProfileLoader.match_field("textbox", "E-Mail-Adresse", PROFILE),
            "jeremy@example.com",
        )

    def test_en_label_email_address(self):
        self.assertEqual(
            ProfileLoader.match_field("textbox", "Email Address", PROFILE),
            "jeremy@example.com",
        )

    def test_placeholder_mailadresse(self):
        self.assertEqual(
            ProfileLoader.match_field("textbox", "", PROFILE, placeholder="mailadresse@..."),
            "jeremy@example.com",
        )


class TestBirthYearMatch(unittest.TestCase):
    def test_de_geburtsjahr(self):
        self.assertEqual(
            ProfileLoader.match_field("textbox", "Geburtsjahr", PROFILE),
            "1993",
        )

    def test_en_year_of_birth(self):
        self.assertEqual(
            ProfileLoader.match_field("spinbutton", "Year of birth", PROFILE),
            "1993",
        )

    def test_jahrgang(self):
        self.assertEqual(
            ProfileLoader.match_field("textbox", "Jahrgang", PROFILE),
            "1993",
        )

    def test_fallback_from_age_when_no_dob(self):
        prof = {"age": 30}  # kein date_of_birth
        # Year sollte aus age berechnet werden (heute.year - age).
        from datetime import date as _date

        expected = str(_date.today().year - 30)
        self.assertEqual(
            ProfileLoader.match_field("textbox", "Geburtsjahr", prof),
            expected,
        )


class TestPostalCodeMatch(unittest.TestCase):
    def test_de_plz(self):
        self.assertEqual(
            ProfileLoader.match_field("textbox", "PLZ", PROFILE),
            "10785",
        )

    def test_de_postleitzahl(self):
        self.assertEqual(
            ProfileLoader.match_field("textbox", "Postleitzahl", PROFILE),
            "10785",
        )

    def test_en_zip_code(self):
        self.assertEqual(
            ProfileLoader.match_field("textbox", "ZIP code", PROFILE),
            "10785",
        )

    def test_en_postal_code(self):
        self.assertEqual(
            ProfileLoader.match_field("spinbutton", "Postal Code", PROFILE),
            "10785",
        )

    def test_postal_code_wins_over_city(self):
        """Label 'PLZ und Stadt' MUSS PLZ ergeben (postal_code vor city)."""
        self.assertEqual(
            ProfileLoader.match_field("textbox", "PLZ und Stadt", PROFILE),
            "10785",
        )


class TestCityMatch(unittest.TestCase):
    def test_de_stadt(self):
        self.assertEqual(
            ProfileLoader.match_field("textbox", "Stadt", PROFILE),
            "Berlin",
        )

    def test_de_wohnort(self):
        self.assertEqual(
            ProfileLoader.match_field("textbox", "Wohnort", PROFILE),
            "Berlin",
        )

    def test_en_city(self):
        self.assertEqual(
            ProfileLoader.match_field("textbox", "City", PROFILE),
            "Berlin",
        )


class TestStreetMatch(unittest.TestCase):
    def test_de_strasse(self):
        self.assertEqual(
            ProfileLoader.match_field("textbox", "Straße", PROFILE),
            "Kurfürstenstraße 124",
        )

    def test_en_address(self):
        self.assertEqual(
            ProfileLoader.match_field("textbox", "Address line 1", PROFILE),
            "Kurfürstenstraße 124",
        )


class TestFirstLastNameMatch(unittest.TestCase):
    def test_de_vorname(self):
        self.assertEqual(
            ProfileLoader.match_field("textbox", "Vorname", PROFILE),
            "Jeremy",
        )

    def test_en_first_name(self):
        self.assertEqual(
            ProfileLoader.match_field("textbox", "First Name", PROFILE),
            "Jeremy",
        )

    def test_de_nachname(self):
        self.assertEqual(
            ProfileLoader.match_field("textbox", "Nachname", PROFILE),
            "Schulze",
        )

    def test_en_surname(self):
        self.assertEqual(
            ProfileLoader.match_field("textbox", "Surname", PROFILE),
            "Schulze",
        )

    def test_full_name_after_specific(self):
        # generisches "Name" → full_name
        self.assertEqual(
            ProfileLoader.match_field("textbox", "Name", PROFILE),
            "Jeremy Schulze",
        )

    def test_first_name_beats_full_name(self):
        # "Vorname" muss BEFORE "Name" matchen
        self.assertEqual(
            ProfileLoader.match_field("textbox", "Vorname / First Name", PROFILE),
            "Jeremy",
        )


class TestAgeMatch(unittest.TestCase):
    def test_de_alter(self):
        self.assertEqual(
            ProfileLoader.match_field("spinbutton", "Ihr Alter", PROFILE),
            "32",
        )

    def test_en_age(self):
        self.assertEqual(
            ProfileLoader.match_field("spinbutton", "Your age", PROFILE),
            "32",
        )

    def test_age_not_matched_by_birth_year_label(self):
        # "Geburtsjahr" muss birth_year liefern, NICHT age
        self.assertEqual(
            ProfileLoader.match_field("textbox", "Geburtsjahr", PROFILE),
            "1993",
        )


class TestHouseholdSizeMatch(unittest.TestCase):
    def test_de_personen_im_haushalt(self):
        self.assertEqual(
            ProfileLoader.match_field("spinbutton", "Personen im Haushalt", PROFILE),
            "3",
        )

    def test_en_household_size(self):
        self.assertEqual(
            ProfileLoader.match_field("spinbutton", "Household size", PROFILE),
            "3",
        )


class TestIncomeMatch(unittest.TestCase):
    def test_de_einkommen(self):
        self.assertEqual(
            ProfileLoader.match_field("textbox", "Einkommen", PROFILE),
            "1000-2000",
        )

    def test_en_salary(self):
        self.assertEqual(
            ProfileLoader.match_field("textbox", "Salary", PROFILE),
            "1000-2000",
        )

    def test_household_income_wins_over_income(self):
        self.assertEqual(
            ProfileLoader.match_field("textbox", "Haushaltseinkommen", PROFILE),
            "3000-4000",
        )

    def test_en_household_income_wins(self):
        self.assertEqual(
            ProfileLoader.match_field("textbox", "Household income", PROFILE),
            "3000-4000",
        )


class TestJobIndustryMatch(unittest.TestCase):
    def test_de_beruf(self):
        self.assertEqual(
            ProfileLoader.match_field("textbox", "Beruf", PROFILE),
            "Meister",
        )

    def test_en_occupation(self):
        self.assertEqual(
            ProfileLoader.match_field("textbox", "Occupation", PROFILE),
            "Meister",
        )

    def test_de_branche(self):
        self.assertEqual(
            ProfileLoader.match_field("textbox", "Branche", PROFILE),
            "Handwerk",
        )

    def test_en_industry(self):
        self.assertEqual(
            ProfileLoader.match_field("textbox", "Industry", PROFILE),
            "Handwerk",
        )


class TestNationalityLanguageMatch(unittest.TestCase):
    def test_de_nationalitaet(self):
        self.assertEqual(
            ProfileLoader.match_field("textbox", "Nationalität", PROFILE),
            "Deutsch",
        )

    def test_en_nationality(self):
        self.assertEqual(
            ProfileLoader.match_field("textbox", "Nationality", PROFILE),
            "Deutsch",
        )

    def test_de_sprache(self):
        self.assertEqual(
            ProfileLoader.match_field("textbox", "Muttersprache", PROFILE),
            "Deutsch",
        )

    def test_en_language(self):
        self.assertEqual(
            ProfileLoader.match_field("textbox", "Language", PROFILE),
            "Deutsch",
        )


class TestStateRegionMatch(unittest.TestCase):
    def test_de_bundesland(self):
        self.assertEqual(
            ProfileLoader.match_field("textbox", "Bundesland", PROFILE),
            "Berlin",
        )

    def test_en_state(self):
        self.assertEqual(
            ProfileLoader.match_field("textbox", "State", PROFILE),
            "Berlin",
        )


# =============================================================================
# Negativ-Tests
# =============================================================================


class TestUnknownLabelReturnsNone(unittest.TestCase):
    def test_random_question_returns_none(self):
        self.assertIsNone(
            ProfileLoader.match_field("textbox", "Welches ist Ihre Lieblings-Pizza?", PROFILE)
        )

    def test_lottery_number_returns_none(self):
        self.assertIsNone(ProfileLoader.match_field("textbox", "Lottozahl", PROFILE))


class TestNonInputRoleReturnsNone(unittest.TestCase):
    def test_button_returns_none(self):
        self.assertIsNone(ProfileLoader.match_field("button", "Stadt", PROFILE))

    def test_radio_returns_none(self):
        self.assertIsNone(ProfileLoader.match_field("radio", "Wohnort", PROFILE))

    def test_link_returns_none(self):
        self.assertIsNone(ProfileLoader.match_field("link", "PLZ", PROFILE))


class TestSpinbuttonRejectsTextFields(unittest.TestCase):
    """spinbutton soll text-Felder (city, street, email) NICHT befuellen."""

    def test_spinbutton_with_city_label_returns_none(self):
        self.assertIsNone(ProfileLoader.match_field("spinbutton", "Stadt", PROFILE))

    def test_spinbutton_with_email_label_returns_none(self):
        self.assertIsNone(ProfileLoader.match_field("spinbutton", "E-Mail-Adresse", PROFILE))

    def test_spinbutton_with_numeric_keyword_works(self):
        self.assertEqual(
            ProfileLoader.match_field("spinbutton", "Alter", PROFILE),
            "32",
        )


class TestEmptyLabelReturnsNone(unittest.TestCase):
    def test_empty_name_no_placeholder(self):
        self.assertIsNone(ProfileLoader.match_field("textbox", "", PROFILE, placeholder=""))

    def test_none_name_no_placeholder(self):
        self.assertIsNone(ProfileLoader.match_field("textbox", None, PROFILE))


class TestProfileMissingFields(unittest.TestCase):
    """Wenn das Profil das gesuchte Feld nicht hat → None (kein Default!)."""

    def test_missing_email_returns_none(self):
        prof = {"city": "Berlin"}  # kein email
        self.assertIsNone(ProfileLoader.match_field("textbox", "E-Mail", prof))

    def test_missing_zip_returns_none(self):
        prof = {"city": "Berlin"}  # kein zip
        self.assertIsNone(ProfileLoader.match_field("textbox", "PLZ", prof))

    def test_empty_profile_returns_none(self):
        self.assertIsNone(ProfileLoader.match_field("textbox", "Stadt", {}))


class TestNameSplittingEdgeCases(unittest.TestCase):
    def test_single_word_name_first_name_returns_word(self):
        prof = {"name": "Madonna"}
        self.assertEqual(
            ProfileLoader.match_field("textbox", "Vorname", prof),
            "Madonna",
        )

    def test_single_word_name_last_name_returns_none(self):
        prof = {"name": "Madonna"}
        self.assertIsNone(ProfileLoader.match_field("textbox", "Nachname", prof))

    def test_three_part_name_last_name_returns_last(self):
        prof = {"name": "Maria Anna Schulze"}
        self.assertEqual(
            ProfileLoader.match_field("textbox", "Nachname", prof),
            "Schulze",
        )


class TestGenderFallback(unittest.TestCase):
    def test_uses_gender_label_when_present(self):
        prof = {"gender": "male", "gender_label": "Männlich"}
        self.assertEqual(
            ProfileLoader.match_field("textbox", "Geschlecht", prof),
            "Männlich",
        )

    def test_falls_back_to_gender_when_no_label(self):
        prof = {"gender": "male"}
        self.assertEqual(
            ProfileLoader.match_field("textbox", "Geschlecht", prof),
            "male",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
