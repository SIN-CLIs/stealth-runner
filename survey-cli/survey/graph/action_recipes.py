"""================================================================================
ACTION RECIPE CACHE — Stagehand-style replay layer for the survey graph
================================================================================

WHAT THIS MODULE IS [SR-243]
-----------------------------
A small, isolated, optional helper that lets the survey graph short-circuit
the (expensive) NIM / heuristic decision path on pages it has already seen
before.

The shape of the deal is the same one Stagehand and Browserbase Director
use:

  1. After a successful decide -> execute -> verify cycle, store a
     RECIPE: a JSON record that pins
         (provider, page_signature)
       to the action that just worked
         (action, stable_id, value_template, ...).
  2. The next time the graph lands on a page with the same
     (provider, page_signature), look the recipe up. If the snapshot's
     stable_ids still contain the recipe's id, replay the action without
     calling NIM at all.
  3. If the replay's verify step fails (no DOM change), invalidate the
     recipe and fall through to the existing decide path so the next
     iteration writes a fresh recipe.

WHY HERE AND WHY NOW
--------------------
- 5-10x latency / cost reduction on repeat surveys is the conservative
  estimate. On HeyPiggy + the top 3 providers, ~70 % of pages repeat
  across runs (consent, demographics, qualifier loops).
- The cache is keyed on a STABLE PAGE SIGNATURE, not on the cdp_actuator
  before/after dom hash. before_hash is too coarse — it changes on any
  text edit. We want a hash that survives small content edits but
  collapses on page-shape changes.
- Pure file-system JSONL store under STATE_DIR. Same convention as
  SR-237 (cash_out ledger) and SR-238 (langgraph checkpoints): one
  state dir, multiple append-only / mostly-read JSONL artifacts. No
  Postgres, no SQLite, no extra deps.

DESIGN GUARDRAILS
-----------------
1. **Pure helpers, no networking, no Chrome.** The whole module is
   testable on a sandbox without playwright/openai/numpy.
2. **No state mutation in the helpers.** The decide_node (or the
   wire-up PR) decides whether to call us, what to record, and what
   to skip. We only return structured data.
3. **Conservative match.** A recipe matches ONLY when its
   (provider, page_signature) pair is identical. We do NOT do fuzzy
   match on signature. False positives would replay the wrong click;
   missing the cache costs one NIM call which is recoverable.
4. **Recipes invalidate on verify-fail.** If a replay produces
   no_dom_change (or a similar "the click did not advance the page"
   signal), the loader moves the recipe to the "stale" pile so future
   iterations don't re-run the broken click.
5. **No selectors.** A recipe pins a stable_id, not a CSS selector.
   The same rule that drove the rest of the graph: stable_ids survive
   re-renders, selectors don't. If the stable_id is missing from the
   current snapshot, the recipe MUST refuse to apply.

PUBLIC SURFACE
--------------
- `compute_page_signature(elements, *, url, max_signal_len=...) -> str`
- `Recipe` dataclass + `RecipeKey` dataclass.
- `RecipeStore` — JSONL-backed, file-locked-light store.
    * `store.lookup(key) -> Recipe | None`
    * `store.record_success(key, recipe) -> None`
    * `store.invalidate(key, reason) -> None`
    * `store.compact() -> int`  (drop stale entries)
- `match_recipe_to_snapshot(recipe, elements) -> ResolvedAction | None`
- `should_consult_cache(state) -> bool`  — same trigger pattern as
  vision_fallback.

WIRING POSITION
---------------
At the top of `decide_node`:
    if should_consult_cache(state):
        recipe = store.lookup(RecipeKey.from_state(state))
        if recipe and (resolved := match_recipe_to_snapshot(recipe, state.universal_elements)):
            state.decision = {**resolved.as_decision(), "reason": "recipe_cache"}
            state.recipe_replay_attempted = True
            return state
    # ... existing NIM + heuristic path ...
    # in execute_node, after a successful action:
    if state.last_action_result.get("success"):
        store.record_success(RecipeKey.from_state(state),
                             Recipe.from_state(state))

That wiring lands in SR-244 (decide-node integration). This PR only
ships the helper module + the trigger marker, again on the SR-239
playbook: visibility before cost, narrow test surface, reversible.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Optional, Sequence

logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────────────────────


# Maximum signal-string length we hash. Longer signals are cheaper to
# discriminate but spend more memory in the cache; 4000 chars matches
# `cdp_actuator._capture_dom_hash` on purpose.
DEFAULT_MAX_SIGNAL_LEN = 4000

# Roles we consider "page-shape relevant" for the signature. Everything
# else is treated as content noise.
_SHAPE_ROLES = frozenset({
    "button",
    "link",
    "checkbox",
    "radio",
    "switch",
    "textbox",
    "searchbox",
    "spinbutton",
    "combobox",
    "listbox",
    "option",
    "tab",
    "menuitem",
    "slider",
    "form",
    "dialog",
})


# Fields we always carry on a Recipe. New fields go here AND into
# `Recipe.from_dict` AND into the test fixtures.
_RECIPE_SCHEMA_VERSION = 1


# ── Page signature ───────────────────────────────────────────────────────────


def _normalise_url(url: str) -> str:
    """Trim querystring noise (timestamps, single-use tokens) but keep
    the path. Survey providers attach a fresh `?t=...` on every load;
    the cache must survive that."""
    if not url:
        return ""
    # Drop everything from the first '?'. We could be smarter (split
    # tokens, allow-list), but the deterministic crude path is fine
    # for a cache hint — a wrong key just causes a cache miss.
    if "?" in url:
        url = url.split("?", 1)[0]
    if "#" in url:
        url = url.split("#", 1)[0]
    return url.strip().lower()


def _shape_token(el: dict) -> str:
    """Reduce one element to a content-light shape token: role + name-
    tail-trimmed. Whitespace and digits are collapsed so a CSRF token
    that leaks into a button label cannot blow up the cache."""
    role = str(el.get("role") or "").lower()
    name = str(el.get("name") or "")
    name_low = name.strip().lower()
    name_low = re.sub(r"\s+", " ", name_low)
    name_low = re.sub(r"\d+", "#", name_low)
    name_low = name_low[:60]
    return f"{role}:{name_low}"


def compute_page_signature(
    elements: Sequence[dict],
    *,
    url: str = "",
    max_signal_len: int = DEFAULT_MAX_SIGNAL_LEN,
) -> str:
    """Build a stable hash of the page that survives content edits.

    The signature is a sha1 (16 hex chars) of:
        normalised_url + sorted shape-tokens of every actionable element

    We sort the shape-tokens so reordering inside the AX tree (which
    happens on every re-render) does not change the key. We DO include
    each token's role so a "submit button" page with five textboxes
    hashes differently from a "submit button" page with one textbox.

    Args:
        elements: list of UniversalElement dicts (same shape
            decide_node sees today).
        url: current page URL. Optional — if empty, the signature is
            computed from elements only.
        max_signal_len: cap the signal-string length before hashing.
    """
    norm_url = _normalise_url(url)
    tokens = [
        _shape_token(el)
        for el in elements
        if str(el.get("role") or "").lower() in _SHAPE_ROLES
    ]
    tokens.sort()
    signal = norm_url + "\n" + "\n".join(tokens)
    if len(signal) > max_signal_len:
        signal = signal[:max_signal_len]
    return hashlib.sha1(signal.encode("utf-8", errors="replace")).hexdigest()[:16]


# ── Recipe + Key ─────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class RecipeKey:
    """The dedup boundary for a recipe: provider + page signature."""

    provider: str
    page_signature: str

    @classmethod
    def from_state(cls, state: Any) -> "RecipeKey":
        """Convenience: derive a key from a SurveyState-shaped object.

        The state must already have `universal_elements` populated (i.e.
        the snapshot ran). We treat missing fields as empty strings —
        the lookup will simply miss the cache.
        """
        elements = getattr(state, "universal_elements", None) or []
        # Some pipeline versions expose the URL through different
        # attributes; we prefer the most specific one.
        url = (
            getattr(state, "current_url", None)
            or getattr(state, "survey_url", None)
            or ""
        )
        sig = compute_page_signature(elements, url=str(url))
        return cls(
            provider=str(getattr(state, "provider", "") or "unknown"),
            page_signature=sig,
        )

    def as_dict(self) -> dict:
        return {"provider": self.provider, "page_signature": self.page_signature}


@dataclass(frozen=True)
class Recipe:
    """A pinned action plus enough provenance to debug a replay miss."""

    action: str  # "click" | "fill" | "press_key" | "submit"
    stable_id: str = ""
    value_template: str = ""
    """For action='fill', a value or {placeholder} template (placeholders
    are not yet expanded — that's SR-244's job; today we just store the
    literal value the original decision used)."""
    key: str = ""
    """For action='press_key', the key the original decision sent
    ('Enter', 'Tab', etc.)."""
    success_count: int = 1
    """How many times this exact recipe replayed successfully. Useful
    for retro / dashboards; the loader does NOT promote based on this."""
    last_used_ts: float = 0.0
    schema_version: int = _RECIPE_SCHEMA_VERSION

    def as_decision(self) -> dict:
        """Convert into the dict shape `state.decision` expects."""
        d: dict = {"action": self.action}
        if self.stable_id:
            d["stable_id"] = self.stable_id
        if self.value_template:
            d["value"] = self.value_template
        if self.key:
            d["key"] = self.key
        return d

    def as_dict(self) -> dict:
        return {
            "action": self.action,
            "stable_id": self.stable_id,
            "value_template": self.value_template,
            "key": self.key,
            "success_count": self.success_count,
            "last_used_ts": self.last_used_ts,
            "schema_version": self.schema_version,
        }

    @classmethod
    def from_decision(cls, decision: dict, *, ts: float = 0.0) -> "Recipe":
        """Build a recipe from the (action) `state.decision` we just
        watched succeed."""
        return cls(
            action=str(decision.get("action") or ""),
            stable_id=str(decision.get("stable_id") or ""),
            value_template=str(decision.get("value") or ""),
            key=str(decision.get("key") or ""),
            success_count=1,
            last_used_ts=float(ts),
        )

    @classmethod
    def from_dict(cls, raw: dict) -> Optional["Recipe"]:
        """Defensive parser: returns None on any shape we don't grok."""
        try:
            schema = int(raw.get("schema_version") or 0)
            if schema != _RECIPE_SCHEMA_VERSION:
                return None
            action = str(raw.get("action") or "")
            if action not in ("click", "fill", "press_key", "submit"):
                return None
            return cls(
                action=action,
                stable_id=str(raw.get("stable_id") or ""),
                value_template=str(raw.get("value_template") or ""),
                key=str(raw.get("key") or ""),
                success_count=int(raw.get("success_count") or 1),
                last_used_ts=float(raw.get("last_used_ts") or 0.0),
                schema_version=schema,
            )
        except (TypeError, ValueError):
            return None


