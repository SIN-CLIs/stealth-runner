#!/usr/bin/env python3
"""Integration Test (Issue #80): LLM-Path Qualification Filter + Telemetry.

Diese Tests ergänzen ``test_qualification_integration.py``: dort wird der
HEURISTIK-Pfad in ``decide_node`` getestet (filter_safe_answers). Hier
prüfen wir:

  1. ``matched_disqualifying_pattern`` liefert das exakte Pattern zurück,
     nicht nur True/False.
  2. ``record_qualification_block`` schreibt ein wohlgeformtes JSONL-Event
     in ``survey-cli/logs/qualification-blocks-{date}.jsonl``.
  3. Telemetry ist Best-Effort: I/O-Fehler dürfen NIEMALS propagieren.

Pflicht-Kontext: SR-80 / AGENTS.md Deep-Dive "Issue #80".
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).parent.parent))

from survey.qualification_rules import (  # noqa: E402
    is_disqualifying_answer,
    matched_disqualifying_pattern,
    record_qualification_block,
)


def test_matched_pattern_returns_source_regex():
    """matched_disqualifying_pattern liefert den Pattern-String zurück."""
    pat = matched_disqualifying_pattern("Möchte nicht angeben")
    assert pat is not None
    assert "möchte" in pat or "nicht" in pat or "angeben" in pat

    pat_en = matched_disqualifying_pattern("Prefer not to say")
    assert pat_en is not None
    assert "prefer" in pat_en

    # Safe Antworten -> None
    assert matched_disqualifying_pattern("Ja, habe Kinder") is None
    assert matched_disqualifying_pattern("Vollzeit beschäftigt") is None


def test_matched_pattern_consistent_with_is_disqualifying():
    """Beide Funktionen müssen für jeden Input dieselbe Klassifikation
    treffen — sonst hat der Filter Bypass-Pfade."""
    samples = [
        "Möchte nicht angeben",
        "Prefer not to say",
        "Keine Kinder",
        "No pets",
        "Ja, habe Kinder",
        "1-2 Kinder",
        "Hund",
        "Vollzeit beschäftigt",
        "Unter 20.000€",
    ]
    for s in samples:
        is_dq = is_disqualifying_answer(s)
        pat = matched_disqualifying_pattern(s)
        assert is_dq == (pat is not None), (
            f"Mismatch for '{s}': is_dq={is_dq}, pat={pat}"
        )


def test_record_qualification_block_writes_jsonl(tmp_path, monkeypatch):
    """record_qualification_block schreibt eine wohlgeformte Zeile."""
    # Umlenken auf tmp_path über __file__-Pfad. Wir patchen Path(__file__)
    # ist umständlich — einfacher: in das module's resolve()-Ziel
    # symlinken. Hier nutzen wir den simpleren Weg: wir monkeypatchen
    # die Logs-Directory-Funktion indirekt, indem wir ``Path`` im Modul
    # nicht überschreiben, sondern den Pfad mit chdir trickreich
    # umlenken können — UNSAFE. Daher nutzen wir stattdessen mock.patch
    # auf ``pathlib.Path.mkdir`` plus ``builtins.open`` und prüfen den
    # geschriebenen Inhalt.
    captured: list[str] = []

    real_open = open

    def fake_open(path, mode="r", *a, **kw):  # type: ignore[no-untyped-def]
        if "qualification-blocks" in str(path) and "a" in mode:
            class _F:
                def write(self_inner, data):
                    captured.append(data)

                def __enter__(self_inner):
                    return self_inner

                def __exit__(self_inner, *exc):
                    return False
            return _F()
        return real_open(path, mode, *a, **kw)

    with mock.patch("builtins.open", side_effect=fake_open):
        record_qualification_block(
            question_text="Haben Sie Kinder?",
            answer_text="Möchte nicht angeben",
            source="decide_node:llm",
            survey_id="67064749",
            provider="purespectrum",
            iteration=3,
            stable_id="e42",
        )

    assert len(captured) == 1, "Expected exactly one JSONL line"
    line = captured[0].rstrip("\n")
    entry = json.loads(line)
    assert entry["source"] == "decide_node:llm"
    assert entry["survey_id"] == "67064749"
    assert entry["provider"] == "purespectrum"
    assert entry["iteration"] == 3
    assert entry["stable_id"] == "e42"
    assert entry["answer_text"] == "Möchte nicht angeben"
    assert entry["question_text"] == "Haben Sie Kinder?"
    assert entry["matched_pattern"]  # nicht leer
    assert "ts" in entry and "unix_ts" in entry


def test_record_qualification_block_swallows_io_errors():
    """Telemetry darf NIE einen Survey-Run brechen — auch wenn open() crasht."""
    def boom(*a, **kw):
        raise OSError("disk full")

    with mock.patch("builtins.open", side_effect=boom):
        # Muss ohne Exception durchlaufen.
        record_qualification_block(
            question_text="x",
            answer_text="Möchte nicht angeben",
        )


def test_record_qualification_block_auto_resolves_pattern():
    """Wenn matched_pattern nicht übergeben wird, soll der Helper es
    selbst nachschlagen — Aufrufer dürfen das Feld weglassen."""
    captured: list[str] = []

    def fake_open(path, mode="r", *a, **kw):  # type: ignore[no-untyped-def]
        if "qualification-blocks" in str(path) and "a" in mode:
            class _F:
                def write(self_inner, data):
                    captured.append(data)

                def __enter__(self_inner):
                    return self_inner

                def __exit__(self_inner, *exc):
                    return False
            return _F()
        return open(path, mode, *a, **kw)

    with mock.patch("builtins.open", side_effect=fake_open):
        record_qualification_block(
            question_text="",
            answer_text="Prefer not to say",
        )

    entry = json.loads(captured[0])
    assert entry["matched_pattern"]  # auto-resolved
    assert "prefer" in entry["matched_pattern"]


if __name__ == "__main__":
    test_matched_pattern_returns_source_regex()
    test_matched_pattern_consistent_with_is_disqualifying()
    test_record_qualification_block_swallows_io_errors()
    test_record_qualification_block_auto_resolves_pattern()
    print("ALL DIRECT TESTS PASSED (run via pytest for full coverage)")
