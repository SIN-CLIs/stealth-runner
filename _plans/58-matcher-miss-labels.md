# Plan: Issue #58 (SR-59) — Persistent semantically-tagged matcher miss_labels

> Temporary planning file. **DELETE in the same PR that closes #58.**

## Goal
Telemetry must carry structured miss context (not raw strings) so the aggregator (SR-55) can cluster.

## Schema
```python
miss_labels: list[dict] = [
  {"ts": ..., "question_text": str, "page_url": str | None,
   "snapshot_hash": str, "candidate_keys": list[str],
   "user_value_provided": bool}  # boolean only — never PII
]
```

## Implementation Checklist
- [ ] Extend `ProfileLoader._telemetry` schema
- [ ] Write `miss_labels` to `logs/matcher-telemetry-{run_id}.jsonl`
- [ ] `survey/learn/aggregator.py` reads `miss_labels`, groups via token-Jaccard ≥0.6
- [ ] CLI: `survey profile dump --miss-labels`
- [ ] Test: `tests/test_profile_miss_labels.py` (schema + JSONL roundtrip)

## Privacy Invariant
- `user_value_provided` is boolean ONLY — never log the actual user value.

## Files Affected
- `survey-cli/survey/profile_loader.py`
- `survey-cli/survey/learn/aggregator.py`
- `tests/test_profile_miss_labels.py` (new)

## Cleanup
After PR merge: `git rm _plans/58-matcher-miss-labels.md`.
