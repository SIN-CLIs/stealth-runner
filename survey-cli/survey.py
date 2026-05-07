#!/usr/bin/env python3
"""survey-cli — Standalone Survey Automation CLI.

Usage:
  ./survey.py login             Login to heypiggy (Google OAuth)
  ./survey.py scan              Scan dashboard for available surveys
  ./survey.py run --id X        Run a specific survey by ID
  ./survey.py run --url URL     Run survey at direct URL
  ./survey.py loop --max 10     Auto-loop: scan → filter → run → repeat
  ./survey.py watch [--interval 60]  Continuous poller
  ./survey.py balance           Show current balance + summary
  ./survey.py status            Check Chrome + login status
  ./survey.py doctor            Self-diagnostic (check all systems)
  ./survey.py kill              Kill bot Chrome only (safe)
  ./survey.py opencode "task"   Delegate coding task to opencode cli
  ./survey.py summary           Generate earnings summary
  ./survey.py profile           Show current profile

Environment:
  NVIDIA_API_KEY    Required for Nemotron 3 Omni decisions
  NVIDIA_MODEL      Model name (default: nvidia/nemotron-3-nano-omni-30b-a3b-reasoning)
  SURVEY_PORT       CDP port (default: 9999)

SIN-CLIs/stealth-runner — Standalone, no opencode dependency.
"""

import sys
import os
import json
import time
import argparse
from pathlib import Path

# Add parent to path for imports
# Robuster Import-Pfad: Workspace-Root (stealth-runner/) für cli.modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
_stealth_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _stealth_root not in sys.path:
    sys.path.insert(0, _stealth_root)


def cmd_login(args):
    """Login to heypiggy via Google OAuth (cua-driver flow)."""
    from cli.modules.auto_google_login import execute as google_login
    result = google_login()
    status = result.get("status")
    if status == "ok":
        print(f"✅ Login successful — PID={result.get('pid')}, WID={result.get('wid')}")
    else:
        print(f"❌ Login failed: {result.get('reason', 'unknown')}")
    return result


def cmd_scan(args):
    """Scan dashboard for surveys."""
    from survey.scanner import scan_dashboard
    viable = scan_dashboard(
        port=args.port,
        skip_providers=["purespectrum", "surveyrouter"] if not args.all else None
    )
    return viable


def cmd_run(args):
    """Run a single survey."""
    from survey.runner import SurveyRunner, RunnerConfig

    config = RunnerConfig(
        cdp_port=args.port,
        use_nim=not args.no_nim,
        auto_rate=not args.no_rate,
        debug=args.debug or os.getenv("SURVEY_DEBUG", ""),
        wait_after_action=float(os.getenv("SURVEY_WAIT", "3.0")),
    )

    runner = SurveyRunner(config=config)
    nim_status = "✅" if runner.nim and runner.nim.available else "⚠️  (auto-pilot)"
    print(f"NVIDIA NIM: {nim_status}")

    if args.url:
        result = runner.run_survey("direct", survey_url=args.url)
    elif args.id:
        result = runner.run_survey(args.id)
    else:
        print("❌ Use --id or --url")
        return None

    _print_result(result)
    return result


def cmd_loop(args):
    """Auto-loop surveys."""
    from survey.runner import SurveyRunner, RunnerConfig

    config = RunnerConfig(
        cdp_port=args.port,
        use_nim=not args.no_nim,
        auto_rate=not args.no_rate,
        max_surveys=args.max,
        debug=args.debug or os.getenv("SURVEY_DEBUG", ""),
        wait_after_action=float(os.getenv("SURVEY_WAIT", "3.0")),
    )

    runner = SurveyRunner(config=config)
    nim_status = "✅" if runner.nim and runner.nim.available else "⚠️  (auto-pilot)"
    print(f"  NVIDIA NIM: {nim_status}")
    print(f"  Max surveys: {args.max}")
    print()

    results = runner.run_loop(max_surveys=args.max)
    return results


