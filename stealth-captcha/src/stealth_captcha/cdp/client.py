"""Async CDP WebSocket client with multiplexed sessions and event streaming.

Design:
  - Single WebSocket connection → multiplexed sessions via CDP Target.attachToTarget
  - Auto-incrementing message IDs with Future-based dispatch
  - Background reader task that routes responses to pending futures and events to handlers
  - Tenacity-based reconnection (exponential backoff, 5 attempts)
  - Context manager support for both client and sessions

CDP protocol primer: https://chromedevtools.github.io/devtools-protocol/
"""

from __future__ import annotations

import asyncio
import contextlib
import itertools
import json
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

import websockets
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)
from websockets.asyncio.client import ClientConnection

from stealth_captcha.exceptions import CDPCommandError, CDPConnectionError
from stealth_captcha.telemetry import get_logger

log = get_logger(__name__)


@dataclass(slots=True)
class _Pending:
    """A Future waiting for a CDP response, keyed by message ID."""

    future: asyncio.Future[dict[str, Any]]


@dataclass(slots=True)
class CDPSession:
    """A session attached to a specific CDP target (page/iframe).

    Created via CDPClient.attach(target_id). All domain commands (Page, Runtime,
    Input, DOM, etc.) are sent through this session.
    """

    session_id: str
    target_id: str
    client: CDPClient

    async def send(
        self,
        method: str,
        params: dict[str, Any] | None = None,
        *,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        """Send a CDP command and wait for the result.

        Args:
            method: CDP method name (e.g. "Runtime.evaluate")
            params: Command parameters
            timeout: Override the client-wide command_timeout_s

        Returns:
            The 'result' dict from the CDP response.

        Raises:
            CDPCommandError: If the command returns an error or times out.
        """
        return await self.client._send(
            method, params or {},
            session_id=self.session_id,
            timeout=timeout,
        )

    def on(self, event: str, handler: Any) -> None:
        """Register an event handler for this session.

        Args:
            event: CDP event name (e.g. "Page.loadEventFired")
            handler: Callable (sync or async) that receives the params dict.
        """
        self.client._handlers.setdefault((self.session_id, event), []).append(handler)

    def off(self, event: str, handler: Any) -> None:
        """Remove a previously registered event handler."""
        bucket = self.client._handlers.get((self.session_id, event), [])
        if handler in bucket:
            bucket.remove(handler)


@dataclass(slots=True)
class CDPClient:
    """Root CDP client connected to a browser WebSocket endpoint.

    Usage:
        async with await CDPClient.connect(ws_url) as c:
            session = await c.attach(target_id)
            result = await session.send("Runtime.evaluate", {"expression": "1+1"})
    """

    ws_url: str
    command_timeout_s: float = 15.0
    _ws: ClientConnection | None = field(default=None, repr=False)
    _id_gen: Any = field(default_factory=lambda: itertools.count(1), repr=False)
    _pending: dict[int, _Pending] = field(default_factory=dict, repr=False)
    _handlers: dict[tuple[str | None, str], list[Any]] = field(default_factory=dict, repr=False)
    _reader_task: asyncio.Task[None] | None = field(default=None, repr=False)
    _closed: bool = field(default=False, repr=False)

    @classmethod
    async def connect(cls, ws_url: str, *, timeout_s: float = 10.0) -> CDPClient:
        """Connect to a CDP WebSocket endpoint with automatic retry.

        Args:
            ws_url: WebSocket URL (e.g. "ws://127.0.0.1:9222/devtools/browser/...")
            timeout_s: Connection timeout per attempt.

        Returns:
            An open CDPClient ready to attach targets.

        Raises:
            CDPConnectionError: After 5 failed attempts.
        """
        try:
            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(5),
                wait=wait_exponential(multiplier=0.3, max=2.0),
                retry=retry_if_exception_type((OSError, websockets.exceptions.WebSocketException)),
                reraise=True,
            ):
                with attempt:
                    ws = await asyncio.wait_for(
                        websockets.connect(ws_url, max_size=64 * 1024 * 1024),
                        timeout=timeout_s,
                    )
        except Exception as e:
            raise CDPConnectionError(f"Could not open CDP WebSocket at {ws_url}: {e}") from e

        client = cls(ws_url=ws_url, _ws=ws)
        client._reader_task = asyncio.create_task(client._reader_loop(), name="cdp-reader")
        log.info("cdp_connected", ws_url=ws_url)
        return client

    async def aclose(self) -> None:
        """Close the CDP connection gracefully."""
        if self._closed:
            return
        self._closed = True
        if self._reader_task:
            self._reader_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._reader_task
        if self._ws:
            await self._ws.close()
        for p in self._pending.values():
            if not p.future.done():
                p.future.cancel()
        log.info("cdp_disconnected")

    async def __aenter__(self) -> CDPClient:
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.aclose()

    async def attach(self, target_id: str) -> CDPSession:
        """Attach to a target (page) and return a session for it.

        Uses flatten=True so events come directly over the root WebSocket,
        not through a separate session pipe.
        """
        result = await self._send(
            "Target.attachToTarget",
            {"targetId": target_id, "flatten": True},
        )
        return CDPSession(
            session_id=result["sessionId"],
            target_id=target_id,
            client=self,
        )

    async def _send(
        self,
        method: str,
        params: dict[str, Any],
        *,
        session_id: str | None = None,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        """Low-level CDP command send.

        Assigns a unique message ID, serializes the request, sends over the
        WebSocket, and waits for a response via Future.
        """
        ws = self._ws
        if not ws or self._closed:
            raise CDPConnectionError("CDP socket is closed or was never connected")
        msg_id = next(self._id_gen)
        payload: dict[str, Any] = {"id": msg_id, "method": method, "params": params}
        if session_id:
            payload["sessionId"] = session_id

        future: asyncio.Future[dict[str, Any]] = asyncio.get_running_loop().create_future()
        self._pending[msg_id] = _Pending(future=future)

        await ws.send(json.dumps(payload))
        try:
            return await asyncio.wait_for(future, timeout=timeout or self.command_timeout_s)
        except TimeoutError as e:
            self._pending.pop(msg_id, None)
            raise CDPCommandError(
                f"CDP command timed out after {timeout or self.command_timeout_s}s: {method}"
            ) from e

    async def _reader_loop(self) -> None:
        """Background task: reads JSON messages from the WebSocket and dispatches them.

        Messages with "id" → resolve/reject pending futures.
        Messages with "method" → dispatch to registered event handlers.
        """
        ws = self._ws
        if not ws:
            return
        try:
            async for raw in ws:
                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    log.warning("cdp_invalid_json", raw=raw[:200])
                    continue
                # Command response
                if "id" in msg:
                    pending = self._pending.pop(msg["id"], None)
                    if pending is None:
                        continue
                    if "error" in msg:
                        err = msg["error"]
                        pending.future.set_exception(
                            CDPCommandError(f"CDP error {err.get('code')}: {err.get('message')}")
                        )
                    else:
                        pending.future.set_result(msg.get("result", {}))
                # Event
                else:
                    method = msg.get("method")
                    sid = msg.get("sessionId")
                    if not method:
                        continue
                    # Dispatch to all matching handlers [(sid, method), (None, method)]
                    for handler in (
                        *self._handlers.get((sid, method), ()),
                        *self._handlers.get((None, method), ()),
                    ):
                        try:
                            result = handler(msg.get("params", {}))
                            if asyncio.iscoroutine(result):
                                asyncio.create_task(result)
                        except Exception:
                            log.exception("cdp_event_handler_error", event=method)
        except websockets.exceptions.ConnectionClosed:
            log.info("cdp_connection_closed")
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("cdp_reader_task_crashed")

    @contextlib.asynccontextmanager
    async def event_stream(
        self,
        session: CDPSession,
        event: str,
    ) -> AsyncIterator[asyncio.Queue[dict[str, Any]]]:
        """Context manager: yields an asyncio.Queue that receives CDP events.

        Example:
            async with client.event_stream(session, "Page.loadEventFired") as q:
                event_params = await q.get()
        """
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()

        def _handler(params: dict[str, Any]) -> None:
            queue.put_nowait(params)

        session.on(event, _handler)
        try:
            yield queue
        finally:
            session.off(event, _handler)
