"""Aggregate matcher-telemetry-*.jsonl Misses into pattern suggestions.

Pipeline:
  1. Read all matcher-telemetry-*.jsonl from logs/ dir.
  2. Extract miss_labels per persona, normalize (whitespace, *, parens).
  3. Group by (role, normalized_label) and count.
  4. For each group above min_count, call suggester.suggest_family().
  5. Write JSONL with {normalized_label, role, count, suggested_family,
                       confidence, matched_tokens, sample_labels}.
"""

from __future__ import annotations

import datetime
import json
import os
import re
from collections import Counter, defaultdict
from typing import Dict, Iterable, List, Optional

from .suggester import (
    FAMILY_TOKENS,
    LLMSuggestion,
    SuggestedFamily,
    suggest_family,
    suggest_via_llm,
)
from .llm_client import is_available as _llm_is_available, warn_if_unavailable as _llm_warn


# Normalisierung: trim, lowercase, "*", "(Pflicht)" entfernen, multi-space
_PFLICHT_RE = re.compile(
    r"\s*\*\s*$|\s*\(\s*(?:pflicht|required|optional)\s*\)\s*$",
    re.I,
)
_MULTI_WS = re.compile(r"\s+")


def normalize_label(label: str) -> str:
    """Whitespace + Pflicht-Marker entfernen, lowercase fuer Gruppierung.

    Beispiel:
        normalize_label("  Postleitzahl *  ") == "postleitzahl"
        normalize_label("PLZ (Pflicht)")     == "plz"
    """
    s = label.strip()
    s = _PFLICHT_RE.sub("", s)
    s = _MULTI_WS.sub(" ", s).strip()
    return s.lower()


def _iter_telemetry_files(log_dir: str) -> Iterable[str]:
    """Yield matcher-telemetry-*.jsonl files in log_dir (sorted, newest first)."""
    if not os.path.isdir(log_dir):
        return
    names = [n for n in os.listdir(log_dir)
             if n.startswith("matcher-telemetry-") and n.endswith(".jsonl")]
    names.sort(reverse=True)
    for n in names:
        yield os.path.join(log_dir, n)


