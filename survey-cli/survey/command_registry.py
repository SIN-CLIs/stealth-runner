"""
Command Registry — Pre-flight validation for survey commands.

Load registry → validate command → execute → record result → auto-update.
Prevents known crash patterns (e.g., submit immediately after radio select).
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone

REGISTRY_PATH = Path(__file__).parent.parent / "data" / "command_registry.json"


class CommandRegistryError(Exception):
    """Base error for command registry violations."""
    pass


class CommandBannedError(CommandRegistryError):
    """Raised when attempting to execute a banned command."""
    pass


class CommandNotVerifiedError(CommandRegistryError):
    """Warning-level: command not in verified list."""
    pass


class CommandRegistry:
    """Validates commands against known success/failure patterns."""

    def __init__(self, registry_path: Optional[Path] = None):
        self.path = registry_path or REGISTRY_PATH
        self._data = self._load()

    def _load(self) -> Dict[str, Any]:
        """Load registry from JSON file."""
        if not self.path.exists():
            return self._default_registry()
        with open(self.path, "r") as f:
            return json.load(f)

    def _save(self):
        """Persist registry to JSON file."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "w") as f:
            json.dump(self._data, f, indent=2, ensure_ascii=False)

    def _default_registry(self) -> Dict[str, Any]:
        """Return empty registry structure."""
        return {
            "version": "1.0.0",
            "last_updated": datetime.now(timezone.utc).isoformat(),
            "survey_provider": "",
            "survey_id": "",
            "verified_commands": [],
            "banned_commands": [],
            "safe_sequences": [],
            "chrome_recovery": {"status": "unknown"},
        }

    def is_banned(self, command_id: str) -> bool:
        """Check if command is banned."""
        return any(
            b["id"] == command_id
            for b in self._data.get("banned_commands", [])
        )

    def is_verified(self, command_id: str) -> bool:
        """Check if command is verified."""
        return any(
            v["id"] == command_id
            for v in self._data.get("verified_commands", [])
        )

    def get_banned_reason(self, command_id: str) -> Optional[str]:
        """Get reason why command is banned."""
        for b in self._data.get("banned_commands", []):
            if b["id"] == command_id:
                return b.get("error", "Unknown reason")
        return None

    def get_safe_sequence(self, action_type: str) -> Optional[List[str]]:
        """Get verified step sequence for an action type."""
        for seq in self._data.get("safe_sequences", []):
            if action_type in seq["id"]:
                return seq["steps"]
        return None

    def validate_command(self, command_id: str) -> bool:
        """
        Pre-flight check: validate command before execution.

        Returns True if safe to execute.
        Raises CommandBannedError if command is banned.
        Raises CommandNotVerifiedError if command is unknown (warning only).
        """
        if self.is_banned(command_id):
            reason = self.get_banned_reason(command_id)
            raise CommandBannedError(
                f"Command '{command_id}' is BANNED: {reason}"
            )

        if not self.is_verified(command_id):
            raise CommandNotVerifiedError(
                f"Command '{command_id}' not verified. Proceed with caution."
            )

        return True

    def record_success(self, command_id: str, notes: str = ""):
        """Record successful command execution."""
        now = datetime.now(timezone.utc).isoformat()

        for cmd in self._data.get("verified_commands", []):
            if cmd["id"] == command_id:
                cmd["success_count"] += 1
                cmd["last_success"] = now
                if notes:
                    cmd["notes"] = notes
                self._save()
                return

        # Add new verified command
        self._data["verified_commands"].append({
            "id": command_id,
            "description": "",
            "pattern": "",
            "success_count": 1,
            "failure_count": 0,
            "last_success": now,
            "status": "verified",
            "notes": notes,
        })
        self._save()

    def record_failure(self, command_id: str, error: str, notes: str = ""):
        """Record failed command execution."""
        now = datetime.now(timezone.utc).isoformat()

        # Check if already banned
        for b in self._data.get("banned_commands", []):
            if b["id"] == command_id:
                b["failure_count"] += 1
                b["last_failure"] = now
                if error:
                    b["error"] = error
                if notes:
                    b["notes"] = notes
                self._save()
                return

        # Add to banned list
        self._data["banned_commands"].append({
            "id": command_id,
            "description": "",
            "pattern": "",
            "failure_count": 1,
            "last_failure": now,
            "error": error,
            "status": "banned",
            "fix": "",
            "notes": notes,
        })
        self._save()

    def record_execution(
        self,
        command_id: str,
        provider: str = "",
        survey_id: str = "",
        status: str = "completed",  # "completed" | "screen_out" | "error"
        steps: int = 0,
        earned: float = 0.0,
    ):
        """
        Record survey execution result — auto-update registry after survey.

        Called by FastAPI after each survey attempt.

        Flow:
          - completed + earned > 0 → record_success, promote if threshold reached
          - screen_out → record_failure (provider might be unreliable)
          - error → record_failure

        Args:
            command_id: e.g. "survey_cint_67078106"
            provider: Provider name (cint, purespectrum, etc.)
            survey_id: HeyPiggy survey ID
            status: "completed" | "screen_out" | "error"
            steps: Number of NEMO loop iterations
            earned: Balance earned from survey (€)
        """
        now = datetime.now(timezone.utc).isoformat()

        # Update survey-level tracking
        key = f"survey_{provider}_{survey_id}"

        if status == "completed" and earned > 0:
            self.record_success(key, notes=f"earned=€{earned:.2f}, steps={steps}")
        elif status in ("screen_out", "error"):
            self.record_failure(key, error=f"{status} (earned=€{earned:.2f})", notes=f"steps={steps}")  # noqa: E501

        # Also update provider-level
        prov_key = f"provider_{provider}"
        if provider:
            if status == "completed" and earned > 0:
                self.record_success(prov_key, notes=f"survey {survey_id} earned €{earned:.2f}")
            elif status in ("screen_out", "error"):
                # Screen-out: provider might be unreliable → increment failure count
                self.record_failure(prov_key, error=f"screen_out on survey {survey_id}")

        self._data["last_execution"] = {
            "command_id": command_id,
            "provider": provider,
            "survey_id": survey_id,
            "status": status,
            "steps": steps,
            "earned": earned,
            "timestamp": now,
        }
        self._save()

    def promote_to_verified(self, command_id: str, success_threshold: int = 3):
        """
        Promote command to verified after N successes.
        Auto-called by record_success when threshold reached.
        """
        for cmd in self._data.get("verified_commands", []):
            if cmd["id"] == command_id and cmd["success_count"] >= success_threshold:
                cmd["status"] = "verified"
                self._save()
                return True
        return False

    def get_stats(self) -> Dict[str, int]:
        """Return registry statistics."""
        return {
            "verified": len(self._data.get("verified_commands", [])),
            "banned": len(self._data.get("banned_commands", [])),
            "safe_sequences": len(self._data.get("safe_sequences", [])),
            "total_successes": sum(
                c.get("success_count", 0)
                for c in self._data.get("verified_commands", [])
            ),
            "total_failures": sum(
                c.get("failure_count", 0)
                for c in self._data.get("banned_commands", [])
            ),
        }



    def record_command(self, command_id: str, ok: bool, details: str = ""):
        """
        Alias for record_success/record_failure — used by tool_*.py files.

        Added 2026-05-13 to fix SR-194 A6 (AttributeError: record_command missing).

        Args:
            command_id: Command identifier (e.g. "solve_captcha", "universal_answer")
            ok: True for success, False for failure
            details: Additional info (error message for failure, notes for success)
        """
        if ok:
            self.record_success(command_id, notes=details)
        else:
            self.record_failure(command_id, error=details)
