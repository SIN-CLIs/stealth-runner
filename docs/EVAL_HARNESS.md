# Trajectory eval harness (SR-240)

> **Status:** Production. Owner: Eng. Last reviewed: 2026-05-17.
> **Pairs with:** `survey/reliability/trajectory_judge.py`, `evals/trajectory/run_eval.py`, `.github/workflows/ci.yml`.

## Why this exists

Without a behaviour-level regression seatbelt, every PR can change the survey graph in a way that looks fine in unit tests but degrades the actual running flow — more retries per page, shaky no-DOM-change handling, qualification blocks slipping through, mis-detected completion outcomes. We had no signal for that until SR-240.

The harness now runs on every PR through `.github/workflows/ci.yml`. It loads a frozen JSONL golden set of trajectories, drives them through `TrajectoryJudge` with a deterministic rule-based backend, aggregates the four canonical scores, and fails the build when the aggregate mean drops below the threshold.

## How it gates a PR

```
.github/workflows/ci.yml
└── job: test
    ├── ... (lint, mypy, pytest, match_field eval)
    └── Run trajectory eval harness (SR-240)
        └── python -m evals.trajectory.run_eval
              --threshold 0.65
              --report evals/trajectory/last-report.json
              --exit-non-zero-on-threshold-miss
```

`--exit-non-zero-on-threshold-miss` is the default; an explicit `--no-exit-non-zero-on-threshold-miss` flag exists for ad-hoc local exploration but is forbidden in CI.

## What the four scores mean

The Judge backend in CI is `RuleBasedJudgeBackend`, deterministic and offline. Its scores correlate with the four dimensions the real LLM Judge is trained on:

| score | rises when | drops when |
|---|---|---|
| compliance | every decide step succeeds, no `human_delegate` | failed clicks, delegated escalations |
| efficiency | one click / page, no `attempts > 1` | retries, `no_dom_change` events |
| accuracy | trail's final outcome matches `expected_outcome`; no qualification-block events | mismatch, qualif-block telemetry on the trail |
| coherence | iteration numbers monotonic, terminal node is `detect_completion` or `human_delegate` | non-monotonic iters, weird terminal node |

Aggregate threshold = mean of all four across all golden trajectories. The bundled 10 trajectories produce ~0.98 today; threshold 0.65 sits comfortably in the regression-detect band without flapping on small wording changes.

## When and how to update the golden set

The golden file at `survey-cli/evals/trajectory/trajectories.golden.jsonl` is **frozen**. Updating it is a deliberate act:

1. Open a separate PR titled `chore(eval): update golden trajectories — <reason>`.
2. The PR body MUST explain (a) which trajectories changed, (b) why the new shape is now expected, (c) what scores the new shape produces. Snippet from the run output is fine.
3. A reviewer signs off ONLY when the new scores are still above the threshold.
4. Same-PR-as-feature updates are forbidden — features cannot ship their own seatbelt.

The format is one JSON record per line:

```json
{
  "id": "qualtrics-clean-1",
  "provider": "qualtrics",
  "expected_outcome": "completed",
  "trajectory": [ <step records>, ... ]
}
```

A step record is whatever the survey graph emits today — `node`, `stable_id`, `action`, `success`, `no_dom_change`, `iteration`, plus optional fields like `attempts`, `outcome`, `event`. The harness is tolerant of extra fields; the regression seatbelt is on the SHAPE of the trajectory, not on string equality.

## Running locally

From `survey-cli/`:

```bash
# Default (mock backend, fail on threshold miss):
PYTHONPATH=. python -m evals.trajectory.run_eval

# Strict per-trajectory gate as well:
PYTHONPATH=. python -m evals.trajectory.run_eval --per-trajectory --per-trajectory-threshold 0.6

# Tune the threshold up to feel where regressions would fire:
PYTHONPATH=. python -m evals.trajectory.run_eval --threshold 0.95
```

The report is written to `evals/trajectory/last-report.json` for retro / dashboards.

## What is NOT in this harness (yet)

- **Live LLM Judge.** The `--live` flag exists but is rejected with an explanatory error until SR-241 lands the real `gpt-4o-mini`-class judge. The reason: gating PRs on a frontier model is non-deterministic, costs tokens, and turns vendor outages into red builds. We use the live judge in `nightly-e2e.yml` — a separate workflow on a schedule.
- **Real Chrome trajectories.** Today's golden set is hand-curated to mirror the shape that the survey graph produces. SR-242 will add a `record-trajectory` mode to the daemon that captures real runs into the same JSONL format, with PII scrubbing.

## Failure modes you might see

| symptom | likely cause |
|---|---|
| `JudgeParseError` in CI logs | rule-based backend returned malformed JSON — programming error, fix `_score_trajectory` |
| aggregate mean dropped below 0.65 | the survey graph started producing more retries / failed clicks; investigate the diff that landed |
| per-trajectory violation list non-empty (when `--per-trajectory` is on) | one provider's trajectory regressed; the report names the record id |
| `golden file not found` (exit 2) | mis-rooted CI step; `cd survey-cli` must precede `python -m evals.trajectory.run_eval` |

## Why a mock backend is the right call for CI

We discussed making the gate a real LLM call. Three reasons it stays mocked:

1. **Determinism.** Every PR re-runs the same trajectories; identical input → identical output → identical pass/fail signal. A frontier-LLM gate flickers on prompt-cache misses.
2. **Cost.** 10 trajectories × 4 score dimensions × every PR × every reviewer-pushed fixup = thousands of LLM calls per week of active development. The deterministic mock costs zero.
3. **Test surface.** Unit tests can drive the same `_score_trajectory` function the CI gate uses. Confidence is high that the gate is not a black box.

The trade-off is that we are gating on the *mock's* opinion, not the *real Judge's* opinion. The mock's heuristics are explicit and reviewable; if a future reviewer thinks they relax things in the wrong direction, the answer is to ship a follow-up PR adjusting the rule, not to swap in the real LLM.