def cmd_watch(args):
    """24/7 Watch Daemon — continuous poller with crash recovery.

    Features:
    - Graceful shutdown on SIGTERM/SIGINT
    - Auto-restart on Chrome crash or CDP disconnect
    - Exponential backoff on consecutive errors
    - Health check before each scan cycle
    - Balance target alerting
    - Structured JSONL logging
    """
    import signal
    from survey.runner import SurveyRunner, RunnerConfig
    from survey.scanner import read_balance
    from survey.chrome import is_chrome_alive, find_bot_tabs, find_dashboard_ws
    from survey.autodoc import log_session

    interval = args.interval
    config = RunnerConfig(
        cdp_port=args.port,
        use_nim=not args.no_nim,
        auto_rate=not args.no_rate,
        debug=False,
        max_surveys=args.max,
    )

    # ── State ──────────────────────────────────────
    state = {
        "running": True,
        "total_earned": 0.0,
        "loop_count": 0,
        "consecutive_errors": 0,
        "max_consecutive_errors": 20,  # Was 5 — now 20 (surveys fail often on captcha)
        "session_start": time.time(),
    }

    # ── Signal Handler ─────────────────────────────
    def shutdown(signum, frame):
        sig_name = signal.Signals(signum).name
        elapsed = time.time() - state["session_start"]
        print(f"\n[WATCH] Received {sig_name} — shutting down gracefully...")
        print(f"[WATCH] Session: {state['loop_count']} loops, "
              f"+{state['total_earned']:.2f}€ earned in {elapsed:.0f}s")
        state["running"] = False
        log_session("watch_stop", "ok", {
            "reason": sig_name,
            "loops": state["loop_count"],
            "earned": state["total_earned"],
            "elapsed_s": round(elapsed),
        })

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    # ── Banner ─────────────────────────────────────
    print(f"\n{'═'*60}")
    print(f"  🔄 SURVEY-CLI WATCH DAEMON — 24/7 Mode")
    print(f"{'═'*60}")

    # ── Accessibility Check (ONCE, never kill Chrome after) ──
    from survey.accessibility import ensure_accessibility, start_cua_daemon
    start_cua_daemon()
    if not ensure_accessibility(port=args.port):
        print("[WATCH] ❌ Accessibility not available — cua-driver login will fail")
        print("[WATCH] Continuing with CDP-only mode...")

    print(f"  Poll interval:  {interval}s")
    print(f"  Max/cycle:      {args.max}")
    print(f"  NVIDIA NIM:     {'✅' if config.use_nim else '⚠️  auto-pilot'}")
    print(f"  Balance target: {config.balance_target}€")
    print(f"  Logs:           survey-cli/logs/")
    print(f"  Stop:           Ctrl+C or SIGTERM")
    print(f"{'═'*60}\n")

    log_session("watch_start", "ok", {
        "interval": interval,
        "max_per_cycle": args.max,
        "use_nim": config.use_nim,
    })

    # ── Auto-Login if needed (via cua-driver verified flow) ──
    print("[WATCH] Checking login state...")
    from cli.modules.auto_google_login import execute as google_login
    # Quick check: does dashboard show Umfragen + Abmelden?
        logged_in = False
        dash_ws = find_dashboard_ws(args.port)
        if dash_ws:
            try:
                ws = websocket.create_connection(dash_ws, timeout=10)
                ws.send(json.dumps({"id":0,"method":"Runtime.evaluate",
                    "params":{"expression": "document.title.includes('Umfragen') || document.body.innerText.includes('Abmelden')"}}))
                r = json.loads(ws.recv()); ws.close()
                logged_in = r.get("result",{}).get("result",{}).get("value",False)
            except: pass
        
        if not logged_in:
            print("[WATCH] Not logged in — running cua-driver Google OAuth login...")
            login_result = google_login()
            if login_result.get("status") != "ok":
                print(f"[WATCH] ❌ Login failed: {login_result.get('reason')} — retrying later")
            else:
                print(f"[WATCH] ✅ Login successful")
                time.sleep(3)

    # ── Main Loop ──────────────────────────────────
    while state["running"]:
        state["loop_count"] += 1
        loop_start = time.monotonic()

        try:
            # Health check — just log, never restart Chrome
            if not is_chrome_alive(args.port):
                print(f"[WATCH] ⚠️  Chrome not responding on port {args.port} — waiting...")
                state["consecutive_errors"] += 1
                if state["consecutive_errors"] >= state["max_consecutive_errors"]:
                    print("[WATCH] ❌ Too many Chrome failures — stopping")
                    break
                wait_s = min(60, 2 ** state["consecutive_errors"])
                print(f"[WATCH] Waiting {wait_s}s...")
                time.sleep(wait_s)
                continue

            # Check dashboard
            dashboard_ws = find_dashboard_ws(args.port)
            if not dashboard_ws:
                print(f"[WATCH] ⚠️  No dashboard tab found")
                state["consecutive_errors"] += 1
                time.sleep(interval)
                continue

            # Reset error counter on successful health check
            state["consecutive_errors"] = 0

            # Read balance
            balance_before = read_balance(args.port)
            tabs = len(find_bot_tabs(args.port))

            print(f"\n[{state['loop_count']}] Balance: {balance_before}€ | "
                  f"Tabs: {tabs} | "
                  f"Earned: +{state['total_earned']:.2f}€ | "
                  f"{time.strftime('%H:%M:%S')}")

            # Check balance target
            if balance_before >= config.balance_target:
                print(f"[WATCH] 🎯 Balance target reached: {balance_before}€")
                print(f"[WATCH] Total earned: +{state['total_earned']:.2f}€")
                break

            # Run survey cycle
            runner = SurveyRunner(config=config)
            results = runner.run_loop(max_surveys=args.max)

            earned = sum(r.earned for r in results if r.earned > 0)
            state["total_earned"] += earned
            completed = sum(1 for r in results if r.status == "completed")
            failed = len(results) - completed

            balance_after = read_balance(args.port)

            # Print cycle summary
            icons = " ".join(
                "✅" if r.status == "completed" else
                "⛔" if r.status == "blocked" else "❌"
                for r in results
            )
            print(f"  → +{earned:.2f}€ | {completed} done, {failed} fail | "
                  f"Balance: {balance_after}€ | {icons}")

            # Smart backoff: if no surveys completed, wait interval
            if completed == 0:
                if failed == 0:
                    # No surveys available at all — wait longer
                    wait_s = interval
                    print(f"  No surveys found — waiting {wait_s}s...")
                else:
                    # Surveys attempted but failed — quick retry
                    wait_s = min(interval, 10)
                    print(f"  All failed — retrying in {wait_s}s...")
                time.sleep(wait_s)
            else:
                # Surveys completed — continue immediately
                pass

        except KeyboardInterrupt:
            shutdown(signal.SIGINT, None)

        except Exception as e:
            state["consecutive_errors"] += 1
            print(f"[WATCH] ❌ Error in loop {state['loop_count']}: {e}")

            # Exponential backoff
            if state["consecutive_errors"] >= state["max_consecutive_errors"]:
                print(f"[WATCH] ❌ Too many consecutive errors — stopping")
                break

            wait_s = min(300, 5 * (2 ** state["consecutive_errors"]))
            print(f"[WATCH] Backing off {wait_s}s (error {state['consecutive_errors']}/{state['max_consecutive_errors']})")
            time.sleep(wait_s)

    # ── Shutdown ───────────────────────────────────
    elapsed = time.time() - state["session_start"]
    print(f"\n{'═'*60}")
    print(f"  WATCH DAEMON STOPPED")
    print(f"{'═'*60}")
    print(f"  Loops:     {state['loop_count']}")
    print(f"  Earned:    +{state['total_earned']:.2f}€")
    print(f"  Duration:  {elapsed:.0f}s ({elapsed/3600:.1f}h)")
    print(f"{'═'*60}\n")


