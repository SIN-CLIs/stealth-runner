"""Auto-Documentation Engine — append-only JSONL logs.

WARUM: Jeder Survey-Run, jeder Fehler und jede Session generiert
Wissen. Ohne Auto-Dokumentation geht dieses Wissen verloren.
LLMs sollen Dokumentation NICHT schreiben (Halluzinations-Risiko).
Diese Engine schreibt append-only JSONL — atomar, strukturiert,
maschinenlesbar. Jeder Eintrag ist immutable.

ARCHITEKTUR: 4 Log-Streams: earnings.jsonl (Verdienst), errors.jsonl
(Fehler mit Kontext), sessions.jsonl (Metadaten), summary.md
(Markdown-Übersicht). Append-only: existierende Zeilen werden NIE
modifiziert. Rotation: neuer File pro Tag (YYYY-MM-DD.jsonl).
Rich Context: URL, Provider, Error-Type, PID, WID, Timestamp.
Kein LLM-Call für Doku — reines Logging.

BANNED METHODS — NIEMALS VERWENDEN:
❌ playstealth launch
❌ webauto-nodriver — ABSOLUT BANNED
❌ cua-driver click (raw index)
❌ --remote-allow-origins=* (ohne Quotes)
❌ /tmp/heypiggy-bot (fixed profile)
❌ Hardcoded PIDs
❌ pkill -f "Google Chrome"
❌ killall Google Chrome
❌ skylight-cli click --element-index
"""

import json
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List

# ── Log Directory ──────────────────────────────────────

LOGS_DIR = Path(__file__).parent.parent / "logs"


def _ensure_logs():
    """Ensure logs directory exists."""
    LOGS_DIR.mkdir(parents=True, exist_ok=True)


def _daily_file(name: str) -> Path:
    """Get daily log file path."""
    date = datetime.now().strftime("%Y-%m-%d")
    return LOGS_DIR / f"{name}-{date}.jsonl"


# ── Public API ─────────────────────────────────────────

def log_earnings(survey_id: str, provider: str, amount: float,
                 status: str, duration_s: float, details: Optional[Dict] = None):
    """Log survey earnings (append-only).

    Args:
        survey_id: CPX survey ID or 'direct'
        provider: e.g. 'qualtrics', 'tolunastart'
        amount: Amount earned in EUR (0 for screen-out)
        status: 'completed', 'screen_out', 'error', 'blocked'
        duration_s: Duration in seconds
        details: Optional extra metadata
    """
    _ensure_logs()
    entry = {
        "ts": datetime.now().isoformat(),
        "unix_ts": time.time(),
        "type": "earnings",
        "survey_id": survey_id,
        "provider": provider,
        "amount_eur": amount,
        "status": status,
        "duration_s": round(duration_s, 1),
        "details": details or {},
    }
    fp = _daily_file("earnings")
    with open(fp, "a") as f:
        f.write(json.dumps(entry) + "\n")
    return entry


def log_error(context: str, error: str, survey_id: str = "",
              provider: str = "", details: Optional[Dict] = None):
    """Log an error (append-only).

    Captures full stack trace automatically.

    Args:
        context: Where the error occurred (e.g. 'run_survey', 'nim_decision')
        error: Error message
        survey_id: Optional survey ID
        provider: Optional provider name
        details: Optional extra metadata
    """
    _ensure_logs()
    entry = {
        "ts": datetime.now().isoformat(),
        "unix_ts": time.time(),
        "type": "error",
        "context": context,
        "error": str(error)[:500],
        "traceback": traceback.format_exc()[-1000:],
        "survey_id": survey_id,
        "provider": provider,
        "details": details or {},
    }
    fp = _daily_file("errors")
    with open(fp, "a") as f:
        f.write(json.dumps(entry) + "\n")


def log_session(action: str, status: str, details: Optional[Dict] = None):
    """Log a session event (append-only).

    Args:
        action: e.g. 'scan', 'run', 'login', 'loop'
        status: 'ok', 'error', 'running'
        details: Optional metadata
    """
    _ensure_logs()
    entry = {
        "ts": datetime.now().isoformat(),
        "unix_ts": time.time(),
        "type": "session",
        "action": action,
        "status": status,
        "details": details or {},
    }
    fp = _daily_file("sessions")
    with open(fp, "a") as f:
        f.write(json.dumps(entry) + "\n")


def log_decision(snapshot_elements: int, actions: List[Dict],
                 nim_calls: int, elapsed_ms: float,
                 survey_id: str = "", provider: str = ""):
    """Log a NEMO decision (for debugging/analysis).

    Args:
        snapshot_elements: Number of elements in snapshot
        actions: List of actions decided
        nim_calls: Number of NIM API calls
        elapsed_ms: Decision time in ms
        survey_id: Optional survey ID
        provider: Optional provider name
    """
    _ensure_logs()
    entry = {
        "ts": datetime.now().isoformat(),
        "unix_ts": time.time(),
        "type": "decision",
        "snapshot_elements": snapshot_elements,
        "actions_count": len(actions),
        "actions": actions[:10],  # Keep first 10 for context
        "nim_calls": nim_calls,
        "elapsed_ms": round(elapsed_ms, 1),
        "survey_id": survey_id,
        "provider": provider,
    }
    fp = _daily_file("decisions")
    with open(fp, "a") as f:
        f.write(json.dumps(entry) + "\n")


# ── Summary Generation ─────────────────────────────────

def generate_summary(days: int = 7) -> Dict[str, Any]:
    """Generate a summary of recent activity.

    Args:
        days: Number of days to look back

    Returns:
        Dict with summary data
    """
    _ensure_logs()
    summary = {
        "total_earned": 0.0,
        "surveys_completed": 0,
        "surveys_failed": 0,
        "errors_count": 0,
        "by_provider": {},
        "recent_sessions": [],
    }

    # Scan daily files
    for i in range(days):
        date = (datetime.now().timestamp() - i * 86400)
        date_str = datetime.fromtimestamp(date).strftime("%Y-%m-%d")

        # Earnings
        fp = LOGS_DIR / f"earnings-{date_str}.jsonl"
        if fp.exists():
            with open(fp) as f:
                for line in f:
                    try:
                        e = json.loads(line)
                        if e.get("amount_eur", 0) > 0:
                            summary["total_earned"] += e["amount_eur"]
                        if e.get("status") == "completed":
                            summary["surveys_completed"] += 1
                        else:
                            summary["surveys_failed"] += 1
                        prov = e.get("provider", "unknown")
                        summary["by_provider"][prov] = \
                            summary["by_provider"].get(prov, 0) + 1
                    except (json.JSONDecodeError, KeyError):
                        pass

        # Errors
        fp = LOGS_DIR / f"errors-{date_str}.jsonl"
        if fp.exists():
            with open(fp) as f:
                for line in f:
                    summary["errors_count"] += 1

    return summary


def print_summary(summary: Dict[str, Any]):
    """Print a formatted summary."""
    print(f"\n{'='*50}")
    print("  SURVEY SUMMARY")
    print(f"{'='*50}")
    print(f"  Total earned:   {summary['total_earned']:.2f}€")
    print(f"  Completed:      {summary['surveys_completed']}")
    print(f"  Failed/Blocked: {summary['surveys_failed']}")
    print(f"  Total errors:   {summary['errors_count']}")
    if summary["by_provider"]:
        print("\n  By Provider:")
        for prov, count in sorted(summary["by_provider"].items(), key=lambda x: -x[1]):
            print(f"    {prov:20s}: {count}")
    print(f"{'='*50}\n")
