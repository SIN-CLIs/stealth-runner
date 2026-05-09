# Plan 06: TEST COVERAGE

> **Parent**: ULTIMATE-PLAN.md | **Phase**: 3 | **Priority**: P1
> **Effort**: 2 days | **Risk**: LOW

---

## PROBLEM

**20 of 53 source files (38%) have zero test coverage:**

- `src/stealth_survey/nim_client.py` — no test
- `src/stealth_survey/batch_executor.py` — no test
- `src/stealth_survey/survey_agent.py` — no test
- `src/stealth_survey/compact_snapshot.py` — no test
- ALL 8 `survey-cli/survey/agents/` files — 0 tests
- ALL 4 `survey-cli/survey/providers/` files — 0 tests
- Various others

After Phase 1 merges, some of these disappear. But new `engine/` files and provider files need tests.

## PLAN

### Step 1: After merge, audit remaining gaps

```bash
python scripts/audit_coverage.py
```

### Step 2: Unit tests for engine

```
tests/unit/
├── test_nim_client.py         ← Test circuit breaker, retry, decide(), parse_response()
├── test_snapshot.py           ← Test generate(), element extraction, completion detection
├── test_batch_executor.py     ← Test execute(), provider dispatch, validation errors
└── test_survey_agent.py       ← Test run_survey flow, _simple_actions fallback
```

### Step 3: Unit tests for providers

```
tests/unit/
└── test_providers/
    ├── test_qualtrics.py      ← Test .NextButton, .LabelWrapper, label matching
    ├── test_toluna.py         ← Test .cf-radio, submit
    ├── test_strat7.py         ← Test .bsbutton
    ├── test_purespectrum.py   ← Test CDP click, Angular dispatch
    └── test_generic.py        ← Test generic fallback
```

### Step 4: Integration tests

```
tests/integration/
├── test_tab_switching.py      ← NEW: Survey opens in new tab → detect + switch
├── test_login_flow.py         ← Mock CDP for 6-step login verification
├── test_e2e_survey.py         ← Mock CDP + mock NIM for full survey flow
└── test_pre_qualifier.py      ← Pre-qualifier detection + answering
```

### Step 5: Minimum test requirements

Every public function must have:
- 1 happy-path test
- 1 error-path test
- 1 edge-case test

## DELIVERABLES

- [ ] Coverage ≥90% (from ~62%)
- [ ] All `engine/` files have ≥80% line coverage
- [ ] All `providers/` files have tests
- [ ] Integration test for tab switching
- [ ] Integration test for full survey loop

## VERIFICATION

```bash
pytest --cov=survey_cli --cov-report=term-missing tests/
# Target: 90%+ coverage, no gaps >10 lines
```