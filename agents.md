# agents.md — stealth-runner brain

> **Purpose.** Single source of truth for any agent (human or LLM) opening
> this repo. If you only read one file, read this one. It tells you *what
> we are building*, *in what order*, *with what blast radius rules*, and
> *where to look* for the actual code.
>
> Treat sections marked **Doctrine** as non-negotiable. Phase deliverables
> can shift; doctrine does not.

---

## 0. TL;DR — what stealth-runner is

A reliability layer around browser-driven survey automation. The agent
visits a panel survey, parses questions, generates plausible answers, fills
them in, **verifies they actually landed**, submits, and persists state to
SQLite. Stealth-aware: no fingerprintable Playwright defaults, no banned
ChromeDriver patterns (see `banned.md`).

LangGraph orchestrates the state machine. The core graph lives in
`survey-cli/survey/daemon/survey_agent_graph.py`. Every other module hangs
off that graph as a node or as a reliability primitive consumed by nodes.

---

## 1. Meta-plan — Issue #172

Tracked as the long-term roadmap. Five phases, each gated on the previous
one being green in CI.

| Phase | Issue | Scope                                                   | Status |
| ----- | ----- | ------------------------------------------------------- | ------ |
| 1     | #167  | Post-action verifier node                               | this PR |
| 2     | #168  | Idempotent skip-on-stable-hash (uses #167 page_hash)    | next   |
| 3     | #169  | DLQ wiring on terminal verifier failure                 | after #168 |
| 4     | #170  | Contradiction store + answer rewriter                   | after #169 |
| 5     | #171  | End-to-end golden replay harness                        | last   |

The dependency is real, not cosmetic. Phase 2 *cannot* skip work without
the hash-stable snapshot Phase 1 introduces. Phase 3 needs a verifier
result object to push into the DLQ. Phase 4 needs verifier history to
detect contradictions. Phase 5 needs all of the above.

**Do not** start Phase N until Phase N-1 has merged to `main` and CI is
green for two consecutive runs.

---

## 2. Phase 1 — Post-action verifier (SR-167)

### Why it exists

Before this phase, `_answer` → `_submit` was a blind handoff. If a click
landed on a stale selector, if a dropdown snapped back, if a slider didn't
fire `change`, the survey moved on with garbage and the session corrupted.
We had no way to know whether an answer actually took without re-parsing
the next page and reverse-engineering the result — which is too late.

### Architecture

```
parse → check_status → answer → verify → submit
                                  │
                                  ├── retry → answer   (≤ MAX_VERIFY_ATTEMPTS)
                                  └── fail  → handle_error
```

Three new building blocks:

* **`survey/snapshot_v2.py`** — deterministic per-question DOM-state capture.
  One JS round-trip; returns sorted, normalized control list grouped by
  `data-question-id`. Each frame gets a `subtree_hash`; the whole page
  gets a `page_hash`. Hashes are SHA-256 of canonical JSON, so two
  identical states produce byte-identical hashes regardless of DOM order.

* **`survey/daemon/verifier.py`** — `verify_action(questions, answers,
  snapshot_before, snapshot_after, attempt)` returns a `VerificationResult`.
  Dispatches per `QuestionType` to small pure verifiers; returns a list of
  `Mismatch` objects (`reason ∈ {not_checked, wrong_value, wrong_set,
  text_mismatch, out_of_range, missing_control}`). Also emits
  `dom_unstable: bool` (snapshot_before == snapshot_after despite attempted
  answers → action never landed) and `unchanged_qids` for Phase 2.

* **`SurveyAgentGraph._verify` node** + extended `AgentState` (TypedDict
  with `total=False` for additive fields: `snapshot_before`,
  `last_verification`, `verify_attempts`).

### Question-type matrix (initial coverage)

| Type        | Read from DOM                                | Compare semantics |
| ----------- | -------------------------------------------- | ----------------- |
| RADIO       | `:checked` value in `input[name=qid]`        | `answer.value` ∈ checked |
| CHECKBOX    | set of `:checked` values                     | `set(expected) == set(actual)` |
| DROPDOWN    | `select.value` / `selectedOptions[0]`        | string equal |
| OPEN_TEXT   | `input.value` / `textarea.value`             | case-insens. equal, or `actual.startswith(expected)` |
| SLIDER      | `input[type=range].value` or `aria-valuenow` | `float(actual) == float(expected)` |
| NUMBER      | `input[type=number].value`                   | `float(actual) == float(expected)` |
| (others)    | frame must exist; value-compare deferred     | Phase 2 / open |