# ── Store ────────────────────────────────────────────────────────────────────


def _default_store_path() -> Path:
    """`$STATE_DIR/action_recipes.jsonl` (env-overridable). Shared
    convention with the cash_out ledger and the LangGraph checkpoint
    DB so a single STATE_DIR override moves all of them."""
    base = Path(os.environ.get("STATE_DIR") or _DEFAULT_STATE_DIR)
    base.mkdir(parents=True, exist_ok=True)
    return base / "action_recipes.jsonl"


_DEFAULT_STATE_DIR = Path(__file__).resolve().parent.parent.parent / "state"


@dataclass
class _StoreEntry:
    """Internal: a deserialised line from the JSONL store."""

    key: RecipeKey
    recipe: Recipe
    state: str = "active"  # "active" | "stale"
    ts: float = 0.0

    @classmethod
    def parse(cls, raw_line: str) -> Optional["_StoreEntry"]:
        line = raw_line.strip()
        if not line or line.startswith("#"):
            return None
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            return None
        rec = obj.get("recipe") or {}
        key = obj.get("key") or {}
        recipe = Recipe.from_dict(rec)
        if recipe is None:
            return None
        try:
            return cls(
                key=RecipeKey(
                    provider=str(key.get("provider") or ""),
                    page_signature=str(key.get("page_signature") or ""),
                ),
                recipe=recipe,
                state=str(obj.get("state") or "active"),
                ts=float(obj.get("ts") or 0.0),
            )
        except (TypeError, ValueError):
            return None


