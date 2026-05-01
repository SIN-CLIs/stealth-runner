"""
Chrome Health-Check und Recovery.
"""
import time
import logging
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any

try:
    import psutil
except ImportError:
    raise ImportError("psutil required. Install: python3 -m pip install --break-system-packages psutil")

logger = logging.getLogger("security")


def is_chrome_running(pid: int) -> bool:
    """Prüft, ob Chrome-Prozess noch läuft."""
    try:
        return psutil.pid_exists(pid) and any(
            "chrome" in proc.name().lower() and proc.pid == pid
            for proc in psutil.process_iter(['name', 'pid'])
        )
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return False


def relaunch_chrome(url: str, old_pid: Optional[int] = None) -> int:
    """Startet Chrome neu und gibt Haupt-PID zurück."""
    if old_pid:
        try:
            psutil.Process(old_pid).terminate()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    timestamp = int(time.time())
    profile_dir = f"/tmp/heypiggy-bot-{timestamp}"
    cmd = [
        "open", "-a", "Google Chrome",
        "--args",
        f"--user-data-dir={profile_dir}",
        "--new-window",
        url,
        "--remote-debugging-port=9222"
    ]

    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    logger.warning(f"Chrome neu gestartet! Haupt-PID: {process.pid}, Profil: {profile_dir}")
    
    # Warte kurz, damit Prozess sicher gestartet ist
    time.sleep(2)
    
    # Fallback: Falls psutil den Prozess nicht findet, gebe trotzdem die Popen-PID zurück
    if not is_chrome_running(process.pid):
        logger.warning(f"Haupt-PID {process.pid} nicht in psutil gefunden! Nutze trotzdem diese PID.")
    
    return process.pid


def chrome_health_check(state: Dict[str, Any]) -> Dict[str, Any]:
    """Führt Health-Check durch und startet Chrome neu falls nötig."""
    pid = state.get("pid")
    url = state.get("url")

    if pid and not is_chrome_running(pid):
        logger.error(f"Chrome (PID {pid}) abgestürzt! Starte neu...")
        new_pid = relaunch_chrome(url, pid)
        state["pid"] = new_pid
        return {"status": "recovered", "pid": new_pid}

    return {"status": "healthy", "pid": pid}
