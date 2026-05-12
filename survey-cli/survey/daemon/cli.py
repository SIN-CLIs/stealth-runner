"""
Survey Agent CLI - OpenCode Integration

Commands:
    survey run <url>        - Run single survey
    survey heypiggy         - Run HeyPiggy session
    survey daemon start     - Start 24/7 daemon
    survey daemon stop      - Stop daemon
    survey daemon status    - Show daemon status
    survey stats            - Show statistics
    survey config           - Manage configuration

SR-152 Commands:
    survey dlq-list         - List DLQ items
    survey dlq-replay <id>  - Replay a DLQ item
    survey contradiction-scan <persona_id> - Scan for persona contradictions
"""

# ruff: noqa: E501  # CSS selectors / argparse help / log strings — wrapping changes semantics
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("survey-cli")


def get_config_path() -> Path:
    """Get config file path."""
    return Path.home() / ".survey_agent" / "config.json"


def load_config() -> dict:
    """Load configuration."""
    config_path = get_config_path()
    if config_path.exists():
        with open(config_path) as f:
            return json.load(f)
    return {}


def save_config(config: dict) -> None:
    """Save configuration."""
    config_path = get_config_path()
    config_path.parent.mkdir(parents=True, exist_ok=True)
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)


def get_persona():
    """Get configured persona."""
    from .answer_engine import Persona

    config = load_config()
    persona_config = config.get("persona", {})

    return Persona(
        name=persona_config.get("name", "Alex"),
        age=persona_config.get("age", 32),
        gender=persona_config.get("gender", "non-binary"),
        occupation=persona_config.get("occupation", "Software Engineer"),
        income_bracket=persona_config.get("income", "$75,000-$99,999"),
        education=persona_config.get("education", "Bachelor's degree"),
        location=persona_config.get("location", "California, USA"),
        interests=persona_config.get("interests", ["technology", "gaming", "music"]),
    )


async def cmd_run_survey(args) -> int:
    """Run a single survey."""
    from .survey_agent_graph import SurveyAgentGraph

    load_config()
    persona = get_persona()

    graph = SurveyAgentGraph(
        persona=persona,
        nvidia_local=True,  # FREE NVIDIA Vision for CAPTCHAs
        headless=not args.visible,
    )

    print(f"Running survey: {args.url}")

    result = await graph.run(args.url)

    print(f"\nResult: {result['status']}")
    if result.get("error"):
        print(f"Error: {result['error']}")

    print(f"Pages: {result['current_page']}")
    print(f"Questions answered: {len(result['answers'])}")

    return 0 if result["status"] == "completed" else 1


async def cmd_heypiggy(args) -> int:
    """Run HeyPiggy survey session."""
    from .heypiggy import run_heypiggy_session

    config = load_config()
    persona = get_persona()

    # Get credentials
    email = args.email or config.get("heypiggy_email") or os.environ.get("HEYPIGGY_EMAIL")
    password = (
        args.password or config.get("heypiggy_password") or os.environ.get("HEYPIGGY_PASSWORD")
    )

    if not email or not password:
        print("Error: HeyPiggy credentials required")
        print("Set via: --email/--password, config, or HEYPIGGY_EMAIL/HEYPIGGY_PASSWORD env vars")
        return 1

    print("Starting HeyPiggy session...")
    print(f"Max surveys: {args.max_surveys}")
    print(f"Headless: {not args.visible}")

    result = await run_heypiggy_session(
        email=email,
        password=password,
        persona=persona,
        nvidia_local=True,  # FREE NVIDIA Vision for CAPTCHAs
        max_surveys=args.max_surveys,
        headless=not args.visible,
    )

    if "error" in result and result["error"]:
        print(f"\nError: {result['error']}")

    stats = result.get("stats", {})
    print("\n=== Session Results ===")
    print(f"Surveys attempted: {stats.get('surveys_attempted', 0)}")
    print(f"Surveys completed: {stats.get('surveys_completed', 0)}")
    print(f"Surveys disqualified: {stats.get('surveys_disqualified', 0)}")
    print(f"Total points: {stats.get('total_points', 0)}")
    print(f"Estimated USD: ${stats.get('total_points', 0) / 100:.2f}")
    print(f"Completion rate: {stats.get('completion_rate', 0):.1%}")
    print(f"Effective hourly rate: ${stats.get('usd_per_hour', 0):.2f}/hr")

    return 0


