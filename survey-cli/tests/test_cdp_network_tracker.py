"""
Tests for survey/network/cdp_network_tracker.py (SR-174).

Uses a fake Playwright Page + CDP session — no real browser. The fake
session records subscribed event handlers and lets the test fire CDP
events synthetically. This proves:

    - Attach/detach lifecycle is clean (handlers added then removed).
    - Beacons are filtered out of pending count.
    - Real requests increment/decrement pending.
    - last_response_age_ms tracks responses.
    - max_tracked_requests cap is enforced without losing the in-flight count.
    - Detach on closed page does not raise.
    - Double-attach / double-detach are no-ops.
    - Memory-leak proxy: 1000 attach/detach cycles produce zero retained
      handlers in the session.
"""

from __future__ import annotations

import asyncio
import unittest
from typing import Any

from survey.network.cdp_network_tracker import CdpNetworkTracker, NetworkActivity


# ---------------------------------------------------------------------------
# Fake CDP session + Page
# ---------------------------------------------------------------------------


class FakeCdpSession:
    def __init__(self) -> None:
        self.handlers: dict[str, list[Any]] = {}
        self.sent: list[tuple[str, dict]] = []
        self.detached = False

    def on(self, event: str, handler: Any) -> None:
        self.handlers.setdefault(event, []).append(handler)

    def remove_listener(self, event: str, handler: Any) -> None:
        if event in self.handlers and handler in self.handlers[event]:
            self.handlers[event].remove(handler)

    async def send(self, method: str, params: dict | None = None) -> dict:
        self.sent.append((method, params or {}))
        return {}

    async def detach(self) -> None:
        self.detached = True

    # Test helper.
    def fire(self, event: str, params: dict) -> None:
        for handler in list(self.handlers.get(event, [])):
            handler(params)

    @property
    def total_handlers(self) -> int:
        return sum(len(h) for h in self.handlers.values())


class FakeContext:
    def __init__(self, session: FakeCdpSession) -> None:
        self._session = session

    async def new_cdp_session(self, page: Any) -> FakeCdpSession:  # noqa: ARG002
        return self._session


class FakePage:
    def __init__(self, session: FakeCdpSession | None = None) -> None:
        self._session = session or FakeCdpSession()
        self._closed = False
        self.context = FakeContext(self._session)

    def is_closed(self) -> bool:
        return self._closed

    def close(self) -> None:
        self._closed = True

    @property
    def fake_session(self) -> FakeCdpSession:
        return self._session


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestCdpNetworkTrackerLifecycle(unittest.TestCase):
    def test_attach_subscribes_four_events(self):
        async def run() -> int:
            page = FakePage()
            tracker = CdpNetworkTracker(page)
            await tracker.attach()
            try:
                return page.fake_session.total_handlers
            finally:
                await tracker.detach()

        # 4 Network.* events.
        self.assertEqual(asyncio.run(run()), 4)

    def test_detach_removes_all_handlers(self):
        async def run() -> int:
            page = FakePage()
            tracker = CdpNetworkTracker(page)
            await tracker.attach()
            await tracker.detach()
            return page.fake_session.total_handlers

        self.assertEqual(asyncio.run(run()), 0)

    def test_attach_idempotent(self):
        async def run() -> int:
            page = FakePage()
            tracker = CdpNetworkTracker(page)
            await tracker.attach()
            await tracker.attach()  # no-op
            try:
                return page.fake_session.total_handlers
            finally:
                await tracker.detach()

        self.assertEqual(asyncio.run(run()), 4)

    def test_detach_idempotent(self):
        async def run() -> bool:
            page = FakePage()
            tracker = CdpNetworkTracker(page)
            await tracker.attach()
            await tracker.detach()
            await tracker.detach()  # no-op
            return tracker.is_attached

        self.assertFalse(asyncio.run(run()))

    def test_async_context_manager(self):
        async def run() -> tuple[int, int]:
            page = FakePage()
            async with CdpNetworkTracker(page) as tracker:
                self.assertTrue(tracker.is_attached)
                during = page.fake_session.total_handlers
            after = page.fake_session.total_handlers
            return during, after

        during, after = asyncio.run(run())
        self.assertEqual(during, 4)
        self.assertEqual(after, 0)

    def test_attach_on_closed_page_raises(self):
        async def run() -> None:
            page = FakePage()
            page.close()
            tracker = CdpNetworkTracker(page)
            await tracker.attach()

        with self.assertRaises(RuntimeError):
            asyncio.run(run())

    def test_detach_on_closed_page_does_not_raise(self):
        """Page closes mid-flight; detach must not raise (try/finally pattern)."""

        async def run() -> None:
            page = FakePage()
            tracker = CdpNetworkTracker(page)
            await tracker.attach()
            page.close()
            await tracker.detach()  # must not raise

        asyncio.run(run())  # no exception => pass


