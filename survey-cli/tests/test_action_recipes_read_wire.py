"""Tests for the SR-245 action-recipe READ-path hook in decide_node.

Scope: prove decide_node short-circuits to a cached recipe when the
trigger conditions are met, and falls through to the existing NIM /
heuristic path when they aren't. We stub the heavy survey.nim and
websocket modules so the test runs on a sandbox without those deps.
"""

from __future__ import annotations

import os
import sys
import tempfile
import types
import unittest
from dataclasses import dataclass
from typing import Any, Dict
from unittest.mock import patch


# ── sandbox dependency stubs (CI has the real packages) ─────────────────────


# Drop the path-loaded stubs that test_action_recipes installs, so the
# real `survey` / `survey.graph` packages get imported here. Otherwise
# `from survey.graph.nodes import decide_node` would land in the stub
# package and miss the real module.
for _to_drop in (
    "survey.graph.action_recipes",
    "survey.graph",
    "survey",
):
    sys.modules.pop(_to_drop, None)


if "websocket" not in sys.modules:
    _ws = types.ModuleType("websocket")

    def _create_connection(*_a, **_kw):
        raise RuntimeError("websocket stub: not available in this test")

    _ws.create_connection = _create_connection  # type: ignore[attr-defined]
    sys.modules["websocket"] = _ws


def _install_nim_stub(out: Dict[str, Any] | None = None):
    """Replace `survey.nim` with a deterministic stub. Returns the stub
    NIM client so the test can assert on call_count.

    decide_node does `from ..nim import get_nim` lazily inside the
    function body. survey.nim imports openai which is absent on the
    sandbox; replacing the whole module before the lazy import runs is
    the cleanest workaround.
    """
    fake = types.ModuleType("survey.nim")

    class _FakeNimClient:
        def __init__(self, payload):
            self.payload = payload
            self.calls = 0

        def decide(self, *, snapshot, profile):  # noqa: D401
            self.calls += 1
            return self.payload

    client = _FakeNimClient(out or {"actions": []})

    def _get_nim():
        return client

    fake.get_nim = _get_nim  # type: ignore[attr-defined]
    sys.modules["survey.nim"] = fake
    return client


def _make_state(**overrides: Any):
    from survey.graph.state import SurveyState

    s = SurveyState(survey_id="t1", provider="qx", cdp_port=9999)
    for k, v in overrides.items():
        setattr(s, k, v)
    return s


def _el(sid: str, role: str = "button", *, name: str = "", disabled: bool = False) -> dict:
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


