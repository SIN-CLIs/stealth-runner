# SR-152 — Reliability Hardening: DLQ + Retry Policy + Persona Contradiction Detection

## Context

`survey_daemon.py` runs surveys in a loop. When something breaks:
- Hard error → log, move on to next survey
- Soft error (transient network) → log, move on

There is **no retry**, **no dead-letter queue**, **no alerting**. Production-quality 24/7 operation requires all three. Additionally, `AnswerEngine` stores answers in SQLite but doesn't actively scan for cross-panel contradictions — a single persona might say "age 35" on Toluna and "age 28" on Lucid in the same week, getting flagged as fraud.

## Goal

Add 3 reliability primitives that work together:

1. **Retry policy** — exponential backoff with classified retryability (transient vs permanent)
2. **Dead-Letter Queue** — failed surveys after N retries land in a JSONL DLQ for human review
3. **Persona contradiction detector** — scans answer-history SQLite for inconsistencies and flags them before the next answer is given

Plus optional **webhook alerting** for DLQ-pushed events (Slack/Discord/Generic webhook).

## Files

### NEW (5)
- `survey-cli/survey/reliability/retry_policy.py` — `RetryPolicy.run(coro, max_attempts, classify_fn)`
- `survey-cli/survey/reliability/dlq.py` — `DLQ.push(survey, error, context)` + JSONL persistence
- `survey-cli/survey/reliability/contradiction.py` — `ContradictionDetector.scan(persona_id) -> list[Contradiction]`
- `survey-cli/survey/reliability/__init__.py` — package marker, exports
- `survey-cli/tests/test_reliability.py` — 22+ tests

### MODIFY (3)
- `survey-cli/survey/daemon/survey_daemon.py`
  - Wrap survey-run loop in `RetryPolicy`
  - On final failure, push to `DLQ`
- `survey-cli/survey/daemon/answer_engine.py`
  - Before generating an answer for a persona-identity question (age, gender, income, education), call `ContradictionDetector.check()` and pin the answer to the most-frequent prior answer
- `survey-cli/survey/daemon/cli.py`
  - Add `dlq-list` (list pending DLQ items)
  - Add `dlq-replay <id>` (retry a single DLQ item)
  - Add `contradiction-scan <persona_id>` (one-shot scan for a persona)

## Retry Policy

```python
class Retryability(str, Enum):
    TRANSIENT = "transient"   # retry with backoff
    PERMANENT = "permanent"   # do not retry, push to DLQ
    FATAL = "fatal"           # do not retry, do not DLQ, halt
```

Classification rules (built-in):
- `TRANSIENT`: `TimeoutError`, `ConnectionError`, `aiohttp.ClientError`, HTTP 5xx, "service unavailable"
- `PERMANENT`: HTTP 4xx (except 408/429), "account banned", "ip blocked"
- `FATAL`: assertion errors, `SystemExit`, `KeyboardInterrupt`

Backoff: `delay = base * (2 ** attempt) + jitter(0, 0.5*delay)`, base=1.0s, cap at 60s.

## DLQ Schema

```jsonl
{
  "id": "dlq-{uuid}",
  "ts": "2026-05-12T15:30:00Z",
  "survey_id": "heypiggy-abc123",
  "persona_id": "anna_meyer",
  "provider": "lucid",
  "url": "https://...",
  "error_class": "PermanentError",
  "error_message": "...",
  "attempt_count": 3,
  "context": { "last_question": "...", "page_html_b64": "..." },
  "status": "pending"   // pending | replayed | discarded
}
```

File: `logs/dlq-<ISO8601-date>.jsonl`, rotated daily.

## Contradiction Detection

The SQLite answer-history (from `AnswerEngine._init_db`) already stores `(persona_id, question_hash, answer_value, ts)`.

For persona-identity questions, normalize the question into a category:
- AGE (any question containing "age", "alter", "born", "wie alt")
- GENDER ("gender", "geschlecht", "sex")
- INCOME ("income", "einkommen", "salary", "household income")
- EDUCATION ("education", "highest degree", "bildung", "abschluss")
- EMPLOYMENT ("employment", "occupation", "beruf")
- HOUSEHOLD_SIZE ("how many people", "haushaltsgroesse")
- COUNTRY / REGION

When a new question arrives in one of these categories:
1. Look up the most-frequent prior answer for this persona+category
2. If found, return THAT answer (overrides random selection)
3. If found AND the new question's options don't include it → return the option closest to the prior (e.g. prior was "25-34" and new question has ranges "26-35" → return "26-35")
4. Log a `Contradiction` event if the engine WOULD have chosen differently

`contradiction-scan` CLI prints a report:
```
Persona: anna_meyer
  AGE       12 answers, 11x "25-34", 1x "35-44"  ⚠ contradiction
  GENDER    8 answers, 8x "female"               ✓ consistent
  INCOME    15 answers, 12x "30-50k EUR", 3x "50-75k EUR" ⚠ contradiction (within band)
```

