"""===============================================================================
SURVEY DAEMON — Persistent survey runner with auto-recovery
===============================================================================

Usage:
    python -m survey.daemon run       # Start daemon (blocks)
    python -m survey.daemon status    # Show daemon status
    python -m survey.daemon stop      # Stop daemon
    python -m survey.daemon restart   # Restart daemon

Lifecycle:
    [START] → verify_chrome() → verify_login() → [LOOP]
                                              ↓
                        ┌─ survey.run() → success → balance += earn
                        ├─ survey.run() → error   → log + continue
                        ├─ login broken            → auto_relogin()
                        ├─ chrome dead             → restart_chrome()
                        └─ max_surveys reached     → shutdown

Auto-recovery:
    - Chrome on wrong port → relaunch on 9999
    - Not logged in → google_login()
    - Survey tab dead → create new tab + retry
    - Session stale → restart session + continue

CRITICAL RULES:
    - NEVER kill user Chrome (no pkill, no killall on generic patterns)
    - Chrome flags: --force-renderer-accessibility + --remote-allow-origins="*"
    - Daemon state persisted in ~/.stealth/daemon_state.json
    - Logs in survey/logs/daemon/*.jsonl

===============================================================================

BANNED METHODS — NIEMALS VERWENDEN (siehe /banned.md):
  ❌ playstealth launch — setzt NICHT --force-renderer-accessibility
  ❌ webauto-nodriver — ABSOLUT BANNED
  ❌ cua-driver click (raw index) — instabil, nutze tool_click.py
  ❌ --remote-allow-origins=* (ohne Quotes) — zsh glob expansion
  ❌ /tmp/heypiggy-bot (fixed profile) — korruptiert nach Neustart
  ❌ Hardcoded PIDs — dynamisch, niemals hardcodieren
  ❌ pkill -f "Google Chrome" — tötet USER Chrome
  ❌ killall Google Chrome — tötet ALLE Chrome
  ❌ skylight-cli click --element-index — Index instabil

KORREKT:
  ✅ --remote-allow-origins="*" (MIT Anführungszeichen)
  ✅ --user-data-dir="/tmp/heypiggy-new-$(date +%s)"
  ✅ --force-renderer-accessibility
  ✅ NUR tool_*.py verwenden (nicht rohes cua-driver)
==============================================================================="""

import atexit
import json
import os
import signal
import subprocess
import sys
import threading
import time
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

# ── Paths ───────────────────────────────────────────────────────────────────

STEALTH_DIR = Path.home() / ".stealth"
STEALTH_DIR.mkdir(exist_ok=True)
DAEMON_STATE_FILE = STEALTH_DIR / "daemon_state.json"
LOG_DIR = Path(__file__).parent / "logs" / "daemon"
LOG_DIR.mkdir(parents=True, exist_ok=True)

PID_FILE = STEALTH_DIR / "daemon.pid"

# ── Constants ───────────────────────────────────────────────────────────────

CHROME_PORT = 9223
HEYPIGGY_URL = "https://www.heypiggy.com/?page=dashboard"
MAX_CONSECUTIVE_ERRORS = 3
MAX_SURVEYS_PER_RUN = 10
HEARTBEAT_INTERVAL = 30  # seconds


# ═══════════════════════════════════════════════════════════════════════════
# STATE MANAGEMENT
# ═══════════════════════════════════════════════════════════════════════════

def load_state() -> Dict:
    try:
        with open(DAEMON_STATE_FILE) as f:
            return json.load(f)
    except Exception:
        return {"started_at": None, "surveys_completed": 0,
                "balance": 0.0, "last_error": None, "running": False}