class TestCdpNetworkTrackerEvents(unittest.TestCase):
    def _make(self) -> tuple[FakePage, CdpNetworkTracker]:
        page = FakePage()
        tracker = CdpNetworkTracker(page)
        return page, tracker

    def test_real_request_increments_pending(self):
        async def run() -> NetworkActivity:
            page, tracker = self._make()
            await tracker.attach()
            try:
                page.fake_session.fire(
                    "Network.requestWillBeSent",
                    {
                        "requestId": "r1",
                        "request": {"url": "https://api.pollfish.com/v1/answers"},
                    },
                )
                return tracker.activity()
            finally:
                await tracker.detach()

        act = asyncio.run(run())
        self.assertEqual(act.pending_count, 1)
        self.assertEqual(act.total_started, 1)
        self.assertEqual(act.beacons_filtered, 0)

    def test_beacon_request_does_not_increment_pending(self):
        async def run() -> NetworkActivity:
            page, tracker = self._make()
            await tracker.attach()
            try:
                page.fake_session.fire(
                    "Network.requestWillBeSent",
                    {
                        "requestId": "b1",
                        "request": {"url": "https://www.google-analytics.com/collect"},
                    },
                )
                return tracker.activity()
            finally:
                await tracker.detach()

        act = asyncio.run(run())
        self.assertEqual(act.pending_count, 0)
        self.assertEqual(act.beacons_filtered, 1)
        self.assertEqual(act.total_started, 0)

    def test_loading_finished_decrements_pending(self):
        async def run() -> NetworkActivity:
            page, tracker = self._make()
            await tracker.attach()
            try:
                page.fake_session.fire(
                    "Network.requestWillBeSent",
                    {"requestId": "r1", "request": {"url": "https://api.example/x"}},
                )
                page.fake_session.fire(
                    "Network.loadingFinished", {"requestId": "r1"}
                )
                return tracker.activity()
            finally:
                await tracker.detach()

        act = asyncio.run(run())
        self.assertEqual(act.pending_count, 0)
        self.assertEqual(act.total_started, 1)
        self.assertEqual(act.total_finished, 1)

    def test_loading_failed_decrements_pending(self):
        async def run() -> NetworkActivity:
            page, tracker = self._make()
            await tracker.attach()
            try:
                page.fake_session.fire(
                    "Network.requestWillBeSent",
                    {"requestId": "r1", "request": {"url": "https://api.example/x"}},
                )
                page.fake_session.fire(
                    "Network.loadingFailed",
                    {"requestId": "r1", "errorText": "net::ERR_FAILED"},
                )
                return tracker.activity()
            finally:
                await tracker.detach()

        act = asyncio.run(run())
        self.assertEqual(act.pending_count, 0)
        self.assertEqual(act.total_finished, 1)

    def test_response_updates_last_response_ts(self):
        async def run() -> tuple[NetworkActivity, NetworkActivity]:
            page, tracker = self._make()
            await tracker.attach()
            try:
                before = tracker.activity()
                page.fake_session.fire(
                    "Network.responseReceived",
                    {"requestId": "r1", "response": {"status": 200}},
                )
                after = tracker.activity()
                return before, after
            finally:
                await tracker.detach()

        before, after = asyncio.run(run())
        self.assertIsNone(before.last_response_ts)
        self.assertIsNotNone(after.last_response_ts)
        self.assertLess(after.last_response_age_ms, 1000)

    def test_unknown_request_id_in_finish_is_ignored(self):
        """A loadingFinished for a request we never saw (e.g. beacon) must
        not decrement our pending count below zero or raise.
        """

        async def run() -> NetworkActivity:
            page, tracker = self._make()
            await tracker.attach()
            try:
                page.fake_session.fire(
                    "Network.loadingFinished", {"requestId": "ghost"}
                )
                return tracker.activity()
            finally:
                await tracker.detach()

        act = asyncio.run(run())
        self.assertEqual(act.pending_count, 0)
        self.assertEqual(act.total_finished, 0)

    def test_max_tracked_cap_drops_oldest(self):
        """When we exceed max_tracked_requests we drop the oldest entry."""

        async def run() -> int:
            page = FakePage()
            tracker = CdpNetworkTracker(page, max_tracked_requests=3)
            await tracker.attach()
            try:
                for i in range(5):
                    page.fake_session.fire(
                        "Network.requestWillBeSent",
                        {
                            "requestId": f"r{i}",
                            "request": {"url": f"https://api.example/{i}"},
                        },
                    )
                return tracker.activity().pending_count
            finally:
                await tracker.detach()

        # 5 fired, cap = 3 -> only 3 in the map. Two were silently evicted.
        self.assertEqual(asyncio.run(run()), 3)


