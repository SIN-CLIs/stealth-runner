"""Regression tests for survey.universal.loop lock helpers.

SR-194 A1: `time.mgmtime` typo crashed every lock-recovery path with
AttributeError. The fix replaces the broken time-module gymnastics with
`datetime.fromisoformat(...).replace(tzinfo=timezone.utc)` (also satisfies
SR-187 datetime hygiene: tz-aware UTC, no `datetime.utcnow`).

These tests would have caught the bug if they had existed.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from survey.universal import loop as loop_module
from survey.universal.loop import (
    _acquire_lock,
    _release_lock,
    _wipe_stale_locks,
)


@pytest.fixture
def tmp_lock(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect LOCK_PATH into an isolated tmp dir for each test."""
    lock_path = tmp_path / ".survey_lock.json"
    monkeypatch.setattr(loop_module, "LOCK_PATH", lock_path)
    return lock_path


def _write_lock(path: Path, started: str, survey_id: str = "t") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"survey_id": survey_id, "started": started, "pid": 0}))


def test_acquire_lock_no_existing_lock(tmp_lock: Path) -> None:
    assert _acquire_lock("survey-1") is True
    assert tmp_lock.exists()
    data = json.loads(tmp_lock.read_text())
    assert data["survey_id"] == "survey-1"


def test_acquire_lock_blocks_when_fresh_lock_exists(tmp_lock: Path) -> None:
    fresh_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    _write_lock(tmp_lock, fresh_iso)
    assert _acquire_lock("survey-2") is False


def test_acquire_lock_overrides_stale_lock(tmp_lock: Path) -> None:
    """A lock older than 30 min must NOT block.

    This is the regression test for SR-194 A1: previously this path
    raised AttributeError before ever reaching the age comparison.
    """
    stale_iso = (
        datetime.now(timezone.utc) - timedelta(hours=2)
    ).strftime("%Y-%m-%dT%H:%M:%S")
    _write_lock(tmp_lock, stale_iso)

    # Pre-fix: AttributeError: module 'time' has no attribute 'mgmtime'
    # Post-fix: returns True and replaces the stale lock file.
    assert _acquire_lock("survey-3") is True
    assert json.loads(tmp_lock.read_text())["survey_id"] == "survey-3"


def test_wipe_stale_locks_removes_stale(tmp_lock: Path) -> None:
    stale_iso = (
        datetime.now(timezone.utc) - timedelta(hours=2)
    ).strftime("%Y-%m-%dT%H:%M:%S")
    _write_lock(tmp_lock, stale_iso)
    _wipe_stale_locks()
    assert not tmp_lock.exists()


def test_wipe_stale_locks_keeps_fresh(tmp_lock: Path) -> None:
    fresh_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    _write_lock(tmp_lock, fresh_iso)
    _wipe_stale_locks()
    assert tmp_lock.exists()


def test_release_lock_idempotent(tmp_lock: Path) -> None:
    """Releasing without a lock file must not raise."""
    _release_lock()
    _write_lock(tmp_lock, datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S"))
    _release_lock()
    assert not tmp_lock.exists()
    _release_lock()  # second call also fine
