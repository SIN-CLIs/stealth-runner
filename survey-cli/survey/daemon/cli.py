"""
OpenCode CLI Integration for Survey Daemon.

Commands:
    opencode survey start     - Start the daemon
    opencode survey stop      - Stop the daemon
    opencode survey status    - Get daemon status and stats
    opencode survey earnings  - Show earnings report
    opencode survey config    - Manage configuration
"""
from __future__ import annotations

import argparse
import json
import os
import signal
import sys
from datetime import datetime, timedelta
from pathlib import Path

from .survey_daemon import (
    SurveyDaemon,
    DEFAULT_PID_PATH,
    DEFAULT_CONFIG_PATH,
    HEALTH_CHECK_PORT,
    install_launchagent,
    uninstall_launchagent,
)


def cmd_start(args: argparse.Namespace) -> int:
    """Start the survey daemon."""
    if SurveyDaemon.is_running():
        print("ERROR: Daemon is already running")
        return 1
    
    if args.background:
        # Fork to background
        pid = os.fork()
        if pid > 0:
            print(f"Daemon started in background (PID: {pid})")
            return 0
        
        # Child process
        os.setsid()
        
    print("Starting Survey Daemon...")
    daemon = SurveyDaemon()
    daemon.start()
    return 0


def cmd_stop(args: argparse.Namespace) -> int:
    """Stop the survey daemon."""
    if not SurveyDaemon.is_running():
        print("ERROR: Daemon is not running")
        return 1
    
    try:
        with open(DEFAULT_PID_PATH) as f:
            pid = int(f.read().strip())
        os.kill(pid, signal.SIGTERM)
        print(f"Stop signal sent to PID {pid}")
        return 0
    except Exception as e:
        print(f"ERROR: Could not stop daemon: {e}")
        return 1


def cmd_status(args: argparse.Namespace) -> int:
    """Get daemon status and statistics."""
    status = SurveyDaemon.get_status()
    
    if status.get("status") == "not_running":
        print("Status: NOT RUNNING")
        return 1
    
    print(f"Status: {status['status'].upper()}")
    print(f"Uptime: {_format_uptime(status.get('uptime_seconds', 0))}")
    
    stats = status.get("stats", {})
    if stats:
        print("\n--- Statistics ---")
        print(f"Total Surveys:    {stats.get('total_surveys', 0)}")
        print(f"Completed:        {stats.get('completed', 0)}")
        print(f"Failed:           {stats.get('failed', 0)}")
        print(f"Disqualified:     {stats.get('disqualified', 0)}")
        print(f"Completion Rate:  {stats.get('completion_rate', 0):.1%}")
        print(f"Total Earnings:   ${stats.get('total_earnings', 0):.2f}")
    
    return 0


def cmd_earnings(args: argparse.Namespace) -> int:
    """Show earnings report."""
    import sqlite3
    
    db_path = Path("~/.survey_agent/state.db").expanduser()
    if not db_path.exists():
        print("No data available yet.")
        return 0
    
    conn = sqlite3.connect(db_path)
    
    # Calculate date range
    if args.period == "today":
        start_date = datetime.now().replace(hour=0, minute=0, second=0)
    elif args.period == "week":
        start_date = datetime.now() - timedelta(days=7)
    elif args.period == "month":
        start_date = datetime.now() - timedelta(days=30)
    else:  # all
        start_date = datetime(2000, 1, 1)
    
    cursor = conn.execute("""
        SELECT 
            DATE(completed_at) as date,
            COUNT(*) as surveys,
            SUM(earnings) as earnings
        FROM survey_sessions
        WHERE status = 'completed' 
        AND completed_at >= ?
        GROUP BY DATE(completed_at)
        ORDER BY date DESC
    """, (start_date.isoformat(),))
    
    rows = cursor.fetchall()
    
    if not rows:
        print("No completed surveys in this period.")
        return 0
    
    print(f"\n{'Date':<12} {'Surveys':<10} {'Earnings':<10}")
    print("-" * 32)
    
    total_surveys = 0
    total_earnings = 0
    
    for date, surveys, earnings in rows:
        print(f"{date:<12} {surveys:<10} ${earnings:.2f}")
        total_surveys += surveys
        total_earnings += earnings or 0
    
    print("-" * 32)
    print(f"{'TOTAL':<12} {total_surveys:<10} ${total_earnings:.2f}")
    
    # Calculate hourly rate
    cursor = conn.execute("""
        SELECT 
            SUM(
                (julianday(completed_at) - julianday(started_at)) * 24
            ) as total_hours
        FROM survey_sessions
        WHERE status = 'completed' AND completed_at >= ?
    """, (start_date.isoformat(),))
    
    total_hours = cursor.fetchone()[0] or 0
    if total_hours > 0:
        hourly_rate = total_earnings / total_hours
        print(f"\nAverage Hourly Rate: ${hourly_rate:.2f}/hr")
    
    conn.close()
    return 0


