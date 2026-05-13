"""
Runner policy — Per-provider tuning knobs for the survey daemon.

SR-174: Per-provider Pre-Click Network-Gate thresholds.

Some survey providers fire constant analytics beacons (Cint pings every ~50ms),
which means a strict ``pending == 0`` gate would never settle. The
:data:`PROVIDER_NETWORK_TUNING` table records the empirically-derived
thresholds for each provider. Lookup is normalized (case-insensitive,
trimmed) and falls back to ``"_default"``.

Design notes:
    - Stored as a module-level dict of frozen dataclass instances. Provider
      names are simple strings, not an Enum, because new providers are added
      frequently and we don't want to rebuild the codebase for each one.
    - All values are conservative defaults. Override at runtime via the
      ``override`` parameter to :func:`get_network_tuning` (callers must
      pass a complete :class:`NetworkTuning`; partial overrides are intentionally
      not supported to avoid silent merge drift).
    - Future tuning knobs (DOM stability, retry budgets, vision budget) will
      live in the same module as additional frozen dataclasses.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

# Sentinel key for the fallback entry.
DEFAULT_PROVIDER: Final[str] = "_default"


@dataclass(frozen=True, slots=True)
class NetworkTuning:
    """Per-provider thresholds for the Pre-Click Network Gate (SR-174).

    Attributes:
        network_quiet_ms: Minimum age of the most recent network response
            before the gate considers the network quiet.
        max_pending_requests: Maximum number of in-flight (non-beacon)
            requests tolerated while still calling the network quiet.
            ``cint`` uses 2 because they keep ~2 analytics polls alive
            continuously; a strict 0 would block forever.
        max_wait_ms: Hard upper bound on how long the gate will wait
            before giving up and emitting ``network_never_quiet``. The
            gate then proceeds anyway (force-proceed) — better to click
            on a slightly busy page than to deadlock.
    """

    network_quiet_ms: int
    max_pending_requests: int
    max_wait_ms: int = 2000


# Empirically derived from production traffic. Keep entries lowercase.
# Adding a new provider: pick threshold > observed steady-state pending count.
PROVIDER_NETWORK_TUNING: Final[dict[str, NetworkTuning]] = {
    "pollfish": NetworkTuning(network_quiet_ms=100, max_pending_requests=0),
    "cint": NetworkTuning(network_quiet_ms=150, max_pending_requests=2),
    "lucid": NetworkTuning(network_quiet_ms=80, max_pending_requests=0),
    "qualtrics": NetworkTuning(network_quiet_ms=120, max_pending_requests=1),
    "prolific": NetworkTuning(network_quiet_ms=100, max_pending_requests=0),
    "heypiggy": NetworkTuning(network_quiet_ms=100, max_pending_requests=0),
    DEFAULT_PROVIDER: NetworkTuning(network_quiet_ms=100, max_pending_requests=0),
}


def _normalize(provider: str | None) -> str:
    if not provider:
        return DEFAULT_PROVIDER
    return provider.strip().lower()


def get_network_tuning(
    provider: str | None,
    *,
    override: NetworkTuning | None = None,
) -> NetworkTuning:
    """Look up the :class:`NetworkTuning` for ``provider``.

    Lookup is case-insensitive and trims whitespace. Unknown providers fall
    back to the ``"_default"`` entry. Passing ``override`` short-circuits
    the lookup entirely and returns the override unchanged — used by tests
    and per-survey overrides.
    """
    if override is not None:
        return override
    key = _normalize(provider)
    return PROVIDER_NETWORK_TUNING.get(key, PROVIDER_NETWORK_TUNING[DEFAULT_PROVIDER])


__all__ = [
    "NetworkTuning",
    "PROVIDER_NETWORK_TUNING",
    "DEFAULT_PROVIDER",
    "get_network_tuning",
]
