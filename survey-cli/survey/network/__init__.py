"""
Stealth-Runner — Network Module.

SR-151: Proxy pool, IP-quality scoring.
SR-174: Per-page CDP network tracker + beacon filter (pre-click gate input).

Exports:
    Proxy pool (SR-151):
        ProxyEntry, ProxyPool, get_proxy_pool
        score, persist_event, is_cold, load_events, aggregate_stats

    Pre-click gate inputs (SR-174):
        BeaconFilter, DEFAULT_BEACON_PATTERNS, get_default_filter, is_beacon
        CdpNetworkTracker, NetworkActivity
"""

from .proxy_pool import ProxyEntry, ProxyPool, get_proxy_pool
from .ip_quality import score, persist_event, is_cold, load_events, aggregate_stats
from .beacon_filter import (
    BeaconFilter,
    DEFAULT_BEACON_PATTERNS,
    get_default_filter,
    is_beacon,
)
from .cdp_network_tracker import CdpNetworkTracker, NetworkActivity

__all__ = [
    # proxy_pool.py exports (SR-151)
    "ProxyEntry",
    "ProxyPool",
    "get_proxy_pool",
    # ip_quality.py exports (SR-151)
    "score",
    "persist_event",
    "is_cold",
    "load_events",
    "aggregate_stats",
    # beacon_filter.py exports (SR-174)
    "BeaconFilter",
    "DEFAULT_BEACON_PATTERNS",
    "get_default_filter",
    "is_beacon",
    # cdp_network_tracker.py exports (SR-174)
    "CdpNetworkTracker",
    "NetworkActivity",
]
