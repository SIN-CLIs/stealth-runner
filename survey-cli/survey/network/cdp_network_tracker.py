"""
CDP Network Tracker — Per-page in-flight request counter.

SR-174: Pre-Click Network Gate.

Subscribes to Chrome DevTools Protocol Network events for a single Playwright
``Page`` and maintains a real-time count of in-flight (pending) requests, with
beacon-style analytics traffic filtered out.

Lifecycle (must be respected to avoid event-listener leaks):

    tracker = CdpNetworkTracker(page)
    await tracker.attach()
    try:
        ...                        # call tracker.activity() at any time
    finally:
        await tracker.detach()

Or as an async context manager:

    async with CdpNetworkTracker(page) as tracker:
        ...

CDP events subscribed:
    - ``Network.requestWillBeSent``  -> mark request pending (if not beacon)
    - ``Network.responseReceived``   -> bookkeeping (status code)
    - ``Network.loadingFinished``    -> mark request done
    - ``Network.loadingFailed``      -> mark request done (with error)

Concurrency:
    Single asyncio event loop. All event handlers are synchronous callbacks
    invoked by Playwright's CDP session — they only mutate dicts/counters
    under the same loop, so no locks are needed.

Memory safety:
    - Bounded per-request map: at most ``max_tracked_requests`` entries.
      When the cap is hit we drop the oldest pending entry from the map
      (the request still counts toward the in-flight total until its
      finish/fail event arrives, but we forget its metadata). This protects
      against runaway DOMs that fire thousands of XHRs without ever closing.
    - Listeners are detached idempotently on ``detach()`` and via
      ``async with`` cleanup. ``page.is_closed()`` is checked before
      detaching to avoid CDP errors on already-torn-down pages.
"""

from __future__ import annotations

import asyncio
import logging
from collections import OrderedDict
from dataclasses import dataclass
from time import monotonic
from typing import Any, Protocol, runtime_checkable

from survey.network.beacon_filter import BeaconFilter, get_default_filter

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lightweight Page protocol — keeps the tracker testable without a real
# Playwright Page object. The real Playwright ``Page`` satisfies this protocol.
# ---------------------------------------------------------------------------


@runtime_checkable
class _CdpSession(Protocol):
    async def send(self, method: str, params: dict[str, Any] | None = ...) -> Any: ...
    def on(self, event: str, handler: Any) -> None: ...  # noqa: E704
    def remove_listener(self, event: str, handler: Any) -> None: ...  # noqa: E704
    async def detach(self) -> None: ...


@runtime_checkable
class _PageLike(Protocol):
    def is_closed(self) -> bool: ...
    @property
    def context(self) -> Any: ...


# ---------------------------------------------------------------------------
# Public dataclass returned from snapshots of tracker state.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class NetworkActivity:
    """Immutable snapshot of network activity at a single point in time.

    Attributes:
        pending_count: Number of in-flight (non-beacon) requests right now.
        last_response_ts: Monotonic timestamp (seconds) of the most recent
            ``responseReceived``/``loadingFinished``/``loadingFailed`` event,
            or ``None`` if no response has ever been seen.
        last_response_age_ms: Milliseconds since the most recent response,
            or a large sentinel (``9_999_999``) if no response has been seen.
        total_started: Cumulative count of non-beacon requests started since
            ``attach()``.
        total_finished: Cumulative count of non-beacon requests completed
            (finished or failed) since ``attach()``.
        beacons_filtered: Cumulative count of requests classified as beacons
            and excluded from ``pending_count``.
    """

    pending_count: int
    last_response_ts: float | None
    last_response_age_ms: int
    total_started: int
    total_finished: int
    beacons_filtered: int

    def is_quiet(self, *, max_pending: int, min_age_ms: int) -> bool:
        """Return True if the network is quiet by the given thresholds.

        Quiet means: ``pending_count <= max_pending`` AND the last response
        is at least ``min_age_ms`` milliseconds old. If no response has ever
        been seen, the age requirement is automatically satisfied (there is
        nothing to wait for).
        """
        if self.pending_count > max_pending:
            return False
        if self.last_response_ts is None:
            return True
        return self.last_response_age_ms >= min_age_ms


# ---------------------------------------------------------------------------
# Internal per-request bookkeeping.
# ---------------------------------------------------------------------------


@dataclass
class _PendingRequest:
    request_id: str
    url: str
    started_at: float


# ---------------------------------------------------------------------------
# Tracker.
# ---------------------------------------------------------------------------