# Convenience function for quick validation
def can_execute(command_id: str, registry_path: Optional[Path] = None) -> bool:
    """
    Quick pre-flight check: can this command be executed safely?

    Usage:
        if can_execute("select_radio"):
            execute_command()
    """
    reg = CommandRegistry(registry_path)
    return reg.validate_command(command_id)


# ═══════════════════════════════════════════════════════════════════════════════
# SURVEY LOCK — Prevents parallel survey execution (critical!)
# ═══════════════════════════════════════════════════════════════════════════════
#
# ROOT CAUSE (2026-05-10): Multiple survey tabs open simultaneously.
# Bug: Completion detection failed → loop continued → background loop started
#      next survey → previous tab still open → 6 tabs stacked!
#
# FIX: Survey lock file. Before running a survey, acquire lock. After survey
#      completes/errors, release lock. Kein neuer Survey wenn Lock aktiv.
#
# File: survey-cli/data/.survey_lock.json
# Structure: {"survey_id": "67078106", "started": "2026-05-10T...", "pid": 12345}

SURVEY_LOCK_PATH = Path(__file__).parent.parent / "data" / ".survey_lock.json"


def acquire_survey_lock(survey_id: str = "") -> bool:
    """
    Acquire survey lock. Returns True if lock acquired, False if already locked.

    Prevents parallel survey execution.
    """
    if SURVEY_LOCK_PATH.exists():
        try:
            with open(SURVEY_LOCK_PATH, "r") as f:
                lock = json.load(f)
            # Lock is stale if older than 30 minutes (surveys shouldn't take that long)
            lock_time = datetime.fromisoformat(lock.get("started", "2000-01-01"))
            age_minutes = (datetime.now(timezone.utc) - lock_time).total_seconds() / 60
            if age_minutes < 30:
                return False  # Lock is fresh — survey still running
            # Lock is stale — remove it and proceed
        except Exception:
            pass

    # Acquire lock
    SURVEY_LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(SURVEY_LOCK_PATH, "w") as f:
        json.dump({
            "survey_id": survey_id,
            "started": datetime.now(timezone.utc).isoformat(),
            "pid": os.getpid(),
        }, f)
    return True


def release_survey_lock():
    """Release survey lock after survey completes/errors."""
    try:
        if SURVEY_LOCK_PATH.exists():
            SURVEY_LOCK_PATH.unlink()
    except Exception:
        pass


def is_survey_locked() -> bool:
    """Check if a survey is currently running."""
    if not SURVEY_LOCK_PATH.exists():
        return False
    try:
        with open(SURVEY_LOCK_PATH, "r") as f:
            lock = json.load(f)
        lock_time = datetime.fromisoformat(lock.get("started", "2000-01-01"))
        age_minutes = (datetime.now(timezone.utc) - lock_time).total_seconds() / 60
        return age_minutes < 30  # Lock stale after 30 min
    except Exception:
        return False


# Example usage in survey flow
def execute_with_validation(
    command_id: str,
    executor_func,
    registry_path: Optional[Path] = None,
) -> Any:
    """
    Execute a command with pre-flight validation and post-flight recording.

    Usage:
        result = execute_with_validation(
            "select_radio",
            lambda: cdp_execute("document.getElementById('...').checked = true")
        )
    """
    reg = CommandRegistry(registry_path)

    # Pre-flight
    reg.validate_command(command_id)

    # Execute
    try:
        result = executor_func()
        reg.record_success(command_id)
        return result
    except Exception as e:
        reg.record_failure(command_id, str(e))
        raise
