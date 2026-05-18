"""Tests for survey.graph.vision_fallback (SR-239 / CEO-WAVE-1).

Scope
-----
Pure unit tests on the helpers — no network, no Chrome, no NVIDIA NIM.
The injectable VisionBackend seam is exercised with a deterministic
stub so we can assert the orchestration loop end-to-end.
"""

from __future__ import annotations

import unittest
from dataclasses import dataclass, field
from typing import Any
from unittest.mock import MagicMock

from survey.graph.vision_fallback import (
    DEFAULT_NO_DOM_CHANGE_THRESHOLD,
    MAX_MARKS_PER_FRAME,
    MarkedElement,
    SetOfMarkPlan,
    VisionBackend,
    VisionDecision,
    build_set_of_mark,
    parse_vlm_response,
    run_vision_fallback,
    should_use_vision_fallback,
)


# ── State double ──────────────────────────────────────────────────────────────


@dataclass
class _State:
    no_dom_change_count: int = 0
    universal_elements: list = field(default_factory=list)
    decision: dict = field(default_factory=dict)


def _el(
    sid: str,
    role: str = "button",
    *,
    name: str = "",
    bbox: dict | None = None,
    disabled: bool = False,
) -> dict:
    return {
        "stable_id": sid,
        "role": role,
        "name": name,
        "bbox": bbox if bbox is not None else {"x": 10, "y": 10, "width": 80, "height": 30},
        "state": {"disabled": disabled},
    }


# ── should_use_vision_fallback ────────────────────────────────────────────────


class TestShouldTrigger(unittest.TestCase):
    def test_does_not_trigger_when_dom_is_quiet(self) -> None:
        s = _State(no_dom_change_count=0, universal_elements=[_el("a")])
        self.assertFalse(should_use_vision_fallback(s))

    def test_triggers_when_dom_change_count_at_threshold(self) -> None:
        s = _State(
            no_dom_change_count=DEFAULT_NO_DOM_CHANGE_THRESHOLD,
            universal_elements=[_el("a")],
            decision={},  # no DOM-path decision this iteration
        )
        self.assertTrue(should_use_vision_fallback(s))

    def test_does_not_trigger_when_dom_path_already_decided(self) -> None:
        s = _State(
            no_dom_change_count=2,
            universal_elements=[_el("a")],
            decision={"action": "click", "stable_id": "a"},
        )
        self.assertFalse(should_use_vision_fallback(s))

    def test_triggers_unconditionally_when_ax_tree_is_empty(self) -> None:
        """An empty AX tree means the DOM path has nothing to work with;
        even with `require_empty_dom_decision=False` the fallback is
        the only sensible next move."""
        s = _State(no_dom_change_count=2, universal_elements=[])
        self.assertTrue(
            should_use_vision_fallback(s, require_empty_dom_decision=False)
        )

    def test_threshold_can_be_overridden(self) -> None:
        s = _State(no_dom_change_count=3, universal_elements=[_el("a")])
        self.assertFalse(should_use_vision_fallback(s, no_dom_change_threshold=5))
        self.assertTrue(should_use_vision_fallback(s, no_dom_change_threshold=2))

    def test_state_without_attributes_is_safe(self) -> None:
        """Duck-typing contract: a bare object that lacks the optional
        attributes should not crash — it should default to "no, do not
        trigger" because we cannot prove the page is stuck."""

        class Bare:
            pass

        self.assertFalse(should_use_vision_fallback(Bare()))


# ── build_set_of_mark ─────────────────────────────────────────────────────────


class TestBuildSetOfMark(unittest.TestCase):
    def test_marks_are_numbered_starting_at_one(self) -> None:
        plan = build_set_of_mark([_el("a"), _el("b"), _el("c")])
        self.assertEqual([m.mark for m in plan.marks], [1, 2, 3])

    def test_drops_disabled(self) -> None:
        plan = build_set_of_mark([_el("a", disabled=True), _el("b")])
        self.assertEqual([m.stable_id for m in plan.marks], ["b"])

    def test_drops_avoid_id(self) -> None:
        plan = build_set_of_mark(
            [_el("a"), _el("b")], avoid_stable_id="a"
        )
        self.assertEqual([m.stable_id for m in plan.marks], ["b"])

    def test_drops_off_screen_elements(self) -> None:
        # A bbox that sits entirely below the viewport must not be
        # marked — the VLM cannot see it.
        offscreen = _el(
            "a", bbox={"x": 0, "y": 2000, "width": 50, "height": 50}
        )
        onscreen = _el("b")
        plan = build_set_of_mark([offscreen, onscreen], viewport=(1280, 800))
        self.assertEqual([m.stable_id for m in plan.marks], ["b"])

    def test_drops_zero_area_bbox(self) -> None:
        zero = _el("a", bbox={"x": 0, "y": 0, "width": 0, "height": 0})
        nonzero = _el("b")
        plan = build_set_of_mark([zero, nonzero])
        self.assertEqual([m.stable_id for m in plan.marks], ["b"])

    def test_drops_non_actionable_roles(self) -> None:
        plan = build_set_of_mark([
            _el("h", role="heading"),
            _el("g", role="generic"),
            _el("real", role="button"),
        ])
        self.assertEqual([m.stable_id for m in plan.marks], ["real"])

    def test_caps_at_max_marks_and_reports_skipped(self) -> None:
        elements = [_el(f"e{i}") for i in range(MAX_MARKS_PER_FRAME + 7)]
        plan = build_set_of_mark(elements)
        self.assertEqual(len(plan.marks), MAX_MARKS_PER_FRAME)
        self.assertEqual(plan.skipped_count, 7)

    def test_dedupes_stable_id(self) -> None:
        # Defensive: a duplicate stable_id from a buggy snapshot must not
        # land twice in the plan.
        plan = build_set_of_mark([_el("a"), _el("a"), _el("b")])
        self.assertEqual([m.stable_id for m in plan.marks], ["a", "b"])

    def test_marked_element_center_uses_bbox_center(self) -> None:
        plan = build_set_of_mark([
            _el("a", bbox={"x": 100, "y": 200, "width": 50, "height": 30})
        ])
        self.assertEqual(plan.marks[0].center, (125.0, 215.0))


