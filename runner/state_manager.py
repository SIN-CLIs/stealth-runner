"""
State-File Management mit Backup & Recovery.
"""
import json
import time
import shutil
import logging
from pathlib import Path
from typing import Dict, Any

logger = logging.getLogger("state_manager")

STATE_FILE = Path("/tmp/stealth_step.json")
BACKUP_DIR = Path("/tmp/stealth_backups")


def load_state() -> Dict[str, Any]:
    """Lädt State mit Backup-Recovery."""
    if not STATE_FILE.exists():
        logger.warning("State-File existiert nicht! Erstelle neues State.")
        return {"step": 0, "pid": None, "url": None, "eur": 0.0}

    try:
        with open(STATE_FILE) as f:
            state = json.load(f)
        _validate_state(state)
        return state
    except (json.JSONDecodeError, KeyError, ValueError) as e:
        logger.error(f"State-File korrupt! Versuche Recovery: {e}")
        return _recover_state()


def save_state(state: Dict[str, Any]) -> None:
    """Speichert State mit Backup."""
    BACKUP_DIR.mkdir(exist_ok=True)
    backup_file = BACKUP_DIR / f"stealth_step_{int(time.time())}.json"

    # Backup erstellen
    if STATE_FILE.exists():
        shutil.copy(STATE_FILE, backup_file)
        logger.info(f"State-Backup erstellt: {backup_file.name}")

    # State speichern
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)
    logger.debug(f"State gespeichert: {state}")


def _recover_state() -> Dict[str, Any]:
    """Versucht, State aus Backups wiederherzustellen."""
    backups = sorted(BACKUP_DIR.glob("stealth_step_*.json"), reverse=True)
    for backup in backups:
        try:
            with open(backup) as f:
                state = json.load(f)
            _validate_state(state)
            logger.warning(f"State aus Backup {backup.name} wiederhergestellt!")
            return state
        except Exception as e:
            logger.error(f"Backup {backup.name} ungültig: {e}")
    logger.error("Kein gültiges Backup gefunden! Erstelle neues State.")
    return {"step": 0, "pid": None, "url": None, "eur": 0.0}


def _validate_state(state: Dict[str, Any]) -> None:
    """Validiert State-Struktur."""
    required_keys = {"step", "pid", "url", "eur"}
    if not required_keys.issubset(state.keys()):
        raise ValueError("State fehlen required keys")
    if not isinstance(state["step"], int):
        raise ValueError("step muss int sein")
    if not isinstance(state["eur"], (int, float)):
        raise ValueError("eur muss Zahl sein")