## Webhook Alerting (Optional)

Env var `RELIABILITY_WEBHOOK_URL` — if set, DLQ pushes POST a JSON payload to the URL. Format:
```json
{
  "text": "SR-152 alert: DLQ push {survey_id} for {persona_id}: {error_class}: {error_message}",
  "details": { ... full DLQ record ... }
}
```
Compatible with Slack/Discord generic webhooks (both accept `{text}` payloads).

Webhook call is fire-and-forget with 5s timeout; failures do not block the DLQ write.

## Acceptance Criteria

### retry_policy.py
- [ ] `RetryPolicy(max_attempts=3, base_delay=1.0, max_delay=60.0)` constructor
- [ ] `async run(coro_fn, classify_fn=default_classify, on_retry=None) -> result | raises`
- [ ] Default classify_fn correctly categorizes TimeoutError → TRANSIENT, ValueError → PERMANENT, etc.
- [ ] Backoff respects max_delay cap

### dlq.py
- [ ] `DLQ.push(survey_id, persona_id, provider, url, error, context) -> dlq_id`
- [ ] `DLQ.list_pending() -> list[DLQRecord]`
- [ ] `DLQ.mark_replayed(dlq_id)` / `DLQ.mark_discarded(dlq_id)`
- [ ] Writes to `logs/dlq-<ISO8601-date>.jsonl`
- [ ] Optional webhook call uses `RELIABILITY_WEBHOOK_URL` env var, 5s timeout, fire-and-forget

### contradiction.py
- [ ] `ContradictionDetector(answer_db_path)` constructor
- [ ] `categorize(question_text: str) -> str | None` returns AGE/GENDER/INCOME/EDUCATION/EMPLOYMENT/HOUSEHOLD_SIZE/COUNTRY or None
- [ ] `check(persona_id, question) -> Answer | None` returns the prior pinned answer if category matches
- [ ] `scan(persona_id) -> dict[category, list[ContradictionEvent]]` returns full report
- [ ] Multi-language: detects German + English keywords for all 7 categories

### daemon/survey_daemon.py wiring
- [ ] Survey loop wrapped in `RetryPolicy.run(...)`
- [ ] On final failure, push DLQ
- [ ] No regression: success path unchanged

### answer_engine.py wiring
- [ ] `_select_age_option`, `_select_gender_option`, `_select_income_option`, `_select_education_option` consult `ContradictionDetector.check()` first
- [ ] If check returns an Answer, use it; else fall through to current logic

### CLI subcommands (cli.py)
- [ ] `survey dlq-list [--status pending|replayed|discarded] [--limit N]`
- [ ] `survey dlq-replay <id>` retries the survey; on success marks replayed, on failure leaves pending
- [ ] `survey contradiction-scan <persona_id>` prints the report described above

### Tests (test_reliability.py)
- [ ] 6 retry: success-no-retry / transient-2x-then-success / permanent-no-retry / max-attempts-exceeded / backoff-timing-respects-max / classify-fn-override
- [ ] 6 DLQ: push / list-pending / mark-replayed / mark-discarded / JSONL-format / daily-rotation
- [ ] 6 contradiction: categorize-german / categorize-english / check-no-prior / check-with-prior / scan-no-conflicts / scan-with-conflicts
- [ ] 2 webhook: env-set-fires / env-unset-skipped / webhook-timeout-doesnt-block
- [ ] 2 integration: daemon-uses-retry-policy / engine-uses-contradiction-check

### Quality
- [ ] ruff clean (E,W,F line-length 100, py312)
- [ ] No new pip deps (stdlib `urllib.request` for webhook)
- [ ] Closes #152 in commit + PR body
- [ ] Branch: `feat/152-reliability-hardening`

## Out of Scope

- Prometheus / OpenTelemetry exporters (observability/metrics.py stays unchanged)
- Auto-replay loop for DLQ (manual `dlq-replay` only — no scheduled replay)
- Multi-persona contradiction (cross-persona check, e.g. "anna_meyer claims to be 35 in Berlin, jeremy_schulze also claims 35 in Berlin" — out of scope, future work)
- Question-type changes (SR-150 owns)
- Network / proxy work (SR-151 owns)

## References

- Daemon entry: https://raw.githubusercontent.com/SIN-CLIs/stealth-runner/main/survey-cli/survey/daemon/survey_daemon.py
- Engine identity-question methods: https://raw.githubusercontent.com/SIN-CLIs/stealth-runner/main/survey-cli/survey/daemon/answer_engine.py (lines 563-650)
- Existing logger: https://raw.githubusercontent.com/SIN-CLIs/stealth-runner/main/survey-cli/survey/observability/logger.py

## Parallel-Safety

Zero file overlap with SR-150 or SR-151.

## Dependencies

None.