def save_state(state: Dict) -> None:
    with open(DAEMON_STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


# ═══════════════════════════════════════════════════════════════════════════
# LOGGING
# ═══════════════════════════════════════════════════════════════════════════

def log(event: str, data: Optional[Dict] = None) -> None:
    entry = {
        "ts": datetime.now().isoformat(),
        "event": event,
        "data": data or {}
    }
    log_file = LOG_DIR / f"{datetime.now():%Y-%m-%d}.jsonl"
    with open(log_file, "a") as f:
        f.write(json.dumps(entry) + "\n")
    print(f"[DAEMON {datetime.now():%H:%M:%S}] {event}: {data or {}}")


# ═══════════════════════════════════════════════════════════════════════════
# CHROME LIFECYCLE
# ═══════════════════════════════════════════════════════════════════════════

def is_chrome_alive(port: int = CHROME_PORT) -> bool:
    try:
        urllib.request.urlopen(f"http://127.0.0.1:{port}/json", timeout=3)
        return True
    except Exception:
        return False


def find_dashboard_pid(port: int = CHROME_PORT) -> Optional[int]:
    try:
        pages = json.loads(urllib.request.urlopen(
            f"http://127.0.0.1:{port}/json", timeout=3).read())
        for p in pages:
            if "dashboard" in p.get("url", "").lower():
                return p.get("id")  # CDP targetId (not OS PID)
        return None
    except Exception:
        return None


def get_balance(port: int = CHROME_PORT) -> Optional[float]:
    """CDP: Get balance from dashboard body text."""
    try:
        import websocket
        pages = json.loads(urllib.request.urlopen(
            f"http://127.0.0.1:{port}/json", timeout=3).read())
        for p in pages:
            if "dashboard" in p.get("url", "").lower():
                ws = websocket.create_connection(
                    p["webSocketDebuggerUrl"], timeout=10)
                ws.send(json.dumps({"id": 0, "method": "Runtime.evaluate",
                    "params": {"expression": "document.body.innerText"}}))
                r = json.loads(ws.recv()); ws.close()  # noqa: E702
                text = r.get("result", {}).get("result", {}).get("value", "")
                import re
                m = re.search(r'([\d.,]+)\s*€', text)
                if m:
                    return float(m.group(1).replace(",", "."))
        return None
    except Exception:
        return None


def is_logged_in(port: int = CHROME_PORT) -> bool:
    """CDP: Check if dashboard shows 'Abmelden' (logged in) or 'Anmelden' (not)."""
    try:
        import websocket
        pages = json.loads(urllib.request.urlopen(
            f"http://127.0.0.1:{port}/json", timeout=3).read())
        for p in pages:
            if "dashboard" in p.get("url", "").lower():
                ws = websocket.create_connection(
                    p["webSocketDebuggerUrl"], timeout=10)
                ws.send(json.dumps({"id": 0, "method": "Runtime.evaluate",
                    "params": {"expression": "document.body.innerText"}}))
                r = json.loads(ws.recv()); ws.close()  # noqa: E702
                text = r.get("result", {}).get("result", {}).get("value", "")
                return "Abmelden" in text
        return False
    except Exception:
        return False


def launch_chrome(url: str = HEYPIGGY_URL, port: int = CHROME_PORT) -> bool:
    """DEPRECATED: Use ChromeLauncher.launch_and_verify() instead."""
    from survey.chrome import ChromeLauncher
    result = ChromeLauncher(port=port).launch_and_verify(url=url)
    return result.get("ok", False)


# ═══════════════════════════════════════════════════════════════════════════
# LOGIN
# ═══════════════════════════════════════════════════════════════════════════

def ensure_login(port: int = CHROME_PORT) -> bool:
    """Check + auto-login if needed. Returns True if logged in."""
    if is_logged_in(port):
        return True

    print("[DAEMON] Not logged in — running google_login...")
    try:
        # Robuster Import: Workspace-Root in sys.path einfügen
        # (daemon.py läuft aus survey-cli/survey/, cli/modules ist auf stealth-runner/)
        import sys
        from pathlib import Path
        _root = str(Path(__file__).parent.parent.parent)
        if _root not in sys.path:
            sys.path.insert(0, _root)
        from cli.modules.auto_google_login import execute as google_login
        result = google_login()
        logged_in = result.get("status") == "ok"
        if logged_in:
            log("login_success")
        else:
            log("login_failed", {"reason": result.get("reason")})
        return logged_in
    except Exception as e:
        log("login_error", {"error": str(e)[:200]})
        return False


# ═══════════════════════════════════════════════════════════════════════════
# CUA-DRIVER DAEMON MANAGER — state machine + auto-recovery
# ═══════════════════════════════════════════════════════════════════════════

CUA_DAEMON_STATE_FILE = STEALTH_DIR / "cua_daemon_state.json"
CUA_DAEMON_LOG = "/tmp/cua-daemon.log"
CUA_DAEMON_MAX_RESTART_INTERVAL = 60  # seconds — cap on backoff
CUA_DAEMON_HEALTH_TIMEOUT = 5  # seconds — timeout for list_windows check


class DaemonManager:
    """Manages cua-driver daemon with state machine and auto-recovery.

    State machine: STOPPED → STARTING → HEALTHY → DEGRADED → FAILED

    - STOPPED:   No process running, no state file, intentional stop
    - STARTING:  Process launched, waiting for readiness
    - HEALTHY:   list_windows returns valid windows within timeout
    - DEGRADED:  Process running but list_windows slow/unreliable
    - FAILED:    Process crashed, unreachable, or stuck

    WARUM separate von SessionManager?
      SessionManager managed Chrome (Browser). DaemonManager managed cua-driver
      (Accessibility Daemon). Zwei verschiedene Prozesse, zwei verschiedene
      Lifecycles. cua-driver ist Legacy-Fallback, aber KRITISCH für Login.
    """

    STATE_STOPPED = "STOPPED"
    STATE_STARTING = "STARTING"
    STATE_HEALTHY = "HEALTHY"
    STATE_DEGRADED = "DEGRADED"
    STATE_FAILED = "FAILED"

    def __init__(self):
        self.state = self._load_state()
        self._consecutive_failures = 0
        self._last_restart_time = 0.0

    def _load_state(self) -> str:
        try:
            with open(CUA_DAEMON_STATE_FILE) as f:
                data = json.load(f)
                return data.get("state", self.STATE_STOPPED)
        except Exception:
            return self.STATE_STOPPED

    def _save_state(self):
        STEALTH_DIR.mkdir(exist_ok=True)
        with open(CUA_DAEMON_STATE_FILE, "w") as f:
            json.dump({"state": self.state,
                       "consecutive_failures": self._consecutive_failures,
                       "updated_at": datetime.now().isoformat()}, f, indent=2)

    def _is_process_alive(self) -> bool:
        try:
            result = subprocess.run(
                ["pgrep", "-f", "cua-driver serve"],
                capture_output=True, text=True, timeout=5)
            return result.returncode == 0 and bool(result.stdout.strip())
        except Exception:
            return False

    def start(self) -> bool:
        if self._is_process_alive():
            log("cua_daemon", {"msg": "Already running", "state": self.state})
            self.state = self.STATE_HEALTHY
            self._save_state()
            return True

        self.state = self.STATE_STARTING
        self._save_state()
        log("cua_daemon", {"msg": "Starting daemon"})

        try:
            subprocess.Popen(
                ["nohup", "cua-driver", "serve"],
                stdout=open(CUA_DAEMON_LOG, "a"),
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
        except Exception as e:
            self.state = self.STATE_FAILED
            self._save_state()
            log("cua_daemon_error", {"error": str(e)[:200]})
            return False

        time.sleep(2)
        if self._is_process_alive():
            self.state = self.STATE_HEALTHY
            self._consecutive_failures = 0
            self._save_state()
            log("cua_daemon", {"msg": "Started successfully", "state": self.STATE_HEALTHY})
            return True
        else:
            self.state = self.STATE_FAILED
            self._save_state()
            log("cua_daemon_error", {"msg": "Process not found after launch"})
            return False

    def stop(self) -> bool:
        if not self._is_process_alive():
            self.state = self.STATE_STOPPED
            self._save_state()
            return True

        try:
            subprocess.run(["pkill", "-f", "cua-driver serve"], timeout=5, capture_output=True)
            time.sleep(1)
            if not self._is_process_alive():
                self.state = self.STATE_STOPPED
                self._save_state()
                log("cua_daemon", {"msg": "Stopped"})
                return True
        except Exception:
            pass

        subprocess.run(["pkill", "-9", "-f", "cua-driver serve"], timeout=5, capture_output=True)
        self.state = self.STATE_STOPPED
        self._save_state()
        return True

    def health_check(self) -> Dict:
        if not self._is_process_alive():
            self.state = self.STATE_FAILED
            self._save_state()
            return {"healthy": False, "state": self.STATE_FAILED,
                    "reason": "process_not_found"}

        try:
            result = subprocess.run(
                ["cua-driver", "call", "list_windows"],
                capture_output=True, text=True, timeout=CUA_DAEMON_HEALTH_TIMEOUT)
            if result.returncode != 0:
                self.state = self.STATE_DEGRADED
                self._save_state()
                return {"healthy": False, "state": self.STATE_DEGRADED,
                        "reason": f"exit_code={result.returncode}"}
            data = json.loads(result.stdout)
            if not data.get("windows"):
                self.state = self.STATE_DEGRADED
                self._save_state()
                return {"healthy": False, "state": self.STATE_DEGRADED,
                        "reason": "no_windows_returned"}
            self.state = self.STATE_HEALTHY
            self._consecutive_failures = 0
            self._save_state()
            return {"healthy": True, "state": self.STATE_HEALTHY,
                    "windows_count": len(data["windows"])}
        except subprocess.TimeoutExpired:
            self.state = self.STATE_DEGRADED
            self._save_state()
            return {"healthy": False, "state": self.STATE_DEGRADED,
                    "reason": "health_check_timeout"}
        except json.JSONDecodeError:
            self.state = self.STATE_DEGRADED
            self._save_state()
            return {"healthy": False, "state": self.STATE_DEGRADED,
                    "reason": "invalid_json_response"}
        except Exception as e:
            self.state = self.STATE_FAILED
            self._save_state()
            return {"healthy": False, "state": self.STATE_FAILED,
                    "reason": f"exception: {str(e)[:100]}"}

    def ensure_running(self) -> bool:
        health = self.health_check()
        if health["healthy"]:
            return True

        self._consecutive_failures += 1
        log("cua_daemon", {"msg": "Not healthy — restarting",
                           "state": health.get("state"),
                           "reason": health.get("reason"),
                           "failures": self._consecutive_failures})

        now = time.time()
        if now - self._last_restart_time < 10:
            time.sleep(5)

        backoff = min(2 ** self._consecutive_failures, CUA_DAEMON_MAX_RESTART_INTERVAL)
        time.sleep(min(backoff, 30))

        self.stop()
        time.sleep(2)
        self._last_restart_time = time.time()
        return self.start()

    def heartbeat(self) -> Dict:
        chrome_ok = is_chrome_alive()
        health = self.health_check()
        return {
            "chrome": "ok" if chrome_ok else "dead",
            "cua_daemon": health.get("state", "UNKNOWN"),
            "cua_healthy": health.get("healthy", False),
            "surveys_completed": load_state().get("surveys_completed", 0),
            "ts": datetime.now().isoformat(),
        }


# ═══════════════════════════════════════════════════════════════════════════
# SURVEY RUN
# ═══════════════════════════════════════════════════════════════════════════

def run_survey_batch(max_surveys: int = 3, port: int = CHROME_PORT) -> Dict:
    """Run up to max_surveys surveys. Returns summary."""
    from survey.runner import run_survey, detect_available_surveys

    results = []
    available = detect_available_surveys(port=port)

    if not available:
        log("no_surveys")
        return {"status": "ok", "surveys": [], "message": "No surveys available"}

    for i, survey_id in enumerate(available[:max_surveys]):
        log("survey_start", {"survey_id": survey_id, "index": i+1})
        try:
            result = run_survey(survey_id, port=port)
            results.append(result)
            log("survey_done", {"survey_id": survey_id, "result": result.get("status")})
        except Exception as e:
            log("survey_error", {"survey_id": survey_id, "error": str(e)[:200]})
            results.append({"status": "error", "survey_id": survey_id, "error": str(e)})

    return {"status": "ok", "surveys": results}


# ═══════════════════════════════════════════════════════════════════════════
# HEARTBEAT + RECOVERY
# ═══════════════════════════════════════════════════════════════════════════

class DaemonProcess:
    def __init__(self):
        self.running = False
        self.consecutive_errors = 0
        self.surveys_completed = 0
        self._stop_event = threading.Event()
        self.cua_manager = DaemonManager()

    def verify_chrome(self) -> bool:
        if not is_chrome_alive():
            print("[DAEMON] Chrome dead — relaunching via ChromeLauncher...")
            log("chrome_relaunch")
            from survey.chrome import ChromeLauncher
            result = ChromeLauncher(port=CHROME_PORT).launch_and_verify(
                url=HEYPIGGY_URL)
            return result.get("ok", False)
        return True

    def verify_cua_daemon(self) -> bool:
        if not self.cua_manager._is_process_alive():
            print("[DAEMON] cua-driver daemon not running — starting...")
            log("cua_daemon", {"msg": "Not running, starting"})
            return self.cua_manager.ensure_running()
        health = self.cua_manager.health_check()
        if not health.get("healthy"):
            print(f"[DAEMON] cua-driver degraded: {health.get('reason')} — restarting...")
            log("cua_daemon", {"msg": "Degraded, restarting", "health": health})
            return self.cua_manager.ensure_running()
        return True

    def verify_login(self) -> bool:
        """Ensure user is logged in."""
        if not is_logged_in():
            print("[DAEMON] Session expired — re-logging in...")
            log("session_relogin")
            return ensure_login()
        return True

    def heartbeat(self) -> Dict:
        """Health check. Returns status dict."""
        chrome_ok = is_chrome_alive()
        logged_in = is_logged_in() if chrome_ok else False
        balance = get_balance() if logged_in else None
        cua_health = self.cua_manager.health_check()
        return {
            "chrome": "ok" if chrome_ok else "dead",
            "logged_in": logged_in,
            "balance": balance,
            "surveys_completed": self.surveys_completed,
            "consecutive_errors": self.consecutive_errors,
            "running": self.running,
            "cua_daemon": cua_health.get("state", "UNKNOWN"),
            "cua_healthy": cua_health.get("healthy", False),
            "ts": datetime.now().isoformat(),
        }

    def run_loop(self, max_surveys: int = MAX_SURVEYS_PER_RUN) -> None:
        """Main loop: verify → run surveys → sleep → repeat."""
        self.running = True
        save_state({"running": True, "started_at": datetime.now().isoformat()})

        while not self._stop_event.is_set():
            try:
                if not self.verify_chrome():
                    self.consecutive_errors += 1
                    time.sleep(10)
                    continue

                if not self.verify_cua_daemon():
                    self.consecutive_errors += 1
                    if self.consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
                        log("max_errors_reached", {"errors": self.consecutive_errors})
                        break
                    time.sleep(10)
                    continue

                if not self.verify_login():
                    self.consecutive_errors += 1
                    if self.consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
                        log("max_errors_reached", {"errors": self.consecutive_errors})
                        break
                    time.sleep(15)
                    continue

                # Reset error counter on successful login
                self.consecutive_errors = 0

                # Run survey batch
                result = run_survey_batch(max_surveys=2, port=CHROME_PORT)
                surveys = result.get("surveys", [])
                self.surveys_completed += len([s for s in surveys if s.get("status") == "ok"])

                # Save state
                state = load_state()
                state["surveys_completed"] = self.surveys_completed
                state["balance"] = get_balance() or state.get("balance", 0)
                state["last_run"] = datetime.now().isoformat()
                save_state(state)

                # Sleep before next batch
                log("batch_complete", {
                    "surveys_run": len(surveys),
                    "total_completed": self.surveys_completed
                })
                time.sleep(300)  # 5 min between batches

            except Exception as e:
                log("loop_error", {"error": str(e)[:200]})
                self.consecutive_errors += 1
                time.sleep(30)

        self.running = False
        save_state({"running": False, "stopped_at": datetime.now().isoformat(),
                    "surveys_completed": self.surveys_completed})
        log("daemon_stopped", {"surveys_completed": self.surveys_completed})

    def stop(self) -> None:
        """Signal daemon to stop gracefully."""
        self._stop_event.set()
        self.running = False
        print("[DAEMON] Stop signal sent")


# ═══════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════

def status() -> None:
    state = load_state()
    health = DaemonProcess().heartbeat()
    print(json.dumps({"state": state, "health": health}, indent=2))


def stop() -> None:
    pid_file = PID_FILE
    if pid_file.exists():
        pid = int(pid_file.read_text().strip())
        try:
            os.kill(pid, signal.SIGTERM)
            print(f"[DAEMON] Stopped PID={pid}")
        except Exception as e:
            print(f"[DAEMON] Cannot kill PID={pid}: {e}")
    else:
        print("[DAEMON] No PID file — daemon not running")


def start_daemon() -> None:
    """Fork daemon process (background)."""
    # Check if already running
    if PID_FILE.exists():
        pid = int(PID_FILE.read_text().strip())
        try:
            os.kill(pid, 0)
            print(f"[DAEMON] Already running PID={pid}")
            return
        except Exception:
            pass  # PID is stale

    log("daemon_start")
    pid = os.fork()
    if pid == 0:
        # Child: become session leader, run loop
        os.setsid()
        signal.signal(signal.SIGTERM, lambda *args: sys.exit(0))
        atexit.register(_cleanup)
        daemon = DaemonProcess()
        PID_FILE.write_text(str(os.getpid()))
        try:
            daemon.run_loop()
        finally:
            _cleanup()
    else:
        # Parent: verify started
        time.sleep(3)
        if PID_FILE.exists():
            print(f"[DAEMON] Started PID={pid}")
        else:
            print("[DAEMON] Failed to start")


def _cleanup() -> None:
    try:
        os.remove(PID_FILE)
    except Exception:
        pass


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"

    if cmd == "run":
        daemon = DaemonProcess()
        daemon.run_loop()
    elif cmd == "start":
        start_daemon()
    elif cmd == "stop":
        stop()
    elif cmd == "restart":
        stop()
        time.sleep(2)
        start_daemon()
    elif cmd == "status":
        status()
    else:
        print("Usage: python -m survey.daemon [run|start|stop|restart|status]")
