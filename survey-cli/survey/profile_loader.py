"""ProfileLoader — load persona profile + map form fields to profile values.

WARUM: runner.py hatte ~40 Zeilen Profil-Laden mit Fallback-Daten.
ProfileLoader isoliert ALLES was mit "Wer ist der Survey-Teilnehmer?" zu tun
hat — Laden, Alter-Berechnung UND das Zuordnen von Formular-Feldern (z.B.
"PLZ"-Textbox → profile["zip"]) zur Reduktion von LLM-Fallbacks im
``decide_node`` Heuristik-Pfad 2b.

================================================================================
KONTRAKT MIT ``decide_node`` (survey-cli/survey/graph/nodes.py, Heuristik 2b)
================================================================================

Frueher (vor 2026-05-11 +Mapping-Extension):

    val = str(profile.get("city", "Berlin"))   # immer city, egal welches Feld

Jetzt:

    val = ProfileLoader.match_field(role=e["role"],
                                    name=e.get("name"),
                                    placeholder=e.get("attrs", {}).get("placeholder"),
                                    profile=profile)
    if val is None:
        # KEIN passendes Feld → LLM-Fallback uebernimmt im naechsten Tick.
        continue

→ Damit kann die Heuristik echte Survey-Formulare korrekt befuellen
  (PLZ, E-Mail, Geburtsjahr, Adresse, …) ohne den teuren LLM-Aufruf,
  und der LLM-Fallback laeuft nur noch wenn KEIN Keyword matcht
  (z.B. "Wie gross ist Ihr Auto?" — sowas muss der LLM machen).

================================================================================
KEYWORD-FAMILIEN (DE + EN, lowercase, substring-match auf name+placeholder)
================================================================================

  +------------------+--------------------------------------------------+--------------------------+
  | Profil-Feld      | Keywords (Beispiele)                             | Quelle im Profile-Dict   |
  +------------------+--------------------------------------------------+--------------------------+
  | birth_year       | geburtsjahr, jahrgang, year of birth, birth year | date_of_birth[:4]        |
  | age              | alter, age, wie alt                              | age                      |
  | email            | e-mail, email, mail, e mail                      | email                    |
  | postal_code      | plz, postleitzahl, zip, postal code, postcode    | zip                      |
  | city             | stadt, ort, wohnort, city, town                  | city                     |
  | state_region     | bundesland, region, state, province              | state                    |
  | street           | strasse, straße, street, adresse, address        | street                   |
  | first_name       | vorname, first name, given name                  | name.split()[0]          |
  | last_name        | nachname, last name, surname, familyname         | name.split()[-1]         |
  | full_name        | name, full name, vollstaendiger name             | name                     |
  | household_size   | haushalt, personen im haushalt, household size   | household_size           |
  | income           | einkommen, income, gehalt, salary                | personal_income          |
  | hh_income        | haushaltseinkommen, household income             | household_income         |
  | job_title        | beruf, job title, taetigkeit, occupation         | job_title                |
  | industry         | branche, industry, sector                        | industry                 |
  | nationality      | nationalitaet, nationality, staatsangehoerigkeit | nationality              |
  | language         | sprache, language                                | language                 |
  | gender           | geschlecht, gender, sex                          | gender_label             |
  +------------------+--------------------------------------------------+--------------------------+

Reihenfolge ist WICHTIG: spezifischere Patterns ZUERST. Beispiel:
  "Wie ist Ihre Postleitzahl in Berlin?" — wuerde sowohl "Postleitzahl"
  (postal_code) als auch "Berlin" (city, wenn es im Label stehen wuerde)
  matchen. ``match_field`` returned beim ersten Treffer.

ROLE-FILTER:
  - ``role="spinbutton"`` → bevorzugt numerische Felder (age, household_size,
    income, birth_year, postal_code). Wenn Keyword nicht eindeutig: skip.
  - ``role="textbox"`` / ``role="searchbox"`` / ``role="combobox"``
    → akzeptiert alle Familien.
  - andere Rollen → returns None (Heuristik 2b skippt das Element).

UNKNOWN-RETURN:
  Wenn KEIN Keyword matcht und role ist textbox: returns None.
  ``decide_node`` macht dann **kein** Heuristik-Fill und ueberlaesst dem
  LLM-Tick die Entscheidung. So vermeiden wir, sinnlos "Berlin" in ein
  E-Mail-Feld zu schreiben.

================================================================================
TEST-ABDECKUNG
================================================================================

Siehe survey-cli/tests/test_profile_match_field.py — pro Keyword-Familie
mindestens ein DE und ein EN Test, plus Negativ-Tests (Unknown-Feld,
falsche Role, leeres Profile).

================================================================================
BANNED METHODS — NIEMALS VERWENDEN
================================================================================
  ❌ playstealth launch
  ❌ webauto-nodriver — ABSOLUT BANNED
  ❌ Hardcoded Fallback "Berlin" als universeller default (alte 2b-Heuristik)
"""

from __future__ import annotations

import json
import os
import re
from datetime import date
from typing import Dict, Any, Optional, Tuple, List


