"""Tests für dom_prescan – Vision-free Fast Path."""
from __future__ import annotations
import pytest
from runner.dom_prescan import prescan_dom, classify_element, CONFIDENCE_THRESHOLD


class TestClassifyElement:
    def test_button_is_clickable(self):
        assert classify_element({"role": "AXButton", "label": "Submit"}) == "clickable"

    def test_link_is_clickable(self):
        assert classify_element({"role": "AXLink", "label": "Next"}) == "clickable"

    def test_checkbox_is_clickable(self):
        assert classify_element({"role": "AXCheckBox", "label": "Accept"}) == "clickable"

    def test_text_field_is_text_input(self):
        assert classify_element({"role": "AXTextField", "label": "Name"}) == "text_input"

    def test_question_text_detected(self):
        assert classify_element({"role": "AXStaticText", "label": "What is your age?"}) == "question_text"

    def test_unknown_element(self):
        assert classify_element({"role": "AXGroup", "label": "container"}) == "unknown"

    def test_high_confidence_fallback(self):
        assert classify_element({"role": "AXUnknown", "label": "OK", "confidence": 0.95}) == "clickable"


class TestPrescanDom:
    def test_empty_elements(self):
        result = prescan_dom({"elements": []})
        assert result["confidence"] == 0.0
        assert result["action"] is None

    def test_no_elements_key(self):
        result = prescan_dom({})
        assert result["confidence"] == 0.0

    def test_single_clickable_high_confidence(self):
        dom = {"elements": [{"role": "AXButton", "label": "Start", "confidence": 0.95}]}
        result = prescan_dom(dom)
        assert result["action"] == "click"
        assert result["confidence"] >= CONFIDENCE_THRESHOLD
        assert result["path"] == "vision_free"
        assert result["element_id"] == 0

    def test_question_with_button(self):
        dom = {"elements": [
            {"role": "AXStaticText", "label": "What is your name?", "confidence": 0.92},
            {"role": "AXButton", "label": "Next", "confidence": 0.90},
        ]}
        result = prescan_dom(dom)
        assert result["action"] == "click"
        assert result["path"] == "vision_free"

    def test_low_confidence_falls_back(self):
        dom = {"elements": [
            {"role": "AXStaticText", "label": "What is your age?", "confidence": 0.5},
            {"role": "AXButton", "label": "Next", "confidence": 0.4},
        ]}
        result = prescan_dom(dom)
        assert result["path"] == "needs_vision"

    def test_text_input_detected(self):
        dom = {"elements": [
            {"role": "AXStaticText", "label": "Enter your email:", "confidence": 0.90},
            {"role": "AXTextField", "label": "Email", "confidence": 0.92},
        ]}
        result = prescan_dom(dom)
        assert result["action"] == "type"
        assert result["path"] == "vision_free"

    def test_multiple_clickables_picks_best(self):
        dom = {"elements": [
            {"role": "AXButton", "label": "Cancel", "confidence": 0.70},
            {"role": "AXButton", "label": "Submit", "confidence": 0.95},
        ]}
        result = prescan_dom(dom)
        assert result["element_id"] == 1
        assert result["confidence"] >= CONFIDENCE_THRESHOLD
