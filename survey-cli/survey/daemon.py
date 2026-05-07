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

CHROME_PORT = 9999
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
                r = json.loads(ws.recv()); ws.close()
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
                r = json.loads(ws.recv()); ws.close()
                text = r.get("result", {}).get("result", {}).get("value", "")
                return "Abmelden" in text
        return False
    except Exception:
        return False


def launch_chrome(url: str = HEYPIGGY_URL, port: int = CHROME_PORT) -> bool:
    """Launch Chrome with BOTH flags. Blocks 8s for startup."""
    # Kill existing bot chrome first
    _kill_bot_chrome()

    cmd = [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        f"--remote-debugging-port={port}",
        "--remote-allow-origins=*",
        "--force-renderer-accessibility",
        "--no-first-run",
        "--no-default-browser-check",
        f"--user-data-dir=/tmp/heypiggy-new-{int(time.time())}",
        url,
    ]
    subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print(f"[DAEMON] Chrome launched: port={port}")
    time.sleep(8)
    return is_chrome_alive(port)


def _kill_bot_chrome() -> None:
    """Kill ONLY bot Chrome (profile /tmp/heypiggy-new-*). NEVER user Chrome."""
    try:
        result = subprocess.run(["ps", "aux"], capture_output=True, text=True, timeout=5)
        for line in result.stdout.split("\n"):
            if "/tmp/heypiggy-new-" in line and "/Contents/MacOS/Google Chrome" in line:
                parts = line.split()
                if parts and parts[1].isdigit():
                    pid = int(parts[1])
                    try:
                        os.kill(pid, 9)
                        print(f"[DAEMON] Killed bot Chrome PID={pid}")
                    except Exception:
                        pass
    except Exception:
        pass


# ═══════════════════════════════════════════════════════════════════════════
# LOGIN
# ═══════════════════════════════════════════════════════════════════════════

def ensure_login(port: int = CHROME_PORT) -> bool:
    """Check + auto-login if needed. Returns True if logged in."""
    if is_logged_in(port):
        return True

    print("[DAEMON] Not logged in — running google_login...")
    try:
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

    def verify_chrome(self) -> bool:
        """Ensure Chrome is alive on port 9999."""
        if not is_chrome_alive():
            print("[DAEMON] Chrome dead — relaunching...")
            log("chrome_relaunch")
            return launch_chrome()
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
        return {
            "chrome": "ok" if chrome_ok else "dead",
            "logged_in": logged_in,
            "balance": balance,
            "surveys_completed": self.surveys_completed,
            "consecutive_errors": self.consecutive_errors,
            "running": self.running,
            "ts": datetime.now().isoformat(),
        }

    def run_loop(self, max_surveys: int = MAX_SURVEYS_PER_RUN) -> None:
        """Main loop: verify → run surveys → sleep → repeat."""
        self.running = True
        save_state({"running": True, "started_at": datetime.now().isoformat()})

        while not self._stop_event.is_set():
            try:
                # Verify invariants
                if not self.verify_chrome():
                    self.consecutive_errors += 1
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
        print(f"Usage: python -m survey.daemon [run|start|stop|restart|status]")