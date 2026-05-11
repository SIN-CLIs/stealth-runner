"""Heuristic family suggester — Token-Set Vergleich mit bekannten Families.

WARUM keine LLM:
- Lernschleife muss offline + deterministisch laufen (CI-tauglich).
- LLMs halluzinieren Familien (z.B. "stadt" → "address" weil naeher an
  englischen Trainingsdaten als "city"). Token-Overlap ist robust.
- Phase 2 darf LLM einbinden, sobald Eval-Harness steht.

WIE:
- Pro Familie pflegen wir ein ``FAMILY_TOKENS`` Set mit ALLEN Tokens, die
  bisher in den FIELD_PATTERNS dieser Familie auftauchen (DE+EN).
- Fuer ein gemissen Label tokenisieren wir es und berechnen Jaccard-
  Aehnlichkeit gegen jede Familie. Hoechste Aehnlichkeit ueber Schwelle =
  Vorschlag.

LIMITATIONEN:
- "Lieblingsfarbe" hat keinen Token-Overlap mit irgendeiner Familie → wir
  geben ``SuggestedFamily(None, 0.0, ...)`` zurueck. Das ist OK: das
  Label braucht eine *neue* Familie, KEIN Pattern-Erweiterung.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, FrozenSet, List, Optional


# WARUM hardcoded und nicht aus FIELD_PATTERNS abgeleitet:
# FIELD_PATTERNS sind Regexes mit Sonderzeichen ("\bplz\b", "stra(?:ss|ß)e").
# Token-Extraktion aus Regex ist fehleranfaellig. Wartung minimal: wenn eine
# Familie ein neues Sprach-Synonym bekommt, auch hier eintragen.
FAMILY_TOKENS: Dict[str, FrozenSet[str]] = {
    "email": frozenset({"email", "mail", "e", "mailadresse", "address"}),
    "phone": frozenset({
        "phone", "telefon", "tel", "handy", "mobil", "mobile",
        "mobilnummer", "cell", "nummer", "number",
    }),
    "birth_year": frozenset({
        "birth", "year", "born", "geburtsjahr", "jahrgang", "jahr",
        "geboren", "geburt", "of",
    }),
    "postal_code": frozenset({
        "plz", "postleitzahl", "zip", "code", "postal", "postcode",
    }),
    "hh_income": frozenset({
        "haushaltseinkommen", "household", "income", "familieneinkommen",
        "haushalt", "einkommen",
    }),
    "income": frozenset({
        "einkommen", "gehalt", "salary", "personal", "netto",
        "income", "nettoeinkommen",
    }),
    "first_name": frozenset({
        "vorname", "first", "name", "given", "forename",
    }),
    "last_name": frozenset({
        "nachname", "last", "name", "surname", "family", "familyname",
    }),
    "street": frozenset({
        "strasse", "straße", "street", "adresse", "address", "line",
        "anschrift",
    }),
    "city": frozenset({"stadt", "wohnort", "ort", "city", "town"}),
    "country": frozenset({
        "land", "country", "nation", "residence", "wohnsitzland",
        "herkunftsland",
    }),
    "state_region": frozenset({
        "bundesland", "region", "state", "province", "kanton",
    }),
    "household_size": frozenset({
        "haushaltsgroesse", "haushaltsgröße", "personen", "haushalt",
        "household", "size", "people", "wie", "viele",
    }),
    "age": frozenset({"alter", "age", "wie", "alt", "ihr", "your"}),
    "job_title": frozenset({
        "beruf", "job", "title", "taetigkeit", "tätigkeit", "occupation",
        "profession", "position",
    }),
    "industry": frozenset({
        "branche", "industry", "sector", "wirtschaftszweig",
    }),
    "nationality": frozenset({
        "nationalitaet", "nationalität", "nationality",
        "staatsangehoerigkeit", "staatsangehörigkeit",
    }),
    "language": frozenset({"muttersprache", "sprache", "language"}),
    "gender": frozenset({"geschlecht", "gender", "sex"}),
    "full_name": frozenset({"name", "full", "vollstaendiger", "vollständiger"}),
}


_TOKEN_RE = re.compile(r"[a-zäöüß]+", re.I)


@dataclass(frozen=True)
class SuggestedFamily:
    """Result of suggest_family — None family + 0.0 confidence = "new family"."""

    family: Optional[str]
    confidence: float
    matched_tokens: List[str]
    label_tokens: List[str]


def _tokenize(label: str) -> List[str]:
    """Lowercase + nur a-z+ Umlaute. Strippt Pflicht-Marker (*), Klammern, etc."""
    label = label.replace("ß", "ss")
    return [t.lower() for t in _TOKEN_RE.findall(label)]


def suggest_family(label: str, min_confidence: float = 0.20) -> SuggestedFamily:
    """Suggest a FIELD_PATTERNS family for an unmatched label.

    Args:
        label: Das Label, fuer das ProfileLoader keinen Match hatte.
        min_confidence: Schwelle [0..1]. Darunter geben wir family=None
                        zurueck → Vorschlag: neue Familie noetig.

    Returns:
        SuggestedFamily mit besten Match. ``family=None`` wenn keine
        bestehende Familie ueber der Schwelle liegt.

    Beispiele:
        >>> r = suggest_family("Mobilfunknummer")
        >>> r.family
        'phone'

        >>> r = suggest_family("Lieblingsfarbe")
        >>> r.family is None
        True
    """
    tokens = _tokenize(label)
    if not tokens:
        return SuggestedFamily(None, 0.0, [], [])
    token_set = set(tokens)

    best_family: Optional[str] = None
    best_score = 0.0
    best_matched: List[str] = []

    for family, fam_tokens in FAMILY_TOKENS.items():
        overlap = token_set & fam_tokens
        # Substring-Match: Deutsche Komposita ("Mobilfunknummer", "Faxnummer",
        # "Telefon-Nr") landen als EIN Token im Set, sind also nicht
        # exakt-equal zu Familie-Tokens. Wir matchen daher zusaetzlich, ob
        # ein Familie-Token (>=4 chars) als Substring im Label-Token steckt
        # ("nummer" in "faxnummer"). Schwelle 4 verhindert false-positives
        # durch sehr kurze Tokens wie "of"/"an".
        substring_hits: List[str] = []
        for tok in tokens:
            for fam_tok in fam_tokens:
                if len(fam_tok) >= 4 and fam_tok in tok and tok not in overlap:
                    substring_hits.append(fam_tok)
                    break
        # GEWICHTUNG: Exact-Token-Match (overlap) zaehlt 1.0 pro Treffer,
        # Substring-Match (Kompositum) nur 0.7 — sonst wuerde "Hausnummer"
        # in einer Strasse-Frage faelschlich zu phone-Familie tendieren.
        # Substring ist zwar wertvoll fuer DE-Komposita, ist aber unscharfer.
        weighted = len(overlap) * 1.0 + len(substring_hits) * 0.7
        if weighted == 0:
            continue
        score = weighted / max(len(tokens), 1)
        if score > best_score:
            best_score = score
            best_family = family
            best_matched = sorted(overlap | set(substring_hits))

    if best_score < min_confidence:
        return SuggestedFamily(None, best_score, [], tokens)
    return SuggestedFamily(best_family, best_score, best_matched, tokens)
