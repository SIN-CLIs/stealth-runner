"""Tests for survey.graph.action_recipes (SR-243).

Scope: pure unit tests on the helpers — no Chrome, no LLM, no graph.
Wiring into decide_node is the SR-244 PR's job; this PR locks the
helper contract so a future change cannot silently relax it.
"""

from __future__ import annotations

import importlib.util
import os
import sys
import tempfile
import types
import unittest
from dataclasses import dataclass, field

# Import the module directly from its file path so the test does NOT
# pull in survey.graph.__init__ (which imports websocket via nodes.py
# transitively). The cache module is intentionally network-free; this
# import shape mirrors that.
_HERE = os.path.dirname(os.path.abspath(__file__))
_SURVEY_CLI = os.path.dirname(_HERE)
_AR_PATH = os.path.join(
    _SURVEY_CLI, "survey", "graph", "action_recipes.py",
)


def _load_action_recipes():
    """Load survey.graph.action_recipes via spec-from-path so dataclass
    introspection finds the module in sys.modules (CPython 3.12 needs
    that for `dataclass(frozen=True)` to resolve cls.__module__)."""
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
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


_ar = _load_action_recipes()
Recipe = _ar.Recipe
RecipeKey = _ar.RecipeKey
RecipeStore = _ar.RecipeStore
compute_page_signature = _ar.compute_page_signature
match_recipe_to_snapshot = _ar.match_recipe_to_snapshot
should_consult_cache = _ar.should_consult_cache


# ── Fixtures ─────────────────────────────────────────────────────────────────


def _el(
    sid: str,
    role: str = "button",
    *,
    name: str = "",
    disabled: bool = False,
) -> dict:
    return {
        "stable_id": sid,
        "role": role,
        "name": name,
        "state": {"disabled": disabled},
    }


@dataclass
class _State:
    universal_elements: list = field(default_factory=list)
    provider: str = "test"
    recipe_replay_attempted: bool = False
    survey_url: str = ""


class _IsolatedStateDir(unittest.TestCase):
    """Mixin: every test runs against a fresh STATE_DIR."""

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


# ── compute_page_signature ──────────────────────────────────────────────────


class TestPageSignature(unittest.TestCase):
    def test_deterministic_for_same_input(self) -> None:
        a = compute_page_signature([_el("a"), _el("b")], url="https://x/p")
        b = compute_page_signature([_el("a"), _el("b")], url="https://x/p")
        self.assertEqual(a, b)

    def test_invariant_to_element_order(self) -> None:
        a = compute_page_signature([_el("a"), _el("b"), _el("c")], url="https://x/p")
        b = compute_page_signature([_el("c"), _el("a"), _el("b")], url="https://x/p")
        self.assertEqual(a, b)

    def test_invariant_to_querystring_changes(self) -> None:
        """Survey providers attach fresh `?t=...` on every load. The
        cache MUST survive that — otherwise we never hit the cache."""
        a = compute_page_signature([_el("a")], url="https://x/p?t=1&u=alice")
        b = compute_page_signature([_el("a")], url="https://x/p?t=2&u=bob")
        self.assertEqual(a, b)

    def test_invariant_to_url_fragment(self) -> None:
        a = compute_page_signature([_el("a")], url="https://x/p#section1")
        b = compute_page_signature([_el("a")], url="https://x/p#section2")
        self.assertEqual(a, b)

    def test_changes_on_role_change(self) -> None:
        a = compute_page_signature([_el("a", role="button")], url="https://x/p")
        b = compute_page_signature([_el("a", role="link")], url="https://x/p")
        self.assertNotEqual(a, b)

    def test_changes_on_visible_name_change(self) -> None:
        a = compute_page_signature([_el("a", name="Continue")], url="https://x/p")
        b = compute_page_signature([_el("a", name="Submit")], url="https://x/p")
        self.assertNotEqual(a, b)

    def test_invariant_to_csrf_token_in_label(self) -> None:
        """Digit-collapse rule: a number that leaks into a label
        (CSRF / nonce) MUST NOT change the signature."""
        a = compute_page_signature(
            [_el("a", name="Submit form 12345")], url="https://x/p",
        )
        b = compute_page_signature(
            [_el("a", name="Submit form 99999")], url="https://x/p",
        )
        self.assertEqual(a, b)

    def test_ignores_non_actionable_roles(self) -> None:
        """A 'paragraph' role is content noise, not page shape."""
        with_para = compute_page_signature(
            [_el("a"), _el("p1", role="paragraph", name="hello")],
            url="https://x/p",
        )
        without_para = compute_page_signature([_el("a")], url="https://x/p")
        self.assertEqual(with_para, without_para)

    def test_truncates_extremely_long_signal(self) -> None:
        many = [
            _el(f"sid{i}", name="Continue " * 200) for i in range(200)
        ]
        sig = compute_page_signature(many, url="https://x/p")
        self.assertEqual(len(sig), 16)

    def test_empty_input_still_yields_stable_short_hash(self) -> None:
        # The empty signature happens when the snapshot is empty. The
        # store refuses to record under an empty signature; here we
        # just pin that the helper itself is total.
        sig = compute_page_signature([])
        self.assertEqual(len(sig), 16)


