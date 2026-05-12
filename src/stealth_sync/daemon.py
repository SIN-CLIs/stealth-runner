"""Main daemon module for stealth-sync.

This module implements the core daemon that monitors OpenCode sessions,
performs semantic analysis, and generates documentation automatically.

The daemon uses:
  - OpenCodeDBPoller: Polls the OpenCode SQLite database
  - SemanticAnalyzer: Classifies sessions using NVIDIA NIM API
  - OutputGenerator: Creates YAML/JSON documentation units
   - APScheduler: Handles periodic polling tasks
"""

# BANNED METHODS — NIEMALS VERWENDEN (siehe /banned.md):
#   ❌ playstealth launch — setzt NICHT --force-renderer-accessibility
#   ❌ webauto-nodriver — ABSOLUT BANNED
#   ❌ cua-driver click (raw index) — instabil
#   ❌ --remote-allow-origins=* (ohne Quotes) — zsh glob expansion
#   ❌ /tmp/heypiggy-bot (fixed profile) — korruptiert nach Neustart
#   ❌ Hardcoded PIDs — dynamisch, niemals hardcodieren
#   ❌ pkill -f "Google Chrome" — tötet USER Chrome
#   ❌ killall Google Chrome — tötet ALLE Chrome

import signal
import time
from typing import Any

import structlog
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

# Local module imports
from src.stealth_sync.db_poller import OpenCodeDBPoller
from src.stealth_sync.output_generator import OutputGenerator
from src.stealth_sync.semantic_engine import SemanticAnalyzer

# Initialize structured logger for the daemon
logger = structlog.get_logger(__name__)


