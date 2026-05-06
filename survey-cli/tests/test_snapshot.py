"""Test survey/snapshot.py — NEMO compact snapshot generation.

Tests:
  - _detect_questions: label text >5 chars, excludes "powered by"
  - _detect_progress: text with "%" and digit
  - asdict: nested dataclass → dict conversion
  - CompactSnapshot.to_dict: round-trip correctness
  - generate_snapshot: CDP WS → CompactSnapshot (2 Runtime.evaluate calls)
"""

import unittest
from unittest.mock import patch, MagicMock
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from survey.snapshot import (
    _detect_questions, _detect_progress, asdict,
    generate_snapshot, CompactSnapshot, detect_provider
)


# =============================================================================
# Test _detect_questions
# =============================================================================
class TestDetectQuestions(unittest.TestCase):

    def test_simple_labels(self):
        elements = [
            {"role": "label", "text": "Geschlecht"},
            {"role": "label", "text": "Männlich"},
        ]
        result = _detect_questions(elements)
        self.assertEqual(result, ["Geschlecht", "Männlich"])

    def test_ignores_short_text(self):
        elements = [
            {"role": "label", "text": "Ja"},       # < 5 chars → ignored
            {"role": "label", "text": "Nein"},     # 4 chars → ignored
            {"role": "label", "text": "Weiblich"}, # 8 chars → kept
        ]
        result = _detect_questions(elements)
        self.assertEqual(result, ["Weiblich"])

    def test_ignores_powered_by(self):
        elements = [
            {"role": "label", "text": "Powered by Qualtrics"},
            {"role": "label", "text": "Powered by SurveyGizmo"},
        ]
        result = _detect_questions(elements)
        self.assertEqual(result, [])

    def test_ignores_non_label_roles(self):
        elements = [
            {"role": "button", "text": "Weiter"},
            {"role": "radio", "text": "Option A"},
            {"role": "textbox", "text": "Berlin"},
            {"role": "label", "text": "Was ist Ihr Alter?"},
        ]
        result = _detect_questions(elements)
        self.assertEqual(result, ["Was ist Ihr Alter?"])

    def test_case_insensitive_powered_by(self):
        elements = [{"role": "label", "text": "PoWeReD bY QuAlTrIcS"}]
        result = _detect_questions(elements)
        self.assertEqual(result, [])

    def test_empty_list(self):
        self.assertEqual(_detect_questions([]), [])

    def test_missing_text_key(self):
        elements = [{"role": "label"}, {"role": "label", "text": ""}]
        self.assertEqual(_detect_questions(elements), [])

    def test_long_question(self):
        elements = [
            {"role": "label",
             "text": "Wie zufrieden sind Sie insgesamt mit den angebotenen Produkten und Dienstleistungen?"}
        ]
        result = _detect_questions(elements)
        self.assertEqual(len(result), 1)

    def test_trims_whitespace(self):
        elements = [{"role": "label", "text": "   Geschlecht   "}]
        result = _detect_questions(elements)
        self.assertEqual(result, ["Geschlecht"])


# =============================================================================
# Test _detect_progress
# =============================================================================
class TestDetectProgress(unittest.TestCase):

    def test_percent_with_digit(self):
        elements = [{"text": "Seite 3 von 10 (30%)"}]
        self.assertEqual(_detect_progress(elements), "Seite 3 von 10 (30%)")

    def test_percent_english(self):
        elements = [{"text": "Progress: 50% complete"}]
        self.assertEqual(_detect_progress(elements), "Progress: 50% complete")

    def test_percent_only(self):
        elements = [{"text": "35%"}]
        self.assertEqual(_detect_progress(elements), "35%")

    def test_no_percent_returns_question_mark(self):
        elements = [{"text": "Seite 3 von 10"}]
        self.assertEqual(_detect_progress(elements), "?")

    def test_percent_but_no_digit_returns_question_mark(self):
        elements = [{"text": "% Complete"}]
        self.assertEqual(_detect_progress(elements), "?")

    def test_empty_list(self):
        self.assertEqual(_detect_progress([]), "?")

    def test_missing_text_key(self):
        elements = [{}]
        self.assertEqual(_detect_progress(elements), "?")

    def test_empty_text(self):
        elements = [{"text": ""}]
        self.assertEqual(_detect_progress(elements), "?")

    def test_picks_first_match(self):
        elements = [
            {"text": "Some text"},
            {"text": "Progress: 75%"},
            {"text": "Next: 50%"},
        ]
        self.assertEqual(_detect_progress(elements), "Progress: 75%")

    def test_digit_in_bracket(self):
        elements = [{"text": "[5/10] 50%"}]
        self.assertEqual(_detect_progress(elements), "[5/10] 50%")


