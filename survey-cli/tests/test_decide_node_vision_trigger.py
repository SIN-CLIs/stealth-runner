"""Tests for the SR-239 vision-fallback trigger hook in decide_node.

Scope: prove that decide_node sets vision_fallback_requested correctly
based on the same trigger logic vision_fallback.should_use_vision_fallback
ships. We do NOT call any VLM — the hook is observation-only in this PR.

These tests mock out the heavy LLM/profile dependencies of decide_node
so the test exercises ONLY the hook plumbing, not the existing decision
heuristics.
"""

from __future__ import annotations

import unittest
from dataclasses import dataclass, field
from typing import Any, Dict, List
from unittest.mock import patch


def _make_state(**overrides: Any):
    """Build a real SurveyState with sensible defaults for the hook tests."""
    from survey.graph.state import SurveyState

    s = SurveyState(survey_id="t1", provider="test", cdp_port=9999)
    for k, v in overrides.items():
        setattr(s, k, v)
    return s


def _el(sid: str, role: str = "button", *, name: str = "", disabled: bool = False) -> Dict:
    return {
        "stable_id": sid,
        "role": role,
        "name": name,
        "value": "",
        "tag": "button",
        "bbox": {"x": 10, "y": 10, "width": 80, "height": 30},
        "state": {"checked": False, "disabled": disabled},
        "attrs": {},
    }


class _FakeNim:
    """Stub that lets us pin decide_node's LLM behaviour deterministically."""

    def __init__(self, out: Dict[str, Any] | None = None) -> None:
        self.out = out or {"actions": []}

    def decide(self, *, snapshot, profile):  # noqa: D401  (mirrors real shape)
        return self.out


class TestVisionTriggerHook(unittest.TestCase):
    def setUp(self) -> None:
        # Profile loader is heavy; pin it to a stable, empty profile so the
        # heuristic path picks predictable answers.
        patcher = patch(
            "survey.profile_loader.ProfileLoader.load_profile",
            return_value={"city": "Berlin"},
        )
        self.addCleanup(patcher.stop)
        patcher.start()

        # Quiet the qualification-rules import path. We are not testing
        # those rules here; the hook must work with or without them.
        # Letting decide_node use whatever is present is fine.

    def test_does_not_set_flag_on_quiet_iteration(self) -> None:
        """No previous failures + plenty of DOM candidates → no vision."""
        from survey.graph.nodes import decide_node

        state = _make_state(
            no_dom_change_count=0,
            universal_elements=[
                _el("r1", role="radio", name="Yes"),
                _el("r2", role="radio", name="No"),
            ],
            iteration=1,
        )
        with patch("survey.nim.get_nim", return_value=_FakeNim()):
            out = decide_node(state)

        self.assertFalse(out.vision_fallback_requested)
        self.assertEqual(out.vision_fallback_reason, "")

    def test_does_not_set_flag_when_dom_decision_was_made_this_round(self) -> None:
        """A DOM-path decision wins even when no_dom_change_count >= 1.
        We want to see what THAT click does first; only when even the DOM
        path gives up do we burn VLM tokens."""
        from survey.graph.nodes import decide_node

        state = _make_state(
            no_dom_change_count=1,
            universal_elements=[
                _el("r1", role="radio", name="Yes"),  # heuristic picks this
            ],
            iteration=2,
        )
        with patch("survey.nim.get_nim", return_value=_FakeNim()):
            out = decide_node(state)

        self.assertEqual(out.decision.get("action"), "click")
        self.assertFalse(out.vision_fallback_requested)

    def test_sets_flag_when_stuck_and_no_candidate(self) -> None:
        """no_dom_change_count >= 1 AND no DOM candidate → flag is set."""
        from survey.graph.nodes import decide_node

        state = _make_state(
            no_dom_change_count=2,
            universal_elements=[],  # totally empty AX tree
            iteration=3,
        )
        with patch("survey.nim.get_nim", return_value=_FakeNim()):
            out = decide_node(state)

        # Without any element decide_node falls through to the
        # "wait / no_candidate_found" branch — exactly when vision
        # fallback should fire.
        self.assertEqual(out.decision.get("action"), "wait")
        self.assertTrue(out.vision_fallback_requested)
        self.assertIn("no_dom_change", out.vision_fallback_reason)

    def test_flag_resets_on_recovery_iteration(self) -> None:
        """Once the page is moving again, the flag must drop back to False
        so the next cycle does not re-fire."""
        from survey.graph.nodes import decide_node

        state = _make_state(
            no_dom_change_count=0,  # recovered: previous click moved DOM
            universal_elements=[_el("r1", role="radio", name="Yes")],
            vision_fallback_requested=True,  # carry-over from the bad iter
            vision_fallback_reason="stale",
        )
        with patch("survey.nim.get_nim", return_value=_FakeNim()):
            out = decide_node(state)

        self.assertFalse(out.vision_fallback_requested)
        self.assertEqual(out.vision_fallback_reason, "")

    def test_helper_failure_does_not_break_decide(self) -> None:
        """If `should_use_vision_fallback` raises (e.g. import-time bug),
        decide_node MUST still return a usable decision and just record
        the failure as an error entry. The earnings loop cannot be
        held hostage to an optional fallback."""
        from survey.graph.nodes import decide_node

        state = _make_state(
            no_dom_change_count=2,
            universal_elements=[_el("r1", role="radio", name="Yes")],
        )
        with patch("survey.nim.get_nim", return_value=_FakeNim()), patch(
            "survey.graph.vision_fallback.should_use_vision_fallback",
            side_effect=RuntimeError("simulated"),
        ):
            out = decide_node(state)

        self.assertIn("action", out.decision)
        self.assertFalse(out.vision_fallback_requested)
        # The error must be on the trail so observability sees the bug.
        self.assertTrue(
            any("vision_fallback skipped" in e.get("error", "") for e in out.errors)
        )


if __name__ == "__main__":
    unittest.main()