def cmd_daemon_start(args) -> int:
    """Start the survey daemon."""
    from .survey_daemon import SurveyDaemon, install_launchagent

    load_config()
    persona = get_persona()

    if args.background:
        # Install and start LaunchAgent
        install_launchagent()
        print("Daemon installed and started in background")
        print("Check status: survey daemon status")
        print("View logs: tail -f ~/.survey_agent/daemon.log")
        return 0

    # Run in foreground
    print("Starting survey daemon in foreground (Ctrl+C to stop)...")

    daemon = SurveyDaemon(
        persona=persona,
        nvidia_local=True,  # FREE NVIDIA Vision for CAPTCHAs
    )

    try:
        asyncio.run(daemon.run_forever())
    except KeyboardInterrupt:
        print("\nDaemon stopped")

    return 0


def cmd_daemon_stop(args) -> int:
    """Stop the survey daemon."""
    from .survey_daemon import uninstall_launchagent

    uninstall_launchagent()
    print("Daemon stopped and uninstalled")
    return 0


def cmd_daemon_status(args) -> int:
    """Show daemon status."""
    import subprocess

    plist_path = Path.home() / "Library/LaunchAgents/com.stealth-runner.survey-daemon.plist"

    if not plist_path.exists():
        print("Status: Not installed")
        return 0

    result = subprocess.run(
        ["launchctl", "list", "com.stealth-runner.survey-daemon"],
        capture_output=True,
        text=True,
    )

    if result.returncode == 0:
        print("Status: Running")
        lines = result.stdout.strip().split("\n")
        for line in lines:
            print(f"  {line}")
    else:
        print("Status: Installed but not running")

    # Show recent stats
    from .survey_agent_graph import SurveyAgentGraph

    try:
        graph = SurveyAgentGraph(persona=get_persona())
        stats = graph.get_stats()
        print("\n=== Statistics ===")
        print(f"Total surveys: {stats['total_surveys']}")
        print(f"Completed: {stats['completed']}")
        print(f"Failed: {stats['failed']}")
        print(f"Disqualified: {stats['disqualified']}")
        print(f"Completion rate: {stats['completion_rate']:.1%}")
        print(f"Total earnings: ${stats['total_earnings']:.2f}")
    except Exception:
        pass

    # SR-152: Show DLQ stats
    from ..reliability import DLQ

    try:
        dlq = DLQ()
        counts = dlq.count_by_status()
        print("\n=== DLQ Status (SR-152) ===")
        print(f"Pending: {counts.get('pending', 0)}")
        print(f"Replayed: {counts.get('replayed', 0)}")
        print(f"Discarded: {counts.get('discarded', 0)}")
    except Exception:
        pass

    return 0


def cmd_stats(args) -> int:
    """Show statistics."""
    from .survey_agent_graph import SurveyAgentGraph

    graph = SurveyAgentGraph(persona=get_persona())
    stats = graph.get_stats()

    print("=== Survey Statistics ===")
    print(f"Total surveys: {stats['total_surveys']}")
    print(f"Completed: {stats['completed']}")
    print(f"Failed: {stats['failed']}")
    print(f"Disqualified: {stats['disqualified']}")
    print(f"Completion rate: {stats['completion_rate']:.1%}")
    print(f"Total earnings: ${stats['total_earnings']:.2f}")

    return 0


def cmd_config(args) -> int:
    """Manage configuration."""
    config = load_config()

    if args.show:
        print(json.dumps(config, indent=2))
        return 0

    if args.set:
        key, value = args.set.split("=", 1)

        # Handle nested keys
        parts = key.split(".")
        target = config
        for part in parts[:-1]:
            if part not in target:
                target[part] = {}
            target = target[part]

        # Try to parse as JSON
        try:
            target[parts[-1]] = json.loads(value)
        except json.JSONDecodeError:
            target[parts[-1]] = value

        save_config(config)
        print(f"Set {key} = {value}")
        return 0

    if args.delete:
        parts = args.delete.split(".")
        target = config
        for part in parts[:-1]:
            if part not in target:
                print(f"Key not found: {args.delete}")
                return 1
            target = target[part]

        if parts[-1] in target:
            del target[parts[-1]]
            save_config(config)
            print(f"Deleted {args.delete}")
        else:
            print(f"Key not found: {args.delete}")
            return 1

        return 0

    # Show help
    print("Usage:")
    print("  survey config --show               Show all config")
    print("  survey config --set key=value      Set config value")
    print("  survey config --delete key         Delete config key")
    print("\nExamples:")
    print("  # No API key needed - uses FREE NVIDIA Vision model")
    print("  survey config --set persona.age=28")
    print("  survey config --set heypiggy_email=user@email.com")

    return 0


