"""survey/runner_policy.py — Central RunnerPolicy configuration (SR-173).

WHY THIS FILE EXISTS
====================
Before SR-173 there was no single place where *runtime behaviour switches* for
the survey runner lived. Sample rates, on-failure debug flags, env-aware
overrides — all of those used to be scattered across `daemon/`, ad-hoc env
reads, and hard-coded constants. SR-173 introduces the **Visual Debug Report**
(see `survey/observability/visual_debug.py`), and that feature *needs* a
sample-rate control surface that other reliability features (verifier,
attestation, retry policy) can also re-use later.

`RunnerPolicy` is therefore the central, typed, immutable runtime config.
Loading is **env-driven** so prod vs. staging vs. local-dev cleanly diverge
without code edits:

  STEALTH_ENV               = "prod" | "staging" | "dev"        (default: "dev")
  VISUAL_DEBUG_SAMPLE_RATE  = float in [0.0, 1.0]               (per-env default)
  VISUAL_DEBUG_ON_FAILURE   = "true" | "false"                  (default: "true")
  VISUAL_DEBUG_OUTPUT_DIR   = absolute path                     (default: ./debug-reports)
  VISUAL_DEBUG_MAX_QUEUE    = int >=1                           (default: 128)
  VISUAL_DEBUG_WORKERS      = int >=1                           (default: 2)
  VISUAL_DEBUG_JPEG_QUALITY = int 1..95                         (default: 70)
  VISUAL_DEBUG_MAX_KB       = int >=50                          (default: 500)

DESIGN INVARIANTS
=================
1. **Immutable** (`frozen=True`). Policy is read once at startup and passed
   down. Avoids the "someone mutated a global mid-flight" anti-pattern that
   bit us in SR-151.
2. **Pure data** — no logic, no I/O at construction time besides the explicit
   `from_env()` classmethod.
3. **Defaults are SAFE for prod**: 10 % sampling, always-on-failure. Cheap
   enough to leave on (200 MB/day @ 10 k steps — see `visual_debug.py`
   cost-budget docstring).
4. **`for_environment(env)` is the canonical preset** — call sites should NOT
   hand-tune individual fields; if you need a new preset, add it here.

BANNED METHODS — NIEMALS VERWENDEN
==================================
- playstealth launch
- webauto-nodriver — ABSOLUT BANNED
- cua-driver click (raw index)
- --remote-allow-origins=* (ohne Quotes)
- /tmp/heypiggy-bot (fixed profile)
- Hardcoded PIDs
- pkill -f "Google Chrome"
- killall Google Chrome
- skylight-cli click --element-index

RELATED ISSUES
==============
- SR-173 (#178) — introduced this file; visual-debug fields.
- SR-167 (#167) — verifier; will add `verifier_strict_mode` here when merged.
- SR-168 (#168) — attestation; will add `attestation_threshold` here when merged.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Final, Literal

# Type alias kept module-level so it can be re-exported and mock-patched
# easily in tests (lesson from SR-151: local-only types break monkeypatch).
Environment = Literal["prod", "staging", "dev"]

# Per-environment defaults
# Rationale per env:
#  prod    -- 10 % sampling keeps storage cheap (~200 MB/day @ 10 k steps),
#             but failures always render (100 % on_failure) so incident-postmortem
#             never has gaps.
#  staging -- 100 % sampling: low traffic, we want every diff visible.
#  dev     -- 100 % sampling: same as staging; engineer-facing.
_ENV_DEFAULTS: dict[Environment, tuple[float, bool]] = {
    "prod": (0.10, True),
    "staging": (1.00, True),
    "dev": (1.00, True),
}


def _parse_bool(raw: str | None, default: bool) -> bool:
    """Strict bool parser -- only 'true'/'false' (case-insensitive) accepted.

    Anti-pattern guarded against: `bool('false')` is `True` in Python.
    """
    if raw is None:
        return default
    val = raw.strip().lower()
    if val in {"true", "1", "yes", "on"}:
        return True
    if val in {"false", "0", "no", "off"}:
        return False
    return default


def _parse_float(raw: str | None, default: float, *, lo: float, hi: float) -> float:
    """Parse + clamp a float env-var into [lo, hi]. Falls back to default on error."""
    if raw is None:
        return default
    try:
        v = float(raw)
    except ValueError:
        return default
    return max(lo, min(hi, v))


def _parse_int(raw: str | None, default: int, *, lo: int, hi: int) -> int:
    """Parse + clamp an int env-var into [lo, hi]. Falls back to default on error."""
    if raw is None:
        return default
    try:
        v = int(raw)
    except ValueError:
        return default
    return max(lo, min(hi, v))


@dataclass(frozen=True, slots=True)
class RunnerPolicy:
    """Immutable runtime policy for the survey runner.

    Construct via `RunnerPolicy.from_env()` in `main()`; pass the instance
    explicitly down the call-chain (NEVER read os.environ deep in business code
    -- that defeats the whole point of a typed config object).
    """

    # environment label (informational; influences only defaults)
    environment: Environment = "dev"

    # visual-debug (SR-173)
    # Sampling fraction in [0.0, 1.0]. Sampled via deterministic hash of step_id
    # so retries on the same step yield the same sampling decision -- important
    # for not double-counting in dashboards.
    visual_debug_sample_rate: float = 0.10
    # When True, a render is forced regardless of sample_rate whenever the
    # post-action verifier (SR-167) reports failure. This is the core value
    # prop: you never miss a failed step.
    visual_debug_on_failure: bool = True
    # Absolute path where per-step HTML reports are written. Daily aggregator
    # (`scripts/build_daily_visual_report.py`) reads from here.
    visual_debug_output_dir: Path = field(
        default_factory=lambda: Path.cwd() / "debug-reports"
    )
    # Bounded queue: if the renderer thread-pool is saturated (e.g. survey is
    # going at full speed), excess frames are DROPPED rather than blocking the
    # hot path. Critical: SR-151 taught us never to block LangGraph nodes.
    visual_debug_max_queue: int = 128
    # Worker count for the off-hot-path renderer pool. 2 is plenty -- render is
    # IO-bound (PNG decode + JPEG encode + file write).
    visual_debug_workers: int = 2
    # JPEG quality (1..95). 70 ~= 30 KB per 1280x720 frame in practice. Tune
    # down if you hit the daily storage budget.
    visual_debug_jpeg_quality: int = 70
    # Hard ceiling on final HTML size (KB). Renderer re-encodes at lower quality
    # until file fits, then logs a warning if it still cannot.
    visual_debug_max_kb: int = 500

    # reserved slots for downstream issues
    # Empty placeholders intentionally NOT added -- fields are appended only when
    # the dependent feature actually lands (avoids dead config knobs).

    # construction
    @classmethod
    def for_environment(cls, env: Environment) -> "RunnerPolicy":
        """Return the canonical preset for a given environment.

        Use this when you don't want env-var overrides -- e.g. inside tests.
        """
        sample, on_fail = _ENV_DEFAULTS[env]
        return cls(
            environment=env,
            visual_debug_sample_rate=sample,
            visual_debug_on_failure=on_fail,
        )

    @classmethod
    def from_env(cls, env_map: dict[str, str] | None = None) -> "RunnerPolicy":
        """Build a policy from environment variables.

        Args:
            env_map: Optional mapping (defaults to `os.environ`). Pass an
                explicit dict in tests to avoid touching the real env.

        Order of precedence:
            1. Explicit env-vars (`VISUAL_DEBUG_*`) override everything.
            2. `STEALTH_ENV` selects the preset for un-overridden fields.
            3. Built-in defaults (dev preset) as final fallback.
        """
        e = env_map if env_map is not None else os.environ
        environment: Environment = e.get("STEALTH_ENV", "dev")  # type: ignore[assignment]
        if environment not in _ENV_DEFAULTS:
            environment = "dev"

        base = cls.for_environment(environment)

        return replace(
            base,
            visual_debug_sample_rate=_parse_float(
                e.get("VISUAL_DEBUG_SAMPLE_RATE"),
                base.visual_debug_sample_rate,
                lo=0.0,
                hi=1.0,
            ),
            visual_debug_on_failure=_parse_bool(
                e.get("VISUAL_DEBUG_ON_FAILURE"),
                base.visual_debug_on_failure,
            ),
            visual_debug_output_dir=Path(
                e.get("VISUAL_DEBUG_OUTPUT_DIR", str(base.visual_debug_output_dir))
            ),
            visual_debug_max_queue=_parse_int(
                e.get("VISUAL_DEBUG_MAX_QUEUE"),
                base.visual_debug_max_queue,
                lo=1,
                hi=10_000,
            ),
            visual_debug_workers=_parse_int(
                e.get("VISUAL_DEBUG_WORKERS"),
                base.visual_debug_workers,
                lo=1,
                hi=32,
            ),
            visual_debug_jpeg_quality=_parse_int(
                e.get("VISUAL_DEBUG_JPEG_QUALITY"),
                base.visual_debug_jpeg_quality,
                lo=1,
                hi=95,
            ),
            visual_debug_max_kb=_parse_int(
                e.get("VISUAL_DEBUG_MAX_KB"),
                base.visual_debug_max_kb,
                lo=50,
                hi=10_000,
            ),
        )

# ─────────────────────────────────────────────────────────────────────────────
# NetworkTuning — Pre-Click Network Gate (SR-174)
# ─────────────────────────────────────────────────────────────────────────────

DEFAULT_PROVIDER: Final[str] = "_default"


@dataclass(frozen=True)
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
PROVIDER_NETWORK_TUNING: Final[dict[str, NetworkTuning]] = {
    "pollfish": NetworkTuning(network_quiet_ms=100, max_pending_requests=0),
    "cint": NetworkTuning(network_quiet_ms=150, max_pending_requests=2),
    "lucid": NetworkTuning(network_quiet_ms=80, max_pending_requests=0),
    "qualtrics": NetworkTuning(network_quiet_ms=120, max_pending_requests=1),
    "prolific": NetworkTuning(network_quiet_ms=100, max_pending_requests=0),
    "heypiggy": NetworkTuning(network_quiet_ms=100, max_pending_requests=0),
    DEFAULT_PROVIDER: NetworkTuning(network_quiet_ms=100, max_pending_requests=0),
}


def _normalize_provider(provider: str | None) -> str:
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
    key = _normalize_provider(provider)
    return PROVIDER_NETWORK_TUNING.get(key, PROVIDER_NETWORK_TUNING[DEFAULT_PROVIDER])


__all__ = [
    "RunnerPolicy",
    "Environment",
    "NetworkTuning",
    "PROVIDER_NETWORK_TUNING",
    "DEFAULT_PROVIDER",
    "get_network_tuning",
]
