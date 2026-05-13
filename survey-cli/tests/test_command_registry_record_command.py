"""SR-194 A6: regression tests for CommandRegistry.record_command.

The method was called from four tool files but never existed on the
class, so every call raised ``AttributeError`` — and because all four
call sites wrap the telemetry in a bare ``except Exception: pass`` the
failure was silent. The tests below pin the new method's contract:

1. The method must exist and be callable with the 3-arg shape the
   tool files use: ``record_command(command_id, ok, details)``.
2. On ``ok=True`` it must increment ``success_count`` (never touch
   ``banned_commands``).
3. On ``ok=False`` it must increment ``failure_count`` *without*
   moving the command to ``banned_commands`` (that's the semantic
   difference vs. ``record_failure`` — see issue #200 / PR-C body).
4. Repeated calls are idempotent w.r.t. registry structure.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from survey.command_registry import CommandRegistry


@pytest.fixture
def registry(tmp_path: Path) -> CommandRegistry:
    """Fresh registry backed by a tmp_path file (no global state pollution)."""
    return CommandRegistry(registry_path=tmp_path / "registry.json")


def _verified(reg: CommandRegistry, cmd_id: str) -> dict | None:
    for cmd in reg._data.get("verified_commands", []):
        if cmd["id"] == cmd_id:
            return cmd
    return None


def _banned(reg: CommandRegistry, cmd_id: str) -> dict | None:
    for cmd in reg._data.get("banned_commands", []):
        if cmd["id"] == cmd_id:
            return cmd
    return None


def test_record_command_method_exists(registry: CommandRegistry):
    """A6: the method must exist with the (id, ok, details) shape."""
    assert hasattr(registry, "record_command")
    # No TypeError when called with the exact signature the tool files use.
    registry.record_command("universal_answer", True, "ok")


def test_record_command_success_creates_verified_entry(registry: CommandRegistry):
    registry.record_command("scan_dashboard", True, "first run")
    entry = _verified(registry, "scan_dashboard")
    assert entry is not None
    assert entry["success_count"] == 1
    assert entry["failure_count"] == 0
    assert entry["notes"] == "first run"
    # Must NOT have banned the command.
    assert _banned(registry, "scan_dashboard") is None


def test_record_command_failure_does_not_ban(registry: CommandRegistry):
    """The whole point of A6: tool telemetry must not auto-ban tools."""
    registry.record_command("solve_captcha", False, "captcha timeout")
    entry = _verified(registry, "solve_captcha")
    assert entry is not None
    assert entry["failure_count"] == 1
    assert entry["success_count"] == 0
    # Critically: a single failure must NOT land in banned_commands.
    assert _banned(registry, "solve_captcha") is None, (
        "record_command moved a command to banned on the first failure — "
        "this defeats its purpose vs. record_failure. See SR-194 A6."
    )


def test_record_command_counters_accumulate(registry: CommandRegistry):
    registry.record_command("universal_answer", True, "")
    registry.record_command("universal_answer", True, "")
    registry.record_command("universal_answer", False, "page parse error")
    entry = _verified(registry, "universal_answer")
    assert entry is not None
    assert entry["success_count"] == 2
    assert entry["failure_count"] == 1
    # Last failure note wins.
    assert entry["notes"] == "page parse error"
    assert _banned(registry, "universal_answer") is None


def test_record_command_persists_across_instances(tmp_path: Path):
    """Counters survive a fresh CommandRegistry() pointed at the same file.

    This mirrors the real call pattern from
    ``tools/tool_universal_answer.py`` where every invocation creates a
    fresh ``CommandRegistry()`` instance.
    """
    reg_path = tmp_path / "registry.json"
    CommandRegistry(registry_path=reg_path).record_command("solve_drag_puzzle", True, "")
    CommandRegistry(registry_path=reg_path).record_command("solve_drag_puzzle", False, "drag missed")

    fresh = CommandRegistry(registry_path=reg_path)
    entry = _verified(fresh, "solve_drag_puzzle")
    assert entry is not None
    assert entry["success_count"] == 1
    assert entry["failure_count"] == 1

    # And the file on disk reflects it (sanity).
    on_disk = json.loads(reg_path.read_text())
    assert any(
        c["id"] == "solve_drag_puzzle" and c["success_count"] == 1 and c["failure_count"] == 1
        for c in on_disk.get("verified_commands", [])
    )
