"""Tests for the SR-244 record_execute_outcome wire-up helper.

Scope: prove the helper makes the right write/tombstone/skip decision
on every realistic execute_node outcome. We DO NOT exercise nodes.py
itself here — that file pulls in `websocket` at import time which is
not available in the sandbox. The integration test for the hooked
nodes.py path lives in test_decide_node_recipe_wire (next PR).

The branches we pin:

    success=True  + click/fill/submit + stable_id  -> "recorded"
    success=True  + press_key + key                 -> "recorded"
    success=True  + click without stable_id         -> "skipped"
    success=False + reason="no_dom_change"          -> "invalidated"
    success=False + reason="no_dom_change_after_retries" -> "invalidated"
    success=False + reason="other_error"            -> "skipped"
    decision={action: "wait"|"done"|"noop"|""}      -> "skipped"
    state with empty universal_elements             -> "skipped"
    store raises on record_success                  -> "skipped" (defensive)
"""

from __future__ import annotations

import importlib.util
import os
import sys
import tempfile
import types
import unittest
from dataclasses import dataclass, field

# Same load pattern as test_action_recipes (avoids pulling websocket
# via survey.graph.__init__).
_HERE = os.path.dirname(os.path.abspath(__file__))
_SURVEY_CLI = os.path.dirname(_HERE)
_AR_PATH = os.path.join(
    _SURVEY_CLI, "survey", "graph", "action_recipes.py",
)


def _load_action_recipes():
    if "survey" not in sys.modules:
        sys.modules["survey"] = types.ModuleType("survey")
        sys.modules["survey"].__path__ = []  # type: ignore[attr-defined]
    if "survey.graph" not in sys.modules:
        sys.modules["survey.graph"] = types.ModuleType("survey.graph")
        sys.modules["survey.graph"].__path__ = []  # type: ignore[attr-defined]
    name = "survey.graph.action_recipes"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, _AR_PATH)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


_ar = _load_action_recipes()
record_execute_outcome = _ar.record_execute_outcome
RecipeStore = _ar.RecipeStore
RecipeKey = _ar.RecipeKey
Recipe = _ar.Recipe


@dataclass
class _State:
    universal_elements: list = field(default_factory=list)
    provider: str = "qx"
    survey_url: str = "https://qx.test/p?t=1"
    recipe_replay_attempted: bool = False


def _el(sid: str, role: str = "button", *, name: str = "") -> dict:
    return {
        "stable_id": sid,
        "role": role,
        "name": name,
        "state": {"disabled": False},
    }