def aggregate_misses(
    log_dir: str,
    min_count: int = 1,
    persona: Optional[str] = None,
    use_llm: bool = False,
    llm_model: Optional[str] = None,
    llm_min_confidence: float = 0.0,
) -> List[Dict[str, object]]:
    """Aggregate miss_labels across matcher-telemetry JSONLs.

    Args:
        log_dir: Pfad zum Verzeichnis mit matcher-telemetry-*.jsonl.
        min_count: Vorschlaege nur ab dieser Frequenz (Schutz vor Einmal-Misses).
        persona: Optional Persona-Filter (default: alle).
        use_llm: SR-57 #56 — wenn True UND Heuristik leer/<0.20, ruft LLM-
                 Suggester (Phase 2) auf. Default False fuer rueckwaerts-
                 Kompatibilitaet. Wirft nicht, wenn AI_GATEWAY_API_KEY fehlt
                 — schreibt nur eine stderr-Warnung.
        llm_model: Override fuer default-Model. None → openai/gpt-5-mini.
        llm_min_confidence: Mindest-Confidence fuer LLM-Vorschlaege im
                 OUTPUT. Default 0.0 = alle LLM-Antworten landen in der
                 Inbox (auch low-conf), damit der Reviewer sie sieht.
                 Der downstream apply-Pfad (SR-58 #57) hat einen eigenen
                 strengeren Gate (0.85 fuer source=llm).

    Returns:
        Liste von Suggestion-Dicts, sortiert absteigend nach count. Jedes
        Dict hat zusaetzlich ``source`` field (``"substring"`` oder ``"llm"``)
        und bei ``source=="llm"`` auch ``model`` + ``prompt_hash`` + ``reason``.
    """
    counters: "Counter[tuple[str, str]]" = Counter()
    samples: Dict[tuple, List[str]] = defaultdict(list)

    for path in _iter_telemetry_files(log_dir):
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if persona and rec.get("persona") != persona:
                    continue
                for ml in rec.get("miss_labels", []):
                    role = (ml.get("role") or "").lower()
                    raw_label = ml.get("label") or ""
                    norm = normalize_label(raw_label)
                    if not norm:
                        continue
                    key = (role, norm)
                    counters[key] += 1
                    if len(samples[key]) < 5 and raw_label not in samples[key]:
                        samples[key].append(raw_label)

    # SR-57 #56: optional Phase-2-Fallback. Warne EINMAL, falls user --llm
    # gesetzt hat aber AI_GATEWAY_API_KEY fehlt.
    if use_llm and not _llm_is_available():
        _llm_warn()  # one-shot stderr msg; use_llm bleibt True (caller
                     # entscheidet, ob das ein Hard-Fail ist).

    allowed_families = list(FAMILY_TOKENS.keys())

    suggestions: List[Dict[str, object]] = []
    for (role, norm), count in counters.most_common():
        if count < min_count:
            continue
        # Phase 1: heuristic.
        sug: SuggestedFamily = suggest_family(norm)
        record: Dict[str, object] = {
            "role": role,
            "normalized_label": norm,
            "count": count,
            "sample_labels": samples[(role, norm)],
            "suggested_family": sug.family,
            "confidence": round(sug.confidence, 3),
            "matched_tokens": sug.matched_tokens,
            "label_tokens": sug.label_tokens,
            # SR-57 #56: explicit source tag (default heuristic). apply.py
            # gates differently per source ("substring" 0.7, "llm" 0.85).
            "source": "substring",
            # WICHTIG fuer review-CLI: explicit status.
            "status": "open",
        }

        # Phase 2: LLM-fallback when heuristic is empty OR weakly-confident.
        # ``< 0.20`` matches the suggest_family() default min_confidence
        # threshold — sub-threshold heuristic already returns family=None,
        # but we add the explicit guard so future threshold-bumps stay safe.
        if use_llm and _llm_is_available() and (
            sug.family is None or sug.confidence < 0.20
        ):
            llm: LLMSuggestion = suggest_via_llm(
                norm, allowed_families, model=llm_model,
            )
            # Only OVERRIDE the heuristic record if the LLM actually returned
            # a family — otherwise we keep the heuristic's None (which is
            # itself a useful signal: "new family needed").
            if llm.family is not None and \
                    llm.confidence >= llm_min_confidence:
                record["suggested_family"] = llm.family
                record["confidence"] = round(llm.confidence, 3)
                record["source"] = "llm"
                record["model"] = llm.model
                record["prompt_hash"] = llm.prompt_hash
                record["reason"] = llm.reason
                # Heuristic-only fields lose meaning in LLM mode — keep
                # them for the reviewer but namespace them.
                record["heuristic_family"] = sug.family
                record["heuristic_confidence"] = round(sug.confidence, 3)
            elif llm.error:
                # No override, but record the attempt for forensics.
                record["llm_error"] = llm.error
                record["model"] = llm.model
                record["prompt_hash"] = llm.prompt_hash

        suggestions.append(record)
    return suggestions


def write_suggestions(
    out_path: str,
    suggestions: List[Dict[str, object]],
) -> None:
    """Schreibt JSONL — eine Zeile pro Vorschlag.

    Existiert die Datei schon, wird sie ueberschrieben — Reviewer-CLI fuehrt
    den Status in einer separaten ``-accepted.jsonl`` / ``-rejected.jsonl``.
    """
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w") as f:
        for s in suggestions:
            f.write(json.dumps(s, ensure_ascii=False) + "\n")


def default_suggestions_path(log_dir: str) -> str:
    """logs/pattern-suggestions-YYYY-MM-DD.jsonl"""
    today = datetime.date.today().isoformat()
    return os.path.join(log_dir, f"pattern-suggestions-{today}.jsonl")

