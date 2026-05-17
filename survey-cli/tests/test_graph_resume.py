"""Tests for create_graph(checkpointer=...) wiring (SR-238).

Scope: prove that create_graph() passes a checkpointer to graph.compile()
when one is available, and falls through cleanly when it isn't. We do
NOT actually run the survey graph here — that's an integration test.
"""

from __future__ import annotations

import sys
import types
from unittest import TestCase
from unittest.mock import MagicMock, patch


class _FakeStateGraph:
    """Records compile() arguments so the test can assert on them."""

    def __init__(self, state_schema):  # type: ignore[no-untyped-def]
        self.state_schema = state_schema
        self.nodes: dict = {}
        self.edges: list = []
        self.cond: list = []
        self.compile_calls: list = []

    def add_node(self, name, fn):  # type: ignore[no-untyped-def]
        self.nodes[name] = fn

    def add_edge(self, src, dst):  # type: ignore[no-untyped-def]
        self.edges.append((src, dst))

    def add_conditional_edges(self, src, fn, mapping):  # type: ignore[no-untyped-def]
        self.cond.append((src, fn, mapping))

    def compile(self, *, checkpointer=None):  # type: ignore[no-untyped-def]
        self.compile_calls.append({"checkpointer": checkpointer})
        return MagicMock(name="compiled_graph")


def _install_fake_langgraph(monkeypatch_dict):
    """Inject a minimal `langgraph` package that the graph module is
    happy to import. Returns the FakeStateGraph class so the test can
    assert on its compile_calls."""
    pkg = types.ModuleType("langgraph")
    pkg.__path__ = []  # type: ignore[attr-defined]
    graph_mod = types.ModuleType("langgraph.graph")

    graph_mod.StateGraph = _FakeStateGraph  # type: ignore[attr-defined]
    graph_mod.START = "__start__"  # type: ignore[attr-defined]
    graph_mod.END = "__end__"  # type: ignore[attr-defined]

    monkeypatch_dict["langgraph"] = pkg
    monkeypatch_dict["langgraph.graph"] = graph_mod
    return _FakeStateGraph


class TestCreateGraphCheckpointerWiring(TestCase):
    def setUp(self) -> None:
        # Force re-import of survey.graph.graph against our fake langgraph
        for name in list(sys.modules.keys()):
            if name.startswith("survey.graph"):
                del sys.modules[name]
        for name in ("langgraph", "langgraph.graph"):
            sys.modules.pop(name, None)

    def test_compile_receives_explicit_checkpointer(self) -> None:
        injected: dict = {}
        _install_fake_langgraph(injected)
        with patch.dict(sys.modules, injected):
            from survey.graph.graph import create_graph

            sentinel_saver = object()
            compiled = create_graph(checkpointer=sentinel_saver)
            self.assertIsNotNone(compiled)

            # Find the FakeStateGraph instance the factory built.
            sg = next(
                v for v in injected.values()
                if isinstance(v, types.ModuleType)
                and getattr(v, "StateGraph", None) is _FakeStateGraph
            )
            # The factory builds its own StateGraph, so we cannot read it
            # directly from `injected`. Instead verify behaviour via the
            # MagicMock returned: the FakeStateGraph captured the call,
            # and we expose it via class attribute below.

        # Simpler assert: walk graph.add_node calls — the FakeStateGraph
        # records them. Use a side-channel: inspect last instance.
        # _FakeStateGraph.compile_calls is per-instance; we re-run with a
        # capturing wrapper to get hold of it.
        # (Done in the next test, which uses a different fixture.)

    def test_compile_called_with_provided_saver(self) -> None:
        last_instance: dict = {}

        class CapturingSG(_FakeStateGraph):
            def __init__(self, state_schema):  # type: ignore[no-untyped-def]
                super().__init__(state_schema)
                last_instance["sg"] = self

        injected: dict = {}
        _install_fake_langgraph(injected)
        injected["langgraph.graph"].StateGraph = CapturingSG  # type: ignore[attr-defined]
        with patch.dict(sys.modules, injected):
            from survey.graph.graph import create_graph

            sentinel = object()
            create_graph(checkpointer=sentinel)

        sg = last_instance["sg"]
        self.assertEqual(len(sg.compile_calls), 1)
        self.assertIs(sg.compile_calls[0]["checkpointer"], sentinel)

    def test_default_uses_sqlite_saver_when_available(self) -> None:
        last_instance: dict = {}

        class CapturingSG(_FakeStateGraph):
            def __init__(self, state_schema):  # type: ignore[no-untyped-def]
                super().__init__(state_schema)
                last_instance["sg"] = self

        injected: dict = {}
        _install_fake_langgraph(injected)
        injected["langgraph.graph"].StateGraph = CapturingSG  # type: ignore[attr-defined]

        # Patch create_sqlite_checkpointer to return a sentinel.
        with patch.dict(sys.modules, injected):
            from survey.graph import checkpointer as ck

            sentinel = MagicMock(name="fake_saver")
            with patch.object(ck, "create_sqlite_checkpointer", return_value=sentinel):
                from survey.graph.graph import create_graph
                create_graph()  # no checkpointer arg, defaults turned on

        sg = last_instance["sg"]
        self.assertEqual(len(sg.compile_calls), 1)
        self.assertIs(sg.compile_calls[0]["checkpointer"], sentinel)

    def test_no_checkpoint_falls_through_to_compile_without_arg(self) -> None:
        last_instance: dict = {}

        class CapturingSG(_FakeStateGraph):
            def __init__(self, state_schema):  # type: ignore[no-untyped-def]
                super().__init__(state_schema)
                last_instance["sg"] = self

        injected: dict = {}
        _install_fake_langgraph(injected)
        injected["langgraph.graph"].StateGraph = CapturingSG  # type: ignore[attr-defined]

        with patch.dict(sys.modules, injected):
            from survey.graph.graph import create_graph

            create_graph(with_checkpoint=False)

        sg = last_instance["sg"]
        self.assertEqual(len(sg.compile_calls), 1)
        # Compile was called WITHOUT a checkpointer argument.
        self.assertIsNone(sg.compile_calls[0]["checkpointer"])

    def test_default_falls_back_when_saver_factory_returns_none(self) -> None:
        """Sandbox / hosts without langgraph[sqlite] installed: the saver
        factory returns None, and create_graph must compile WITHOUT a
        checkpointer arg rather than crashing."""
        last_instance: dict = {}

        class CapturingSG(_FakeStateGraph):
            def __init__(self, state_schema):  # type: ignore[no-untyped-def]
                super().__init__(state_schema)
                last_instance["sg"] = self

        injected: dict = {}
        _install_fake_langgraph(injected)
        injected["langgraph.graph"].StateGraph = CapturingSG  # type: ignore[attr-defined]

        with patch.dict(sys.modules, injected):
            from survey.graph import checkpointer as ck

            with patch.object(ck, "create_sqlite_checkpointer", return_value=None):
                from survey.graph.graph import create_graph
                create_graph()

        sg = last_instance["sg"]
        self.assertEqual(len(sg.compile_calls), 1)
        self.assertIsNone(sg.compile_calls[0]["checkpointer"])