class _IsolatedStateDir(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self._old = os.environ.get("STATE_DIR")
        os.environ["STATE_DIR"] = self._tmp.name

    def tearDown(self) -> None:
        if self._old is None:
            os.environ.pop("STATE_DIR", None)
        else:
            os.environ["STATE_DIR"] = self._old
        self._tmp.cleanup()


class TestRecordExecuteOutcomeBranches(_IsolatedStateDir):
    def test_records_on_successful_click(self) -> None:
        s = _State(universal_elements=[_el("next-btn")])
        out = record_execute_outcome(
            s,
            {"action": "click", "stable_id": "next-btn"},
            result_success=True,
            result_reason="ok",
        )
        self.assertEqual(out, "recorded")
        # Verify it actually landed in the store.
        key = RecipeKey.from_state(s)
        self.assertIsNotNone(RecipeStore().lookup(key))

    def test_records_on_successful_fill(self) -> None:
        s = _State(universal_elements=[_el("email", role="textbox")])
        out = record_execute_outcome(
            s,
            {"action": "fill", "stable_id": "email", "value": "alice@x.test"},
            result_success=True,
            result_reason="ok",
        )
        self.assertEqual(out, "recorded")

    def test_records_on_successful_press_key(self) -> None:
        s = _State(universal_elements=[_el("email", role="textbox")])
        out = record_execute_outcome(
            s,
            {"action": "press_key", "key": "Enter"},
            result_success=True,
            result_reason="ok",
        )
        self.assertEqual(out, "recorded")

    def test_skips_when_action_is_wait(self) -> None:
        s = _State(universal_elements=[_el("a")])
        for action in ("", "wait", "done", "noop"):
            out = record_execute_outcome(
                s,
                {"action": action},
                result_success=True,
                result_reason="ok",
            )
            self.assertEqual(out, "skipped", msg=f"action={action!r}")

    def test_skips_when_click_without_stable_id(self) -> None:
        s = _State(universal_elements=[_el("a")])
        out = record_execute_outcome(
            s,
            {"action": "click", "stable_id": ""},
            result_success=True,
            result_reason="ok",
        )
        self.assertEqual(out, "skipped")

    def test_skips_when_press_key_without_key_field(self) -> None:
        s = _State(universal_elements=[_el("a")])
        out = record_execute_outcome(
            s,
            {"action": "press_key", "key": ""},
            result_success=True,
            result_reason="ok",
        )
        self.assertEqual(out, "skipped")

    def test_skips_when_unknown_action(self) -> None:
        s = _State(universal_elements=[_el("a")])
        out = record_execute_outcome(
            s,
            {"action": "drag_drop", "stable_id": "a"},
            result_success=True,
            result_reason="ok",
        )
        self.assertEqual(out, "skipped")

    def test_invalidates_on_no_dom_change(self) -> None:
        s = _State(universal_elements=[_el("next-btn")])
        # Seed the store first with an active recipe.
        key = RecipeKey.from_state(s)
        RecipeStore().record_success(
            key, Recipe(action="click", stable_id="next-btn"),
        )
        out = record_execute_outcome(
            s,
            {"action": "click", "stable_id": "next-btn"},
            result_success=False,
            result_reason="no_dom_change",
        )
        self.assertEqual(out, "invalidated")
        self.assertIsNone(RecipeStore().lookup(key))

    def test_invalidates_on_no_dom_change_after_retries(self) -> None:
        s = _State(universal_elements=[_el("next-btn")])
        key = RecipeKey.from_state(s)
        RecipeStore().record_success(
            key, Recipe(action="click", stable_id="next-btn"),
        )
        out = record_execute_outcome(
            s,
            {"action": "click", "stable_id": "next-btn"},
            result_success=False,
            result_reason="no_dom_change_after_retries",
        )
        self.assertEqual(out, "invalidated")
        self.assertIsNone(RecipeStore().lookup(key))

    def test_skips_on_other_failure_reasons(self) -> None:
        """A click that fails because the page navigated mid-flight or
        the actuator timed out is NOT a stale-recipe signal — the
        recipe was right, the page was misbehaving. We must not
        tombstone in that case (it would force NIM to pay again on the
        next iteration for no benefit)."""
        s = _State(universal_elements=[_el("next-btn")])
        key = RecipeKey.from_state(s)
        RecipeStore().record_success(
            key, Recipe(action="click", stable_id="next-btn"),
        )
        for reason in ("timeout", "selector_not_found", "actuator_error"):
            out = record_execute_outcome(
                s,
                {"action": "click", "stable_id": "next-btn"},
                result_success=False,
                result_reason=reason,
            )
            self.assertEqual(out, "skipped", msg=f"reason={reason!r}")
        # Recipe is still there.
        self.assertIsNotNone(RecipeStore().lookup(key))

    def test_skips_on_empty_snapshot(self) -> None:
        """No snapshot → no signature → no key. RecipeStore would
        also refuse this, but the helper short-circuits earlier so we
        don't pay for the write attempt."""
        s = _State(universal_elements=[])
        out = record_execute_outcome(
            s,
            {"action": "click", "stable_id": "next"},
            result_success=True,
            result_reason="ok",
        )
        self.assertEqual(out, "skipped")

    def test_returns_skipped_when_store_raises_on_record(self) -> None:
        """Defensive: a bug in the store MUST NOT break the earnings loop."""

        class _BoomStore:
            def record_success(self, *a, **kw):
                raise RuntimeError("disk full")

            def invalidate(self, *a, **kw):
                pass  # never reached on the success path

        s = _State(universal_elements=[_el("a")])
        out = record_execute_outcome(
            s,
            {"action": "click", "stable_id": "a"},
            result_success=True,
            result_reason="ok",
            store=_BoomStore(),
        )
        self.assertEqual(out, "skipped")

    def test_returns_skipped_when_store_raises_on_invalidate(self) -> None:
        class _BoomStore:
            def record_success(self, *a, **kw):
                pass

            def invalidate(self, *a, **kw):
                raise RuntimeError("disk full")

        s = _State(universal_elements=[_el("a")])
        out = record_execute_outcome(
            s,
            {"action": "click", "stable_id": "a"},
            result_success=False,
            result_reason="no_dom_change",
            store=_BoomStore(),
        )
        self.assertEqual(out, "skipped")

    def test_decision_dict_is_optional(self) -> None:
        s = _State(universal_elements=[_el("a")])
        # `decision = None` should not crash.
        out = record_execute_outcome(
            s,
            None,  # type: ignore[arg-type]
            result_success=True,
            result_reason="ok",
        )
        self.assertEqual(out, "skipped")


class TestRecordExecuteOutcomeRoundtrip(_IsolatedStateDir):
    def test_record_then_invalidate_then_record(self) -> None:
        """Lifecycle: a page that was learned, broke once (no_dom_change),
        and was re-learned on the next attempt must end with the latest
        active recipe."""
        s = _State(universal_elements=[_el("next-btn")])
        decision = {"action": "click", "stable_id": "next-btn"}

        out1 = record_execute_outcome(
            s, decision, result_success=True, result_reason="ok",
        )
        self.assertEqual(out1, "recorded")

        out2 = record_execute_outcome(
            s, decision, result_success=False, result_reason="no_dom_change",
        )
        self.assertEqual(out2, "invalidated")

        out3 = record_execute_outcome(
            s, decision, result_success=True, result_reason="ok",
        )
        self.assertEqual(out3, "recorded")

        # And the cache is happy again.
        self.assertIsNotNone(RecipeStore().lookup(RecipeKey.from_state(s)))


if __name__ == "__main__":
    unittest.main()