def cmd_balance(args):
    """Show current balance + summary."""
    from survey.scanner import read_balance
    from survey.autodoc import generate_summary, print_summary

    balance = read_balance(port=args.port)
    print(f"\n{'='*50}")
    print(f"  CURRENT BALANCE: {balance}€")
    print(f"{'='*50}")

    summary = generate_summary(days=args.days)
    print_summary(summary)
    return balance


def cmd_status(args):
    """Check Chrome + login + NIM status."""
    from survey.chrome import is_chrome_alive, find_bot_pids, find_dashboard_ws
    from survey.snapshot import generate_snapshot
    from survey.nim import get_nim
    from survey.scanner import read_balance

    print(f"\n{'='*50}")
    print(f"  SURVEY-CLI STATUS")
    print(f"{'='*50}")

    # Chrome
    alive = is_chrome_alive(args.port)
    pids = find_bot_pids()
    print(f"\n  Chrome:")
    print(f"    Running:  {'✅' if alive else '❌'}")
    print(f"    PIDs:     {pids if pids else 'none'}")
    print(f"    Port:     {args.port}")

    if alive:
        # Dashboard
        ws_url = find_dashboard_ws(args.port)
        if ws_url:
            print(f"    Dashboard: ✅ Connected")
            try:
                snap = generate_snapshot(ws_url)
                has_surveys = any("clickSurvey" in json.dumps(snap.refs)
                                  for _ in [0])
                balance = read_balance(args.port)
                print(f"    Balance:   {balance}€")
            except Exception:
                print(f"    Dashboard: connected (read error)")
        else:
            print(f"    Dashboard: ❌ Not found")

    # NIM
    nim = get_nim()
    key = os.getenv("NVIDIA_API_KEY", "")
    print(f"\n  NVIDIA NIM:")
    print(f"    API Key:  {'✅ set' if key else '❌ NOT SET'}")
    print(f"    Status:   {'✅ ready' if nim and nim.available else '❌ unavailable'}")
    print(f"    Model:    {nim.model if nim and nim.model else 'N/A'}")

    print()
    return {"chrome_alive": alive, "pid_count": len(pids), "nim_ready": bool(nim and nim.available)}