# ── Recipe (de)serialise ────────────────────────────────────────────────────


class TestRecipe(unittest.TestCase):
    def test_from_decision_extracts_relevant_fields(self) -> None:
        r = Recipe.from_decision(
            {"action": "click", "stable_id": "a", "value": "", "reason": "llm"},
            ts=1234.5,
        )
        self.assertEqual(r.action, "click")
        self.assertEqual(r.stable_id, "a")
        self.assertEqual(r.last_used_ts, 1234.5)

    def test_as_decision_matches_state_decision_shape(self) -> None:
        r = Recipe(action="fill", stable_id="email", value_template="alice@x.test")
        d = r.as_decision()
        self.assertEqual(d["action"], "fill")
        self.assertEqual(d["stable_id"], "email")
        self.assertEqual(d["value"], "alice@x.test")

    def test_from_dict_drops_unknown_action(self) -> None:
        bad = {
            "action": "drag_drop",  # not in our supported set
            "stable_id": "a",
            "schema_version": 1,
        }
        self.assertIsNone(Recipe.from_dict(bad))

    def test_from_dict_drops_wrong_schema_version(self) -> None:
        bad = {
            "action": "click",
            "stable_id": "a",
            "schema_version": 999,
        }
        self.assertIsNone(Recipe.from_dict(bad))


# ── Match a recipe against a fresh snapshot ─────────────────────────────────


class TestMatchRecipeToSnapshot(unittest.TestCase):
    def test_click_matches_when_stable_id_present(self) -> None:
        r = Recipe(action="click", stable_id="next-btn")
        elements = [_el("next-btn", role="button", name="Next")]
        resolved = match_recipe_to_snapshot(r, elements)
        self.assertIsNotNone(resolved)
        self.assertEqual(resolved.action, "click")
        self.assertEqual(resolved.stable_id, "next-btn")

    def test_click_misses_when_stable_id_missing(self) -> None:
        r = Recipe(action="click", stable_id="next-btn")
        elements = [_el("other-btn")]
        self.assertIsNone(match_recipe_to_snapshot(r, elements))

    def test_click_misses_when_target_disabled(self) -> None:
        r = Recipe(action="click", stable_id="next-btn")
        elements = [_el("next-btn", disabled=True)]
        self.assertIsNone(match_recipe_to_snapshot(r, elements))

    def test_fill_carries_value_template_through(self) -> None:
        r = Recipe(action="fill", stable_id="email", value_template="alice@x.test")
        elements = [_el("email", role="textbox")]
        resolved = match_recipe_to_snapshot(r, elements)
        self.assertIsNotNone(resolved)
        self.assertEqual(resolved.value, "alice@x.test")

    def test_press_key_does_not_need_stable_id_match(self) -> None:
        r = Recipe(action="press_key", key="Enter")
        # Even an empty snapshot is fine — keys go to whatever is focused.
        resolved = match_recipe_to_snapshot(r, [])
        self.assertIsNotNone(resolved)
        self.assertEqual(resolved.key, "Enter")

    def test_press_key_without_key_field_misses(self) -> None:
        r = Recipe(action="press_key", key="")
        self.assertIsNone(match_recipe_to_snapshot(r, []))

    def test_click_missing_stable_id_field_misses(self) -> None:
        r = Recipe(action="click", stable_id="")
        self.assertIsNone(match_recipe_to_snapshot(r, [_el("a")]))


