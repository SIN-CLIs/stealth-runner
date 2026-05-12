"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                              ║
║              STEALTH-RUNNER — Network Module (SR-151)                        ║
║                                                                              ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  Package marker and public exports for the network module.                  ║
║                                                                              ║
║  EXPORTS:                                                                    ║
║  ────────                                                                    ║
║  ProxyEntry      - Dataclass representing a single proxy                    ║
║  ProxyPool       - Thread-safe pool manager with score-based selection      ║
║  get_proxy_pool  - Singleton getter for global pool instance               ║
║  score           - Calculate IP quality score                               ║
║  persist_event   - Log proxy event to JSONL                                ║
║  is_cold         - Check if score is below cold threshold                  ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝

Closes #151
"""

from .proxy_pool import ProxyEntry, ProxyPool, get_proxy_pool
from .ip_quality import score, persist_event, is_cold, load_events, aggregate_stats

__all__ = [
    # proxy_pool.py exports
    "ProxyEntry",
    "ProxyPool",
    "get_proxy_pool",
    # ip_quality.py exports
    "score",
    "persist_event",
    "is_cold",
    "load_events",
    "aggregate_stats",
]