# =============================================================================
# SR-152: DLQ Commands
# =============================================================================


def cmd_dlq_list(args) -> int:
    """List DLQ items (SR-152)."""
    from ..reliability import DLQ

    dlq = DLQ()

    # Filter by status if specified
    status = args.status if hasattr(args, "status") and args.status else None
    limit = args.limit if hasattr(args, "limit") else 20

    records = dlq.list_all(status=status, limit=limit)

    if not records:
        print("No DLQ records found.")
        return 0

    # Count by status
    counts = dlq.count_by_status()
    print("=== DLQ Summary ===")
    print(
        f"Pending: {counts.get('pending', 0)} | Replayed: {counts.get('replayed', 0)} | Discarded: {counts.get('discarded', 0)}"
    )
    print()

    # List records
    print(f"{'ID':<20} {'Status':<10} {'Provider':<10} {'Persona':<15} {'Error':<30} {'Time'}")
    print("-" * 100)

    for record in records:
        error_short = (
            record.error_message[:27] + "..."
            if len(record.error_message) > 30
            else record.error_message
        )
        ts_short = record.ts[:19] if len(record.ts) > 19 else record.ts
        print(
            f"{record.id:<20} {record.status:<10} {record.provider:<10} {record.persona_id:<15} {error_short:<30} {ts_short}"
        )

    return 0


async def cmd_dlq_replay(args) -> int:
    """Replay a DLQ item (SR-152)."""
    from ..reliability import DLQ
    from .survey_agent_graph import SurveyAgentGraph

    dlq = DLQ()
    record = dlq.get(args.id)

    if not record:
        print(f"DLQ record not found: {args.id}")
        return 1

    if record.status != "pending":
        print(f"Record is not pending (status: {record.status})")
        if not args.force:
            print("Use --force to replay anyway")
            return 1

    print(f"Replaying DLQ record: {record.id}")
    print(f"  Survey: {record.survey_id}")
    print(f"  URL: {record.url}")
    print(f"  Original error: {record.error_class}: {record.error_message}")
    print()

    # Get persona for replay
    persona = get_persona()

    graph = SurveyAgentGraph(
        persona=persona,
        nvidia_local=True,
        headless=not args.visible if hasattr(args, "visible") else True,
    )

    try:
        result = await graph.run(record.url)

        if result["status"] == "completed":
            print("SUCCESS: Survey completed!")
            print(f"  Questions answered: {len(result.get('answers', []))}")
            dlq.mark_replayed(record.id)
            print("  DLQ record marked as replayed")
            return 0
        else:
            print(f"FAILED: Survey ended with status {result['status']}")
            if result.get("error"):
                print(f"  Error: {result['error']}")
            print("  DLQ record remains pending for retry")
            return 1

    except Exception as e:
        print(f"FAILED: {type(e).__name__}: {e}")
        print("  DLQ record remains pending for retry")
        return 1


def cmd_contradiction_scan(args) -> int:
    """Scan for persona contradictions (SR-152)."""
    from ..reliability import ContradictionDetector

    detector = ContradictionDetector()

    # Get persona ID
    persona_id = args.persona_id

    print(f"Scanning contradictions for persona: {persona_id}")
    print()

    results = detector.scan(persona_id)

    if not results:
        print("No identity answers recorded for this persona.")
        print()
        print("Identity answers are recorded when answering questions about:")
        print("  - AGE (age, wie alt, birth year)")
        print("  - GENDER (gender, geschlecht)")
        print("  - INCOME (income, einkommen, salary)")
        print("  - EDUCATION (education, bildung, degree)")
        print("  - EMPLOYMENT (employment, beruf, occupation)")
        print("  - HOUSEHOLD_SIZE (household size, haushaltsgroesse)")
        print("  - COUNTRY (country, land, region)")
        return 0

    # Print formatted report
    report = detector.format_report(results)
    print(report)
    print()

    # Summary
    contradictions = [c for c in results.values() if c.is_contradicted]
    if contradictions:
        print(f"!! {len(contradictions)} contradiction(s) detected")
        print("These may trigger fraud detection on survey panels.")
        print("The daemon will pin future answers to the most-frequent prior value.")
    else:
        print("ok All identity categories are consistent")

    return 0