class StealthSyncDaemon:
    """Main daemon class for the stealth-sync service.

    This daemon runs continuously, polling the OpenCode database for new sessions,
    analyzing them with NVIDIA NIM, and generating structured documentation.

    Attributes:
        db_poller: Instance of OpenCodeDBPoller for database access
        analyzer: Instance of SemanticAnalyzer for LLM classification
        generator: Instance of OutputGenerator for documentation output
        scheduler: APScheduler instance for periodic polling
        running: Boolean flag indicating if the daemon is active
        poll_interval: Seconds between polling cycles
    """

    def __init__(
        self,
        db_path: str | None = None,
        poll_interval: int = 10,
        output_dir: str = "docs/opencode-sessions/",
        logbook_path: str = "logbook.stealth.yaml",
    ):
        """Initialize the stealth-sync daemon.

        Args:
            db_path: Path to opencode.db (default: ~/.local/share/opencode/opencode.db)
            poll_interval: Seconds between polling cycles (default: 10)
            output_dir: Directory for generated documentation (default: docs/opencode-sessions/)
            logbook_path: Path to central logbook YAML file (default: logbook.stealth.yaml)
        """
        # Initialize database poller with OpenCode DB path
        self.db_poller = OpenCodeDBPoller(db_path=db_path)
        logger.info("db_poller_initialized", db_path=db_path or "default")

        # Initialize semantic analyzer with NVIDIA NIM credentials from env
        self.analyzer = SemanticAnalyzer()
        logger.info("semantic_analyzer_initialized")

        # Initialize output generator with output directory
        self.generator = OutputGenerator(output_dir=output_dir)
        logger.info("output_generator_initialized", output_dir=output_dir)

        # Store configuration
        self.logbook_path = logbook_path
        self.poll_interval = poll_interval
        self.running = False

        # Initialize APScheduler for periodic polling
        self.scheduler = BackgroundScheduler(daemon=True)
        self.scheduler.add_job(
            func=self._poll_and_process,
            trigger=IntervalTrigger(seconds=poll_interval),
            id="opencode_poll",
            name="OpenCode Session Poller",
            replace_existing=True,
        )
        logger.info("scheduler_initialized", poll_interval=poll_interval)

    def start(self) -> None:
        """Start the daemon and begin polling.

        This method sets up signal handlers for graceful shutdown,
        starts the scheduler, and enters the main loop.
        """
        # Set up signal handlers for graceful shutdown (SIGINT, SIGTERM)
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        logger.info("signal_handlers_registered")

        # Mark daemon as running
        self.running = True
        logger.info("daemon_starting")

        # Start the scheduler
        self.scheduler.start()
        logger.info("scheduler_started")

        # Main loop - keep alive until shutdown signal
        try:
            while self.running:
                time.sleep(1)  # Sleep to prevent CPU spinning
        except KeyboardInterrupt:
            logger.info("keyboard_interrupt_received")
        finally:
            self.stop()

    def stop(self) -> None:
        """Stop the daemon gracefully.

        Shuts down the scheduler and performs cleanup.
        """
        self.running = False
        if self.scheduler.running:
            self.scheduler.shutdown(wait=True)
            logger.info("scheduler_stopped")
        logger.info("daemon_stopped")

    def _signal_handler(self, signum, frame) -> None:
        """Handle shutdown signals (SIGINT, SIGTERM).

        Args:
            signum: Signal number
            frame: Current stack frame (unused)
        """
        logger.info("shutdown_signal_received", signal=signum)
        self.running = False

    def _poll_and_process(self) -> None:
        """Poll for new sessions and process them.

        This is the main work function called by the scheduler.
        It polls for new sessions, analyzes them, and generates docs.
        """
        try:
            # Poll for new sessions since last check
            logger.info("polling_started")
            new_sessions = self.db_poller.get_new_sessions()

            if not new_sessions:
                logger.info("no_new_sessions")
                return

            logger.info("new_sessions_found", count=len(new_sessions))

            # Process each new session
            for session in new_sessions:
                self._process_session(session)

        except Exception as e:
            logger.error("poll_error", error=str(e), exc_info=True)

    def _process_session(self, session: dict[str, Any]) -> None:
        """Process a single OpenCode session.

        Fetches messages, classifies the session, generates
        documentation, and updates the logbook.

        Args:
            session: Session dictionary from the database
        """
        session_id = session.get("id")
        if not session_id:
            logger.warning("session_missing_id")
            return

        try:
            logger.info("processing_session", session_id=session_id)

            # Fetch all messages for this session
            messages = self.db_poller.get_session_messages(session_id)
            if not messages:
                logger.info("no_messages_for_session", session_id=session_id)
                return

            logger.info("messages_fetched", count=len(messages))

            # Classify the session using NVIDIA NIM
            classification = self.analyzer.classify_session(messages)
            logger.info("session_classified", classification=classification)

            # Generate documentation unit
            doc_unit = self.analyzer.generate_doc_unit(session_id, messages, classification)

            # Write documentation outputs
            yaml_path = self.generator.generate_yaml(doc_unit)
            json_path = self.generator.generate_json(doc_unit)
            self.generator.update_changelog(doc_unit)
            self.generator.update_logbook(doc_unit, self.logbook_path)

            logger.info(
                "session_documented",
                session_id=session_id,
                yaml=str(yaml_path),
                json=str(json_path),
            )

        except Exception as e:
            logger.error(
                "session_processing_error",
                session_id=session_id,
                error=str(e),
                exc_info=True,
            )


def main():
    """Entry point for the stealth-sync daemon."""
    import os

    from dotenv import load_dotenv

    # Load environment variables from .env file
    load_dotenv()

    # Read configuration from environment
    db_path = os.getenv("OPENCODE_DB_PATH")
    poll_interval = int(os.getenv("POLL_INTERVAL", "10"))
    output_dir = os.getenv("OUTPUT_DIR", "docs/opencode-sessions/")
    logbook_path = os.getenv("LOGBOOK_PATH", "logbook.stealth.yaml")

    # Create and start the daemon
    daemon = StealthSyncDaemon(
        db_path=db_path,
        poll_interval=poll_interval,
        output_dir=output_dir,
        logbook_path=logbook_path,
    )
    daemon.start()


if __name__ == "__main__":
    main()
