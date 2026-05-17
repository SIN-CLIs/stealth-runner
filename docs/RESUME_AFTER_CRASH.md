# Resume after crash — operator guide

> **Status:** Production. Owner: Eng. Last reviewed: 2026-05-17.
> **Pairs with:** [`docs/BRANCH_PROTECTION.md`](./BRANCH_PROTECTION.md), SR-237 (cash_out idempotency ledger), SR-238 (this file).

## What this gives you

When the survey daemon crashes mid-run (Chrome dies, host loses power, OOM-killer fires, anyone hits Ctrl-C in the middle of a NEMO loop), you used to lose everything: the survey was abandoned, the next launch started a fresh `SurveyState`, and any partial cash-out logic could fire twice on retry.

After SR-238 + SR-237:

1. **LangGraph SqliteSaver checkpointer** writes a full `SurveyState` snapshot after every superstep into `$STATE_DIR/langgraph_checkpoints.db`, keyed by a deterministic `thread_id`.
2. **Idempotency ledger** for cash-out (`$STATE_DIR/cash_out_ledger.jsonl`) makes the resume operation safe even if the crash happened between "click Auszahlung" and "log success".

Together these mean: **kill -9 the daemon mid-survey, restart, and it resumes from the last completed node without paying out twice.**

## thread_id contract

```
thread_id = f"{provider}:{survey_id}:{attempt}"
```

Examples:

| state | thread_id |
|---|---|
| `provider="purespectrum", survey_id="67064749", attempt=0` | `purespectrum:67064749:0` |
| same, second clean attempt after a fatal failure | `purespectrum:67064749:1` |
| different provider, same numeric id | `qualtrics:67064749:0` |

`attempt` is normally 0. Bump it only when you want a clean run (no resume) of a survey that already has a checkpointed thread. The provider prefix exists because two providers can in principle hand out the same numeric survey id.

## How to resume

Resume is **automatic** — there is no "resume" command. The daemon's normal entry points (`survey_cli_entry._run_survey_via_graph`, `run_survey_protected`) build the same `thread_id` from `(provider, survey_id, attempt)`, and LangGraph picks up the matching checkpoint on its own.

What you control:

- `STATE_DIR` env var → where the SQLite file lives (default: `survey-cli/state/`).
- `with_checkpoint=False` → opt out of checkpointing (tests; absolute last resort in prod).
- explicit `checkpointer=...` → inject a different saver (e.g. PostgresSaver in multi-account fleets).

## Manual operator interventions

### Inspect current threads

```bash
sqlite3 "$STATE_DIR/langgraph_checkpoints.db" \
  "SELECT thread_id, MAX(checkpoint_id) FROM checkpoints GROUP BY thread_id"
```

### Force a fresh attempt of an in-flight survey

Restart the daemon with `attempt=1` instead of 0 for that one survey id. This creates a *new* thread_id; the old checkpoints are kept on disk for forensics until you delete them by hand.

### Rotate the checkpoint DB

Once a quarter, archive and re-init:

```bash
mv "$STATE_DIR/langgraph_checkpoints.db" \
   "$STATE_DIR/archive/langgraph_checkpoints-$(date +%Y%m%d).db"
```

The next daemon launch creates a fresh DB. Surveys still in-flight at the time of rotation lose their resume points; finish them before rotating.

## Sandbox / lint hosts without `langgraph[sqlite]`

`create_sqlite_checkpointer()` returns `None` when the SqliteSaver class cannot be imported. `create_graph()` falls back to compiling without a checkpointer — every behaviour stays identical to the pre-SR-238 path. No exceptions, no guard flags.

In production, install the extra:

```bash
pip install -U 'langgraph[sqlite]>=0.2'
```

The daemon log will say `langgraph checkpointer: sqlite at /…/langgraph_checkpoints.db` on startup when the extra is present.

## Why this is enough for our scale

- 1 account, ≤10 surveys/day, ≤1 cash-out/day. SQLite is plenty.
- Append-only JSONL ledger for cash-out + per-superstep checkpoint snapshot for everything else gives at-least-once durability without a Postgres dependency.
- When we move to ≥5 parallel accounts (Welle 3), swap `SqliteSaver` for `PostgresSaver` via the `checkpointer=...` argument; nothing else has to change.

## What this is NOT

- **Not full durable execution** — LangGraph checkpoints save state; they do not retry failed side effects automatically. That's the cash-out ledger's job, and any *new* side effect we add must get its own idempotency story (see `docs/BRANCH_PROTECTION.md` rule about Definition of Done).
- **Not a replacement for backups.** The DB is convenience, not source of truth for paid-out euros — `earnings-*.jsonl` is.