def cmd_config(args: argparse.Namespace) -> int:
    """Manage daemon configuration."""
    if not DEFAULT_CONFIG_PATH.exists():
        # Create default config
        daemon = SurveyDaemon()
    
    if args.show:
        with open(DEFAULT_CONFIG_PATH) as f:
            config = json.load(f)
        print(json.dumps(config, indent=2))
        return 0
    
    if args.set:
        key, value = args.set.split("=", 1)
        
        with open(DEFAULT_CONFIG_PATH) as f:
            config = json.load(f)
        
        # Navigate nested keys
        keys = key.split(".")
        target = config
        for k in keys[:-1]:
            target = target.setdefault(k, {})
        
        # Try to parse as JSON, fallback to string
        try:
            target[keys[-1]] = json.loads(value)
        except json.JSONDecodeError:
            target[keys[-1]] = value
        
        with open(DEFAULT_CONFIG_PATH, "w") as f:
            json.dump(config, f, indent=2)
        
        print(f"Set {key} = {value}")
        return 0
    
    if args.edit:
        editor = os.environ.get("EDITOR", "nano")
        os.system(f"{editor} {DEFAULT_CONFIG_PATH}")
        return 0
    
    print(f"Config file: {DEFAULT_CONFIG_PATH}")
    return 0


def cmd_install(args: argparse.Namespace) -> int:
    """Install macOS LaunchAgent."""
    plist_path = install_launchagent()
    print(f"\nTo enable auto-start, run:")
    print(f"  launchctl load -w {plist_path}")
    return 0


def cmd_uninstall(args: argparse.Namespace) -> int:
    """Uninstall macOS LaunchAgent."""
    uninstall_launchagent()
    return 0


def _format_uptime(seconds: float) -> str:
    """Format uptime in human-readable format."""
    hours, remainder = divmod(int(seconds), 3600)
    minutes, secs = divmod(remainder, 60)
    
    if hours > 24:
        days = hours // 24
        hours = hours % 24
        return f"{days}d {hours}h {minutes}m"
    return f"{hours}h {minutes}m {secs}s"


def main(argv: list[str] | None = None) -> int:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="survey",
        description="Survey Daemon CLI - Automated survey completion",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    # start
    start_parser = subparsers.add_parser("start", help="Start the daemon")
    start_parser.add_argument("-b", "--background", action="store_true",
                              help="Run in background")
    start_parser.set_defaults(func=cmd_start)
    
    # stop
    stop_parser = subparsers.add_parser("stop", help="Stop the daemon")
    stop_parser.set_defaults(func=cmd_stop)
    
    # status
    status_parser = subparsers.add_parser("status", help="Get daemon status")
    status_parser.set_defaults(func=cmd_status)
    
    # earnings
    earnings_parser = subparsers.add_parser("earnings", help="Show earnings report")
    earnings_parser.add_argument("-p", "--period", 
                                 choices=["today", "week", "month", "all"],
                                 default="week",
                                 help="Report period")
    earnings_parser.set_defaults(func=cmd_earnings)
    
    # config
    config_parser = subparsers.add_parser("config", help="Manage configuration")
    config_parser.add_argument("--show", action="store_true",
                               help="Show current config")
    config_parser.add_argument("--set", metavar="KEY=VALUE",
                               help="Set config value")
    config_parser.add_argument("--edit", action="store_true",
                               help="Edit config in $EDITOR")
    config_parser.set_defaults(func=cmd_config)
    
    # install
    install_parser = subparsers.add_parser("install", 
                                           help="Install macOS LaunchAgent")
    install_parser.set_defaults(func=cmd_install)
    
    # uninstall
    uninstall_parser = subparsers.add_parser("uninstall",
                                             help="Uninstall macOS LaunchAgent")
    uninstall_parser.set_defaults(func=cmd_uninstall)
    
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