class _IsolatedStateDir(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self._old = os.environ.get("STATE_DIR")
        os.environ["STATE_DIR"] = self._tmp.name

        # Stub heavy dependency on profile.
        patcher = patch(
            "survey.profile_loader.ProfileLoader.load_profile",
            return_value={"city": "Berlin"},
        )
        self.addCleanup(patcher.stop)
        patcher.start()

    def tearDown(self) -> None:
        if self._old is None:
            os.environ.pop("STATE_DIR", None)
        else:
            os.environ["STATE_DIR"] = self._old
        self._tmp.cleanup()


class TestRecipeReadHook(_IsolatedStateDir):
    def test_cache_hit_short_circuits_nim(self) -> None:
        from survey.graph.action_recipes import Recipe, RecipeKey, RecipeStore
        from survey.graph.nodes import decide_node

        elements = [_el("next-btn", role="button", name="Next")]
        state = _make_state(universal_elements=elements)
        key = RecipeKey.from_state(state)
        RecipeStore().record_success(
            key, Recipe(action="click", stable_id="next-btn"),
        )

        nim = _install_nim_stub({"actions": [{"action": "click", "stable_id": "wrong"}]})
        out = decide_node(state)

        self.assertEqual(out.decision.get("action"), "click")
        self.assertEqual(out.decision.get("stable_id"), "next-btn")
        self.assertEqual(out.decision.get("reason"), "recipe_cache_hit")
        self.assertTrue(out.recipe_replay_attempted)
        self.assertEqual(nim.calls, 0,
                         msg="NIM must NOT be called on a cache hit")

    def test_cache_miss_falls_through_to_existing_path(self) -> None:
        from survey.graph.nodes import decide_node

        elements = [_el("foo-btn", role="radio", name="Yes")]
        state = _make_state(universal_elements=elements)

        _install_nim_stub()
        out = decide_node(state)

        self.assertNotEqual(out.decision.get("reason"), "recipe_cache_hit")
        self.assertFalse(out.recipe_replay_attempted)

    def test_disabled_target_in_snapshot_bypasses_replay(self) -> None:
        """A recipe whose stable_id is now disabled MUST NOT replay."""
        from survey.graph.action_recipes import Recipe, RecipeKey, RecipeStore
        from survey.graph.nodes import decide_node

        elements = [_el("next-btn", disabled=True)]
        state = _make_state(universal_elements=elements)
        key = RecipeKey.from_state(state)
        RecipeStore().record_success(
            key, Recipe(action="click", stable_id="next-btn"),
        )

        _install_nim_stub()
        out = decide_node(state)

        self.assertNotEqual(out.decision.get("reason"), "recipe_cache_hit")
        self.assertFalse(out.recipe_replay_attempted)

    def test_avoid_id_blocks_replay(self) -> None:
        """If the previous click already hit no_dom_change on the recipe's
        stable_id, the replay MUST NOT pick the same target."""
        from survey.graph.action_recipes import Recipe, RecipeKey, RecipeStore
        from survey.graph.nodes import decide_node

        elements = [_el("next-btn", role="button", name="Next")]
        state = _make_state(
            universal_elements=elements,
            last_action_result={
                "success": False,
                "reason": "no_dom_change",
                "stable_id": "next-btn",
            },
        )
        key = RecipeKey.from_state(state)
        RecipeStore().record_success(
            key, Recipe(action="click", stable_id="next-btn"),
        )

        _install_nim_stub()
        out = decide_node(state)

        self.assertNotEqual(out.decision.get("reason"), "recipe_cache_hit")
        self.assertFalse(out.recipe_replay_attempted)

    def test_env_off_disables_cache_consultation(self) -> None:
        from survey.graph.action_recipes import Recipe, RecipeKey, RecipeStore
        from survey.graph.nodes import decide_node

        elements = [_el("next-btn", role="button", name="Next")]
        state = _make_state(universal_elements=elements)
        key = RecipeKey.from_state(state)
        RecipeStore().record_success(
            key, Recipe(action="click", stable_id="next-btn"),
        )

        _install_nim_stub()
        with patch.dict(os.environ, {"STEALTH_RECIPE_CACHE": "0"}):
            out = decide_node(state)

        self.assertNotEqual(out.decision.get("reason"), "recipe_cache_hit")
        self.assertFalse(out.recipe_replay_attempted)

    def test_replay_attempted_flag_blocks_second_replay_in_same_iter(self) -> None:
        from survey.graph.action_recipes import Recipe, RecipeKey, RecipeStore
        from survey.graph.nodes import decide_node

        elements = [_el("next-btn", role="button", name="Next")]
        state = _make_state(
            universal_elements=elements,
            recipe_replay_attempted=True,
        )
        key = RecipeKey.from_state(state)
        RecipeStore().record_success(
            key, Recipe(action="click", stable_id="next-btn"),
        )

        _install_nim_stub()
        out = decide_node(state)

        self.assertNotEqual(out.decision.get("reason"), "recipe_cache_hit")

    def test_helper_failure_does_not_break_decide(self) -> None:
        """A bug inside the cache helpers MUST NEVER break the earnings
        loop."""
        from survey.graph.nodes import decide_node

        elements = [_el("foo-btn", role="radio", name="Yes")]
        state = _make_state(universal_elements=elements)

        _install_nim_stub()
        with patch(
            "survey.graph.action_recipes.should_consult_cache",
            side_effect=RuntimeError("simulated"),
        ):
            out = decide_node(state)

        self.assertIn("action", out.decision)
        self.assertTrue(
            any("recipe-read skipped" in e.get("error", "") for e in out.errors)
        )

    def test_snapshot_node_resets_replay_flag(self) -> None:
        """The reset MUST happen at the very top of snapshot_node, before
        any error short-circuit, so a previous-iteration carry-over does
        not deny the cache a chance on a fresh page."""
        from survey.graph.nodes import snapshot_node

        state = _make_state(recipe_replay_attempted=True)
        # No tab_ws → snapshot_node hits the early-return path. The
        # reset MUST happen BEFORE that check.
        out = snapshot_node(state)
        self.assertFalse(out.recipe_replay_attempted)


if __name__ == "__main__":
    unittest.main()
