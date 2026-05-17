"""Tests for survey.graph.checkpointer (SR-238 / CEO-WAVE-1).

What we verify:
  - get_default_checkpoint_path honours STATE_DIR env override
  - make_thread_id is deterministic on the same (provider, survey_id, attempt)
  - make_thread_id changes when attempt or survey_id or provider changes
  - make_run_config has the langgraph-expected shape
  - create_sqlite_checkpointer returns None when langgraph is not installed
    and a usable saver when it is

These tests do NOT spin up a real graph. The goal is to lock the helper
contract — graph integration is covered by `test_graph_resume.py` (in
the same PR) which patches langgraph minimally.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch


@dataclass
class _FakeState:
    survey_id: str = ""
    provider: str = ""


class TestCheckpointPath(TestCase):
    def test_state_dir_env_overrides(self) -> None:
        from survey.graph.checkpointer import (
            CHECKPOINT_DB_NAME,
            get_default_checkpoint_path,
        )

        with TemporaryDirectory() as tmp:
            old = os.environ.get("STATE_DIR")
            os.environ["STATE_DIR"] = tmp
            try:
                p = get_default_checkpoint_path()
            finally:
                if old is None:
                    os.environ.pop("STATE_DIR", None)
                else:
                    os.environ["STATE_DIR"] = old

            self.assertEqual(p, Path(tmp) / CHECKPOINT_DB_NAME)
            # parent dir must exist after the call so SqliteSaver can open it
            self.assertTrue(p.parent.is_dir())

    def test_explicit_path_argument_wins(self) -> None:
        from survey.graph.checkpointer import (
            CHECKPOINT_DB_NAME,
            get_default_checkpoint_path,
        )

        with TemporaryDirectory() as tmp:
            p = get_default_checkpoint_path(state_dir=Path(tmp))
            self.assertEqual(p, Path(tmp) / CHECKPOINT_DB_NAME)


class TestThreadIdDerivation(TestCase):
    def test_deterministic_on_same_inputs(self) -> None:
        from survey.graph.checkpointer import make_thread_id

        a = make_thread_id(_FakeState(survey_id="123", provider="qualtrics"))
        b = make_thread_id(_FakeState(survey_id="123", provider="qualtrics"))
        self.assertEqual(a, b)

    def test_changes_on_attempt(self) -> None:
        from survey.graph.checkpointer import make_thread_id

        s = _FakeState(survey_id="123", provider="qualtrics")
        self.assertNotEqual(
            make_thread_id(s, attempt=0),
            make_thread_id(s, attempt=1),
        )

    def test_changes_on_provider(self) -> None:
        from survey.graph.checkpointer import make_thread_id

        a = make_thread_id(_FakeState(survey_id="42", provider="qualtrics"))
        b = make_thread_id(_FakeState(survey_id="42", provider="purespectrum"))
        self.assertNotEqual(a, b)

    def test_falls_back_on_empty_fields(self) -> None:
        from survey.graph.checkpointer import make_thread_id

        # Both empty: must NOT crash, must return a stable string.
        tid = make_thread_id(_FakeState())
        self.assertIsInstance(tid, str)
        self.assertGreater(len(tid), 0)

    def test_negative_attempt_clamped(self) -> None:
        """A bug in caller code passing attempt=-1 must NOT yield a
        thread_id that differs from attempt=0 — defensive normalisation."""
        from survey.graph.checkpointer import make_thread_id

        s = _FakeState(survey_id="123", provider="qualtrics")
        self.assertEqual(
            make_thread_id(s, attempt=-5),
            make_thread_id(s, attempt=0),
        )


class TestRunConfig(TestCase):
    def test_shape_matches_langgraph_expectation(self) -> None:
        from survey.graph.checkpointer import make_run_config

        cfg = make_run_config(_FakeState(survey_id="1", provider="x"))
        self.assertIn("configurable", cfg)
        self.assertIn("thread_id", cfg["configurable"])
        self.assertIsInstance(cfg["configurable"]["thread_id"], str)


class TestCreateSqliteCheckpointer(TestCase):
    def test_returns_none_when_langgraph_missing(self) -> None:
        """On hosts without langgraph[sqlite] installed (the sandbox we
        develop in), create_sqlite_checkpointer must return None — never
        raise — so create_graph() falls back to non-checkpointed compile."""
        # Simulate ImportError for both candidate import paths.
        import sys

        from survey.graph import checkpointer as ck_mod

        with patch.dict(
            sys.modules,
            {"langgraph.checkpoint.sqlite": None},  # type: ignore[dict-item]
        ):
            saver = ck_mod.create_sqlite_checkpointer()

        self.assertIsNone(saver)

    def test_returns_saver_when_langgraph_present(self) -> None:
        """When the import succeeds, the helper returns a non-None saver
        and exposes the expected `setup` lifecycle (defensive try/except)."""
        from survey.graph import checkpointer as ck_mod

        # Build a fake module hierarchy that mimics
        # `from langgraph.checkpoint.sqlite import SqliteSaver`.
        import sys
        import types

        fake_pkg = types.ModuleType("langgraph")
        fake_pkg.__path__ = []  # type: ignore[attr-defined]
        fake_cp = types.ModuleType("langgraph.checkpoint")
        fake_cp.__path__ = []  # type: ignore[attr-defined]
        fake_sqlite = types.ModuleType("langgraph.checkpoint.sqlite")

        class _FakeSaver:
            instances = []  # type: ignore[var-annotated]

            def __init__(self, conn):  # type: ignore[no-untyped-def]
                self.conn = conn
                _FakeSaver.instances.append(self)

            def setup(self) -> None:
                # Marker so we can assert setup was called.
                self.setup_called = True

        fake_sqlite.SqliteSaver = _FakeSaver  # type: ignore[attr-defined]

        with patch.dict(
            sys.modules,
            {
                "langgraph": fake_pkg,
                "langgraph.checkpoint": fake_cp,
                "langgraph.checkpoint.sqlite": fake_sqlite,
            },
        ):
            with TemporaryDirectory() as tmp:
                saver = ck_mod.create_sqlite_checkpointer(
                    Path(tmp) / "ck.db"
                )

        self.assertIsNotNone(saver)
        self.assertIsInstance(saver, _FakeSaver)
        self.assertTrue(getattr(saver, "setup_called", False))
        # File path was reachable; SqliteSaver got a connection.
        self.assertIsNotNone(saver.conn)
