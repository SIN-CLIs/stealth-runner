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
import logging
import os
import re
from datetime import date, datetime, timezone
import hashlib
from typing import Dict, Any, Optional, Tuple, List, Set


_LOG = logging.getLogger("survey.profile_loader")


class ProfileLoader:
    """Load persona profile from JSON files + map form fields to profile values.

    Class-level constants:
      DEFAULT_PROFILE: Embedded fallback persona, used when no JSON found.
      FIELD_PATTERNS:  Ordered list of (profile_key, regex) tuples — earlier
                       entries win. Substring-match on lowercased label.
      REQUIRED_KEYS:   Set of profile keys that MUST be present in every
                       persona JSON. Missing keys cause a WARNING during
                       load_profile() and reduce match_field coverage.
      OPTIONAL_KEYS:   Set of keys that are nice-to-have. Missing optional
                       keys are silent.
    """

    DEFAULT_PROFILE = {
        "name": "Jeremy Schulze",
        "first_name": "Jeremy",
        "last_name": "Schulze",
        "date_of_birth": "1993-11-13",
        "gender": "male",
        "gender_label": "Männlich",
        "email": "jeremy.schulze.test@example.com",
        "phone": "+49 30 1234567",
        "city": "Berlin",
        "state": "Berlin",
        "country": "Deutschland",
        "zip": "10785",
        "street": "Kurfürstenstraße 124",
        "household_size": 3,
        "marital_status": "married",
        "education": "abitur",
        "employment": "employed_fulltime",
        "employment_label": "Angestellte",
        "job_title": "Meister",
        "industry": "Handwerk",
        "household_income": "3000-4000",
        "personal_income": "1000-2000",
        "nationality": "Deutsch",
        "language": "Deutsch",
    }

    # ── REQUIRED_KEYS ────────────────────────────────────────────────────────
    # Pflichtfelder fuer alle Personas. Wenn eines fehlt, springt der
    # LLM-Fallback in decide_node Heuristik 2b oft — was teure Tokens und
    # latente Risiken (halluzinierte Werte) bedeutet.
    #
    # Erweiterung: nur Felder eintragen, die einer FIELD_PATTERNS-Familie
    # entsprechen UND fuer den Online-Markt-Forschung Standard sind
    # (Demografie, Adresse, Kontakt, Haushalt).
    REQUIRED_KEYS: Set[str] = {
        "name",
        "first_name",
        "last_name",
        "date_of_birth",
        "gender",
        "email",
        "city",
        "country",
        "zip",
        "street",
        "household_size",
        "personal_income",
        "household_income",
        "nationality",
        "language",
    }

    OPTIONAL_KEYS: Set[str] = {
        "gender_label",
        "state",
        "marital_status",
        "education",
        "employment",
        "employment_label",
        "job_title",
        "industry",
        "phone",
        "age",
        "interests",
        "insurance_products",
        "contracts",
        "vehicles",
        "pets",
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

        # Phone — vor city/street, damit "Telefon-Nummer in Berlin" nicht
        # in city laufen kann.
        ("phone", re.compile(
            r"(telefon|tel\.?\s*(nr|nummer)?|handy|mobil(?:nummer)?|"
            r"phone(?:\s*number)?|mobile|cell)",
            re.I,
        )),

        # Birth year — vor age.
        # ``year ... born`` deckt Phrasen wie "What year were you born?",
        # "In welchem Jahr wurden Sie geboren?". Wir matchen "year"/"jahr"
        # + bis zu 40 Zeichen + "born"/"geboren"/"geburt". Lazy (.{0,40}?)
        # damit es nicht ueber mehrere Klauseln greift.
        ("birth_year", re.compile(
            r"(geburtsjahr|jahrgang|year\s*of\s*birth|birth\s*year|"
            r"\byear\b.{0,40}?\bborn\b|"
            r"\bjahr\b.{0,40}?\b(geboren|geburt)\b)",
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

        # Country — vor state_region, sonst frisst "\bland\b" das "Deutschland".
        # Spezifisch: "land" alleine wuerde sowohl "Bundesland" als auch
        # "Land/Country" matchen — deshalb MUSS country zuerst geprueft werden,
        # state_region matcht "\bland\b" nur als state.
        ("country", re.compile(
            r"(\bland\b|country|nation\s*of\s*residence|wohnsitzland|herkunftsland|"
            r"in\s*welchem\s*land)",
            re.I,
        )),

        # State / region.  ``\bland\b`` bewusst NICHT mehr — siehe country oben.
        ("state_region", re.compile(
            r"(bundesland|\bregion\b|\bstate\b|province)", re.I,
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
    # ── _CANDIDATE_HINTS (SR-59 #58) ─────────────────────────────────────────
    # Mapping logical_key → user-facing keyword fragments (substrings). Used
    # ONLY by ``_guess_candidate_keys()`` to populate the ``candidate_keys``
    # field of a miss_label record — never for match decisions (those go via
    # FIELD_PATTERNS). Why a separate list? FIELD_PATTERNS regex sources
    # contain regex metacharacters (``\\b``, ``(?:...)``) which would be a
    # mess to strip; this list is the curated, parseable form.
    _CANDIDATE_HINTS: List[Tuple[str, Tuple[str, ...]]] = [
        ("email", ("email", "e-mail", "mail", "mailadresse")),
        ("phone", ("telefon", "telephone", "phone", "handy", "mobil",
                   "cell", "mobile")),
        ("birth_year", ("geburtsjahr", "jahrgang", "birthyear", "birth year",
                        "born", "geboren")),
        ("age", ("alter", "age", "wie alt")),
        ("postal_code", ("plz", "postleitzahl", "zip", "postal", "postcode")),
        ("hh_income", ("haushaltseinkommen", "familieneinkommen",
                       "household income")),
        ("income", ("einkommen", "gehalt", "salary", "income", "netto")),
        ("first_name", ("vorname", "first name", "given name", "forename")),
        ("last_name", ("nachname", "last name", "surname", "family name",
                       "familyname")),
        ("street", ("strasse", "straße", "street", "adresse", "address")),
        ("city", ("stadt", "wohnort", "ort", "city", "town")),
        ("country", ("land", "country", "nation", "wohnsitzland",
                     "herkunftsland")),
        ("state_region", ("bundesland", "region", "state", "province")),
        ("household_size", ("haushalt", "household size",
                            "personen im haushalt")),
        ("job_title", ("beruf", "job title", "occupation", "taetigkeit",
                       "tätigkeit")),
        ("industry", ("branche", "industry", "sector")),
        ("gender", ("geschlecht", "gender", "sex")),
        ("nationality", ("nationalitaet", "nationalität", "nationality",
                         "staatsangehoerigkeit", "staatsangehörigkeit")),
        ("language", ("sprache", "language")),
    ]

    _NUMERIC_KEYS = {"age", "household_size", "birth_year", "postal_code",
                     "income", "hh_income"}

    # ────────────────────────────────────────────────────────────────────────
    # Loader
    # ────────────────────────────────────────────────────────────────────────

    # Telemetrie (SR-54): pro Persona aggregiert.
    # In-Process-Counter; cli "survey profile dump" zeigt sie an.
    _telemetry: Dict[str, Dict[str, int]] = {}

    @classmethod
    def load_profile(
        cls,
        module_dir: str = "",
        profile_name: str = "jeremy_schulze",
    ) -> Dict[str, Any]:
        """Load profile from JSON or return default with calculated age.

        Args:
            module_dir: Directory to search for profiles/ subdirectory
            profile_name: Basename ohne ``.json`` — z.B. ``"jeremy_schulze"``,
                          ``"anna_meyer"``, ``"thomas_weber"``.

        Returns:
            Profile dict with guaranteed "age" key.

        WARNINGS:
            Wenn ein REQUIRED_KEYS-Feld fehlt, wird via
            ``logging.WARNING`` geloggt. Dadurch sieht der Operator sofort,
            dass die Persona unvollstaendig ist und die Heuristik 2b
            entsprechend oft LLM-Fallback triggern wird.
        """
        filename = f"{profile_name}.json"
        paths = [
            os.path.join(module_dir, "profiles", filename),
            os.path.join(os.path.dirname(module_dir), "config", "profiles",
                         filename),
            # Standard-Location relativ zur survey/-Quelle.
            os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "profiles", filename),
        ]

        profile = None
        loaded_from = ""
        for path in paths:
            if os.path.exists(path):
                try:
                    with open(path) as f:
                        profile = json.load(f)
                    loaded_from = path
                    break
                except Exception as exc:
                    _LOG.warning("profile_loader: bad json at %s (%s)",
                                 path, exc)

        if not profile:
            profile = dict(cls.DEFAULT_PROFILE)
            _LOG.warning(
                "profile_loader: no JSON found for %r, using DEFAULT_PROFILE",
                profile_name,
            )

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

        # Pflichtfeld-Pruefung
        missing = cls._missing_required(profile)
        if missing:
            _LOG.warning(
                "profile_loader: persona %r missing required keys: %s "
                "(loaded from %s) — Heuristik 2b wird haeufiger LLM-Fallback "
                "triggern. Fix: profiles/%s.json um diese Keys ergaenzen.",
                profile_name, sorted(missing), loaded_from or "<default>",
                profile_name,
            )

        # Telemetrie initialisieren
        cls._telemetry.setdefault(profile_name, {
            "loads": 0,
            "match_hits": 0,
            "match_misses": 0,
            "missing_required_count": len(missing),
        })
        cls._telemetry[profile_name]["loads"] += 1
        cls._telemetry[profile_name]["missing_required_count"] = len(missing)
        cls._telemetry[profile_name]["loaded_from"] = loaded_from or "<default>"

        return profile

    # ────────────────────────────────────────────────────────────────────────
    # Pflichtfeld-Pruefung + Telemetrie-Inspect (SR-53 + SR-54)
    # ────────────────────────────────────────────────────────────────────────

    @classmethod
    def _missing_required(cls, profile: Dict[str, Any]) -> Set[str]:
        """Set der REQUIRED_KEYS, die im profile fehlen ODER leer sind."""
        missing: Set[str] = set()
        for key in cls.REQUIRED_KEYS:
            v = profile.get(key)
            if v is None or v == "" or v == []:
                missing.add(key)
        return missing

    @classmethod
    def telemetry(cls) -> Dict[str, Dict[str, Any]]:
        """In-Memory Telemetry-Dump fuer CLI 'survey profile dump' (SR-54)."""
        return {k: dict(v) for k, v in cls._telemetry.items()}

    @classmethod
    def reset_telemetry(cls) -> None:
        """Nur fuer Tests — Counter zuruecksetzen."""
        cls._telemetry.clear()

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
            cls._record_match(profile, hit=True, logical_key=logical_key,
                              role=role, label=label)
            return str(value)

        cls._record_match(profile, hit=False, logical_key=None,
                          role=role, label=label)
        return None

    @classmethod
    def _guess_candidate_keys(cls, text: str, max_k: int = 3) -> List[str]:
        """SR-59 #58: cheap heuristic returning up to ``max_k`` plausible
        ``logical_key`` candidates for an unmatched label.

        Why a heuristic and not the real FIELD_PATTERNS regex set?
          - We are in the MISS path: FIELD_PATTERNS already said "no". This
            field surfaces *near-misses* (e.g. "Mobilnummer" loosely overlapping
            with the phone family) so a human reviewing
            ``logs/matcher-telemetry-*.jsonl`` can spot a missing pattern
            quickly.
          - Substring overlap on ``_CANDIDATE_HINTS`` is O(n) and deterministic;
            tokenising-Jaccard would surface noise on short German labels.

        Returns:
            Ordered, deduplicated list of logical_keys; empty list if no hint
            matches. NEVER raises — telemetry must never break a survey run.
        """
        if not text:
            return []
        low = text.lower()
        out: List[str] = []
        seen: Set[str] = set()
        for logical_key, keywords in cls._CANDIDATE_HINTS:
            for kw in keywords:
                if kw in low:
                    if logical_key not in seen:
                        seen.add(logical_key)
                        out.append(logical_key)
                    break
            if len(out) >= max_k:
                break
        return out

    @classmethod
    def _record_match(
        cls,
        profile: Dict[str, Any],
        hit: bool,
        logical_key: Optional[str],
        role: str = "",
        label: str = "",
    ) -> None:
        """Telemetrie-Hook fuer SR-54 + SR-55.

        Bei Hits zaehlen wir den logical_key-Treffer. Bei Misses speichern
        wir das **konkrete Label** in ``miss_labels`` — das ist die
        Eingabequelle der Lernschleife (survey/learn/aggregator.py).
        Wir cappen die Liste bei 500 Eintraegen pro Persona, damit
        Long-Running-Runs den Speicher nicht sprengen.
        """
        ident = profile.get("_loader_name") or profile.get("name") or "anonymous"
        bucket = cls._telemetry.setdefault(ident, {
            "loads": 0, "match_hits": 0, "match_misses": 0,
            "missing_required_count": 0,
        })
        if hit:
            bucket["match_hits"] = bucket.get("match_hits", 0) + 1
            if logical_key:
                per_key = bucket.setdefault("per_key_hits", {})
                per_key[logical_key] = per_key.get(logical_key, 0) + 1
        else:
            bucket["match_misses"] = bucket.get("match_misses", 0) + 1
            if label:
                miss_labels: List[Dict[str, Any]] = bucket.setdefault(
                    "miss_labels", []
                )
                if len(miss_labels) < 500:
                    # SR-59 #58: rich, semantically-tagged miss record.
                    # PRIVACY INVARIANT: ``user_value_provided`` is a boolean
                    # ONLY — never the actual user value. The aggregator
                    # (survey/learn/aggregator.py) clusters via token-Jaccard
                    # over ``question_text``; ``snapshot_hash`` lets us
                    # deduplicate identical labels across reruns.
                    label_trunc = label[:200]
                    page_url = profile.get("_page_url")
                    miss_labels.append({
                        # Backward-compat fields (consumed by aggregator <#58):
                        "role": role,
                        "label": label_trunc,
                        # SR-59 #58 enrichment:
                        "ts": datetime.now(timezone.utc).isoformat(
                            timespec="seconds"),
                        "question_text": label_trunc,
                        "page_url": page_url if isinstance(page_url, str)
                                    else None,
                        "snapshot_hash": hashlib.sha1(
                            label_trunc.encode("utf-8"),
                            usedforsecurity=False,
                        ).hexdigest()[:12],
                        "candidate_keys": cls._guess_candidate_keys(
                            label_trunc),
                        "user_value_provided": False,
                    })

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
            # Direkter Key gewinnt vor split-aus-name.
            direct = profile.get("first_name")
            if direct:
                return direct
            full = profile.get("name", "")
            return full.split()[0] if full and " " in full else (full or None)

        if logical_key == "last_name":
            direct = profile.get("last_name")
            if direct:
                return direct
            full = profile.get("name", "")
            parts = full.split() if full else []
            return parts[-1] if len(parts) >= 2 else None

        if logical_key == "full_name":
            return profile.get("name") or (
                f"{profile.get('first_name','')} {profile.get('last_name','')}".strip()
                or None
            )

        if logical_key == "phone":
            return profile.get("phone") or profile.get("phone_number")

        if logical_key == "country":
            return profile.get("country") or profile.get("nationality")

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
