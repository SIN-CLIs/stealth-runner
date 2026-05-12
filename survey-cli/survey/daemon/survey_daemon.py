"""
SurveyDaemon - macOS LaunchAgent daemon for 24/7 survey automation.

Features:
    - Auto-start on boot
    - Crash recovery with state persistence
    - Health monitoring endpoint
    - Graceful shutdown handling

Usage:
    daemon = SurveyDaemon()
    daemon.start()  # Runs forever until SIGTERM
"""

# ruff: noqa: E501  # CSS selectors / argparse help / log strings — wrapping changes semantics
from __future__ import annotations

import asyncio
import json
import logging
import os
import signal
import socket
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from .survey_agent_graph import SurveyAgentGraph, Persona

logger = logging.getLogger(__name__)

# Configuration
DEFAULT_CONFIG_PATH = Path("~/.survey_agent/config.json").expanduser()
DEFAULT_STATE_PATH = Path("~/.survey_agent/state.db").expanduser()
DEFAULT_LOG_PATH = Path("~/.survey_agent/logs").expanduser()
DEFAULT_PID_PATH = Path("~/.survey_agent/daemon.pid").expanduser()
HEALTH_CHECK_PORT = 9847


class SurveyDaemon:
    """
    24/7 Survey completion daemon with macOS LaunchAgent support.

    The daemon:
    1. Fetches available surveys from configured sources
    2. Runs them through the SurveyAgentGraph
    3. Tracks earnings and completion stats
    4. Handles crashes and auto-recovery
    """

    def __init__(
        self,
        config_path: Path | str = DEFAULT_CONFIG_PATH,
        state_path: Path | str = DEFAULT_STATE_PATH,
        log_path: Path | str = DEFAULT_LOG_PATH,
    ):
        self.config_path = Path(config_path).expanduser()
        self.state_path = Path(state_path).expanduser()
        self.log_path = Path(log_path).expanduser()

        self._running = False
        self._shutdown_event = asyncio.Event()
        self._config = self._load_config()
        self._agent: SurveyAgentGraph | None = None
        self._health_server: asyncio.Server | None = None

        self._setup_logging()
        self._setup_signal_handlers()

    def _load_config(self) -> dict[str, Any]:
        """Load configuration from JSON file."""
        default_config = {
            "persona": {
                "age": 32,
                "gender": "male",
                "income_bracket": "50k-75k",
                "education": "bachelors",
                "occupation": "software_developer",
                "location": "US",
                "interests": ["technology", "gaming", "travel"],
            },
            "survey_sources": [
                {"name": "swagbucks", "enabled": False, "api_key": ""},
                {"name": "prolific", "enabled": False, "api_key": ""},
            ],
            "captcha": {
                "provider": "2captcha",
                "api_key": "",
            },
            "proxy": {
                "enabled": False,
                "rotation_interval": 300,
                "provider": "",
            },
            "limits": {
                "max_concurrent_surveys": 1,
                "min_delay_between_surveys": 60,
                "max_surveys_per_hour": 10,
                "working_hours": {"start": 8, "end": 22},
            },
            "notifications": {
                "enabled": False,
                "webhook_url": "",
            },
        }

        if self.config_path.exists():
            with open(self.config_path) as f:
                user_config = json.load(f)
                default_config.update(user_config)
        else:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_path, "w") as f:
                json.dump(default_config, f, indent=2)

        return default_config

    def _setup_logging(self) -> None:
        """Configure logging to file and console."""
        self.log_path.mkdir(parents=True, exist_ok=True)
        log_file = self.log_path / f"daemon_{datetime.now():%Y%m%d}.log"

        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler(sys.stdout),
            ],
        )

    def _setup_signal_handlers(self) -> None:
        """Setup graceful shutdown on SIGTERM/SIGINT."""

        def handle_shutdown(signum, frame):
            logger.info(f"Received signal {signum}, initiating shutdown...")
            self._running = False
            self._shutdown_event.set()

        signal.signal(signal.SIGTERM, handle_shutdown)
        signal.signal(signal.SIGINT, handle_shutdown)

    def _write_pid(self) -> None:
        """Write PID file for process management."""
        DEFAULT_PID_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(DEFAULT_PID_PATH, "w") as f:
            f.write(str(os.getpid()))

    def _remove_pid(self) -> None:
        """Remove PID file on shutdown."""
        if DEFAULT_PID_PATH.exists():
            DEFAULT_PID_PATH.unlink()

    async def _start_health_server(self) -> None:
        """Start health check HTTP server."""

        async def handle_health(reader, writer):
            await reader.read(1024)

            stats = self._agent.get_stats() if self._agent else {}
            response_body = json.dumps(
                {
                    "status": "running" if self._running else "stopping",
                    "uptime_seconds": (datetime.now() - self._start_time).total_seconds(),
                    "stats": stats,
                }
            )

            response = (
                f"HTTP/1.1 200 OK\r\n"
                f"Content-Type: application/json\r\n"
                f"Content-Length: {len(response_body)}\r\n"
                f"\r\n"
                f"{response_body}"
            )

            writer.write(response.encode())
            await writer.drain()
            writer.close()

        try:
            self._health_server = await asyncio.start_server(
                handle_health, "127.0.0.1", HEALTH_CHECK_PORT
            )
            logger.info(f"Health server started on port {HEALTH_CHECK_PORT}")
        except OSError as e:
            logger.warning(f"Could not start health server: {e}")

    async def _fetch_available_surveys(self) -> list[dict]:
        """Fetch available surveys from configured sources."""
        surveys = []

        for source in self._config["survey_sources"]:
            if not source["enabled"]:
                continue

            # TODO: Implement actual API calls to survey sources
            logger.info(f"Checking {source['name']} for available surveys...")

        return surveys

    async def _run_survey_loop(self) -> None:
        """Main survey processing loop."""
        persona_config = self._config["persona"]
        persona = Persona(
            age=persona_config["age"],
            gender=persona_config["gender"],
            income_bracket=persona_config["income_bracket"],
            education=persona_config["education"],
            occupation=persona_config["occupation"],
            location=persona_config["location"],
            interests=persona_config.get("interests", []),
        )

        self._agent = SurveyAgentGraph(
            persona=persona,
            db_path=self.state_path,
            captcha_api_key=self._config["captcha"].get("api_key"),
        )

        limits = self._config["limits"]
        min_delay = limits["min_delay_between_surveys"]

        while self._running:
            try:
                # Check working hours
                current_hour = datetime.now().hour
                if not (
                    limits["working_hours"]["start"]
                    <= current_hour
                    < limits["working_hours"]["end"]
                ):
                    logger.info("Outside working hours, sleeping...")
                    await asyncio.sleep(300)
                    continue

                # Fetch available surveys
                surveys = await self._fetch_available_surveys()

                if not surveys:
                    logger.info("No surveys available, waiting...")
                    await asyncio.sleep(60)
                    continue

                # Process highest priority survey
                survey = surveys[0]
                logger.info(f"Starting survey: {survey.get('url', 'unknown')}")

                result = await self._agent.run(survey["url"])

                if result["status"] == "completed":
                    logger.info(f"Survey completed! Earnings: ${result.get('earnings', 0):.2f}")
                else:
                    logger.warning(f"Survey ended with status: {result['status']}")

                # Respect rate limits
                await asyncio.sleep(min_delay)

            except Exception as e:
                logger.exception(f"Error in survey loop: {e}")
                await asyncio.sleep(60)

    async def _run(self) -> None:
        """Async entry point."""
        self._running = True
        self._start_time = datetime.now()
        self._write_pid()

        logger.info("Survey Daemon starting...")
        logger.info(f"Config: {self.config_path}")
        logger.info(f"State DB: {self.state_path}")
        logger.info(f"Logs: {self.log_path}")

        # Start health server
        await self._start_health_server()

        # Run main loop
        try:
            await self._run_survey_loop()
        finally:
            if self._health_server:
                self._health_server.close()
            self._remove_pid()
            logger.info("Survey Daemon stopped.")

    def start(self) -> None:
        """Start the daemon (blocking)."""
        asyncio.run(self._run())

    def stop(self) -> None:
        """Request daemon shutdown."""
        self._running = False
        self._shutdown_event.set()

    @staticmethod
    def is_running() -> bool:
        """Check if daemon is currently running."""
        if not DEFAULT_PID_PATH.exists():
            return False

        try:
            with open(DEFAULT_PID_PATH) as f:
                pid = int(f.read().strip())
            os.kill(pid, 0)
            return True
        except (OSError, ValueError):
            return False

    @staticmethod
    def get_status() -> dict:
        """Get daemon status via health endpoint."""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            sock.connect(("127.0.0.1", HEALTH_CHECK_PORT))
            sock.sendall(b"GET /health HTTP/1.1\r\nHost: localhost\r\n\r\n")
            response = sock.recv(4096).decode()
            sock.close()

            body = response.split("\r\n\r\n", 1)[1]
            return json.loads(body)
        except Exception:
            return {"status": "not_running"}


