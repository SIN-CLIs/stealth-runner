"""RuntimeHealth — Daemon/Chrome/Session health snapshot.

WARUM: Phase 5 — "Fehler werden gemessen, nicht erraten."
RuntimeHealth zeigt auf einen Blick: Läuft der Daemon? Chrome okay?
Sessions korrupt?

ARCHITEKTUR:
  - RuntimeHealth.to_dict() → Snapshot aller Subsysteme
  - is_healthy() → bool (Daemon + Chrome + Sessions OK)
  - checks: daemon_pid, chrome_pids, sessions.json corruption

BANNED METHODS — NIEMALS VERWENDEN:
  ❌ playstealth launch
  ❌ webauto-nodriver — ABSOLUT BANNED
  ❌ Hardcoded PIDs
  ❌ pkill -f "Google Chrome"
  ❌ killall Google Chrome
"""

import json
import os
import signal
from pathlib import Path
from typing import Any, Dict, List, Optional

# ── Session Registry ─────────────────────────────────────

SESSIONS_FILE = Path.home() / ".stealth" / "sessions.json"
MIN_SESSION_SIZE = 100  # Files < 100 bytes are likely corrupted


def is_session_corrupted(fp: Path) -> bool:
    """Check if a session file is corrupted (< 100 bytes or invalid JSON).

    Args:
        fp: Path to session file

    Returns:
        True if file is corrupted
    """
    if not fp.exists():
        return False
    try:
        size = fp.stat().st_size
        if size < MIN_SESSION_SIZE:
            return True
        with open(fp) as f:
            json.loads(f.read())
        return False
    except (json.JSONDecodeError, OSError):
        return True


class RuntimeHealth:
    """Runtime health snapshot of all subsystems.

    Usage:
        health = RuntimeHealth()
        snapshot = health.to_dict()
        if health.is_healthy():
            print("All systems operational")
        else:
            print(f"Issues: {health.issues}")
    """

    def __init__(self, cdp_port: int = 9999):
        self.cdp_port = cdp_port
        self.issues: List[str] = []

    def _check_daemon(self) -> Dict[str, Any]:
        """Check if cua-driver daemon is running."""
        pid_file = Path.home() / ".stealth" / "daemon.pid"
        try:
            if pid_file.exists():
                pid = int(pid_file.read_text().strip())
                os.kill(pid, 0)
                return {"running": True, "pid": pid}
        except (ValueError, ProcessLookupError, PermissionError, FileNotFoundError):
            pass
        return {"running": False, "pid": None}

    def _check_chrome(self) -> Dict[str, Any]:
        """Check if Chrome is running on CDP port."""
        try:
            import urllib.request
            url = f"http://localhost:{self.cdp_port}/json"
            with urllib.request.urlopen(url, timeout=3) as resp:
                tabs = json.loads(resp.read())
                bot_tabs = [
                    t for t in tabs
                    if "/tmp/heypiggy" in t.get("webSocketDebuggerUrl", "")
                    or "heypiggy" in t.get("title", "").lower()
                ]
                return {
                    "running": len(bot_tabs) > 0,
                    "tabs": len(bot_tabs),
                    "port": self.cdp_port,
                }
        except Exception:
            return {"running": False, "tabs": 0, "port": self.cdp_port}

    def _check_sessions(self) -> Dict[str, Any]:
        """Check session registry for corruption."""
        corrupted: List[str] = []
        if SESSIONS_FILE.exists():
            try:
                with open(SESSIONS_FILE) as f:
                    sessions = json.load(f)
                for entry in sessions if isinstance(sessions, list) else []:
                    path = entry.get("profile_path") or entry.get("path", "")
                    if path and is_session_corrupted(Path(path)):
                        corrupted.append(str(path))
            except (json.JSONDecodeError, OSError):
                corrupted.append(str(SESSIONS_FILE))
        return {
            "sessions_file_exists": SESSIONS_FILE.exists(),
            "corrupted_sessions": corrupted,
            "corrupted_count": len(corrupted),
        }

    def to_dict(self) -> Dict[str, Any]:
        """Generate full health snapshot."""
        daemon = self._check_daemon()
        chrome = self._check_chrome()
        sessions = self._check_sessions()

        self.issues = []
        if not daemon["running"]:
            self.issues.append("cua-driver daemon not running")
        if not chrome["running"]:
            self.issues.append("Chrome not running on port " + str(self.cdp_port))
        if sessions["corrupted_count"] > 0:
            self.issues.append(f"{sessions['corrupted_count']} corrupted session(s)")

        return {
            "ts": __import__("datetime").datetime.now().isoformat(),
            "healthy": self.is_healthy(),
            "issues": self.issues,
            "daemon": daemon,
            "chrome": chrome,
            "sessions": sessions,
        }

    def is_healthy(self) -> bool:
        """Return True if all subsystems are operational."""
        snapshot = self.to_dict()
        return len(snapshot["issues"]) == 0


def check_and_alert() -> Optional[Dict[str, Any]]:
    """Check health and return snapshot. Prints alerts for issues.

    Returns:
        Health snapshot dict, or None if check failed
    """
    health = RuntimeHealth()
    snapshot = health.to_dict()
    if not snapshot["healthy"]:
        import sys
        for issue in snapshot["issues"]:
            print(f"[HEALTH] ⚠️  {issue}", file=sys.stderr, flush=True)
    return snapshot