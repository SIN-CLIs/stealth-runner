#!/usr/bin/env python3
"""Test for tool_find_element.py — AX-Tree boundary-match element finder.

BANNED METHODS — NIEMALS VERWENDEN:
❌ playstealth launch
❌ webauto-nodriver — ABSOLUT BANNED
❌ cua-driver click (raw index)
❌ --remote-allow-origins=* (ohne Quotes)
❌ /tmp/heypiggy-bot (fixed profile)
❌ Hardcoded PIDs
❌ pkill -f "Google Chrome"
❌ killall Google Chrome
❌ skylight-cli click --element-index
"""

import unittest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools.tool_find_element import (
    _parse_markdown,
    _boundary_match,
    _text_contains,
    find_element,
    find_all,
    find_button,
    find_radio,
    find_textfield,
    find_link,
    find_checkbox,
    diagnose,
)

MOCK_MARKDOWN = """
- [246] AXButton ("Weiter")
- [247] AXButton ("Weitere Informationen")
- [35] AXTextField ("E-Mail oder Telefonnummer")
- [10] AXRadioButton ("Mannlich")
- [11] AXRadioButton ("Weiblich")
- [12] AXRadioButton ("Divers")
- [54] AXLink ("Google anmelden")
- [200] AXButton ("Zustimmen und fortfahren")
- [300] AXCheckBox ("Ich stimme zu")
- [301] AXButton ("Submit") @(100,200,300,400)
"""


class TestParseMarkdown(unittest.TestCase):
    """Test _parse_markdown — extracting element dictionaries."""

    def test_parses_button_with_text(self):
        elements = _parse_markdown('- [42] AXButton ("Weiter")')
        self.assertEqual(len(elements), 1)
        self.assertEqual(elements[0]["element_index"], 42)
        self.assertEqual(elements[0]["role"], "AXButton")
        self.assertIn("Weiter", elements[0]["text"])

    def test_parses_button_without_text(self):
        elements = _parse_markdown("- [42] AXButton")
        self.assertEqual(len(elements), 1)
        self.assertEqual(elements[0]["text"], "")

    def test_parses_with_bounds(self):
        elements = _parse_markdown('- [301] AXButton ("Submit") @(100,200,300,400)')
        self.assertEqual(len(elements), 1)
        self.assertEqual(elements[0]["bounds"], (100, 200, 300, 400))

    def test_parses_multiple_elements(self):
        elements = _parse_markdown(MOCK_MARKDOWN)
        self.assertGreater(len(elements), 5)

    def test_empty_markdown(self):
        self.assertEqual(_parse_markdown(""), [])
        self.assertEqual(_parse_markdown(None), [])


class TestBoundaryMatch(unittest.TestCase):
    """Test _boundary_match — word-boundary label matching."""

    def test_exact_match(self):
        self.assertTrue(_boundary_match("Weiter", "Weiter"))

    def test_boundary_prevents_prefix(self):
        """'Weiter' should NOT match 'Weitere Informationen'."""
        self.assertFalse(_boundary_match("Weiter", "Weitere Informationen"))

    def test_boundary_allows_suffix(self):
        """'Weiter' matches 'Weiter >' (boundary after word)."""
        self.assertTrue(_boundary_match("Weiter", "Weiter >"))

    def test_case_insensitive(self):
        self.assertTrue(_boundary_match("weiter", "Weiter"))
        self.assertTrue(_boundary_match("WEITER", "weiter"))

    def test_empty_strings(self):
        self.assertFalse(_boundary_match("", "text"))
        self.assertFalse(_boundary_match("text", ""))
        self.assertFalse(_boundary_match("", ""))

    def test_substring_no_boundary(self):
        """'mail' in 'E-Mail oder Telefonnummer' matches via boundary (mail is word-bounded after dash)."""
        self.assertTrue(_boundary_match("mail", "E-Mail oder Telefonnummer"))
        self.assertTrue(_text_contains("mail", "E-Mail oder Telefonnummer"))


