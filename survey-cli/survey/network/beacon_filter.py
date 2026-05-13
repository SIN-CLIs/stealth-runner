"""
Beacon filter — URL classification for non-essential network requests.

SR-174: Pre-Click Network Gate.

Analytics pings, telemetry beacons, and similar fire-and-forget requests must
NOT count toward "pending request" totals — otherwise chatty providers like Cint
would never satisfy a `pending == 0` gate.

Design notes:
    - Patterns are anchored to specific known-analytics signatures, not greedy
      substring matches. The regex ``analytics`` alone would erroneously match
      ``survey-analytics-provider.com`` and break survey progress-tracking.
    - All patterns are precompiled at module import (no per-request compile cost).
    - The filter is conservative: when in doubt, count the request. False
      positives (beacons treated as real) only slow us down. False negatives
      (real requests treated as beacons) silently break the gate.
"""

from __future__ import annotations

import re
from typing import Iterable, Pattern

# Public default patterns. Order does not matter (any match -> beacon).
# Each pattern is anchored to a domain or path fragment that we have observed
# in production logs across pollfish/cint/lucid/qualtrics traffic.
DEFAULT_BEACON_PATTERNS: tuple[str, ...] = (
    # Major analytics providers (full domain match).
    r"^https?://(?:[a-z0-9-]+\.)*google-analytics\.com/",
    r"^https?://(?:[a-z0-9-]+\.)*googletagmanager\.com/",
    r"^https?://(?:[a-z0-9-]+\.)*doubleclick\.net/",
    r"^https?://(?:[a-z0-9-]+\.)*facebook\.com/tr[/?]",
    r"^https?://(?:[a-z0-9-]+\.)*hotjar\.com/",
    r"^https?://(?:[a-z0-9-]+\.)*mixpanel\.com/",
    r"^https?://(?:[a-z0-9-]+\.)*segment\.(?:io|com)/",
    r"^https?://(?:[a-z0-9-]+\.)*amplitude\.com/",
    r"^https?://(?:[a-z0-9-]+\.)*sentry\.io/api/[0-9]+/(?:envelope|store)",
    r"^https?://(?:[a-z0-9-]+\.)*bugsnag\.com/",
    r"^https?://(?:[a-z0-9-]+\.)*newrelic\.com/",
    # Path fragments that are conventionally beacons regardless of host.
    # Anchored to "/beacon", "/telemetry", "/_/log" etc. — must be a path
    # segment, not a substring.
    r"(?:^|/)beacon(?:/|$|\?)",
    r"(?:^|/)telemetry(?:/|$|\?)",
    r"(?:^|/)_/log(?:/|$|\?)",
    r"(?:^|/)collect(?:/|$|\?)",  # GA4 endpoint
    r"(?:^|/)gtag/js",
    # Pixel-style trackers and click pixels with utm/track/click query keys.
    r"\.gif\?(?:[a-z0-9_=&%-]*&)*(?:utm|track|click)",
)


class BeaconFilter:
    """Classify request URLs as 'beacon' (analytics) or 'real' (foreground).

    Patterns are compiled once at construction. The instance is thread-safe
    because compiled regex objects are immutable.

    Args:
        patterns: Iterable of regex pattern strings. If omitted, uses
            ``DEFAULT_BEACON_PATTERNS``. Patterns are matched case-insensitively.
        extra: Additional patterns to extend the default set. Used by
            provider-specific configuration without losing the defaults.
    """

    __slots__ = ("_compiled",)

    def __init__(
        self,
        patterns: Iterable[str] | None = None,
        *,
        extra: Iterable[str] | None = None,
    ) -> None:
        base = tuple(patterns) if patterns is not None else DEFAULT_BEACON_PATTERNS
        if extra:
            base = base + tuple(extra)
        self._compiled: tuple[Pattern[str], ...] = tuple(
            re.compile(p, re.IGNORECASE) for p in base
        )

    def is_beacon(self, url: str) -> bool:
        """Return True if ``url`` matches any beacon pattern.

        Empty/None-like URLs are treated as non-beacon to avoid silently
        absorbing malformed events.
        """
        if not url:
            return False
        for pat in self._compiled:
            if pat.search(url):
                return True
        return False


# Module-level singleton for callers that don't need custom patterns.
_default_filter: BeaconFilter | None = None


def get_default_filter() -> BeaconFilter:
    """Return a shared :class:`BeaconFilter` using ``DEFAULT_BEACON_PATTERNS``.

    Constructed lazily on first call. Subsequent calls return the same
    instance (compiled patterns are immutable and reusable).
    """
    global _default_filter
    if _default_filter is None:
        _default_filter = BeaconFilter()
    return _default_filter


def is_beacon(url: str) -> bool:
    """Convenience: classify ``url`` using the default beacon filter."""
    return get_default_filter().is_beacon(url)


__all__ = [
    "BeaconFilter",
    "DEFAULT_BEACON_PATTERNS",
    "get_default_filter",
    "is_beacon",
]
