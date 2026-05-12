"""SR-101: FCTC-ES Suggester Eval-Harness — Phase 1 vs Phase 2 accuracy.

This package contains the eval-harness for survey.learn.suggester:
- labels.golden.jsonl: frozen 50-record golden test-set covering all 20 families
- run_eval.py:         eval-runner with --phase {1,2} and --mock/--live modes

Run from survey-cli/ directory:

    python -m evals.learn_suggester.run_eval --phase 1
    python -m evals.learn_suggester.run_eval --phase 2 --mock

Closes #101.
"""