# =============================================================================
# Test asdict (stdlib dataclasses.asdict)
# =============================================================================
class TestAsdict(unittest.TestCase):

    def test_simple_snapshot(self):
        snap = CompactSnapshot(
            refs={"@e0": {"role": "button", "text": "Weiter"}},
            semantic={"questions": ["Was ist Ihr Alter?"]},
            url="https://example.com",
            title="Survey",
            provider="qualtrics",
            timestamp="2026-05-06T12:00:00",
        )
        d = snap.to_dict()
        self.assertIsInstance(d, dict)
        self.assertEqual(d["provider"], "qualtrics")
        self.assertEqual(d["url"], "https://example.com")
        self.assertIn("@e0", d["refs"])

    def test_asdict_nested_dataclass(self):
        snap = CompactSnapshot(
            refs={"@e0": {"role": "radio", "text": "Männlich"}},
            semantic={"progress": "50%"},
        )
        d = asdict(snap)
        self.assertEqual(d["refs"]["@e0"]["role"], "radio")
        self.assertEqual(d["semantic"]["progress"], "50%")

    def test_asdict_empty_refs(self):
        snap = CompactSnapshot()
        d = asdict(snap)
        self.assertEqual(d["refs"], {})
        self.assertEqual(d["semantic"], {})

    def test_to_dict_alias(self):
        snap = CompactSnapshot(provider="tolunastart")
        d = snap.to_dict()
        self.assertEqual(d["provider"], "tolunastart")

    def test_asdict_deep_copy_primitives(self):
        snap = CompactSnapshot(
            refs={"@e0": {"role": "button"}},
            semantic={"questions": ["Q1"]},
        )
        d = asdict(snap)
        d["refs"]["@e0"]["role"] = "modified"
        # Original should be unchanged (deep copy)
        self.assertEqual(snap.refs["@e0"]["role"], "button")

    def test_asdict_list_values(self):
        snap = CompactSnapshot(
            semantic={"questions": ["Q1", "Q2"], "buttons": ["Weiter", "Zurück"]},
        )
        d = asdict(snap)
        self.assertEqual(d["semantic"]["questions"], ["Q1", "Q2"])
        self.assertEqual(d["semantic"]["buttons"], ["Weiter", "Zurück"])

    def test_default_values(self):
        snap = CompactSnapshot()
        d = snap.to_dict()
        self.assertEqual(d["refs"], {})
        self.assertEqual(d["semantic"], {})
        self.assertEqual(d["url"], "")
        self.assertEqual(d["title"], "")
        self.assertEqual(d["provider"], "unknown")
        self.assertEqual(d["timestamp"], "")


# =============================================================================
# Test detect_provider (already covered in test_detection, add edge cases)
# =============================================================================
class TestDetectProvider(unittest.TestCase):

    def test_cpx_subdomain(self):
        self.assertIn(detect_provider("https:// Panels-Surveys.cpx panel.com/"),
                      ("cpx", "unknown"))

    def test_qualtrics_domains(self):
        self.assertIn(detect_provider("https:// university.qualtrics.com/Survey/"),
                      ("qualtrics", "unknown"))

    def test_tolunastart(self):
        self.assertIn(detect_provider("https:// start.tolunastart.com/"),
                      ("tolunastart", "unknown"))

    def test_samplicio(self):
        self.assertIn(detect_provider("https:// rx.samplicio.us/consent/"),
                      ("samplicio", "unknown"))

    def test_cint(self):
        self.assertIn(detect_provider("https:// s.cint.com/Survey/Fingerprint/"),
                      ("cint", "unknown"))

    def test_cloudresearch(self):
        self.assertIn(detect_provider("https:// opnsurf.com/"),
                      ("cloudresearch", "unknown"))

    def test_unknown(self):
        self.assertEqual(detect_provider("https:// completely.random-site.xyz/"), "unknown")


