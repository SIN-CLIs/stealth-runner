# Plan: Learn-Apply Smoke Test (#99)

**Status:** IN PROGRESS
**Created:** 2026-05-12
**Author:** v0-Agent

## Objective

Add end-to-end CI smoke test for `survey learn apply` CLI path to catch:
1. AST-shape changes in FIELD_PATTERNS
2. argparse subparser layout changes
3. Subprocess gate behavior in GHA environment

## Scope

### New Files
- [x] `survey-cli/tests/fixtures/learn_apply_smoke_inbox.jsonl` - 3 test entries
- [x] `survey-cli/tests/fixtures/learn_apply_smoke_profile.py` - minimal stub
- [x] `.github/workflows/learn-apply-smoke.yml` - separate CI workflow

### Modified Files
- [x] `survey-cli/survey/learn/cli.py` - add `--target` flag to apply subparser

### Out of Scope (LOCKED)
- NO changes to apply.py, suggester.py, aggregator.py, llm_client.py
- NO changes to profile_loader.py
- NO changes to ci.yml
- NO new Python dependencies

## Implementation Details

### Inbox Fixture (3 entries)
1. `source=substring, confidence=0.92, family=phone` -> APPLIED
2. `source=llm, confidence=0.80` -> REJECTED (below 0.85 gate)
3. `source=substring, family=lieblingsfarbe` -> REJECTED (unknown AST family)

### Workflow Steps
1. Dry-run: verify `accepted=1 rejected=2`
2. Apply: verify file modification + audit log

### CLI Change
Single `--target` argument to override default profile_loader.py path.

## Parallel Safety with #56

- #56 modifies: aggregate subparser (`p_agg`)
- #99 modifies: apply subparser (`p_app`)
- Different hunks -> mechanical git merge

## Acceptance Criteria

- [x] learn-apply-smoke.yml created
- [x] Workflow has dry-run + apply steps
- [x] Fixtures frozen with expected schema
- [x] Action versions: checkout@v5, setup-python@v6
- [ ] Green CI run on merge (pending)

## Delete on Close

This plan file will be deleted in the PR that closes #99.
