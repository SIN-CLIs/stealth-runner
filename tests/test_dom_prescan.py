"""Tests für dom_prescan – Vision-free Fast Path."""
from __future__ import annotations
import pytest
from runner.dom_prescan import prescan_dom, classify_element, CONFIDENCE_THRESHOLD


class TestClassifyElement:
    def test_button_is_clickable(self):
        assert classify_element({"role": "AXButton", "text": "Submit"}) == "clickable"

    def test_link_is_clickable(self):
        assert classify_element({"role": "AXLink", "text": "Next"}) == "clickable"

    def test_checkbox_is_clickable(self):
        assert classify_element({"role": "AXCheckBox", "text": "Accept"}) == "clickable"

    def test_text_field_is_text_input(self):
        assert classify_element({"role": "AXTextField", "text": "Name"}) == "text_input"

    def test_input_role_is_text_input(self):
        assert classify_element({"role": "input", "text": "email"}) == "text_input"

    def test_question_text_detected(self):
        assert classify_element({"role": "div", "text": "What is your age?"}) == "question_text"

    def test_unknown_element(self):
        assert classify_element({"role": "AXGroup", "text": "container"}) == "unknown"

    def test_div_with_text_is_clickable(self):
        assert classify_element({"role": "div", "text": "Continue"}) == "clickable"


class TestPrescanDom:
    def test_empty_elements(self):
        result = prescan_dom([])
        assert result["confidence"] == 0.0
        assert result["action"] is None

    def test_no_elements_key(self):
        result = prescan_dom({})
        assert result["confidence"] == 0.0

    def test_single_clickable_returns_action(self):
        dom = [{"role": "AXButton", "text": "Start Survey Now", "reasons": ["clickable"]}]
        result = prescan_dom(dom)
        assert result["action"] == "click"
        assert result["path"] == "vision_free"
        assert result["element_id"] == 0

    def test_image_element_falls_back_to_vision(self):
        dom = [
            {"selector": "img.survey", "text": "Select the image", "role": "img"},
            {"role": "AXButton", "text": "Next"},
        ]
        result = prescan_dom(dom)
        assert result["path"] == "needs_vision"

    def test_unknown_elements_fall_back(self):
        dom = [
            {"role": "span", "text": "?"},
        ]
        result = prescan_dom(dom)
        assert result["path"] == "needs_vision"

    def test_no_images_pure_text(self):
        dom = [
            {"role": "div", "text": "What is your favorite color?"},
            {"role": "AXButton", "text": "Blue"},
            {"role": "AXButton", "text": "Red"},
        ]
        result = prescan_dom(dom)
        assert result["action"] in ("click", "type")