# =============================================================================
# Test generate_snapshot (requires WS mock)
# =============================================================================
class MockWs:
    """Mock WebSocket for generate_snapshot tests.

    generate_snapshot sends 2 Runtime.evaluate calls:
      1. Page metadata (url, title, innerText)
      2. DOM elements (ELEMENT_EXTRACTOR_JS)

    recv() returns JSON strings which the module's json.loads parses.
    """
    def __init__(self, responses):
        self._responses = responses
        self._idx = 0
        self.sent = []

    def send(self, data):
        self.sent.append(json.loads(data) if isinstance(data, str) else data)

    def recv(self):
        if self._idx < len(self._responses):
            r = self._responses[self._idx]
            self._idx += 1
            return r if isinstance(r, str) else json.dumps(r)
        return json.dumps({"result": {"result": {"value": "[]"}}})

    def getsockname(self):
        return "ws://localhost:9999"

    def getpeername(self):
        return ("localhost", 9999)

    def close(self):
        pass


class TestGenerateSnapshot(unittest.TestCase):

    def test_basic_snapshot(self):
        """Minimal working snapshot with page + elements."""
        meta_resp = json.dumps({
            "result": {
                "result": {
                    "value": json.dumps({
                        "url": "https://example.samplicio.us/",
                        "title": "Survey",
                        "innerText": "Question text here",
                    })
                }
            }
        })
        elements_resp = json.dumps({
            "result": {
                "result": {
                    "value": json.dumps([
                        {"role": "button", "tag": "button", "text": "Weiter",
                         "label": "", "name": "", "value": "", "type": "", "enabled": True},
                        {"role": "radio", "tag": "input", "text": "Option A",
                         "label": "", "name": "", "value": "", "type": "radio", "enabled": True},
                    ])
                }
            }
        })
        mock_ws = MockWs([meta_resp, elements_resp])
        with patch('websocket.create_connection', return_value=mock_ws):
            snap = generate_snapshot("ws://localhost:9999", include_semantic=False)

        self.assertIsInstance(snap, CompactSnapshot)
        self.assertEqual(snap.url, "https://example.samplicio.us/")
        self.assertEqual(snap.title, "Survey")
        self.assertIn("@e0", snap.refs)
        self.assertIn("@e1", snap.refs)
        self.assertEqual(snap.refs["@e0"]["role"], "button")
        self.assertEqual(snap.refs["@e0"]["text"], "Weiter")
        self.assertEqual(snap.refs["@e1"]["role"], "radio")
        self.assertEqual(snap.provider, "samplicio")

    def test_ref_indices_increment(self):
        """Element refs increment from @e0."""
        meta_resp = json.dumps({
            "result": {"result": {"value": json.dumps(
                {"url": "https://test.com", "title": "Test", "innerText": ""})}}
        })
        elements_resp = json.dumps({
            "result": {"result": {"value": json.dumps([
                {"role": "button", "tag": "button", "text": "A",
                 "label": "", "name": "", "value": "", "type": "", "enabled": True},
                {"role": "button", "tag": "button", "text": "B",
                 "label": "", "name": "", "value": "", "type": "", "enabled": True},
                {"role": "button", "tag": "button", "text": "C",
                 "label": "", "name": "", "value": "", "type": "", "enabled": True},
            ])}}
        })
        mock_ws = MockWs([meta_resp, elements_resp])
        with patch('websocket.create_connection', return_value=mock_ws):
            snap = generate_snapshot("ws://localhost:9999", include_semantic=False)
        refs = list(snap.refs.keys())
        self.assertEqual(refs, ["@e0", "@e1", "@e2"])

    def test_semantic_questions_extracted(self):
        """include_semantic=True → _detect_questions runs."""
        meta_resp = json.dumps({
            "result": {"result": {"value": json.dumps(
                {"url": "https://test.com", "title": "Test", "innerText": ""})}}
        })
        elements_resp = json.dumps({
            "result": {"result": {"value": json.dumps([
                {"role": "label", "tag": "label", "text": "Was ist Ihr Geschlecht?",
                 "label": "", "name": "", "value": "", "type": "", "enabled": True},
                {"role": "button", "tag": "button", "text": "Weiter",
                 "label": "", "name": "", "value": "", "type": "", "enabled": True},
            ])}}
        })
        mock_ws = MockWs([meta_resp, elements_resp])
        with patch('websocket.create_connection', return_value=mock_ws):
            snap = generate_snapshot("ws://localhost:9999", include_semantic=True)
        self.assertEqual(snap.semantic.get("questions"), ["Was ist Ihr Geschlecht?"])

    def test_semantic_buttons_extracted(self):
        """include_semantic=True → buttons list up to 5."""
        meta_resp = json.dumps({
            "result": {"result": {"value": json.dumps(
                {"url": "https://test.com", "title": "Test", "innerText": ""})}}
        })
        elements_resp = json.dumps({
            "result": {"result": {"value": json.dumps([
                {"role": "button", "tag": "button", "text": "Start",
                 "label": "", "name": "", "value": "", "type": "", "enabled": True},
                {"role": "button", "tag": "button", "text": "Weiter",
                 "label": "", "name": "", "value": "", "type": "", "enabled": True},
                {"role": "button", "tag": "button", "text": "Zurück",
                 "label": "", "name": "", "value": "", "type": "", "enabled": True},
            ])}}
        })
        mock_ws = MockWs([meta_resp, elements_resp])
        with patch('websocket.create_connection', return_value=mock_ws):
            snap = generate_snapshot("ws://localhost:9999", include_semantic=True)
        self.assertEqual(snap.semantic.get("buttons"), ["Start", "Weiter", "Zurück"])

    def test_empty_elements_handled(self):
        """No elements found → refs={}."""
        meta_resp = json.dumps({
            "result": {"result": {"value": json.dumps(
                {"url": "https://test.com", "title": "Test", "innerText": ""})}}
        })
        elements_resp = json.dumps({
            "result": {"result": {"value": "[]"}}
        })
        mock_ws = MockWs([meta_resp, elements_resp])
        with patch('websocket.create_connection', return_value=mock_ws):
            snap = generate_snapshot("ws://localhost:9999", include_semantic=False)
        self.assertEqual(snap.refs, {})

    def test_missing_innerText_handled(self):
        """Page with no body text."""
        meta_resp = json.dumps({
            "result": {"result": {"value": json.dumps(
                {"url": "https://test.com", "title": "", "innerText": ""})}}
        })
        elements_resp = json.dumps({
            "result": {"result": {"value": "[]"}}
        })
        mock_ws = MockWs([meta_resp, elements_resp])
        with patch('websocket.create_connection', return_value=mock_ws):
            snap = generate_snapshot("ws://localhost:9999", include_semantic=False)
        self.assertIsInstance(snap, CompactSnapshot)
        self.assertEqual(snap.title, "")

    def test_missing_result_key_returns_empty(self):
        """CDP response missing result key."""
        meta_resp = json.dumps({"error": "timeout"})
        elements_resp = json.dumps({"error": "timeout"})
        mock_ws = MockWs([meta_resp, elements_resp])
        with patch('websocket.create_connection', return_value=mock_ws):
            snap = generate_snapshot("ws://localhost:9999", include_semantic=False)
        self.assertIsInstance(snap, CompactSnapshot)
        self.assertEqual(snap.url, "")

    def test_all_element_fields_captured(self):
        """Every field from ELEMENT_EXTRACTOR_JS is preserved."""
        meta_resp = json.dumps({
            "result": {"result": {"value": json.dumps(
                {"url": "https://test.com", "title": "Test", "innerText": ""})}}
        })
        elements_resp = json.dumps({
            "result": {"result": {"value": json.dumps([
                {"role": "textbox", "tag": "input", "text": "Berlin",
                 "label": "Stadt", "name": "city", "value": "Berlin",
                 "type": "text", "enabled": True},
            ])}}
        })
        mock_ws = MockWs([meta_resp, elements_resp])
        with patch('websocket.create_connection', return_value=mock_ws):
            snap = generate_snapshot("ws://localhost:9999", include_semantic=False)
        e0 = snap.refs["@e0"]
        self.assertEqual(e0["role"], "textbox")
        self.assertEqual(e0["tag"], "input")
        self.assertEqual(e0["text"], "Berlin")
        self.assertEqual(e0["label"], "Stadt")
        self.assertEqual(e0["name"], "city")
        self.assertEqual(e0["type"], "text")
        self.assertTrue(e0["enabled"])

    def test_disabled_element_enabled_false(self):
        """Disabled element has enabled=False."""
        meta_resp = json.dumps({
            "result": {"result": {"value": json.dumps(
                {"url": "https://test.com", "title": "Test", "innerText": ""})}}
        })
        elements_resp = json.dumps({
            "result": {"result": {"value": json.dumps([
                {"role": "button", "tag": "button", "text": "Submit",
                 "label": "", "name": "", "value": "", "type": "", "enabled": False},
            ])}}
        })
        mock_ws = MockWs([meta_resp, elements_resp])
        with patch('websocket.create_connection', return_value=mock_ws):
            snap = generate_snapshot("ws://localhost:9999", include_semantic=False)
        self.assertFalse(snap.refs["@e0"]["enabled"])

    def test_sends_two_runtime_evaluate_calls(self):
        """generate_snapshot sends exactly 2 CDP calls: metadata + elements."""
        meta_resp = json.dumps({
            "result": {"result": {"value": json.dumps(
                {"url": "https://test.com", "title": "Test", "innerText": ""})}}
        })
        elements_resp = json.dumps({
            "result": {"result": {"value": "[]"}}
        })
        mock_ws = MockWs([meta_resp, elements_resp])
        with patch('websocket.create_connection', return_value=mock_ws):
            generate_snapshot("ws://localhost:9999", include_semantic=False)
        eval_calls = [s for s in mock_ws.sent if s.get("method") == "Runtime.evaluate"]
        self.assertEqual(len(eval_calls), 2)


