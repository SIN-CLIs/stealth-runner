"""Tests für State-File Recovery."""
import pytest
from runner.state_manager import load_state, save_state, _recover_state


def test_state_save_load():
    # Valid State speichern
    save_state({"step": 1, "pid": 123, "url": "test", "eur": 5.0})

    # Laden
    state = load_state()
    assert state["step"] == 1
    assert state["eur"] == 5.0


def test_state_corrupt_recovery():
    # Bereinige alte Backups/States
    import glob, os, shutil
    for path in glob.glob("/tmp/stealth_step*.json"): os.remove(path)
    shutil.rmtree("/tmp/stealth_backups", ignore_errors=True)

    # Korrupte State-Datei erstellen
    with open("/tmp/stealth_step.json", "w") as f:
        f.write("INVALID JSON {{}")

    # Recovery testen (sollte Default-State zurückgeben, da kein Backup existiert)
    from runner.state_manager import load_state
    state = load_state()
    assert state["step"] == 0
    assert state["eur"] == 0.0


def test_state_backup_creation():
    # State speichern
    save_state({"step": 2, "pid": 456, "url": "test2", "eur": 10.0})

    # Prüfen, ob Backup existiert
    import glob
    backups = glob.glob("/tmp/stealth_backups/stealth_step_*.json")
    assert len(backups) > 0
