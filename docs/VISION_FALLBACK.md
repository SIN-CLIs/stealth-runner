# Vision-fallback perception layer (SR-239)

> **Status:** Trigger-only, observation mode. Owner: Eng. Last reviewed: 2026-05-17.
> **Pairs with:** SR-237 (cash-out idempotency), SR-238 (LangGraph SqliteSaver).

## Why this exists

The DOM-only `decide_node` is great for ~70 % of survey pages (forms with explicit `<input>`, `<select>`, `<button>` semantics). It loses on:

- Shadow-DOM 3+ layers deep (Lit, Shoelace, vendor component libraries).
- Canvas-rendered controls (signature pads, hotspot questions, drawing-based forms).
- Pages where the DOM is identical between two states but the visual content changed (animated reveal, A/B test).

WebVoyager (89 % completion) and Skyvern (86 %) close this gap with a hybrid perception layer: DOM first, vision as a fallback. SR-239 adds the same lever to stealth-runner.

This PR ships **only the trigger and the helper library**. The actual VLM call (Qwen2.5-VL via `survey/captcha/nim_secondary_solver.py`) is wired up in a follow-up PR so we can verify the trigger fires on the right pages in production *before* paying for screenshots and tokens.

## How it triggers

```
no_dom_change_count >= 1   AND   the DOM-only decide path produced no
                                  click candidate (decision.action == "wait"
                                  with reason "no_candidate_found")
```

Both conditions must be true. Threshold = 1 because the captcha node already triggers at 2 — vision picks up cases where the captcha router decided "this isn't a captcha" but the page still won't move.

When the trigger fires, `decide_node` sets:

- `state.vision_fallback_requested = True`
- `state.vision_fallback_reason = "no_dom_change=…, dom_decision=wait"`

A future PR will read those flags in `execute_node` (or a new node before `execute`) to:

1. Capture a screenshot via CDP `Page.captureScreenshot`.
2. Build a Set-of-Mark overlay using `vision_fallback.build_set_of_mark(state.universal_elements)`.
3. Send screenshot + overlay to Qwen2.5-VL with the default prompt from `vision_fallback.DEFAULT_PROMPT`.
4. Parse the response with `vision_fallback.parse_vlm_response(raw, plan)`.
5. Convert the resulting `VisionDecision` into a `state.decision` (either `click stable_id=...` or `click_at(x, y)`).

## Helpers shipped now

`survey/graph/vision_fallback.py` exposes:

| Helper | Purpose |
|---|---|
| `should_use_vision_fallback(state)` | Pure trigger logic. Reuses the same conditions as the decide-node hook. |
| `build_set_of_mark(elements, viewport, max_marks, avoid_stable_id)` | Picks at most 25 actionable elements, drops disabled / off-screen / non-actionable roles, assigns sequential mark ids 1..N. |
| `parse_vlm_response(raw, plan)` | Best-effort JSON / regex parser. Returns a `VisionDecision` with either `stable_id` (mark mapped back) or `coords` (off-DOM canvas hit). Discards hallucinated marks and out-of-viewport coordinates. |
| `run_vision_fallback(backend, screenshot_b64, plan)` | Pure orchestration that drives any `VisionBackend` protocol-compatible client. Tests pass a deterministic stub; production passes the Qwen2.5-VL client. |

## What is NOT in this PR

- No screenshot capture wiring.
- No actual VLM HTTP call.
- No `execute_node` consumption of the flag.
- No CI eval gate (that comes with SR-240).

The trigger is **observation-only**. Daemon logs already print `[decide] vision-fallback TRIGGERED ...` when the conditions match, so we can prove on production traffic that the trigger fires on the right pages before we pay for the upstream model.

## Operator dashboard

After merge, watch the daemon logs for:

```
[decide] vision-fallback TRIGGERED (no_dom_change=2, action=wait)
```

If you see it firing on pages that *should* have a clean DOM target (i.e. false positives), open a follow-up issue with the survey id and the snapshot — the threshold or the `is_actionable` filter probably needs tuning before we wire in the VLM call and start paying for it.

## Why we ship the trigger separately

Three reasons in priority order:

1. **Visibility before cost.** Once the VLM is wired in, every false-positive trigger costs a Qwen2.5-VL invocation. Shipping the trigger alone for one week of production traffic shows us how often it fires on real pages and on which providers.
2. **Reversible.** If the trigger turns out to be wrong (fires too often, fires never, fires on the wrong pages), the rollback is one revert of this PR. After wiring the VLM call, rolling back is harder because retraining the operator dashboard takes time.
3. **Test surface stays narrow.** The whole `vision_fallback.py` module is pure functions plus a `Protocol` seam — fully unit-testable without Chrome or NIM. The wire-up PR can focus its tests on the integration boundary (CDP screenshot path, real VLM call, retry logic) without re-testing helper logic.