# ────────────────────────────────────────────────────────────────────────────
# SR-59 #58: Token-Jaccard clustering of miss_labels
# ────────────────────────────────────────────────────────────────────────────
#
# Why an extra path next to aggregate_misses()? aggregate_misses() groups by
# (role, normalized_label) — exact match on the trimmed label. That gives a
# tight cluster ("postleitzahl" = 3, "PLZ" = 1) but cannot bridge
# semantically-similar misses ("Wie viele Personen leben im Haushalt?" vs
# "Personen im Haushalt").
#
# cluster_miss_labels() complements aggregate_misses() with a fuzzy view:
# token-Jaccard ≥ threshold (default 0.6) bridges paraphrases. Output is a
# dict ``cluster_key → [miss_label, …]`` where cluster_key is a stable
# canonical token-set string usable as a filename / log key.
#
# Privacy: this function consumes structured miss_labels (no user values).
# ``user_value_provided`` is forwarded verbatim — it remains boolean.

_TOKEN_RE = re.compile(r"[A-Za-zÄÖÜäöüß0-9]+")
_STOP_TOKENS = frozenset({
    "der", "die", "das", "des", "dem", "den",
    "ein", "eine", "einen", "einem", "einer",
    "und", "oder", "in", "im", "an", "auf", "fuer", "für", "von", "mit",
    "is", "are", "the", "a", "an", "of", "to", "for", "in", "on", "or", "and",
    "you", "your", "is",
})


def _tokenize(text: str) -> "frozenset[str]":
    """Lowercase tokens, drop short stop-words. Used for Jaccard only."""
    toks = _TOKEN_RE.findall((text or "").lower())
    return frozenset(t for t in toks if len(t) >= 3 and t not in _STOP_TOKENS)


def cluster_miss_labels(
    miss_labels: List[Dict[str, object]],
    threshold: float = 0.6,
) -> Dict[str, List[Dict[str, object]]]:
    """Greedy token-Jaccard clustering of miss_label dicts (SR-59 #58).

    Args:
        miss_labels: List of miss_label dicts (rich schema with
            ``question_text``; falls back to ``label`` for legacy records).
        threshold: Minimum Jaccard overlap to join an existing cluster
            (default 0.6 per AGENTS.md §13.8.1 acceptance criterion).

    Returns:
        Mapping ``cluster_key → members`` where cluster_key is the
        space-joined sorted token set of the cluster's seed label. Empty if
        ``miss_labels`` is empty.

    Algorithm:
        Greedy single-pass: for each miss compute token set, score Jaccard
        against each existing cluster seed, attach to best ≥ threshold, else
        start a new cluster. O(n²) worst-case — adequate for the n<10k miss
        regime; if telemetry ever exceeds that, switch to MinHash/LSH.

    Examples:
        >>> ml = [{"question_text": "Postleitzahl"},
        ...       {"question_text": "Was ist Ihre Postleitzahl?"},
        ...       {"question_text": "Lieblings-Pizza"}]
        >>> clusters = cluster_miss_labels(ml, threshold=0.5)
        >>> len(clusters)  # PLZ-cluster + pizza-cluster
        2
    """
    clusters: Dict[str, List[Dict[str, object]]] = {}
    seed_tokens: Dict[str, frozenset] = {}

    for ml in miss_labels:
        text = ml.get("question_text") or ml.get("label") or ""
        tokens = _tokenize(str(text))
        if not tokens:
            continue

        best_key: Optional[str] = None
        best_score = threshold  # strict: must beat the floor
        for key, ktoks in seed_tokens.items():
            union = tokens | ktoks
            if not union:
                continue
            jaccard = len(tokens & ktoks) / len(union)
            if jaccard >= best_score:
                best_score = jaccard
                best_key = key

        if best_key is None:
            new_key = " ".join(sorted(tokens))
            clusters[new_key] = [ml]
            seed_tokens[new_key] = tokens
        else:
            clusters[best_key].append(ml)

    return clusters