Adding a new type means *one* function in `verifier.py` and *one* entry in
the `_VERIFIERS` table. No graph changes.

### Retry policy

`MAX_VERIFY_ATTEMPTS = 2` (i.e., 1 initial fill + 1 retry). Two attempts
balances "slow-rendering UI gets a second chance" against "we're in a real
selector-drift bug and re-filling won't help." Tunable via constant in
`survey_agent_graph.py`; do not parameterize unless a real survey class
needs it.

On exhaustion: `_route_after_verify` writes a structured `state["error"]`
(truncated mismatch list + `dom_unstable` flag), routes to `handle_error`,
and `_handle_error` persists the failed session to SQLite. **DLQ
integration is Phase 3 (#169)**, not this PR.

### Out of scope (defer)

* Visual / pixel diff verification — not needed; control state is enough.
* Reading from `CompactSnapshot` — different shape, different purpose,
  keep them parallel.
* Adaptive retry counts per question type — premature.
* Recording verifier traces to disk for replay — that's Phase 5 (#171).

---

## 3. Phase 2 — Idempotent skip-on-stable-hash (#168)

Once `snapshot_v2.page_hash` is available, `_parse` and `_answer` become
skippable: if `page_hash` matches a hash we've already processed in this
session, we know the DOM didn't move and re-running fill is wasted work
(plus risk of double-submitting). Phase 2 adds:

* A per-session ring of `(page_hash, decision)` tuples.
* `_route_after_check` consults the ring; on a stable repeat it routes to
  `submit` directly (re-trigger the next button) rather than re-answering.
* Verifier's `unchanged_qids` becomes the unit of skip: answers whose
  subtree didn't shift on retry are not re-filled.

Touch points: `survey_agent_graph.py` only. No new modules.

---

## 4. Phase 3 — DLQ on terminal verifier failure (#169)

`survey/reliability/dlq.py` already exists. Phase 3 wires
`_route_after_verify`'s exhaustion path to push a structured record
(`survey_id`, `current_page`, full `last_verification` dict, sanitized
`html_content` slice) into the DLQ before routing to `handle_error`.
Schema change to the DLQ table is allowed; add a migration.

---

## 5. Phase 4 — Contradiction store + answer rewriter (#170)

`survey/reliability/contradiction.py` exists. Phase 4 makes the answer
engine *read* from it: when the verifier rejects a value, the rejected
`(question_signature, value)` pair is logged to the contradiction store,
and the answer engine's next generation for the same signature *avoids*
that value. Closes the loop between "the verifier saw it didn't work" and
"the agent learns not to try it again."

---

## 6. Phase 5 — Golden replay harness (#171)

Record every `(parse_html, answer_value, verify_result)` triple from real
sessions into fixture JSONL. CI replays them through the graph with a
mock browser driver. New verifier strategies must produce identical
`VerificationResult` shape on the recorded inputs or the build fails. This
is what catches regressions when someone "improves" a verifier function.

---

## 7. Doctrine — non-negotiable rules

### D-1. Path doctrine

* New question-level reliability code lives under
  `survey-cli/survey/reliability/`. The `__init__.py` curates the public
  surface; everything else is an implementation file.
* New graph-adjacent code lives under `survey-cli/survey/daemon/`.
  `verifier.py` is correctly there because it depends on
  `survey_parser` / `answer_engine` and is only invoked from the graph.
* Pure-DOM utilities with no parser/engine deps live one level up at
  `survey-cli/survey/` (e.g., `snapshot.py`, `snapshot_v2.py`,
  `accessibility.py`).
* **Never** put graph nodes outside `survey_agent_graph.py`. The graph is
  the contract; nodes are methods.

### D-2. State shape doctrine

`AgentState` is a `TypedDict` of primitives (or dicts of primitives). It
must remain JSON-serializable for SQLite persistence and replay. No
dataclasses, no Pydantic models, no `datetime` objects. If a node needs a
richer type, it constructs it transiently inside the node and serializes
back before returning.

New `AgentState` fields **must** be added with `total=False` semantics so
older sessions in SQLite still load. Backward-compat reads use `state.get(key, default)`,
never direct subscript.

### D-3. Verification doctrine

* A verifier is *pure*. It takes a snapshot and an expected answer; it
  returns a `Mismatch | None`. It does not touch the browser, does not
  read state, does not log to disk.
* A verifier failure is **never** a hard exception. Return a `Mismatch`,
  let the graph node decide.
* `dom_unstable` is a stronger signal than `mismatches`. If both are set,
  treat as unstable first (the page literally didn't move; mismatch detail
  is noise).

### D-4. Banned methods (mirrors `banned.md`)

* `playstealth launch`
* `webauto-nodriver` — absolutely banned
* `cua-driver click --element-index N` (raw index → unstable across renders)
* `--remote-allow-origins=*` without quotes
* `/tmp/heypiggy-bot` as a fixed profile directory
* Hard-coded PIDs anywhere
* `pkill -f "Google Chrome"` / `killall Google Chrome`
* `skylight-cli click --element-index`

Reviewers reject PRs containing any of these on sight.

### D-5. Test doctrine

* Every new verifier strategy ships with at least one happy-path test and
  one mismatch test.
* Tests use synthetic control dicts via `snapshot_v2.from_controls()`. No
  real browser, no Playwright fixtures. The verifier is pure; the test
  surface should be too.
* DOM-stability tests must cover both the "page didn't move" (dom_unstable
  = True) and "page moved partially" (unchanged_qids populated) cases.
* `pytest -q survey-cli/tests/test_verifier.py
  survey-cli/tests/test_snapshot_v2.py` must stay green on every commit.

### D-6. Token / secret hygiene

* Never commit a `ghp_*`, `slack_*`, `xoxb-*`, or panel-API token.
* PR descriptions never quote a secret value, even redacted.
* The `agents/` directory (sandbox-only) is `.gitignore`'d.

---

## 8. Repo layout (cheat sheet)

```
survey-cli/
├── pyproject.toml
├── survey/
│   ├── __init__.py
│   ├── snapshot.py             # CompactSnapshot — token-efficient DOM dump for LLMs
│   ├── snapshot_v2.py          # SnapshotV2 — per-question state for verifier  ← #167
│   ├── accessibility.py
│   ├── scanner.py
│   ├── reliability/
│   │   ├── __init__.py
│   │   ├── retry_policy.py
│   │   ├── dlq.py              # Phase 3 (#169) wires verifier failures here
│   │   └── contradiction.py    # Phase 4 (#170) reads/writes here
│   └── daemon/
│       ├── browser_driver.py
│       ├── survey_parser.py
│       ├── answer_engine.py
│       ├── captcha_solver.py
│       ├── verifier.py         # post-action verifier  ← #167
│       └── survey_agent_graph.py   # LangGraph state machine; verify node lives here
└── tests/
    ├── test_reliability.py
    ├── test_snapshot_v2.py     # ← #167
    ├── test_verifier.py        # ← #167
    └── ...
```

---

## 9. How to add a new question type to the verifier

1. Add the type to `QuestionType` in `survey_parser.py` (or confirm it
   already exists).
2. Write a `_verify_<type>(q, a, frame) -> Mismatch | None` in
   `survey/daemon/verifier.py`.
3. Register it in `_VERIFIERS = { QuestionType.X.value: _verify_x, ... }`.
4. Add a `_<type>_controls(...)` helper + one happy-path and one
   mismatch test in `tests/test_verifier.py`.
5. If the type needs new DOM fields, extend `_SNAPSHOT_JS` in
   `snapshot_v2.py` and add a `test_snapshot_v2.py` assertion that the
   field survives the round-trip.

Total surface for a new type: ~30 lines verifier + ~20 lines tests.

---

## 10. CI gate (manual until #171 lands)

Before merging anything touching the verifier or the graph:

```bash
cd survey-cli
pytest -q tests/test_verifier.py tests/test_snapshot_v2.py tests/test_reliability.py
ruff check survey/
```

All three must pass. The graph file has `# ruff: noqa: E501` at the top
for selector / JS strings; do not strip it.

---

*Last edited as part of SR-167. Update this file in the same PR whenever
the phase boundaries shift or doctrine changes.*
