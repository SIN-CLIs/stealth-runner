"""Trajectory eval harness — see `run_eval.py` for the entry point.

This package mirrors the layout of `evals/learn_suggester/` so the
two harnesses are interchangeable from CI's point of view: a frozen
JSONL golden set, a deterministic mock backend, threshold gates that
can fail the build.
"""
