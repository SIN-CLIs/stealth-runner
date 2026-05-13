"""SR-194 A2-A5: regression tests for survey.daemon.cli startup.

These tests pin the four constructor/API drifts that were silently
broken before this PR:

- A2: ``SurveyDaemon.run_forever`` did not exist.
- A3: ``SurveyDaemon(persona=..., nvidia_local=...)`` raised TypeError.
- A4: ``SurveyAgentGraph(nvidia_local=...)`` raised TypeError.
- A5: ``Persona(name=...)`` raised TypeError.

The first test is the canonical AC probe from issue #199: a
``python -m survey.daemon.cli --help`` subprocess must exit 0. The
remaining tests use ``inspect.signature`` so they survive in
environments where the heavy LangGraph runtime is not installed.
"""

from __future__ import annotations

import inspect
import subprocess
import sys

import pytest


def test_cli_help_smoketest():
    """`python -m survey.daemon.cli --help` exits 0 (AC from #199)."""
    result = subprocess.run(
        [sys.executable, "-m", "survey.daemon.cli", "--help"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, (
        f"`survey.daemon.cli --help` exited {result.returncode}.\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    # Sanity: the help banner must mention the documented subcommands.
    assert "daemon" in result.stdout
    assert "run" in result.stdout


# ---------------------------------------------------------------------------
# Signature pins. These do not import langgraph; they only import the
# leaf modules whose constructors drifted. Each pin documents exactly
# which kwarg used to crash in production.
# ---------------------------------------------------------------------------


def test_persona_has_no_name_kwarg():
    """A5: Persona must not accept ``name=`` (the CLI used to pass it)."""
    from survey.daemon.answer_engine import Persona

    sig = inspect.signature(Persona)
    assert "name" not in sig.parameters, (
        "Persona accepts `name`; the SR-194 A5 fix in cli.py would be "
        "redundant. Either remove this assertion or remove the kwarg "
        "from get_persona() too."
    )
    # The fields the CLI actually uses must still be there.
    for required in ("age", "gender", "occupation", "income_bracket",
                     "education", "location", "interests"):
        assert required in sig.parameters, f"Persona lost `{required}` field"


def test_survey_daemon_has_run_forever_coroutine():
    """A2: SurveyDaemon.run_forever exists and is a coroutine function."""
    pytest.importorskip("langgraph")  # SurveyDaemon imports SurveyAgentGraph

    from survey.daemon.survey_daemon import SurveyDaemon

    assert hasattr(SurveyDaemon, "run_forever"), (
        "SurveyDaemon.run_forever is missing again; cli.py calls "
        "`asyncio.run(daemon.run_forever())`."
    )
    assert inspect.iscoroutinefunction(SurveyDaemon.run_forever), (
        "SurveyDaemon.run_forever must be `async def` for the CLI to "
        "wrap it in asyncio.run()."
    )


def test_survey_daemon_ctor_accepts_only_path_kwargs():
    """A3: SurveyDaemon.__init__ must not silently accept `persona` etc."""
    pytest.importorskip("langgraph")

    from survey.daemon.survey_daemon import SurveyDaemon

    sig = inspect.signature(SurveyDaemon)
    accepted = set(sig.parameters)
    assert "persona" not in accepted, (
        "SurveyDaemon now accepts `persona`; revisit cli.py — the "
        "A3 workaround can be reverted."
    )
    assert "nvidia_local" not in accepted, (
        "SurveyDaemon now accepts `nvidia_local`; revisit cli.py — "
        "the A3 workaround can be reverted."
    )


def test_survey_agent_graph_does_not_accept_nvidia_local():
    """A4: SurveyAgentGraph.__init__ must not silently accept nvidia_local."""
    pytest.importorskip("langgraph")

    from survey.daemon.survey_agent_graph import SurveyAgentGraph

    sig = inspect.signature(SurveyAgentGraph)
    assert "nvidia_local" not in sig.parameters, (
        "SurveyAgentGraph now accepts `nvidia_local`; revisit cli.py "
        "— the A4 workaround can be reverted."
    )
    # The kwargs the CLI does pass must still be there.
    for required in ("persona", "headless"):
        assert required in sig.parameters, (
            f"SurveyAgentGraph lost `{required}` kwarg"
        )