class TestFindElement(unittest.TestCase):
    """Test find_element — main element finder."""

    def test_find_button_by_label(self):
        el = find_element(MOCK_MARKDOWN, "AXButton", label="Weiter")
        self.assertIsNotNone(el)
        self.assertEqual(el["element_index"], 246)

    def test_boundary_prevents_weiter_in_weitere(self):
        """'Weiter' finds [246] but not [247] 'Weitere Informationen'."""
        el = find_element(MOCK_MARKDOWN, "AXButton", label="Weiter")
        self.assertEqual(el["element_index"], 246)

    def test_find_waitere_matches_weitere(self):
        """'Weitere' should match 'Weitere Informationen'."""
        el = find_element(MOCK_MARKDOWN, "AXButton", label="Weitere")
        self.assertEqual(el["element_index"], 247)

    def test_find_textfield_by_substring(self):
        el = find_element(MOCK_MARKDOWN, "AXTextField", text_sub="e-mail")
        self.assertIsNotNone(el)
        self.assertEqual(el["element_index"], 35)

    def test_find_element_not_found(self):
        self.assertIsNone(find_element(MOCK_MARKDOWN, "AXButton", label="Nicht existent"))

    def test_find_element_empty_markdown(self):
        self.assertIsNone(find_element("", "AXButton", label="Test"))

    def test_find_first_without_label(self):
        el = find_element(MOCK_MARKDOWN, "AXRadioButton")
        self.assertIsNotNone(el)
        self.assertEqual(el["element_index"], 10)

    def test_find_element_case_insensitive_exact_fallback(self):
        el = find_element(MOCK_MARKDOWN, "AXRadioButton", label="Mannlich")
        self.assertEqual(el["element_index"], 10)

    def test_find_link_by_label(self):
        el = find_element(MOCK_MARKDOWN, "AXLink", label="Google anmelden")
        self.assertEqual(el["element_index"], 54)


class TestFindAll(unittest.TestCase):
    """Test find_all — returning multiple matches."""

    def test_find_all_radios(self):
        radios = find_all(MOCK_MARKDOWN, "AXRadioButton")
        self.assertEqual(len(radios), 3)

    def test_find_all_buttons(self):
        buttons = find_all(MOCK_MARKDOWN, "AXButton")
        self.assertGreater(len(buttons), 2)

    def test_find_all_empty(self):
        self.assertEqual(find_all(MOCK_MARKDOWN, "AXSlider"), [])
        self.assertEqual(find_all("", "AXButton"), [])


class TestConvenienceFinders(unittest.TestCase):
    """Test convenience finders: find_button, find_radio, etc."""

    def test_find_button(self):
        self.assertEqual(find_button(MOCK_MARKDOWN, "Weiter")["element_index"], 246)

    def test_find_radio(self):
        self.assertEqual(find_radio(MOCK_MARKDOWN, "Weiblich")["element_index"], 11)

    def test_find_textfield(self):
        self.assertEqual(find_textfield(MOCK_MARKDOWN, "E-Mail")["element_index"], 35)

    def test_find_link(self):
        el = find_link(MOCK_MARKDOWN, "Google anmelden")
        self.assertEqual(el["element_index"], 54)

    def test_find_checkbox(self):
        el = find_checkbox(MOCK_MARKDOWN, "Ich stimme zu")
        self.assertEqual(el["element_index"], 300)


class TestDiagnose(unittest.TestCase):
    """Test diagnose() helper for debugging failed searches."""

    def test_diagnose_returns_elements(self):
        diag = diagnose(MOCK_MARKDOWN, "AXTextField", label="Password")
        self.assertGreater(diag["elements_total"], 0)
        self.assertEqual(diag["role_matches"], 1)
        self.assertEqual(diag["label_requested"], "Password")

    def test_diagnose_empty_markdown(self):
        diag = diagnose("", "AXButton")
        self.assertEqual(diag["elements_total"], 0)

    def test_diagnose_includes_role_elements(self):
        diag = diagnose(MOCK_MARKDOWN, "AXRadioButton")
        self.assertIn("role_elements", diag)
        self.assertEqual(len(diag["role_elements"]), 3)


if __name__ == "__main__":
    unittest.main()
