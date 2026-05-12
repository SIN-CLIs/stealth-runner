"""Regression-Suite fuer survey.nim.parse_response().

WARUM: parse_response() ist die einzige Schnittstelle zwischen rohem NIM-
Nemotron-Output und dem decide_node-Entscheidungsformat. Jede Regression hier
bedeutet stille Halluzinationen im Survey-Loop (Issue #24, Issue #25).
Diese Suite fuettert ECHTE Beispiel-Antworten (gut, schlecht, kaputt) und
sichert die invariants gegen Code-Drift ab.

KONTRAKT (siehe survey-cli/survey/nim.py "RESPONSE-PARSER"):
  - Eingabe: roher string vom LLM (oder None).
  - Ausgabe: list[dict] — IMMER. Niemals None, niemals leer.
  - Bei jedem Versagen (None/leer/garbled/unparseable): [{"action": "wait"}].
  - "complete"/"done" als alleiniger Text-Hinweis ohne JSON: [{"action": "complete"}].
  - ``ref`` aus Legacy-Output wird zu ``stable_id`` normalisiert.
  - Markdown-Fences (```json ... ```) werden abgestreift.
  - Eingebettetes JSON in Fliesstext wird per Regex extrahiert.

WICHTIG (Aenderung gegenueber alter Suite test_nim.py):
  Frueher war das Fallback ``[{"action": "submit"}]``. Das hat blind
  Submit gedrueckt ohne Verify und war eine Halluzinations-Quelle. Neuer
  Kontrakt: Fallback = ``[{"action": "wait"}]``. Der naechste Tick darf
  dann re-scannen + re-deciden.

PFLICHT-VORGEHEN BEIM ERWEITERN:
  - Neuer Schema-Case → hier einen Test hinzufuegen, Beispiel-String wird
    INLINE definiert (KEINE externen Fixtures).
  - Falls parse_response gravierend geaendert wird → AGENTS.md
    "NIM-OUTPUT-VALIDIERUNG" Abschnitt updaten.

BANNED:
  ❌ Tests die parse_response durch Monkey-Patching umgehen
  ❌ Mocking von json.loads — wir testen das echte Parsing-Verhalten
  ❌ "raises Exception" — parse_response darf NIEMALS exception werfen
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from survey.nim import parse_response


# =============================================================================
# Happy-Path: v2-Schema mit stable_id
# =============================================================================


class TestV2SchemaClick(unittest.TestCase):
    def test_dict_with_actions_click(self):
        raw = '{"actions":[{"stable_id":"abc123","action":"click"}]}'
        result = parse_response(raw)
        self.assertEqual(result, [{"stable_id": "abc123", "action": "click"}])


class TestV2SchemaFillWithValue(unittest.TestCase):
    def test_dict_with_actions_fill(self):
        raw = '{"actions":[{"stable_id":"xy7","action":"fill","value":"Berlin"}]}'
        result = parse_response(raw)
        self.assertEqual(
            result,
            [
                {"stable_id": "xy7", "action": "fill", "value": "Berlin"},
            ],
        )


class TestV2SchemaBareList(unittest.TestCase):
    def test_bare_list_of_actions(self):
        raw = '[{"stable_id":"q9","action":"click"}]'
        result = parse_response(raw)
        self.assertEqual(result, [{"stable_id": "q9", "action": "click"}])


class TestV2SchemaWaitOnly(unittest.TestCase):
    def test_pure_wait(self):
        raw = '{"actions":[{"action":"wait"}]}'
        result = parse_response(raw)
        self.assertEqual(result, [{"action": "wait"}])


class TestV2SchemaCompleteOnly(unittest.TestCase):
    def test_pure_complete(self):
        raw = '{"actions":[{"action":"complete"}]}'
        result = parse_response(raw)
        self.assertEqual(result, [{"action": "complete"}])


# =============================================================================
# Legacy: @eN-ref-Schema (wird zu stable_id normalisiert)
# =============================================================================


class TestLegacyRefNormalisedToStableId(unittest.TestCase):
    def test_ref_renamed_when_no_stable_id(self):
        raw = '[{"ref":"@e0","action":"click"}]'
        result = parse_response(raw)
        self.assertEqual(result, [{"stable_id": "@e0", "action": "click"}])

    def test_ref_kept_when_stable_id_present(self):
        # Wenn beides vorhanden, gewinnt stable_id; ref wird nicht ueberschrieben
        # (Parser laesst ref-Feld unangetastet, normalisiert nur fehlende stable_id).
        raw = '[{"ref":"@e0","stable_id":"abc","action":"click"}]'
        result = parse_response(raw)
        # stable_id muss erhalten bleiben
        self.assertEqual(result[0]["stable_id"], "abc")


class TestLegacyDictWithActionsKey(unittest.TestCase):
    def test_dict_actions_with_legacy_ref(self):
        raw = '{"actions":[{"ref":"@e5","action":"select"}]}'
        result = parse_response(raw)
        self.assertEqual(result, [{"stable_id": "@e5", "action": "select"}])


# =============================================================================
# Robustheit: Markdown-Fences, Fliesstext, Whitespace
# =============================================================================


class TestMarkdownFenceJson(unittest.TestCase):
    def test_strips_json_fence(self):
        raw = '```json\n[{"stable_id":"a","action":"click"}]\n```'
        result = parse_response(raw)
        self.assertEqual(result, [{"stable_id": "a", "action": "click"}])


class TestMarkdownFenceBare(unittest.TestCase):
    def test_strips_bare_fence(self):
        raw = '```\n[{"stable_id":"b","action":"click"}]\n```'
        result = parse_response(raw)
        self.assertEqual(result, [{"stable_id": "b", "action": "click"}])


class TestEmbeddedJsonInProse(unittest.TestCase):
    def test_extracts_dict_from_chatter(self):
        raw = (
            "Sure, let me think... I will click the continue button: "
            '{"actions":[{"stable_id":"btn","action":"click"}]} done.'
        )
        result = parse_response(raw)
        self.assertEqual(result, [{"stable_id": "btn", "action": "click"}])

    def test_extracts_list_across_newlines(self):
        raw = (
            "Analysis:\n"
            "I want to pick the male option.\n"
            '[\n  {"stable_id":"male","action":"click"}\n]\n'
            "That is my final answer."
        )
        result = parse_response(raw)
        self.assertEqual(result, [{"stable_id": "male", "action": "click"}])


# =============================================================================
# Defensiver Fallback: Garbage → [{"action":"wait"}]
# =============================================================================


class TestNoneReturnsWait(unittest.TestCase):
    def test_none_input(self):
        self.assertEqual(parse_response(None), [{"action": "wait"}])


class TestEmptyStringReturnsWait(unittest.TestCase):
    def test_empty_string(self):
        self.assertEqual(parse_response(""), [{"action": "wait"}])


class TestWhitespaceOnlyReturnsWait(unittest.TestCase):
    def test_whitespace(self):
        self.assertEqual(parse_response("   \n\t  "), [{"action": "wait"}])


class TestGarbageTextReturnsWait(unittest.TestCase):
    def test_random_words(self):
        self.assertEqual(
            parse_response("asdf qwer zxcv 1234 !@#$"),
            [{"action": "wait"}],
        )


class TestBrokenJsonReturnsWait(unittest.TestCase):
    def test_truncated_json(self):
        # Truncated JSON, kein regex-extrahierbares Subset
        raw = '{"actions":[{"stable_id":"a"'  # cut mid-string
        result = parse_response(raw)
        self.assertEqual(result, [{"action": "wait"}])

    def test_unterminated_brace_returns_wait(self):
        # KEIN valides JSON irgendwo in raw
        raw = "Sure, here is what I'd do: but no JSON included."
        result = parse_response(raw)
        self.assertEqual(result, [{"action": "wait"}])


class TestEmptyActionsArrayReturnsWait(unittest.TestCase):
    def test_dict_with_empty_actions(self):
        raw = '{"actions":[]}'
        result = parse_response(raw)
        self.assertEqual(result, [{"action": "wait"}])

    def test_bare_empty_list(self):
        raw = "[]"
        result = parse_response(raw)
        self.assertEqual(result, [{"action": "wait"}])


# =============================================================================
# Spezial: "complete"/"done" als alleiniger Text-Hinweis
# =============================================================================


class TestCompleteKeywordInProse(unittest.TestCase):
    def test_complete_word_no_json(self):
        # KEIN JSON irgendwo → keyword-Fallback aktiv
        raw = "The survey is now complete. Thanks!"
        result = parse_response(raw)
        self.assertEqual(result, [{"action": "complete"}])


class TestCompleteWordWithoutKeywordSetReturnsWait(unittest.TestCase):
    def test_no_complete_no_json(self):
        raw = "Hmm not sure what to do here."
        result = parse_response(raw)
        self.assertEqual(result, [{"action": "wait"}])


# =============================================================================
# Schema-Resilienz: Plain dict, mixed types, non-dict items
# =============================================================================


class TestPlainDictWrappedInList(unittest.TestCase):
    def test_single_dict_no_actions_key(self):
        raw = '{"stable_id":"x","action":"click"}'
        result = parse_response(raw)
        self.assertEqual(result, [{"stable_id": "x", "action": "click"}])


class TestNonDictItemsFiltered(unittest.TestCase):
    def test_strings_in_list_ignored(self):
        raw = '["junk", {"stable_id":"a","action":"click"}, 42]'
        result = parse_response(raw)
        self.assertEqual(result, [{"stable_id": "a", "action": "click"}])

    def test_all_junk_returns_wait(self):
        raw = '["junk", 42, null]'
        result = parse_response(raw)
        self.assertEqual(result, [{"action": "wait"}])


# =============================================================================
# Realistische NIM-Antwort-Snapshots (synthetisch aber realistisch)
# =============================================================================


class TestRealisticNimResponseFenced(unittest.TestCase):
    def test_typical_nemotron_output(self):
        # So sieht Nemotron's Output in der Realitaet aus: fenced JSON
        # mit korrekt v2-Schema.
        raw = (
            "```json\n"
            "{\n"
            '  "actions": [\n'
            '    {"stable_id": "f0_abc1234", "action": "click"}\n'
            "  ]\n"
            "}\n"
            "```"
        )
        result = parse_response(raw)
        self.assertEqual(
            result,
            [
                {"stable_id": "f0_abc1234", "action": "click"},
            ],
        )


class TestRealisticNimResponseChainOfThought(unittest.TestCase):
    def test_cot_then_json(self):
        raw = (
            "Reasoning: The user must select 'Männlich' to match the profile.\n"
            "The matching element is f0_male_radio.\n\n"
            'JSON: {"actions":[{"stable_id":"f0_male_radio","action":"click"}]}'
        )
        result = parse_response(raw)
        self.assertEqual(
            result,
            [
                {"stable_id": "f0_male_radio", "action": "click"},
            ],
        )


class TestRealisticNimResponseFill(unittest.TestCase):
    def test_fill_with_german_value(self):
        raw = '{"actions":[{"stable_id":"f0_plz","action":"fill","value":"10785"}]}'
        result = parse_response(raw)
        self.assertEqual(
            result,
            [
                {"stable_id": "f0_plz", "action": "fill", "value": "10785"},
            ],
        )


class TestRealisticBrokenNimResponseTrailingComma(unittest.TestCase):
    def test_trailing_comma_breaks_json_but_no_crash(self):
        # JSON mit trailing comma ist invalid → parse_response sollte
        # safe-fallback liefern, KEIN exception werfen.
        raw = '{"actions":[{"stable_id":"a","action":"click",}]}'
        result = parse_response(raw)
        # Entweder wait (parse failed) oder kein crash — wichtig: list
        self.assertIsInstance(result, list)
        self.assertTrue(len(result) >= 1)


class TestRealisticDoubleEncodedJson(unittest.TestCase):
    def test_double_quotes_around_json(self):
        # Modell hat aus Versehen den JSON-string nochmal gequotet
        raw = '"{\\"actions\\":[{\\"stable_id\\":\\"x\\",\\"action\\":\\"click\\"}]}"'
        result = parse_response(raw)
        # Sollte NICHT crashen — entweder wait oder parsed
        self.assertIsInstance(result, list)
        self.assertTrue(len(result) >= 1)


# =============================================================================
# Invariants — ueber alle Inputs garantiert
# =============================================================================


class TestInvariants(unittest.TestCase):
    """Egal welcher Input — parse_response liefert garantiert eine
    nicht-leere Liste mit dict-Items, ohne Exception."""

    INPUTS = [
        None,
        "",
        " ",
        "abc",
        "[]",
        "{}",
        "null",
        "[null]",
        "[{}]",
        '{"actions":[]}',
        '{"actions":null}',
        '[{"action":"click"}]',
        '[{"stable_id":"a","action":"click"}]',
        "```\n[\n```",
        "complete!",
        "done done done",
    ]

    def test_always_returns_list(self):
        for inp in self.INPUTS:
            with self.subTest(input=repr(inp)):
                result = parse_response(inp)
                self.assertIsInstance(result, list, f"failed for {inp!r}")

    def test_always_non_empty(self):
        for inp in self.INPUTS:
            with self.subTest(input=repr(inp)):
                result = parse_response(inp)
                self.assertTrue(len(result) >= 1, f"failed for {inp!r}")

    def test_all_items_are_dicts(self):
        for inp in self.INPUTS:
            with self.subTest(input=repr(inp)):
                result = parse_response(inp)
                for item in result:
                    self.assertIsInstance(
                        item,
                        dict,
                        f"non-dict item {item!r} for input {inp!r}",
                    )

    def test_fallback_path_has_action_key(self):
        """Wenn parse_response auf den Fallback-Pfad geht (kein gueltiges
        actions-Schema), MUSS jedes Item ein 'action'-Key haben.
        Achtung: parse_response leitet ``[{}]`` durch — das ist by design
        (kein Schema-enforcement im Parser, sondern in decide_node)."""
        ambiguous = (None, "", " ", "abc", '{"actions":[]}', "complete!", "done done done")
        for inp in ambiguous:
            with self.subTest(input=repr(inp)):
                result = parse_response(inp)
                for item in result:
                    self.assertIn(
                        "action",
                        item,
                        f"fallback item {item!r} missing 'action' for {inp!r}",
                    )


if __name__ == "__main__":
    unittest.main(verbosity=2)
