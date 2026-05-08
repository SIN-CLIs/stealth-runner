"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                              ║
║           STEALTH-RUNNER — Rate Limiter (In-Memory)                          ║
║                                                                              ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  ZWECK:                                                                      ║
║  Schützt vor Account-Bann durch zu häufige Requests. HeyPiggy und Survey-    ║
║  Provider tracken Request-Patterns. Zu schnelle Automation = Ban.           ║
║                                                                              ║
║  KORREKTE 3-TIER-LOGIK (kein Widerspruch!):                                ║
║  ─────────────────────────────────────────────                               ║
║  Tier 1 (Burst):     Kürzestes Fenster, höchste erlaubte Rate              ║
║  Tier 2 (Hourly):    Längeres Fenster, niedrigere erlaubte Rate            ║
║  Tier 3 (Daily):     Längstes Fenster, niedrigste erlaubte Rate           ║
║                                                                              ║
║  Beispiel /workflow/run-best:                                                ║
║    Tier 1: 1/120s  → 30/h  theoretisch möglich (Burst-Schutz)               ║
║    Tier 2: 15/h    → alle 4min im Schnitt (Hourly-Cap)                    ║
║    Tier 3: 100/day → alle 14min im Schnitt (Daily-Cap)                     ║
║                                                                              ║
║  WARUM das vorher falsch war:                                                ║
║    1/30s + 10/h + 50/day → 1/30s erlaubt 120/h, aber 10/h greift zuerst. ║
║    Das 1/30s-Limit war komplett nutzlos.                                   ║
║                                                                              ║
║  RICHTIGE LOGIK:                                                             ║
║    Wenn man kontinuierlich alle 2min (Tier 1) surveyed → nach 15 Surveys    ║
║    (30min) greift Tier 2 (15/h). Nach 100 Surveys (3.3h) greift Tier 3.    ║
║    Jedes Tier ist restriktiver als das vorherige.                          ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import time
import logging
from typing import Dict, List
from fastapi import Request, HTTPException

logger = logging.getLogger(__name__)

# In-Memory Rate Limit Store.
_rate_store: Dict[str, Dict[str, List[float]]] = {}

# KORREKTE Limits — logisch konsistent (Tier 1 > Tier 2 > Tier 3 in Rate).
# Format: [(max_requests, window_seconds), ...] — von restriktiv zu permissiv.
DEFAULT_LIMITS: Dict[str, List[tuple[int, float]]] = {
    # /workflow/run-best: Kompletter Survey-Start (Session-Check + Scan + Click).
    # Realistisch: Ein Survey dauert 2-15 Minuten.
    # Tier 1: 1/120s (alle 2min) — Burst-Schutz (warte bis Survey geladen).
    # Tier 2: 15/h — Hourly-Cap (nicht zu viele auf einmal).
    # Tier 3: 100/day — Daily-Cap (alle 14min im Schnitt).
    "/workflow/run-best": [(1, 120), (15, 3600), (100, 86400)],
    
    # /survey/click-card: Card auf Dashboard klicken.
    # Tier 1: 1/60s (alle 1min) — warte bis Modal sich öffnet.
    # Tier 2: 30/h — Hourly-Cap.
    # Tier 3: 200/day — Daily-Cap.
    "/survey/click-card": [(1, 60), (30, 3600), (200, 86400)],
    
    # /survey/click-button: "Weiter" klicken während Survey läuft.
    # Kann häufiger sein (jede Frage hat einen "Weiter"-Button).
    # Tier 1: 1/10s (alle 10s) — nicht zu schnell klicken.
    # Tier 2: 100/h — viele Fragen pro Survey.
    # Tier 3: 500/day — Daily-Cap.
    "/survey/click-button": [(1, 10), (100, 3600), (500, 86400)],
    
    "/survey/select-option": [(1, 10), (100, 3600), (500, 86400)],
    "/survey/fill-text": [(1, 10), (100, 3600), (500, 86400)],
    
    # /dashboard/scan: Monitoring — wie viele Surveys verfügbar?
    # Kann öfter abgefragt werden (nur lesend).
    # Tier 1: 1/30s (alle 30s) — nicht zu oft pollen.
    # Tier 2: 60/h — alle 1min im Schnitt.
    # Tier 3: 300/day — alle 5min im Schnitt.
    "/dashboard/scan": [(1, 30), (60, 3600), (300, 86400)],
    
    # /dashboard/balance: Monitoring — Kontostand checken.
    "/dashboard/balance": [(1, 30), (60, 3600), (300, 86400)],
}


def _get_client_id(request: Request) -> str:
    """Erzeugt eine Client-ID aus IP und User-Agent."""
    forwarded = request.headers.get("x-forwarded-for")
    ip = forwarded.split(",")[0].strip() if forwarded else request.client.host if request.client else "unknown"
    ua = request.headers.get("user-agent", "unknown")
    return f"{ip}:{ua[:50]}"


def _cleanup_old_entries():
    """Entfernt Einträge die älter als 24h sind."""
    cutoff = time.time() - 86400
    for client_id in list(_rate_store.keys()):
        for endpoint in list(_rate_store[client_id].keys()):
            _rate_store[client_id][endpoint] = [t for t in _rate_store[client_id][endpoint] if t > cutoff]
            if not _rate_store[client_id][endpoint]:
                del _rate_store[client_id][endpoint]
        if not _rate_store[client_id]:
            del _rate_store[client_id]


async def rate_limit_dependency(request: Request):
    """
    FastAPI Dependency für Rate Limiting.
    Prüft ALLE Tier-Limits. Wenn EINES greift → 429.
    """
    if len(_rate_store) > 100:
        _cleanup_old_entries()
    
    client_id = _get_client_id(request)
    path = request.url.path
    
    limits = DEFAULT_LIMITS.get(path)
    if not limits:
        for prefix, prefix_limits in DEFAULT_LIMITS.items():
            if path.startswith(prefix.rsplit("/", 1)[0] + "/"):
                limits = prefix_limits
                break
    
    if not limits:
        return
    
    now = time.time()
    client_data = _rate_store.setdefault(client_id, {})
    timestamps = client_data.setdefault(path, [])
    
    # Prüfe alle Limits. Das ERSTE das greift gewinnt.
    for max_requests, window in limits:
        count = sum(1 for t in timestamps if now - t < window)
        
        if count >= max_requests:
            # Konvertiere window in human-readable String.
            if window < 60:
                window_str = f"{window}s"
            elif window < 3600:
                window_str = f"{window//60}min"
            elif window < 86400:
                window_str = f"{window//3600}h"
            else:
                window_str = f"{window//86400}d"
            
            logger.warning(f"Rate limit exceeded: {client_id} on {path} ({count}/{max_requests} per {window_str})")
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded: max {max_requests} requests per {window_str}. Please wait."
            )
    
    timestamps.append(now)