def install_launchagent() -> Path:
    """
    Install macOS LaunchAgent for auto-start on boot.

    Returns:
        Path to installed plist file
    """
    plist_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.stealth-runner.survey-daemon</string>

    <key>ProgramArguments</key>
    <array>
        <string>{sys.executable}</string>
        <string>-m</string>
        <string>survey.daemon</string>
        <string>start</string>
    </array>

    <key>RunAtLoad</key>
    <true/>

    <key>KeepAlive</key>
    <dict>
        <key>SuccessfulExit</key>
        <false/>
    </dict>

    <key>WorkingDirectory</key>
    <string>{Path.cwd()}</string>

    <key>StandardOutPath</key>
    <string>{DEFAULT_LOG_PATH}/stdout.log</string>

    <key>StandardErrorPath</key>
    <string>{DEFAULT_LOG_PATH}/stderr.log</string>

    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/usr/local/bin:/usr/bin:/bin</string>
    </dict>
</dict>
</plist>
"""

    plist_path = Path("~/Library/LaunchAgents/com.stealth-runner.survey-daemon.plist").expanduser()
    plist_path.parent.mkdir(parents=True, exist_ok=True)

    with open(plist_path, "w") as f:
        f.write(plist_content)

    logger.info(f"LaunchAgent installed: {plist_path}")
    logger.info(
        "Run: launchctl load -w ~/Library/LaunchAgents/com.stealth-runner.survey-daemon.plist"
    )

    return plist_path


def uninstall_launchagent() -> None:
    """Uninstall macOS LaunchAgent."""
    plist_path = Path("~/Library/LaunchAgents/com.stealth-runner.survey-daemon.plist").expanduser()

    if plist_path.exists():
        os.system(f"launchctl unload -w {plist_path}")
        plist_path.unlink()
        logger.info("LaunchAgent uninstalled")


# CLI entry point
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Survey Daemon")
    parser.add_argument("command", choices=["start", "stop", "status", "install", "uninstall"])
    args = parser.parse_args()

    if args.command == "start":
        if SurveyDaemon.is_running():
            print("Daemon is already running")
            sys.exit(1)
        daemon = SurveyDaemon()
        daemon.start()

    elif args.command == "stop":
        if not SurveyDaemon.is_running():
            print("Daemon is not running")
            sys.exit(1)
        with open(DEFAULT_PID_PATH) as f:
            pid = int(f.read().strip())
        os.kill(pid, signal.SIGTERM)
        print("Stop signal sent")

    elif args.command == "status":
        status = SurveyDaemon.get_status()
        print(json.dumps(status, indent=2))

    elif args.command == "install":
        install_launchagent()

    elif args.command == "uninstall":
        uninstall_launchagent()
