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

from .suggester import SuggestedFamily, suggest_family


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
) -> List[Dict[str, object]]:
    """Aggregate miss_labels across matcher-telemetry JSONLs.

    Args:
        log_dir: Pfad zum Verzeichnis mit matcher-telemetry-*.jsonl.
        min_count: Vorschlaege nur ab dieser Frequenz (Schutz vor Einmal-Misses).
        persona: Optional Persona-Filter (default: alle).

    Returns:
        Liste von Suggestion-Dicts, sortiert absteigend nach count.
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

    suggestions: List[Dict[str, object]] = []
    for (role, norm), count in counters.most_common():
        if count < min_count:
            continue
        sug: SuggestedFamily = suggest_family(norm)
        suggestions.append({
            "role": role,
            "normalized_label": norm,
            "count": count,
            "sample_labels": samples[(role, norm)],
            "suggested_family": sug.family,
            "confidence": round(sug.confidence, 3),
            "matched_tokens": sug.matched_tokens,
            "label_tokens": sug.label_tokens,
            # WICHTIG fuer review-CLI: explicit status.
            "status": "open",
        })
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