def main(args: list[str] | None = None) -> int:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="survey",
        description="Survey Agent CLI - Automated survey completion",
    )
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # survey run <url>
    run_parser = subparsers.add_parser("run", help="Run single survey")
    run_parser.add_argument("url", help="Survey URL")
    run_parser.add_argument("--visible", action="store_true", help="Show browser window")

    # survey heypiggy
    heypiggy_parser = subparsers.add_parser("heypiggy", help="Run HeyPiggy session")
    heypiggy_parser.add_argument("--email", help="HeyPiggy email")
    heypiggy_parser.add_argument("--password", help="HeyPiggy password")
    heypiggy_parser.add_argument(
        "--max-surveys", type=int, default=10, help="Max surveys to complete"
    )
    heypiggy_parser.add_argument("--visible", action="store_true", help="Show browser window")

    # survey daemon
    daemon_parser = subparsers.add_parser("daemon", help="Manage daemon")
    daemon_subparsers = daemon_parser.add_subparsers(dest="daemon_command")

    start_parser = daemon_subparsers.add_parser("start", help="Start daemon")
    start_parser.add_argument("--background", "-b", action="store_true", help="Run in background")

    daemon_subparsers.add_parser("stop", help="Stop daemon")
    daemon_subparsers.add_parser("status", help="Show daemon status")

    # survey stats
    subparsers.add_parser("stats", help="Show statistics")

    # survey config
    config_parser = subparsers.add_parser("config", help="Manage configuration")
    config_parser.add_argument("--show", action="store_true", help="Show all config")
    config_parser.add_argument("--set", metavar="KEY=VALUE", help="Set config value")
    config_parser.add_argument("--delete", metavar="KEY", help="Delete config key")

    # SR-152: DLQ commands
    dlq_list_parser = subparsers.add_parser("dlq-list", help="List DLQ items (SR-152)")
    dlq_list_parser.add_argument(
        "--status", choices=["pending", "replayed", "discarded"], help="Filter by status"
    )
    dlq_list_parser.add_argument("--limit", type=int, default=20, help="Max items to show")

    dlq_replay_parser = subparsers.add_parser("dlq-replay", help="Replay a DLQ item (SR-152)")
    dlq_replay_parser.add_argument("id", help="DLQ record ID")
    dlq_replay_parser.add_argument(
        "--force", action="store_true", help="Replay even if not pending"
    )
    dlq_replay_parser.add_argument("--visible", action="store_true", help="Show browser window")

    contradiction_parser = subparsers.add_parser(
        "contradiction-scan", help="Scan for persona contradictions (SR-152)"
    )
    contradiction_parser.add_argument("persona_id", help="Persona ID to scan")

    parsed = parser.parse_args(args)

    if parsed.command == "run":
        return asyncio.run(cmd_run_survey(parsed))
    elif parsed.command == "heypiggy":
        return asyncio.run(cmd_heypiggy(parsed))
    elif parsed.command == "daemon":
        if parsed.daemon_command == "start":
            return cmd_daemon_start(parsed)
        elif parsed.daemon_command == "stop":
            return cmd_daemon_stop(parsed)
        elif parsed.daemon_command == "status":
            return cmd_daemon_status(parsed)
        else:
            daemon_parser.print_help()
            return 1
    elif parsed.command == "stats":
        return cmd_stats(parsed)
    elif parsed.command == "config":
        return cmd_config(parsed)
    # SR-152: DLQ commands
    elif parsed.command == "dlq-list":
        return cmd_dlq_list(parsed)
    elif parsed.command == "dlq-replay":
        return asyncio.run(cmd_dlq_replay(parsed))
    elif parsed.command == "contradiction-scan":
        return cmd_contradiction_scan(parsed)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