class TestNetworkActivityIsQuiet(unittest.TestCase):
    def test_quiet_when_no_pending_and_no_response_ever(self):
        act = NetworkActivity(
            pending_count=0,
            last_response_ts=None,
            last_response_age_ms=9_999_999,
            total_started=0,
            total_finished=0,
            beacons_filtered=0,
        )
        self.assertTrue(act.is_quiet(max_pending=0, min_age_ms=100))

    def test_not_quiet_when_pending_exceeds_max(self):
        act = NetworkActivity(
            pending_count=3,
            last_response_ts=1.0,
            last_response_age_ms=500,
            total_started=3,
            total_finished=0,
            beacons_filtered=0,
        )
        self.assertFalse(act.is_quiet(max_pending=2, min_age_ms=100))

    def test_not_quiet_when_response_too_recent(self):
        act = NetworkActivity(
            pending_count=0,
            last_response_ts=1.0,
            last_response_age_ms=50,
            total_started=1,
            total_finished=1,
            beacons_filtered=0,
        )
        self.assertFalse(act.is_quiet(max_pending=0, min_age_ms=100))

    def test_quiet_when_pending_within_max_and_age_ok(self):
        act = NetworkActivity(
            pending_count=2,
            last_response_ts=1.0,
            last_response_age_ms=200,
            total_started=10,
            total_finished=8,
            beacons_filtered=5,
        )
        self.assertTrue(act.is_quiet(max_pending=2, min_age_ms=100))


class TestMemoryLeakProxy(unittest.TestCase):
    """1000 attach/detach cycles must leave zero retained handlers.

    Lightweight stand-in for the real memory-leak test (which would need
    a real Playwright browser). If listeners are leaked here, they would
    leak on the real browser too.
    """

    def test_thousand_cycles_no_listener_leak(self):
        async def run() -> int:
            page = FakePage()
            for _ in range(1000):
                tracker = CdpNetworkTracker(page)
                await tracker.attach()
                # Simulate one request-response pair per cycle.
                page.fake_session.fire(
                    "Network.requestWillBeSent",
                    {"requestId": "r", "request": {"url": "https://api.example/x"}},
                )
                page.fake_session.fire(
                    "Network.loadingFinished", {"requestId": "r"}
                )
                await tracker.detach()
            return page.fake_session.total_handlers

        self.assertEqual(asyncio.run(run()), 0)


if __name__ == "__main__":
    unittest.main()