# ── Store: lookup / record / invalidate / compact ───────────────────────────


class TestRecipeStore(_IsolatedStateDir):
    def test_lookup_miss_on_empty_store(self) -> None:
        store = RecipeStore()
        key = RecipeKey("qx", "abcd1234")
        self.assertIsNone(store.lookup(key))

    def test_round_trip_record_then_lookup(self) -> None:
        store = RecipeStore()
        key = RecipeKey("qx", "abcd1234")
        recipe = Recipe(action="click", stable_id="next-btn")
        store.record_success(key, recipe)
        got = store.lookup(key)
        self.assertIsNotNone(got)
        self.assertEqual(got.stable_id, "next-btn")

    def test_lookup_returns_latest_active_recipe(self) -> None:
        store = RecipeStore()
        key = RecipeKey("qx", "abcd1234")
        store.record_success(
            key, Recipe(action="click", stable_id="old-btn"), ts=100.0,
        )
        store.record_success(
            key, Recipe(action="click", stable_id="new-btn"), ts=200.0,
        )
        got = store.lookup(key)
        self.assertIsNotNone(got)
        self.assertEqual(got.stable_id, "new-btn")

    def test_invalidate_makes_lookup_miss(self) -> None:
        store = RecipeStore()
        key = RecipeKey("qx", "abcd1234")
        store.record_success(key, Recipe(action="click", stable_id="next"))
        store.invalidate(key, reason="verify_failed")
        self.assertIsNone(store.lookup(key))

    def test_invalidate_then_record_makes_lookup_hit_again(self) -> None:
        """A page that broke once (recipe got tombstoned) and then
        gets re-learned must be replay-able again."""
        store = RecipeStore()
        key = RecipeKey("qx", "abcd1234")
        store.record_success(
            key, Recipe(action="click", stable_id="next"), ts=100.0,
        )
        store.invalidate(key, ts=200.0)
        store.record_success(
            key, Recipe(action="click", stable_id="next"), ts=300.0,
        )
        got = store.lookup(key)
        self.assertIsNotNone(got)
        self.assertEqual(got.stable_id, "next")

    def test_record_with_empty_signature_is_a_noop(self) -> None:
        """Empty signature = "matches every empty page". Refuse it."""
        store = RecipeStore()
        store.record_success(
            RecipeKey("qx", ""), Recipe(action="click", stable_id="x"),
        )
        # File should not exist OR be empty.
        if store.path.exists():
            self.assertEqual(store.path.read_text(encoding="utf-8").strip(), "")

    def test_compact_drops_redundant_and_stale_lines(self) -> None:
        store = RecipeStore()
        key = RecipeKey("qx", "abcd1234")
        for ts in (100.0, 200.0, 300.0):
            store.record_success(
                key, Recipe(action="click", stable_id="next"), ts=ts,
            )
        # Add an unrelated active key for variety.
        other_key = RecipeKey("ps", "ffff0001")
        store.record_success(
            other_key, Recipe(action="fill", stable_id="email", value_template="x"),
            ts=400.0,
        )
        # And a stale tombstone for `key`.
        store.invalidate(key, ts=500.0)

        before_lines = sum(
            1
            for line in store.path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        )
        dropped = store.compact()
        after_lines = sum(
            1
            for line in store.path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        )
        # The store keeps ONLY the latest active per key. The stale
        # tombstone for `key` plus all earlier dupes for `key` go away.
        self.assertEqual(after_lines, 1)  # only `other_key` survives
        # `dropped` is the implementation's count of "input lines minus
        # unique keys". That includes the stale-tombstone whose key was
        # then dropped during the write step. So:
        #   before_lines = 5 (3 dupes for `key` + 1 other_key + 1 tomb)
        #   unique keys  = 2 (key, other_key)
        #   dropped      = before_lines - unique keys = 3
        # The actual file-line delta is 4 because the stale entry is
        # also dropped on write. The contract we promise the caller is
        # the dropped-vs-unique-keys delta, not the on-disk delta.
        self.assertEqual(dropped, before_lines - 2)
        # And the compacted store agrees: lookup misses on the stale key.
        self.assertIsNone(store.lookup(key))
        self.assertIsNotNone(store.lookup(other_key))

    def test_corrupt_lines_are_skipped(self) -> None:
        store = RecipeStore()
        key = RecipeKey("qx", "abcd1234")
        store.record_success(key, Recipe(action="click", stable_id="next"))
        # Append junk by hand.
        with open(store.path, "a", encoding="utf-8") as f:
            f.write("totally not json\n")
            f.write('{"key": {"provider": "qx"}, "recipe": {"action": "drag_drop"}}\n')
        # Lookup must still see the legit recipe.
        got = store.lookup(key)
        self.assertIsNotNone(got)
        self.assertEqual(got.stable_id, "next")


