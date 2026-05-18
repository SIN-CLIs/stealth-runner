# Action recipe cache (SR-243)

> **Status:** Helper-only ship. Owner: Eng. Last reviewed: 2026-05-17.
> **Pairs with:** SR-237 (cash-out idempotency ledger), SR-238 (LangGraph SqliteSaver checkpointer), SR-239 (vision fallback), [`docs/PORTFOLIO.md`](./PORTFOLIO.md).

## Why this exists

On every survey iteration we currently pay for at least one NIM call (or, when the budget runs out, a heuristic walk). On repeat surveys ~70 % of pages are pages we have already solved correctly: consent banners, demographic tables, qualifier loops, "click Continue" pages. Paying for the same decision over and over is wasteful in latency, in tokens, and in error surface (every NIM call is a chance to pick the wrong radio).

Stagehand and Browserbase Director both close this gap with an action cache: pin the action that worked under a stable page key, replay it the next time. SR-243 ships that cache for the survey graph.

This PR ships **only the helpers and the trigger contract**. The wire-up into `decide_node` (look up the recipe before NIM, persist after a successful execute, invalidate on verify-fail) is the SR-244 PR. Same playbook as SR-239: helper now, observation next, full consumption when we have one week of telemetry.

## What "stable page key" means

```
RecipeKey = (provider, page_signature)
```

`page_signature` is sha1[:16] of:

- the URL with the querystring and fragment removed (survey providers attach single-use `?t=...` tokens; the cache must survive that)
- plus a sorted list of `role:name-tail-trimmed` tokens for every actionable element in the snapshot (button, radio, textbox, …) — content-light, digit-collapsed so a CSRF nonce in a label cannot blow up the key
- truncated at 4 000 characters before hashing

Result: the same page hashes to the same key across re-renders, across token changes, across element-order shuffling. Adding or removing a real form control changes the hash.

## Invariants the helpers enforce

The unit tests pin all of these. Read them as contract.

- Same input → same `page_signature` (deterministic).
- Reorder of elements → same signature.
- New `?t=...` querystring → same signature.
- Number leak in a button label (CSRF / nonce) → same signature.
- Role change on any element → DIFFERENT signature.
- Visible name change on a button → DIFFERENT signature.
- Disabled element → recipe MUST refuse to replay.
- Missing `stable_id` in current snapshot → recipe MUST refuse to replay.
- Empty signature is refused on write so a buggy snapshot can't poison "every empty page".
- Last-write-wins lookup; an `invalidate(key, reason="...")` tombstones the recipe and a fresh `record_success` re-activates it.
- Corrupt JSONL lines are skipped on read, never crash a lookup.

## Storage

Append-only JSONL at `$STATE_DIR/action_recipes.jsonl`. Same convention as the cash-out ledger and the LangGraph checkpoint DB so a single `STATE_DIR` override moves all three for tests / containerised deployments.

Each line is one entry:

```json
{"key": {"provider": "qualtrics", "page_signature": "37f3fb2b0945141b"},
 "recipe": {"action": "click", "stable_id": "qx-btn-next",
            "value_template": "", "key": "",
            "success_count": 1, "last_used_ts": 1779039910.16,
            "schema_version": 1},
 "state": "active", "ts": 1779039910.16}
```

`compact()` rewrites the file keeping only the latest active entry per key. Run it from a daily cron / `survey kill --maintenance` once we wire it up; the file is 1 line per page-touch, so we have weeks before it matters.

## How a replay flows (SR-244 wiring, not in this PR)

```
decide_node(state):
    if should_consult_cache(state):
        key = RecipeKey.from_state(state)
        recipe = store.lookup(key)
        if recipe and (resolved := match_recipe_to_snapshot(recipe, state.universal_elements)):
            state.decision = {**resolved.as_decision(), "reason": "recipe_cache"}
            state.recipe_replay_attempted = True
            return state
    # ... existing NIM + heuristic path lands here ...

execute_node(state):
    # ... act + verify ...
    if state.last_action_result.get("success"):
        store.record_success(RecipeKey.from_state(state),
                             Recipe.from_decision(state.decision))
    elif state.last_action_result.get("reason") == "no_dom_change":
        store.invalidate(RecipeKey.from_state(state),
                         reason="verify_failed")
```

That's it. ~12 lines. No changes to the NIM client, no changes to `cdp_actuator`, no Chrome-level changes.

## Operational controls

| control | default | purpose |
|---|---|---|
| `STEALTH_RECIPE_CACHE` env | `1` (on) | set to `"0"` to disable the cache for one daemon launch — emergency escape hatch |
| `state.recipe_replay_attempted` | `False` | flipped True after the cache picks a decision so a faulty recipe cannot loop |
| `STATE_DIR` env | `<survey-cli>/state/` | move all on-disk state (ledger + checkpoints + recipes) together |

## What this is NOT

- **Not a learning system.** A recipe pins one specific replayable answer. We don't infer "always pick the second radio" from this data; we just record what worked and replay it when we see the same page.
- **Not a substitute for the trajectory eval.** SR-240 still gates the build on graph behaviour. The cache makes a happy path cheaper, not less correct.
- **Not enabled in `decide_node` yet.** This PR is helpers + tests + docs only. The wire-up lands in SR-244 once the helpers have one week of unit-test runs in CI.

## Why we ship the helper before the wiring

Three reasons in priority order:

1. **Reversibility.** The wiring touches `decide_node`, the most-traded surface in the graph. Splitting the change keeps the wire-up PR's diff to ~12 lines, reviewable in five minutes.
2. **Test surface stays narrow.** The helpers are pure functions. The wire-up PR's tests can focus on the integration boundary (does the cache actually short-circuit NIM? does invalidation actually fire on verify-fail?) without re-testing JSONL parsing.
3. **No production exposure.** Even with this PR merged, the cache is silent: nothing reads or writes `action_recipes.jsonl` until SR-244 lands. If a reviewer spots an invariant bug here, the rollback is a clean revert with zero data on disk.
