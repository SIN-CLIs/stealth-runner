"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                              ║
║              STEALTH-RUNNER — IP Quality Scoring & Persistence (SR-151)      ║
║                                                                              ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  ZWECK / PURPOSE:                                                            ║
║  ────────────────                                                            ║
║  IP-Quality Scoring Modul mit JSONL Persistence fuer Proxy-Events.          ║
║  Speichert alle Proxy-Outcomes in tagesrotierenden Log-Dateien.             ║
║                                                                              ║
║  SCORING FORMULA:                                                            ║
║  ─────────────────                                                           ║
║  Score = base(100) + success_count*2 - fail_count*5 - ban_count*10          ║
║  Clamped to [0, 200].                                                        ║
║                                                                              ║
║  PERSISTENCE:                                                                ║
║  ────────────                                                                ║
║  JSONL Format in logs/ip-quality-YYYY-MM-DD.jsonl (taeglich rotiert).       ║
║  Append-only fuer Audit Trail und Analyse.                                  ║
║                                                                              ║
║  JSONL LINE FORMAT:                                                          ║
║  ──────────────────                                                          ║
║  {"ts": "ISO8601", "label": "proxy-name", "country": "DE",                  ║
║   "outcome": "success|fail|banned", "score_before": 100, "score_after": 102}║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝

Closes #151
"""

# ═══════════════════════════════════════════════════════════════════════════════
# IMPORTS
# ═══════════════════════════════════════════════════════════════════════════════

import json
import logging
import threading
from pathlib import Path
from datetime import datetime, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .proxy_pool import ProxyEntry

# ═══════════════════════════════════════════════════════════════════════════════
# LOGGING
# ═══════════════════════════════════════════════════════════════════════════════

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════════
# CONSTANTS
# ═══════════════════════════════════════════════════════════════════════════════

# Basis-Score fuer neue Proxies
BASE_SCORE = 100

# Score-Gewichtung (identisch mit ProxyEntry.score property)
SUCCESS_WEIGHT = 2   # +2 pro Erfolg
FAIL_WEIGHT = 5      # -5 pro Fehler
BAN_WEIGHT = 10      # -10 pro Ban

# Score-Grenzen
MIN_SCORE = 0
MAX_SCORE = 200

# Cold-Schwelle (Proxies unter diesem Score sind "cold")
COLD_THRESHOLD = 10

# Log-Verzeichnis (relativ zum Projekt-Root)
LOG_DIR = Path("logs")

# File Lock fuer Thread-Safety beim Schreiben
_write_lock = threading.Lock()

# ═══════════════════════════════════════════════════════════════════════════════
# FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════


def score(
    success_count: int = 0,
    fail_count: int = 0,
    ban_count: int = 0
) -> int:
    """
    Berechnet den IP-Quality Score nach der Formel:
    Score = base(100) + success_count*2 - fail_count*5 - ban_count*10

    WARUM diese Gewichtung?
    → success*2: Langsames Wachstum, belohnt konsistente Performance.
    → fail*5: Moderate Bestrafung, ein paar Fehler sind akzeptabel.
    → ban*10: Harte Bestrafung, Bans deuten auf kompromittierte IP hin.

    Args:
        success_count: Anzahl erfolgreicher Requests.
        fail_count: Anzahl fehlgeschlagener Requests.
        ban_count: Anzahl Ban-Events (403/429).

    Returns:
        int: Score zwischen 0 und 200 (clamped).

    Example:
        >>> score(success_count=10, fail_count=2, ban_count=0)
        110  # 100 + 20 - 10 - 0
        >>> score(success_count=0, fail_count=0, ban_count=5)
        50   # 100 + 0 - 0 - 50
    """
    raw = (
        BASE_SCORE
        + (success_count * SUCCESS_WEIGHT)
        - (fail_count * FAIL_WEIGHT)
        - (ban_count * BAN_WEIGHT)
    )
    return max(MIN_SCORE, min(MAX_SCORE, raw))


def is_cold(score_value: int) -> bool:
    """
    Prueft ob ein Score als "cold" gilt (< 10).

    Cold Proxies werden bei der Auswahl deprioritized aber nicht geloescht.
    Sie koennen sich erholen wenn sie wieder erfolgreiche Requests haben.

    Args:
        score_value: Der zu pruefende Score.

    Returns:
        bool: True wenn Score < 10.
    """
    return score_value < COLD_THRESHOLD


def get_log_path() -> Path:
    """
    Liefert den Pfad zur heutigen Log-Datei.

    FORMAT: logs/ip-quality-YYYY-MM-DD.jsonl

    WARUM taeglich rotieren?
    → Kleinere Dateien, einfacher zu analysieren.
    → Alte Logs koennen archiviert/geloescht werden.
    → Timestamp im Dateinamen fuer einfache Filterung.

    Returns:
        Path: Pfad zur heutigen Log-Datei.
    """
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return LOG_DIR / f"ip-quality-{today}.jsonl"


def persist_event(
    entry: "ProxyEntry",
    outcome: str,
    score_before: int,
    score_after: int
) -> None:
    """
    Persistiert ein Proxy-Event in die tagesrotierte JSONL-Datei.

    JSONL LINE FORMAT:
    {
        "ts": "2024-01-15T12:34:56.789Z",
        "label": "residential-de-1",
        "country": "DE",
        "outcome": "success",
        "score_before": 100,
        "score_after": 102
    }

    THREAD-SAFETY:
    Verwendet _write_lock um Race Conditions zu vermeiden.
    Mehrere Threads koennen gleichzeitig Events loggen.

    Args:
        entry: Der ProxyEntry fuer den das Event aufgezeichnet wird.
        outcome: "success", "fail", oder "banned".
        score_before: Score vor dem Event.
        score_after: Score nach dem Event.
    """
    with _write_lock:
        try:
            # Log-Verzeichnis erstellen falls nicht vorhanden
            LOG_DIR.mkdir(parents=True, exist_ok=True)

            # Event-Daten
            event = {
                "ts": datetime.now(timezone.utc).isoformat(),
                "label": entry.label,
                "country": entry.country,
                "outcome": outcome,
                "score_before": score_before,
                "score_after": score_after,
            }

            # Append to JSONL (eine JSON-Zeile pro Event)
            log_path = get_log_path()
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(event) + "\n")

            logger.debug(f"Event persistiert: {entry.label} → {outcome}")

        except Exception as e:
            # Logging-Fehler sollten den Hauptfluss nicht blockieren
            logger.warning(f"Fehler beim Persistieren von Event: {e}")


def load_events(date_str: str = None) -> list:
    """
    Laedt Events aus einer JSONL-Datei.

    Args:
        date_str: Datum im Format YYYY-MM-DD. Default: heute.

    Returns:
        list: Liste von Event-Dicts.

    Example:
        >>> events = load_events("2024-01-15")
        >>> len(events)
        42
    """
    if date_str is None:
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    log_path = LOG_DIR / f"ip-quality-{date_str}.jsonl"

    if not log_path.exists():
        return []

    events = []
    with open(log_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    logger.warning(f"Ungueltige JSON-Zeile: {line[:50]}...")

    return events


def aggregate_stats(date_str: str = None) -> dict:
    """
    Aggregiert Statistiken aus Events fuer ein Datum.

    Args:
        date_str: Datum im Format YYYY-MM-DD. Default: heute.

    Returns:
        dict: {
            "total_events": int,
            "success_count": int,
            "fail_count": int,
            "ban_count": int,
            "by_proxy": {label: {"success": n, "fail": n, "banned": n}}
        }
    """
    events = load_events(date_str)

    stats = {
        "total_events": len(events),
        "success_count": 0,
        "fail_count": 0,
        "ban_count": 0,
        "by_proxy": {},
    }

    for event in events:
        outcome = event.get("outcome", "")
        label = event.get("label", "unknown")

        if outcome == "success":
            stats["success_count"] += 1
        elif outcome == "fail":
            stats["fail_count"] += 1
        elif outcome == "banned":
            stats["ban_count"] += 1

        if label not in stats["by_proxy"]:
            stats["by_proxy"][label] = {"success": 0, "fail": 0, "banned": 0}

        if outcome in ("success", "fail", "banned"):
            stats["by_proxy"][label][outcome] += 1

    return stats