# ── parse_vlm_response ────────────────────────────────────────────────────────


class TestParseVlmResponse(unittest.TestCase):
    def setUp(self) -> None:
        self.plan = build_set_of_mark([_el("a"), _el("b"), _el("c")])

    def test_clean_json_mark_wins(self) -> None:
        d = parse_vlm_response('{"mark": 2, "confidence": 0.9}', self.plan)
        self.assertIsNotNone(d)
        self.assertEqual(d.action, "click")
        self.assertEqual(d.stable_id, "b")
        self.assertEqual(d.raw_mark, 2)
        self.assertAlmostEqual(d.confidence, 0.9, places=4)

    def test_markdown_wrapped_json_still_parses(self) -> None:
        raw = "```json\n{\"mark\": 3}\n```"
        d = parse_vlm_response(raw, self.plan)
        self.assertIsNotNone(d)
        self.assertEqual(d.stable_id, "c")

    def test_unrendered_mark_returns_none(self) -> None:
        # Plan rendered marks 1..3; mark=99 is hallucinated.
        self.assertIsNone(parse_vlm_response('{"mark": 99}', self.plan))

    def test_coords_within_viewport(self) -> None:
        d = parse_vlm_response(
            '{"x": 640, "y": 400, "confidence": 0.6}', self.plan
        )
        self.assertIsNotNone(d)
        self.assertEqual(d.coords, (640.0, 400.0))
        self.assertIsNone(d.stable_id)

    def test_coords_outside_viewport_returns_none(self) -> None:
        # Default viewport in build_set_of_mark is (1280, 800).
        self.assertIsNone(
            parse_vlm_response('{"x": 99999, "y": 99999}', self.plan)
        )

    def test_returns_none_on_garbage(self) -> None:
        self.assertIsNone(parse_vlm_response("", self.plan))
        self.assertIsNone(parse_vlm_response("not json at all", self.plan))
        self.assertIsNone(parse_vlm_response(None, self.plan))  # type: ignore[arg-type]

    def test_falls_back_to_regex_when_json_is_dirty(self) -> None:
        raw = (
            "Sure, here is my answer: the right click is\n"
            '{ trailing comma error, "mark": 1 }\n'
            "let me know if you need more"
        )
        d = parse_vlm_response(raw, self.plan)
        self.assertIsNotNone(d)
        self.assertEqual(d.stable_id, "a")


# ── run_vision_fallback ───────────────────────────────────────────────────────


class _StubBackend:
    """Records the call and replays a canned response."""

    def __init__(self, response: str) -> None:
        self.response = response
        self.calls = []

    def query(self, *, screenshot_b64: str, plan: SetOfMarkPlan, prompt: str) -> str:
        self.calls.append({
            "screenshot_b64_len": len(screenshot_b64),
            "marks": [m.mark for m in plan.marks],
            "prompt_len": len(prompt),
        })
        return self.response


class TestRunVisionFallback(unittest.TestCase):
    def test_empty_plan_returns_none_without_calling_backend(self) -> None:
        backend = _StubBackend('{"mark": 1}')
        empty = build_set_of_mark([])  # no elements -> empty plan
        out = run_vision_fallback(
            backend=backend, screenshot_b64="ZmFrZQ==", plan=empty,
        )
        self.assertIsNone(out)
        self.assertEqual(backend.calls, [])

    def test_full_loop_with_stub_backend(self) -> None:
        plan = build_set_of_mark([_el("a"), _el("b")])
        backend = _StubBackend('{"mark": 1, "confidence": 0.7}')
        out = run_vision_fallback(
            backend=backend, screenshot_b64="ZmFrZQ==", plan=plan,
        )
        self.assertIsNotNone(out)
        assert out is not None  # for the type checker
        self.assertEqual(out.stable_id, "a")
        self.assertEqual(backend.calls[0]["marks"], [1, 2])

    def test_unparseable_response_returns_none_but_did_call_backend(self) -> None:
        plan = build_set_of_mark([_el("a")])
        backend = _StubBackend("…unparseable LLM goo…")
        out = run_vision_fallback(
            backend=backend, screenshot_b64="ZmFrZQ==", plan=plan,
        )
        self.assertIsNone(out)
        self.assertEqual(len(backend.calls), 1)


# ── VisionDecision contract ───────────────────────────────────────────────────


class TestVisionDecision(unittest.TestCase):
    def test_actionable_requires_click_plus_target(self) -> None:
        self.assertTrue(
            VisionDecision(action="click", stable_id="a").is_actionable()
        )
        self.assertTrue(
            VisionDecision(action="click", coords=(10, 20)).is_actionable()
        )
        self.assertFalse(VisionDecision(action="click").is_actionable())
        self.assertFalse(
            VisionDecision(action="wait", stable_id="a").is_actionable()
        )


# ── VisionBackend protocol smoke ──────────────────────────────────────────────


class TestVisionBackendProtocol(unittest.TestCase):
    def test_a_protocol_compatible_class_passes_isinstance_via_query(self) -> None:
        # Protocols at runtime are structural — we don't need
        # @runtime_checkable to assert "any object with query() works",
        # but having a positive smoke test pins the public surface.
        b = _StubBackend('{"mark": 1}')
        self.assertTrue(callable(getattr(b, "query")))


if __name__ == "__main__":
    unittest.main()
