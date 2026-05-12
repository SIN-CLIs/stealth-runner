# -*- coding: utf-8 -*-
"""
test_decide_node_combobox.py
============================

Test-Suite fuer Issue #50 (SR-52):
``decide_node`` MUSS combobox-Elemente in zwei Pfaden behandeln:

(a) OPTIONS-BASED COMBOBOX  (Dropdown):
    - ``tag == "select"`` ODER es existieren ``role == "option"`` /
      ``role == "listbox"`` Elemente im Snapshot.
    - Erwartetes Verhalten: dedizierte 2a-bis Heuristik liefert
      ``action == "click"`` mit ``reason`` beginnt mit
      ``"combobox_expand:"`` — das oeffnet das Dropdown im naechsten
      Execute-Tick.
    - Heuristik 2b (Profil-Text-Fill) DARF dieses Element NICHT
      anfassen.

(b) EDITABLE-TEXT COMBOBOX  (Autocomplete):
    - ``role == "combobox"``, KEIN natives ``<select>`` und KEINE
      option/listbox-Geschwister im Snapshot.
    - Erwartetes Verhalten: 2a-bis ueberspringt das Element, 2b
      uebernimmt und liefert ``action == "fill"`` mit dem korrekten
      Profilwert via ``ProfileLoader.match_field()``.

Pflicht-Kontext:
    - ``survey-cli/survey/graph/nodes.py`` decide_node (Heuristik 2a-bis + 2b)
    - ``survey-cli/survey/profile_loader.py`` match_field()
    - AGENTS.md §13.2 (Heuristik-Reihenfolge)
"""

from __future__ import annotations

import os
import sys
import unittest
from unittest.mock import patch

HERE = os.path.dirname(os.path.abspath(__file__))
PARENT = os.path.dirname(HERE)
if PARENT not in sys.path:
    sys.path.insert(0, PARENT)

from survey.graph.nodes import decide_node
from survey.graph.state import SurveyState


# ----------------------------------------------------------------------------
# Element-Factory
# ----------------------------------------------------------------------------


def _element(
    stable_id: str,
    role: str,
    name: str = "",
    value: str = "",
    tag: str = "",
    attrs: dict | None = None,
    state: dict | None = None,
) -> dict:
    return {
        "stable_id": stable_id,
        "role": role,
        "name": name,
        "value": value,
        "tag": tag,
        "text": "",
        "attrs": attrs or {},
        "state": state or {},
        "bbox": {"x": 0, "y": 0, "width": 100, "height": 30},
        "frame_id": "",
        "frame_url": "",
        "backend_node_id": 0,
    }


def _state_with(elements: list[dict]) -> SurveyState:
    s = SurveyState()
    s.universal_elements = elements
    s.provider = "test"
    s.iteration = 1
    s.no_dom_change_count = 0
    return s


# Profil-Mock — match_field bekommt city aus PLZ-/Stadt-Feld
_FAKE_PROFILE = {
    "first_name": "Max",
    "last_name": "Mustermann",
    "city": "Berlin",
    "zip": "10115",
    "email": "max@example.com",
}


# ----------------------------------------------------------------------------
# (a) OPTIONS-BASED COMBOBOX: native <select>
# ----------------------------------------------------------------------------


class TestNativeSelectClickedNotFilled(unittest.TestCase):
    """tag='select' → 2a-bis MUSS click_expand emittieren, 2b NICHT fill."""

    def test_native_select_click_expand(self):
        elements = [
            _element(
                "sel001abc0000000",
                role="combobox",
                name="Bundesland",
                tag="select",
                state={"expanded": False},
            ),
        ]
        state = _state_with(elements)

        with (
            patch("survey.profile_loader.ProfileLoader.load_profile", return_value=_FAKE_PROFILE),
            patch("survey.nim.get_nim", side_effect=ImportError),
        ):
            out = decide_node(state)

        self.assertEqual(out.decision["action"], "click")
        self.assertEqual(out.decision["stable_id"], "sel001abc0000000")
        self.assertTrue(out.decision["reason"].startswith("combobox_expand:"))


class TestExpandedNativeSelectNotReClicked(unittest.TestCase):
    """Wenn state.expanded=True, 2a-bis MUSS ueberspringen."""

    def test_expanded_combobox_skipped(self):
        elements = [
            _element(
                "sel001abc0000000",
                role="combobox",
                name="Bundesland",
                tag="select",
                state={"expanded": True},
            ),
        ]
        state = _state_with(elements)

        with (
            patch("survey.profile_loader.ProfileLoader.load_profile", return_value=_FAKE_PROFILE),
            patch("survey.nim.get_nim", side_effect=ImportError),
        ):
            out = decide_node(state)

        # Kein expand-Click, kein fill (combobox ohne match_field-Mapping
        # fuer "Bundesland") → wait
        self.assertEqual(out.decision["action"], "wait")


# ----------------------------------------------------------------------------
# (a') ARIA-COMBOBOX + sichtbare listbox/option-Geschwister
# ----------------------------------------------------------------------------