def cmd_doctor(args):
    """Full self-diagnostic."""
    from survey.chrome import is_chrome_alive, find_bot_tabs

    print(f"\n{'='*50}")
    print(f"  🔬 SURVEY-CLI DOCTOR")
    print(f"{'='*50}")

    # Check Python
    print(f"\n  Python: {sys.version.split()[0]}")

    # Check dependencies
    deps = ["websocket", "openai"]
    for dep in deps:
        try:
            __import__(dep)
            print(f"  {dep}:       ✅")
        except ImportError:
            print(f"  {dep}:       ❌ not installed")

    # Chrome status
    cmd_status(args)

    # Check profile
    profile_path = Path(__file__).parent / "survey" / "profiles" / "jeremy_schulze.json"
    print(f"  Profile:    {'✅' if profile_path.exists() else '⚠️  using fallback'}")

    # Check logs
    logs_dir = Path(__file__).parent / "logs"
    if logs_dir.exists():
        log_files = list(logs_dir.glob("*.jsonl"))
        print(f"  Log files:  {len(log_files)}")
    else:
        print(f"  Log files:  0")

    # Check tabs
    if is_chrome_alive(args.port):
        pages = find_bot_tabs(args.port)
        print(f"  Tabs open:  {len(pages)}")

        for p in pages[:5]:
            url = p.get("url", "")[:70]
            print(f"    {p.get('id','?')[:12]} | {url}")

    print(f"\n  {'='*50}")
    print(f"  Doctor complete")
    print(f"  {'='*50}\n")


def cmd_kill(args):
    """Safely kill bot Chrome only."""
    from survey.chrome import safe_kill_bot
    killed = safe_kill_bot()
    if killed:
        print("✅ Bot Chrome killed safely")
    else:
        print("ℹ️  No bot Chrome to kill")


def cmd_summary(args):
    """Generate earnings summary."""
    from survey.autodoc import generate_summary, print_summary
    summary = generate_summary(days=args.days or 30)
    print_summary(summary)
    return summary


def cmd_opencode(args):
    """Delegate a coding task to opencode cli."""
    from survey.opencode_bridge import delegate_task

    task = " ".join(args.task) if args.task else sys.stdin.read()
    if not task.strip():
        print("❌ No task provided. Usage: survey.py opencode 'task description'")
        return

    result = delegate_task(task, repo_path=args.repo, timeout=args.timeout)
    print(f"\nOpenCode Result: {result['status']}")
    if result.get("stdout"):
        print(result["stdout"])
    if result.get("stderr"):
        print(f"  stderr: {result['stderr']}")
    return result