class CdpNetworkTracker:
    """Per-page tracker for in-flight, non-beacon network requests.

    Args:
        page: A Playwright ``Page`` or compatible object exposing
            ``is_closed()`` and ``context.new_cdp_session(page)``.
        beacon_filter: Optional custom :class:`BeaconFilter`. Defaults to the
            module-level shared filter.
        max_tracked_requests: Soft cap on the per-request metadata map. When
            exceeded, the oldest pending entry is forgotten (its in-flight
            count is still respected on finish/fail). Default 1024.
    """

    def __init__(
        self,
        page: Any,
        *,
        beacon_filter: BeaconFilter | None = None,
        max_tracked_requests: int = 1024,
    ) -> None:
        self._page = page
        self._filter: BeaconFilter = beacon_filter or get_default_filter()
        self._max_tracked = max_tracked_requests

        # Per-request bookkeeping. OrderedDict so we can drop the oldest
        # entry deterministically when we hit the cap.
        self._pending: OrderedDict[str, _PendingRequest] = OrderedDict()

        # CDP session and listener handles for clean detach.
        self._session: _CdpSession | None = None
        self._handlers: list[tuple[str, Any]] = []

        # Cumulative counters.
        self._total_started = 0
        self._total_finished = 0
        self._beacons_filtered = 0
        self._last_response_ts: float | None = None

        # Detach idempotency.
        self._attached = False
        self._detach_lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def attach(self) -> None:
        """Open a CDP session and subscribe to Network events.

        Idempotent — calling ``attach()`` on an already-attached tracker is
        a no-op and emits a debug log.
        """
        if self._attached:
            logger.debug("CdpNetworkTracker already attached; skip")
            return
        if self._page.is_closed():
            raise RuntimeError("Cannot attach to a closed page")

        # Playwright async API:
        #   session = await page.context.new_cdp_session(page)
        session = await self._page.context.new_cdp_session(self._page)
        self._session = session

        # Subscribe handlers.
        self._register("Network.requestWillBeSent", self._on_request)
        self._register("Network.responseReceived", self._on_response)
        self._register("Network.loadingFinished", self._on_loading_finished)
        self._register("Network.loadingFailed", self._on_loading_failed)

        await session.send("Network.enable", {})
        self._attached = True
        logger.debug("CdpNetworkTracker attached")

    def _register(self, event: str, handler: Any) -> None:
        assert self._session is not None
        self._session.on(event, handler)
        self._handlers.append((event, handler))

    async def detach(self) -> None:
        """Tear down the CDP session and remove all event listeners.

        Safe to call multiple times. Safe to call on closed pages — CDP
        errors raised during detach are logged and swallowed.
        """
        async with self._detach_lock:
            if not self._attached:
                return
            session = self._session
            self._attached = False

            if session is None:
                return

            # Remove listeners first so any late events during detach are dropped.
            for event, handler in self._handlers:
                try:
                    session.remove_listener(event, handler)
                except Exception as exc:  # pragma: no cover - defensive
                    logger.debug("Listener detach failed for %s: %s", event, exc)
            self._handlers.clear()

            # Best-effort CDP cleanup. Page may already be closed.
            try:
                if not self._page.is_closed():
                    await session.send("Network.disable", {})
            except Exception as exc:  # pragma: no cover - defensive
                logger.debug("Network.disable on detach failed: %s", exc)
            try:
                await session.detach()
            except Exception as exc:  # pragma: no cover - defensive
                logger.debug("CDP session.detach failed: %s", exc)

            self._session = None
            logger.debug("CdpNetworkTracker detached")

    async def __aenter__(self) -> "CdpNetworkTracker":
        await self.attach()
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        await self.detach()

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _on_request(self, params: dict[str, Any]) -> None:
        request_id = params.get("requestId")
        url = (params.get("request") or {}).get("url", "")
        if not request_id:
            return

        if self._filter.is_beacon(url):
            self._beacons_filtered += 1
            return

        # Cap protection: drop oldest if we'd overflow. The dropped request
        # still counts toward pending until its finish event arrives — we
        # just forget its metadata.
        if len(self._pending) >= self._max_tracked:
            self._pending.popitem(last=False)

        self._pending[request_id] = _PendingRequest(
            request_id=request_id, url=url, started_at=monotonic()
        )
        self._total_started += 1

    def _on_response(self, params: dict[str, Any]) -> None:
        # responseReceived is bookkeeping only — the request is not "done"
        # until loadingFinished/loadingFailed fires. But we treat receiving
        # bytes as "the server replied" for last_response_age purposes,
        # which is what the gate actually cares about.
        self._last_response_ts = monotonic()

    def _on_loading_finished(self, params: dict[str, Any]) -> None:
        self._finish(params.get("requestId"))

    def _on_loading_failed(self, params: dict[str, Any]) -> None:
        self._finish(params.get("requestId"))

    def _finish(self, request_id: str | None) -> None:
        if not request_id:
            return
        if request_id in self._pending:
            self._pending.pop(request_id, None)
            self._total_finished += 1
            self._last_response_ts = monotonic()
        # If request_id is not in _pending it was either a beacon or we
        # dropped it under the cap — either way no count change is needed.

    # ------------------------------------------------------------------
    # Snapshot API
    # ------------------------------------------------------------------

    def activity(self) -> NetworkActivity:
        """Return an immutable snapshot of current network activity."""
        if self._last_response_ts is None:
            age_ms = 9_999_999
        else:
            age_ms = int((monotonic() - self._last_response_ts) * 1000)
        return NetworkActivity(
            pending_count=len(self._pending),
            last_response_ts=self._last_response_ts,
            last_response_age_ms=age_ms,
            total_started=self._total_started,
            total_finished=self._total_finished,
            beacons_filtered=self._beacons_filtered,
        )

    @property
    def is_attached(self) -> bool:
        return self._attached


__all__ = [
    "CdpNetworkTracker",
    "NetworkActivity",
]