class TestAriaComboboxWithListboxClickedNotFilled(unittest.TestCase):
    """role=combobox + role=listbox im Snapshot → options-based → click."""

    def test_aria_combobox_with_listbox_click(self):
        elements = [
            _element(
                "cb0001000000abcd",
                role="combobox",
                name="Land",
                tag="div",
                state={"expanded": False},
            ),
            _element("lb0002000000abcd", role="listbox", tag="div"),
        ]
        state = _state_with(elements)

        with (
            patch("survey.profile_loader.ProfileLoader.load_profile", return_value=_FAKE_PROFILE),
            patch("survey.nim.get_nim", side_effect=ImportError),
        ):
            out = decide_node(state)

        self.assertEqual(out.decision["action"], "click")
        self.assertEqual(out.decision["stable_id"], "cb0001000000abcd")
        self.assertTrue(out.decision["reason"].startswith("combobox_expand:"))


# ----------------------------------------------------------------------------
# (b) EDITABLE-TEXT COMBOBOX
# ----------------------------------------------------------------------------


class TestEditableComboboxFilledNotClicked(unittest.TestCase):
    """role=combobox, NICHT select, KEINE option-Geschwister → 2b fill."""

    def test_editable_combobox_profile_fill(self):
        # Name = "Stadt" → match_field liefert profile['city']
        elements = [
            _element(
                "ed0001000000abcd",
                role="combobox",
                name="Stadt",
                tag="input",
                attrs={"placeholder": "Ihre Stadt"},
                state={"expanded": False},
            ),
        ]
        state = _state_with(elements)

        with (
            patch("survey.profile_loader.ProfileLoader.load_profile", return_value=_FAKE_PROFILE),
            patch("survey.nim.get_nim", side_effect=ImportError),
        ):
            out = decide_node(state)

        self.assertEqual(out.decision["action"], "fill")
        self.assertEqual(out.decision["stable_id"], "ed0001000000abcd")
        self.assertEqual(out.decision["value"], "Berlin")
        self.assertEqual(out.decision["reason"], "heuristic_fill:profile_match")


# ----------------------------------------------------------------------------
# (c) MIXED SNAPSHOT — Dropdown + Editable Combobox + textbox
# ----------------------------------------------------------------------------


class TestComboboxOrderingDropdownBeforeFill(unittest.TestCase):
    """Im selben Snapshot kommt 2a-bis (Dropdown) VOR 2b (Fill)."""

    def test_dropdown_expand_picked_over_textbox(self):
        elements = [
            _element(
                "dd000000000000ab",
                role="combobox",
                name="Bundesland",
                tag="select",
                state={"expanded": False},
            ),
            _element(
                "tb000000000000cd",
                role="textbox",
                name="Stadt",
                attrs={"placeholder": "Ihre Stadt"},
            ),
        ]
        state = _state_with(elements)

        with (
            patch("survey.profile_loader.ProfileLoader.load_profile", return_value=_FAKE_PROFILE),
            patch("survey.nim.get_nim", side_effect=ImportError),
        ):
            out = decide_node(state)

        # 2a-bis MUSS gewinnen — Dropdown muss zuerst aufgeklappt werden
        self.assertEqual(out.decision["action"], "click")
        self.assertEqual(out.decision["stable_id"], "dd000000000000ab")


class TestDisabledComboboxSkipped(unittest.TestCase):
    """disabled=True → weder 2a-bis click noch 2b fill."""

    def test_disabled_native_select_skipped(self):
        elements = [
            _element(
                "ds000000000000ab",
                role="combobox",
                name="Bundesland",
                tag="select",
                state={"expanded": False, "disabled": True},
            ),
        ]
        state = _state_with(elements)

        with (
            patch("survey.profile_loader.ProfileLoader.load_profile", return_value=_FAKE_PROFILE),
            patch("survey.nim.get_nim", side_effect=ImportError),
        ):
            out = decide_node(state)

        self.assertEqual(out.decision["action"], "wait")


class TestAvoidIdAppliesToCombobox(unittest.TestCase):
    """Wenn avoid_stable_id der combobox entspricht → 2a-bis skipt."""

    def test_avoid_id_skips_combobox_expand(self):
        elements = [
            _element(
                "av000000000000ab",
                role="combobox",
                name="Bundesland",
                tag="select",
                state={"expanded": False},
            ),
        ]
        state = _state_with(elements)
        state.last_action_result = {
            "success": False,
            "reason": "no_dom_change",
            "stable_id": "av000000000000ab",
        }

        with (
            patch("survey.profile_loader.ProfileLoader.load_profile", return_value=_FAKE_PROFILE),
            patch("survey.nim.get_nim", side_effect=ImportError),
        ):
            out = decide_node(state)

        # 2a-bis skipt → 2b skipt (avoid_id wird in 2b auch geprueft) → wait
        self.assertEqual(out.decision["action"], "wait")


if __name__ == "__main__":
    unittest.main(verbosity=2)