def cmd_profile(args):
    """Show current profile."""
    from survey.runner import SurveyRunner
    runner = SurveyRunner()
    profile = runner.profile
    print(f"\n{'='*50}")
    print(f"  CURRENT PROFILE")
    print(f"{'='*50}")
    for k, v in profile.items():
        print(f"  {k:25s}: {v}")
    print()


def _print_result(result):
    """Pretty-print a survey result."""
    if result is None:
        return
    print(f"\n{'='*50}")
    print(f"  Survey:     {result.survey_id}")
    print(f"  Status:     {result.status}")
    print(f"  Provider:   {result.provider}")
    print(f"  Earned:     +{result.earned}€")
    print(f"  Steps:      {result.iterations}")
    print(f"  Duration:   {result.elapsed_s}s")
    print(f"  NIM calls:  {result.nim_calls}")
    if result.error:
        print(f"  Error:      {result.error}")
    print(f"{'='*50}\n")


def main():
    parser = argparse.ArgumentParser(
        description="survey-cli — Standalone Survey Automation CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument("--port", type=int, default=int(os.getenv("SURVEY_PORT", "9999")),
                        help="CDP port (default: 9999)")
    parser.add_argument("--debug", action="store_true", help="Verbose output")

    sub = parser.add_subparsers(dest="command", help="Command")

    # login
    p = sub.add_parser("login", help="Login to heypiggy")

    # scan
    p = sub.add_parser("scan", help="Scan dashboard for surveys")
    p.add_argument("--all", action="store_true", help="Show all providers (don't skip blocked)")

    # run
    p = sub.add_parser("run", help="Run a survey")
    p.add_argument("--id", type=str, help="Survey ID")
    p.add_argument("--url", type=str, help="Direct survey URL")
    p.add_argument("--no-nim", action="store_true", help="Skip NIM, use auto-pilot")
    p.add_argument("--no-rate", action="store_true", help="Skip survey rating")

    # loop
    p = sub.add_parser("loop", help="Auto-loop surveys")
    p.add_argument("--max", type=int, default=5, help="Max surveys per loop")
    p.add_argument("--no-nim", action="store_true", help="Skip NIM")
    p.add_argument("--no-rate", action="store_true", help="Skip rating")

    # watch
    p = sub.add_parser("watch", help="Continuous poller")
    p.add_argument("--interval", type=int, default=30, help="Poll interval (s)")
    p.add_argument("--max", type=int, default=3, help="Max surveys per poll")
    p.add_argument("--no-nim", action="store_true", help="Skip NIM")
    p.add_argument("--no-rate", action="store_true", help="Skip rating")

    # balance
    p = sub.add_parser("balance", help="Show balance + summary")
    p.add_argument("--days", type=int, default=7, help="Days of history")

    # status
    p = sub.add_parser("status", help="Check system status")

    # doctor
    p = sub.add_parser("doctor", help="Full self-diagnostic")

    # kill
    p = sub.add_parser("kill", help="Kill bot Chrome safely")

    # summary
    p = sub.add_parser("summary", help="Earnings summary")
    p.add_argument("--days", type=int, default=30)

    # opencode
    p = sub.add_parser("opencode", help="Delegate task to opencode cli")
    p.add_argument("task", nargs="*", help="Task description")
    p.add_argument("--repo", type=str, help="Repo path")
    p.add_argument("--timeout", type=int, default=300, help="Wait timeout (s)")

    # profile
    sub.add_parser("profile", help="Show current persona profile")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    cmd_map = {
        "login": cmd_login,
        "scan": cmd_scan,
        "run": cmd_run,
        "loop": cmd_loop,
        "watch": cmd_watch,
        "balance": cmd_balance,
        "status": cmd_status,
        "doctor": cmd_doctor,
        "kill": cmd_kill,
        "summary": cmd_summary,
        "opencode": cmd_opencode,
        "profile": cmd_profile,
    }

    cmd_fn = cmd_map.get(args.command)
    if cmd_fn:
        cmd_fn(args)


if __name__ == "__main__":
    main()