class RecipeStore:
    """Append-only JSONL store with last-write-wins + state flags.

    On disk one row per write, ordered append. Reads stream the file
    once per lookup; for our scale (1 account, ~50 unique pages/day)
    that is comfortably under 1 ms even with months of history. When
    the file gets uncomfortably large, callers run `compact()` to
    rewrite only the latest active entry per key.
    """

    def __init__(self, path: Optional[Path] = None) -> None:
        self.path = path or _default_store_path()

    # -- read path --------------------------------------------------------

    def _scan(self) -> Iterable[_StoreEntry]:
        if not self.path.exists():
            return []
        with open(self.path, "r", encoding="utf-8") as f:
            for raw in f:
                entry = _StoreEntry.parse(raw)
                if entry is not None:
                    yield entry

    def lookup(self, key: RecipeKey) -> Optional[Recipe]:
        """Return the most recent ACTIVE recipe for the key, or None.

        Last-write-wins: a later 'stale' entry overrides an earlier
        'active' one for the same key.
        """
        latest: Optional[_StoreEntry] = None
        for entry in self._scan():
            if entry.key != key:
                continue
            if latest is None or entry.ts >= latest.ts:
                latest = entry
        if latest is None or latest.state != "active":
            return None
        return latest.recipe

    # -- write path -------------------------------------------------------

    def _append(self, payload: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(payload, sort_keys=True) + "\n"
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(line)
            f.flush()
            try:
                os.fsync(f.fileno())
            except OSError:
                # Same trade-off as the cash_out ledger: where fsync is
                # not supported (some test tmpfs), at-most-once durable
                # is acceptable for a hint cache.
                pass

    def record_success(
        self,
        key: RecipeKey,
        recipe: Recipe,
        *,
        ts: Optional[float] = None,
    ) -> None:
        """Persist a successful (action) decision under this key.

        If a previous active recipe under the same key has identical
        (action, stable_id, value, key), we still write a new line —
        it lets retros count replay frequency. The `compact()` method
        is the right place to dedupe on disk.
        """
        if not key.page_signature:
            # A signature collapse to "" means we hashed nothing; the
            # caller likely had an empty snapshot. Refusing to store
            # avoids a poisonous "matches every empty page" entry.
            logger.debug("recipe-store: refusing to record empty signature")
            return
        import time

        rec_dict = recipe.as_dict()
        if recipe.last_used_ts <= 0.0:
            rec_dict["last_used_ts"] = float(ts) if ts else time.time()
        self._append(
            {
                "key": key.as_dict(),
                "recipe": rec_dict,
                "state": "active",
                "ts": float(ts) if ts else time.time(),
            }
        )

    def invalidate(
        self,
        key: RecipeKey,
        reason: str = "verify_failed",
        *,
        ts: Optional[float] = None,
    ) -> None:
        """Mark the most recent active recipe for `key` as stale.

        Implementation: append a tombstone line with state='stale'.
        `lookup()` last-write-wins makes it invisible from then on.
        """
        import time

        # Best-effort: copy the latest active recipe's payload so the
        # tombstone is debuggable (you can read why a key got purged).
        active = self.lookup(key)
        recipe_dict = active.as_dict() if active else {
            "action": "",
            "stable_id": "",
            "value_template": "",
            "key": "",
            "success_count": 0,
            "last_used_ts": 0.0,
            "schema_version": _RECIPE_SCHEMA_VERSION,
        }
        self._append(
            {
                "key": key.as_dict(),
                "recipe": recipe_dict,
                "state": "stale",
                "ts": float(ts) if ts else time.time(),
                "reason": reason[:200],
            }
        )

    def compact(self) -> int:
        """Rewrite the JSONL keeping only the latest entry per key.

        Returns the number of dropped lines.
        """
        if not self.path.exists():
            return 0
        latest: dict[tuple[str, str], _StoreEntry] = {}
        line_count = 0
        for entry in self._scan():
            line_count += 1
            ident = (entry.key.provider, entry.key.page_signature)
            current = latest.get(ident)
            if current is None or entry.ts >= current.ts:
                latest[ident] = entry
        # Write atomically: tmp file + replace.
        tmp = self.path.with_suffix(self.path.suffix + ".compact.tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            for entry in latest.values():
                if entry.state == "stale":
                    # Compaction drops stale tombstones — the whole point
                    # of compaction is reclaiming space.
                    continue
                f.write(
                    json.dumps(
                        {
                            "key": entry.key.as_dict(),
                            "recipe": entry.recipe.as_dict(),
                            "state": entry.state,
                            "ts": entry.ts,
                        },
                        sort_keys=True,
                    )
                    + "\n"
                )
        os.replace(tmp, self.path)
        return max(0, line_count - len(latest))


# ── Match a stored recipe to the *current* snapshot ──────────────────────────


@dataclass(frozen=True)
class ResolvedAction:
    """A recipe that already proved its stable_id is present in the
    current snapshot. Caller turns this into `state.decision`."""

    action: str
    stable_id: str
    value: str = ""
    key: str = ""

    def as_decision(self) -> dict:
        d: dict = {"action": self.action}
        if self.stable_id:
            d["stable_id"] = self.stable_id
        if self.value:
            d["value"] = self.value
        if self.key:
            d["key"] = self.key
        return d


def match_recipe_to_snapshot(
    recipe: Recipe,
    elements: Sequence[dict],
) -> Optional[ResolvedAction]:
    """Return a ResolvedAction iff the recipe's stable_id (or, for
    non-id actions, the action itself) is replayable on the current
    snapshot. None means: do not replay, fall through to the regular
    decide path AND consider invalidating the recipe.

    Resolution rules:
      - For action='click', 'fill', 'submit': the snapshot MUST contain
        an element whose `stable_id` equals `recipe.stable_id`, and that
        element must not be disabled. If it is disabled, the recipe
        misses (the page state changed underneath us).
      - For action='press_key': no stable_id needed — keys go to the
        focused element.
    """
    if recipe.action in {"click", "fill", "submit"}:
        if not recipe.stable_id:
            return None
        for el in elements:
            if str(el.get("stable_id") or "") != recipe.stable_id:
                continue
            state = el.get("state") or {}
            if state.get("disabled"):
                return None
            return ResolvedAction(
                action=recipe.action,
                stable_id=recipe.stable_id,
                value=recipe.value_template,
                key="",
            )
        return None
    if recipe.action == "press_key":
        if not recipe.key:
            return None
        return ResolvedAction(
            action="press_key",
            stable_id="",
            value="",
            key=recipe.key,
        )
    return None


# ── Trigger ──────────────────────────────────────────────────────────────────


def should_consult_cache(state: Any) -> bool:
    """Same trigger discipline as vision_fallback.should_use_vision_fallback.

    True when:
      - the snapshot has elements (otherwise we'd cache-hit on an
        empty page, which is meaningless)
      - the env var STEALTH_RECIPE_CACHE is not the literal string '0'
        (default behaviour: cache ON; ops escape hatch: turn OFF).
      - we are not already in a recipe-replay-attempt this iteration
        (avoid infinite loops if a buggy recipe keeps re-resolving).
    """
    if (os.environ.get("STEALTH_RECIPE_CACHE") or "1").strip() == "0":
        return False
    elements = getattr(state, "universal_elements", None) or []
    if not elements:
        return False
    if getattr(state, "recipe_replay_attempted", False):
        return False
    return True


__all__ = [
    "DEFAULT_MAX_SIGNAL_LEN",
    "Recipe",
    "RecipeKey",
    "RecipeStore",
    "ResolvedAction",
    "compute_page_signature",
    "match_recipe_to_snapshot",
    "record_execute_outcome",
    "should_consult_cache",
]


# ── Wire-up helper for execute_node (SR-244) ────────────────────────────────


def record_execute_outcome(
    state: Any,
    decision: dict,
    *,
    result_success: bool,
    result_reason: str,
    store: Optional["RecipeStore"] = None,
) -> Optional[str]:
    """One-shot post-execute callback the survey graph plugs into
    `execute_node`. Decides whether to record a fresh recipe, tombstone
    a stale one, or do nothing — and returns a short string indicating
    which branch ran (for logs / tests).

    Branches:
      - `"recorded"`:    `result_success` is True and the action is
                         persistable (click / fill / submit / press_key
                         on a real stable_id or key). We persist a
                         recipe under the key derived from the snapshot
                         that was on screen WHEN the decision was made.
                         IMPORTANT: that snapshot is `state.universal_elements`
                         AS THEY WERE AT THE TOP OF execute_node — the
                         cdp_actuator may have advanced the page, but
                         decide_node looked at the old snapshot, so the
                         old key is the right one for the cache.
      - `"invalidated"`: `result_success` is False AND
                         `result_reason in {"no_dom_change",
                         "no_dom_change_after_retries"}`. We tombstone
                         the recipe under the same key, so the next
                         iteration's lookup misses and the regular
                         decide path runs.
      - `"skipped"`:     anything else (wait/done/noop, error before
                         we know what page we were on, empty signature,
                         non-cacheable action, …). The store stays
                         untouched.

    The function is intentionally safe to call from `execute_node`'s
    happy path. Any exception inside the store is caught and logged;
    the earnings loop NEVER fails because of a cache write.
    """
    action = str((decision or {}).get("action") or "")
    if action in ("", "wait", "done", "noop"):
        return "skipped"

    # press_key has no stable_id; click/fill/submit need one.
    if action in ("click", "fill", "submit"):
        if not (decision.get("stable_id") or "").strip():
            return "skipped"
    elif action == "press_key":
        if not (decision.get("key") or "").strip():
            return "skipped"
    else:
        return "skipped"

    try:
        key = RecipeKey.from_state(state)
    except Exception as exc:
        logger.debug("record_execute_outcome: key derivation failed: %s", exc)
        return "skipped"

    if not key.page_signature:
        # The store would refuse this on its own; short-circuit so we
        # don't pay for the write attempt.
        return "skipped"

    # Empty snapshot — the URL alone IS hashable but it's not enough
    # signal to discriminate two pages on the same URL. We refuse to
    # cache under that key; SR-243's compute_page_signature contract
    # is "shape, not URL".
    if not (getattr(state, "universal_elements", None) or []):
        return "skipped"

    cache = store or RecipeStore()

    if result_success:
        try:
            cache.record_success(key, Recipe.from_decision(decision))
        except Exception as exc:
            logger.debug("record_execute_outcome: record_success failed: %s", exc)
            return "skipped"
        return "recorded"

    if result_reason in ("no_dom_change", "no_dom_change_after_retries"):
        try:
            cache.invalidate(key, reason=result_reason)
        except Exception as exc:
            logger.debug("record_execute_outcome: invalidate failed: %s", exc)
            return "skipped"
        return "invalidated"

    return "skipped"