# ── RecipeKey.from_state ────────────────────────────────────────────────────


class TestRecipeKeyFromState(unittest.TestCase):
    def test_derives_provider_and_signature(self) -> None:
        s = _State(
            universal_elements=[_el("next", role="button", name="Next")],
            provider="qualtrics",
            survey_url="https://qx.test/p?t=1",
        )
        key = RecipeKey.from_state(s)
        self.assertEqual(key.provider, "qualtrics")
        self.assertEqual(len(key.page_signature), 16)

    def test_empty_provider_falls_back_to_unknown(self) -> None:
        s = _State(universal_elements=[_el("a")], provider="")
        key = RecipeKey.from_state(s)
        self.assertEqual(key.provider, "unknown")

    def test_same_state_yields_same_key(self) -> None:
        s1 = _State(
            universal_elements=[_el("a"), _el("b")],
            provider="qx",
            survey_url="https://x/p?t=1",
        )
        s2 = _State(
            universal_elements=[_el("b"), _el("a")],  # reordered
            provider="qx",
            survey_url="https://x/p?t=42",  # different querystring
        )
        self.assertEqual(RecipeKey.from_state(s1), RecipeKey.from_state(s2))


# ── should_consult_cache ────────────────────────────────────────────────────


class TestShouldConsultCache(unittest.TestCase):
    def setUp(self) -> None:
        # Make sure no previous test left STEALTH_RECIPE_CACHE around.
        self._old = os.environ.pop("STEALTH_RECIPE_CACHE", None)

    def tearDown(self) -> None:
        if self._old is None:
            os.environ.pop("STEALTH_RECIPE_CACHE", None)
        else:
            os.environ["STEALTH_RECIPE_CACHE"] = self._old

    def test_default_on(self) -> None:
        s = _State(universal_elements=[_el("a")])
        self.assertTrue(should_consult_cache(s))

    def test_disabled_via_env(self) -> None:
        os.environ["STEALTH_RECIPE_CACHE"] = "0"
        s = _State(universal_elements=[_el("a")])
        self.assertFalse(should_consult_cache(s))

    def test_skip_when_replay_already_attempted_this_iteration(self) -> None:
        """Avoid infinite loop: if a buggy recipe re-resolves to the
        same page we just acted on, do not consult again."""
        s = _State(
            universal_elements=[_el("a")],
            recipe_replay_attempted=True,
        )
        self.assertFalse(should_consult_cache(s))

    def test_skip_on_empty_snapshot(self) -> None:
        s = _State(universal_elements=[])
        self.assertFalse(should_consult_cache(s))

    def test_object_without_attributes_is_safe(self) -> None:
        """Duck-typing contract: a bare object should not crash; it
        defaults to no-cache because we cannot prove anything."""

        class Bare:
            pass

        self.assertFalse(should_consult_cache(Bare()))


if __name__ == "__main__":
    unittest.main()