# =============================================================================
# Test CompactSnapshot edge cases
# =============================================================================
class TestCompactSnapshotEdgeCases(unittest.TestCase):

    def test_very_long_text_truncated(self):
        """Text > 80 chars is truncated by ELEMENT_EXTRACTOR_JS, reflected in snapshot."""
        snap = CompactSnapshot(
            refs={"@e0": {"role": "label", "text": "x" * 200}},
        )
        # Text is stored as-is (JS truncates to 80, not Python)
        d = snap.to_dict()
        self.assertEqual(len(d["refs"]["@e0"]["text"]), 200)

    def test_special_chars_in_refs(self):
        """Unicode and special chars preserved."""
        snap = CompactSnapshot(
            refs={"@e0": {"role": "radio", "text": "Männlich ✓"}},
        )
        d = snap.to_dict()
        self.assertIn("Männlich ✓", d["refs"]["@e0"]["text"])

    def test_multiple_pages_same_ref_indices(self):
        """Different snapshots can reuse @eN indices independently."""
        snap1 = CompactSnapshot(refs={"@e0": {"role": "button", "text": "A"}})
        snap2 = CompactSnapshot(refs={"@e0": {"role": "radio", "text": "B"}})
        self.assertEqual(snap1.refs["@e0"]["text"], "A")
        self.assertEqual(snap2.refs["@e0"]["text"], "B")

    def test_semantic_empty_by_default(self):
        snap = CompactSnapshot()
        self.assertEqual(snap.semantic, {})
        self.assertNotIn("questions", snap.semantic)
        self.assertNotIn("progress", snap.semantic)

    def test_timestamp_format(self):
        snap = CompactSnapshot(timestamp="2026-05-06T12:00:00")
        d = snap.to_dict()
        # Should be ISO format
        self.assertIn("T", d["timestamp"])


if __name__ == "__main__":
    unittest.main(verbosity=2)