class ProfileLoader:
    """Load persona profile from JSON files + map form fields to values.

    Class-level constants:
      DEFAULT_PROFILE: Embedded fallback persona, used when no JSON found.
      FIELD_PATTERNS:  Ordered list of (profile_key, regex) tuples — earlier
                       entries win. Substring-match on lowercased label.
    """

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

    # ── FIELD_PATTERNS ────────────────────────────────────────────────────────
    # Pflicht-Eigenschaft: spezifischer-zuerst.
    # Format: (logical_key, compiled_regex)
    # ``logical_key`` ist ein interner Schluessel, der dann via
    # ``_resolve_value(logical_key, profile)`` in den konkreten Profile-Wert
    # uebersetzt wird. So koennen wir z.B. "birth_year" liefern obwohl der
    # Profile-Dict nur "date_of_birth" hat.
    #
    # Reihenfolge-Begruendung:
    #   1. "haushaltseinkommen" muss VOR "einkommen" geprueft werden, sonst
    #      matcht "einkommen" zuerst → falscher Wert.
    #   2. "postleitzahl"/"plz" vor "stadt", denn "PLZ und Stadt" wuerde sonst
    #      vom city-Pattern gefressen.
    #   3. "vorname" + "nachname" vor "name", sonst frisst "name" alles.
    #   4. "geburtsjahr" vor "age" generisch.

    FIELD_PATTERNS: List[Tuple[str, "re.Pattern[str]"]] = [
        # Email — sehr spezifisches Pattern, ganz nach oben.
        ("email", re.compile(r"(e[\s\-]?mail|mailadresse|email\s*address)", re.I)),

        # Birth year — vor age.
        ("birth_year", re.compile(
            r"(geburtsjahr|jahrgang|year\s*of\s*birth|birth\s*year|year\s*you\s*were\s*born)",
            re.I,
        )),

        # Postal code — vor city.
        ("postal_code", re.compile(
            r"(\bplz\b|postleitzahl|\bzip(?:\s*code)?\b|postal\s*code|postcode)",
            re.I,
        )),

        # Household income — vor income.
        ("hh_income", re.compile(
            r"(haushaltseinkommen|household\s*income|familieneinkommen)",
            re.I,
        )),

        # Personal income.
        ("income", re.compile(
            r"(einkommen|gehalt|salary|personal\s*income|netto(?:einkommen)?)",
            re.I,
        )),

        # First/last name — vor full_name "name".
        ("first_name", re.compile(
            r"(vorname|first\s*name|given\s*name|forename)", re.I,
        )),
        ("last_name", re.compile(
            r"(nachname|last\s*name|surname|family\s*name|familyname)", re.I,
        )),

        # Street/address.
        ("street", re.compile(
            r"(stra(?:ss|ß)e|street|adresse|address(?:\s*line)?)", re.I,
        )),

        # City — auch "Wohnort" / "Ort".
        ("city", re.compile(r"(stadt|wohnort|\bort\b|\bcity\b|\btown\b)", re.I)),

        # State / region.
        ("state_region", re.compile(
            r"(bundesland|\bregion\b|\bstate\b|province|\bland\b)", re.I,
        )),

        # Household size.
        ("household_size", re.compile(
            r"(haushaltsgr(?:ö|oe)sse|haushaltsgröße|personen\s*im\s*haushalt|"
            r"household\s*size|people\s*in\s*household|wie\s*viele\s*personen)",
            re.I,
        )),

        # Age — nach birth_year.
        ("age", re.compile(
            r"(\balter\b|\bage\b|wie\s*alt|your\s*age|ihr\s*alter)", re.I,
        )),

        # Job / profession.
        ("job_title", re.compile(
            r"(\bberuf\b|job\s*title|t(?:ä|ae)tigkeit|occupation|profession|position)",
            re.I,
        )),

        # Industry / branche.
        ("industry", re.compile(
            r"(\bbranche\b|industry|sector|wirtschaftszweig)", re.I,
        )),

        # Nationality.
        ("nationality", re.compile(
            r"(nationalit(?:ä|ae)t|nationality|staatsangeh(?:ö|oe)rigkeit)",
            re.I,
        )),

        # Language.
        ("language", re.compile(r"(muttersprache|sprache|language)", re.I)),

        # Gender — Texteingaben sind selten, aber falls doch.
        ("gender", re.compile(r"(geschlecht|\bgender\b|\bsex\b)", re.I)),

        # Full name — nach first_name/last_name.
        ("full_name", re.compile(
            r"(\bname\b|full\s*name|vollst(?:ä|ae)ndiger\s*name)", re.I,
        )),
    ]

    # Welche logischen Schluessel sind sinnvolle Treffer fuer ``role=spinbutton``?
    # Alles andere ist verdaechtig (kein numerisches Feld) und wird verworfen.
    _NUMERIC_KEYS = {"age", "household_size", "birth_year", "postal_code",
                     "income", "hh_income"}

    # ────────────────────────────────────────────────────────────────────────
    # Loader
    # ────────────────────────────────────────────────────────────────────────

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

    # ────────────────────────────────────────────────────────────────────────
    # Field matching — used by decide_node Heuristik 2b
    # ────────────────────────────────────────────────────────────────────────

    @classmethod
    def match_field(
        cls,
        role: str,
        name: Optional[str],
        profile: Dict[str, Any],
        placeholder: Optional[str] = None,
    ) -> Optional[str]:
        """Return best-fit profile value for the given form field, or ``None``.

        Strategie:
          1. Baue Label = name + " " + placeholder (lowercased).
          2. Iteriere FIELD_PATTERNS in deklarierter Reihenfolge.
          3. Erster Regex-Treffer mit vorhandenem Profil-Wert gewinnt.
          4. ``role=spinbutton`` filtert auf ``_NUMERIC_KEYS``. Wenn das
             Pattern nicht numerisch ist, wird der Treffer ignoriert und
             es geht weiter (kein Default!).
          5. ``role`` muss in {textbox, searchbox, spinbutton, combobox} sein,
             sonst sofort None.
          6. KEIN globaler Default. Wenn kein Pattern matcht: None.

        Args:
            role: Element-Rolle aus cdp_universal.scan() (z.B. "textbox").
            name: Accessible Name des Elements (Label / aria-label).
            profile: Profile-Dict von ``load_profile()``.
            placeholder: Optional placeholder-Attribut, wird mitgemacht.

        Returns:
            String-Wert zum Eintippen, oder None wenn nichts passt.

        Examples:
            >>> p = {"city": "Berlin", "zip": "10785", "date_of_birth": "1993-11-13"}
            >>> ProfileLoader.match_field("textbox", "Postleitzahl", p)
            '10785'
            >>> ProfileLoader.match_field("textbox", "Geburtsjahr", p)
            '1993'
            >>> ProfileLoader.match_field("textbox", "Lieblings-Pizza?", p) is None
            True
            >>> ProfileLoader.match_field("button", "Weiter", p) is None
            True
        """
        if role not in ("textbox", "searchbox", "spinbutton", "combobox"):
            return None

        label_parts: List[str] = []
        if name:
            label_parts.append(str(name))
        if placeholder:
            label_parts.append(str(placeholder))
        label = " ".join(label_parts).strip()
        if not label:
            return None

        is_numeric_role = role == "spinbutton"

        for logical_key, pattern in cls.FIELD_PATTERNS:
            if not pattern.search(label):
                continue
            if is_numeric_role and logical_key not in cls._NUMERIC_KEYS:
                # spinbutton aber Pattern liefert Text (z.B. city) → skip
                continue
            value = cls._resolve_value(logical_key, profile)
            if value is None or value == "":
                # Match, aber Profile hat den Wert nicht → naechstes Pattern
                continue
            return str(value)

        return None

    # ────────────────────────────────────────────────────────────────────────
    # Resolver — mappt logical_key → konkreter Profil-Wert
    # ────────────────────────────────────────────────────────────────────────

    @classmethod
    def _resolve_value(cls, logical_key: str, profile: Dict[str, Any]) -> Optional[Any]:
        """Map a logical pattern key to the actual value in ``profile``.

        Nicht-1:1-Mappings:
          - ``birth_year`` → ``date_of_birth[:4]`` (string "1993")
          - ``postal_code`` → ``zip``
          - ``hh_income``   → ``household_income``
          - ``state_region``→ ``state``
          - ``first_name``  → ``name.split()[0]``
          - ``last_name``   → ``name.split()[-1]``
          - ``full_name``   → ``name``
          - ``gender``      → ``gender_label`` falls vorhanden, sonst ``gender``

        Returns None wenn das benoetigte Feld im Profile fehlt.
        """
        if logical_key == "birth_year":
            dob = profile.get("date_of_birth", "")
            if isinstance(dob, str) and len(dob) >= 4 and dob[:4].isdigit():
                return dob[:4]
            # Fallback: aus age + heute rechnen
            age = profile.get("age")
            if isinstance(age, int) and age > 0:
                return str(date.today().year - age)
            return None

        if logical_key == "postal_code":
            return profile.get("zip") or profile.get("postal_code")

        if logical_key == "hh_income":
            return profile.get("household_income")

        if logical_key == "income":
            return profile.get("personal_income") or profile.get("income")

        if logical_key == "state_region":
            return profile.get("state") or profile.get("region")

        if logical_key == "first_name":
            full = profile.get("name", "")
            return full.split()[0] if full and " " in full else (full or None)

        if logical_key == "last_name":
            full = profile.get("name", "")
            parts = full.split() if full else []
            return parts[-1] if len(parts) >= 2 else None

        if logical_key == "full_name":
            return profile.get("name")

        if logical_key == "gender":
            return profile.get("gender_label") or profile.get("gender")

        if logical_key == "household_size":
            v = profile.get("household_size")
            return str(v) if v is not None else None

        if logical_key == "age":
            v = profile.get("age")
            return str(v) if v is not None else None

        # Direct 1:1 keys: city, street, email, job_title, industry,
        # nationality, language
        v = profile.get(logical_key)
        if v is None:
            return None
        return v
