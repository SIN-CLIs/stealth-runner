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

import json
import re
from dataclasses import dataclass
from typing import Dict, FrozenSet, List, Optional


# WARUM hardcoded und nicht aus FIELD_PATTERNS abgeleitet:
# FIELD_PATTERNS sind Regexes mit Sonderzeichen ("\bplz\b", "stra(?:ss|ß)e").
# Token-Extraktion aus Regex ist fehleranfaellig. Wartung minimal: wenn eine
# Familie ein neues Sprach-Synonym bekommt, auch hier eintragen.
FAMILY_TOKENS: Dict[str, FrozenSet[str]] = {
    "email": frozenset({"email", "mail", "e", "mailadresse", "address"}),
    "phone": frozenset(
        {
            "phone",
            "telefon",
            "tel",
            "handy",
            "mobil",
            "mobile",
            "mobilnummer",
            "cell",
            "nummer",
            "number",
        }
    ),
    "birth_year": frozenset(
        {
            "birth",
            "year",
            "born",
            "geburtsjahr",
            "jahrgang",
            "jahr",
            "geboren",
            "geburt",
            "of",
        }
    ),
    "postal_code": frozenset(
        {
            "plz",
            "postleitzahl",
            "zip",
            "code",
            "postal",
            "postcode",
        }
    ),
    "hh_income": frozenset(
        {
            "haushaltseinkommen",
            "household",
            "income",
            "familieneinkommen",
            "haushalt",
            "einkommen",
        }
    ),
    "income": frozenset(
        {
            "einkommen",
            "gehalt",
            "salary",
            "personal",
            "netto",
            "income",
            "nettoeinkommen",
        }
    ),
    "first_name": frozenset(
        {
            "vorname",
            "first",
            "name",
            "given",
            "forename",
        }
    ),
    "last_name": frozenset(
        {
            "nachname",
            "last",
            "name",
            "surname",
            "family",
            "familyname",
        }
    ),
    "street": frozenset(
        {
            "strasse",
            "straße",
            "street",
            "adresse",
            "address",
            "line",
            "anschrift",
        }
    ),
    "city": frozenset({"stadt", "wohnort", "ort", "city", "town"}),
    "country": frozenset(
        {
            "land",
            "country",
            "nation",
            "residence",
            "wohnsitzland",
            "herkunftsland",
        }
    ),
    "state_region": frozenset(
        {
            "bundesland",
            "region",
            "state",
            "province",
            "kanton",
        }
    ),
    "household_size": frozenset(
        {
            "haushaltsgroesse",
            "haushaltsgröße",
            "personen",
            "haushalt",
            "household",
            "size",
            "people",
            "wie",
            "viele",
        }
    ),
    "age": frozenset({"alter", "age", "wie", "alt", "ihr", "your"}),
    "job_title": frozenset(
        {
            "beruf",
            "job",
            "title",
            "taetigkeit",
            "tätigkeit",
            "occupation",
            "profession",
            "position",
        }
    ),
    "industry": frozenset(
        {
            "branche",
            "industry",
            "sector",
            "wirtschaftszweig",
        }
    ),
    "nationality": frozenset(
        {
            "nationalitaet",
            "nationalität",
            "nationality",
            "staatsangehoerigkeit",
            "staatsangehörigkeit",
        }
    ),
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


# ────────────────────────────────────────────────────────────────────────────
# SR-57 #56: FCTC-ES Phase 2 — LLM-Suggester for misses heuristic can't handle.
# ────────────────────────────────────────────────────────────────────────────
#
# Trigger contract (enforced in aggregator, NOT here):
#   - Phase 1 ``suggest_family`` returned ``family=None`` OR
#     ``confidence < 0.20``.
#   - ``use_llm=True`` flag is set on the aggregator call (default False).
#   - ``AI_GATEWAY_API_KEY`` is present in env.
#
# Threshold contract (enforced in apply.py):
#   - LLM suggestions are written to JSONL with ``source: "llm"`` regardless
#     of confidence. The downstream ``apply --approve-all`` rejects anything
#     with ``confidence < 0.85`` for ``source == "llm"`` (vs 0.7 for
#     substring). We let LOW-confidence LLM suggestions land in the inbox so
#     the reviewer can see what the LLM thought — but they CANNOT auto-apply.
#
# Privacy:
#   - We send the normalized label text only — NEVER the user value
#     (already enforced by aggregator schema: ``miss_labels`` contain
#     ``label`` + ``role``, never user-provided answers).

from typing import Sequence  # noqa: E402

from .llm_client import LLMResponse, call_llm  # noqa: E402


@dataclass(frozen=True)
class LLMSuggestion:
    """LLM-Vorschlag fuer eine Family-Klassifikation.

    Fields:
        family:       Vorgeschlagene Family ODER None ("none of these").
        confidence:   [0..1], wie sicher das Modell sich war.
        reason:       Kurze Begruendung (max ~140 Zeichen) — Audit.
        model:        Tatsaechliches Modell (z.B. "openai/gpt-5-mini").
        prompt_hash:  sha256-prefix des Prompts — forensische Lookup.
        error:        Falls Call fehlschlug; ``family`` ist dann None.
    """

    family: Optional[str]
    confidence: float
    reason: str
    model: str
    prompt_hash: str
    error: Optional[str] = None


def _build_llm_prompt(label: str, families: Sequence[str]) -> str:
    """Erstellt den User-Prompt fuer die LLM-Klassifikation.

    Stabil + deterministisch (sorted families) → stabiler prompt_hash, der
    sich nur aendert, wenn die Familien-Menge waechst (= bewusst).
    """
    fam_lines = "\n".join(f"  - {f}" for f in sorted(families))
    return (
        f"Classify the German/English survey question label below into "
        f"EXACTLY ONE of the listed profile families. If NONE fits, return "
        f"family=null.\n"
        f"\n"
        f"Label: {label!r}\n"
        f"\n"
        f"Families:\n"
        f"{fam_lines}\n"
        f"\n"
        f"Respond with this JSON schema ONLY (no markdown, no prose):\n"
        f'{{"family": "<one_of_above_or_null>", '
        f'"confidence": <float 0..1>, '
        f'"reason": "<<=140 chars why this family>"}}'
    )


def _parse_llm_response(
    raw: str,
    allowed_families: Sequence[str],
) -> tuple[Optional[str], float, str, Optional[str]]:
    """Parse ``raw`` JSON content → ``(family, confidence, reason, error)``.

    Defensive: strippt optional markdown code-fences (manche Modelle bauen
    die trotz response_format=json_object ein), validiert ``family in
    allowed_families`` ODER ``family is None``, klemmt confidence auf [0,1],
    cut reason auf 140 chars.
    """
    if not raw:
        return None, 0.0, "", "empty response"
    txt = raw.strip()
    if txt.startswith("```"):
        # ```json\n{...}\n```  →  {...}
        lines = txt.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        txt = "\n".join(lines).strip()
    try:
        obj = json.loads(txt)
    except json.JSONDecodeError as e:
        return None, 0.0, "", f"non-json response: {e}"
    if not isinstance(obj, dict):
        return None, 0.0, "", "json was not an object"
    fam = obj.get("family")
    if isinstance(fam, str):
        fam = fam.strip().lower()
        if fam in {"null", "none", ""}:
            fam = None
        elif fam not in allowed_families:
            return None, 0.0, "", (f"family {fam!r} not in allowed set (hallucination)")
    elif fam is not None:
        return None, 0.0, "", f"family is not str|null: {type(fam).__name__}"
    try:
        conf = float(obj.get("confidence", 0.0))
    except (TypeError, ValueError):
        conf = 0.0
    conf = max(0.0, min(1.0, conf))
    reason = str(obj.get("reason", ""))[:140]
    return fam, conf, reason, None


def suggest_via_llm(
    label: str,
    allowed_families: Sequence[str],
    *,
    model: Optional[str] = None,
    timeout: float = 20.0,
) -> LLMSuggestion:
    """Phase-2 LLM classification — fail-soft, never raises.

    Args:
        label:            Normalized label (already lowercase, trimmed).
        allowed_families: List of valid family names — LLM cannot return
                          anything outside this set (post-validation).
        model:            Override default model (openai/gpt-5-mini).
        timeout:          Per-call timeout in seconds.

    Returns:
        LLMSuggestion. ``family is None`` either means "LLM said no match",
        "LLM unavailable", or "LLM hallucinated invalid family" — caller
        should check ``error`` to distinguish.

    Examples:
        >>> r = suggest_via_llm(                  # doctest: +SKIP
        ...     "wie viele personen leben in ihrem haushalt",
        ...     allowed_families=list(FAMILY_TOKENS.keys()),
        ... )
        >>> r.family                              # doctest: +SKIP
        'household_size'
    """
    if not label.strip():
        return LLMSuggestion(
            family=None,
            confidence=0.0,
            reason="",
            model=model or "",
            prompt_hash="",
            error="empty label",
        )
    if not allowed_families:
        return LLMSuggestion(
            family=None,
            confidence=0.0,
            reason="",
            model=model or "",
            prompt_hash="",
            error="no allowed_families given",
        )

    prompt = _build_llm_prompt(label, allowed_families)
    resp: LLMResponse = call_llm(prompt, model=model, timeout=timeout)
    if resp.content is None:
        return LLMSuggestion(
            family=None,
            confidence=0.0,
            reason="",
            model=resp.model,
            prompt_hash=resp.prompt_hash,
            error=resp.error,
        )

    allowed_lower = [f.lower() for f in allowed_families]
    fam, conf, reason, parse_err = _parse_llm_response(resp.content, allowed_lower)
    return LLMSuggestion(
        family=fam,
        confidence=conf,
        reason=reason,
        model=resp.model,
        prompt_hash=resp.prompt_hash,
        error=parse_err,
    )
