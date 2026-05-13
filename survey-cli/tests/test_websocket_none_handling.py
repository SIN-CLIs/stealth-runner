"""SR-194 B1: regression tests for WebSocket | None handling.

Before this PR the four hot-path call sites below would raise
``AttributeError: 'NoneType' object has no attribute 'send'`` (or
``'recv'``) whenever the WebSocket was torn down between attempts:

  - survey/safe_executor.py:86 (SurveyFlowExecutor._send_cdp .send)
  - survey/safe_executor.py:87 (SurveyFlowExecutor._send_cdp .recv)
  - survey/cdp_client.py:248   (CDPConnection.call .send)
  - survey/cdp_client.py:306   (CDPConnection._recv_until_id .recv)

These tests pin the new behaviour: the connection-state contract is
enforced loudly (``CDPConnectionError`` / ``AssertionError``) instead
of silently leaking ``AttributeError`` out of a ``while True`` loop.
"""

from __future__ import annotations

import pytest

from survey.cdp_client import CDPConnection, CDPConnectionError
from survey.safe_executor import SurveyFlowExecutor


# ---------------------------------------------------------------------------
# safe_executor.py — Option A (strict assertion after _ensure_connected)
# ---------------------------------------------------------------------------


def test_safe_executor_asserts_ws_after_ensure_connected(monkeypatch):
    """If _ensure_connected lies and returns True with _ws=None, fail fast."""
    executor = SurveyFlowExecutor(tab_id="dummy")
    # Force the broken invariant: _ensure_connected says True, _ws is None.
    monkeypatch.setattr(executor, "_ensure_connected", lambda: True)
    executor._ws = None

    with pytest.raises(AssertionError, match="self._ws is None"):
        executor._send_cdp("Page.navigate", {"url": "about:blank"})


def test_safe_executor_raises_connection_error_when_not_connected(monkeypatch):
    """_ensure_connected returning False must still surface ConnectionError."""
    executor = SurveyFlowExecutor(tab_id="dummy")
    monkeypatch.setattr(executor, "_ensure_connected", lambda: False)

    with pytest.raises(ConnectionError):
        executor._send_cdp("Page.navigate")


# ---------------------------------------------------------------------------
# cdp_client.py — Option B (loud CDPConnectionError instead of AttributeError)
# ---------------------------------------------------------------------------


def _make_conn(monkeypatch) -> CDPConnection:
    """Build a CDPConnection without actually opening a WebSocket."""
    conn = CDPConnection(ws_url="ws://test/devtools/page/X")
    # Stub connect so the test never touches the network.
    monkeypatch.setattr(conn, "connect", lambda: None)
    return conn


def test_cdp_client_call_raises_when_connect_does_not_set_ws(monkeypatch):
    """call() should raise CDPConnectionError, never AttributeError.

    Regression for cdp_client.py:248 — when connect() returns without
    setting self._ws (e.g. a no-op stub in a test, or a partial
    failure in production), the next iteration's ``.send()`` used to
    crash with ``AttributeError``.
    """
    conn = _make_conn(monkeypatch)
    assert conn._ws is None  # sanity

    with pytest.raises(CDPConnectionError, match="did not establish _ws"):
        conn.call("Page.navigate", retry=False)


def test_cdp_client_recv_loop_raises_on_none_ws(monkeypatch):
    """_recv_until_id must raise CDPConnectionError when _ws disappears.

    Regression for cdp_client.py:306. Pre-fix this was a silent
    ``AttributeError: 'NoneType' object has no attribute 'recv'``
    inside a ``while True`` loop, with no hint of what went wrong.
    """
    conn = _make_conn(monkeypatch)
    conn._ws = None

    with pytest.raises(CDPConnectionError, match="disconnected during _recv_until_id"):
        conn._recv_until_id(target_id=42)


def test_cdp_client_call_re_narrows_each_attempt(monkeypatch):
    """The per-attempt guard at the top of the retry loop must fire.

    Set _ws to a stub that lets connect() pass the initial guard,
    then drop it back to None to simulate a torn-down connection
    entering the retry body.
    """

    class _Stub:
        status = "open"

        def send(self, payload):
            raise OSError("simulated disconnect")

    conn = _make_conn(monkeypatch)
    conn._ws = _Stub()
    # Reconnect callback also clears _ws to simulate a failed reconnect.
    def _bad_reconnect():
        conn._ws = None
    monkeypatch.setattr(conn, "connect", _bad_reconnect)

    with pytest.raises(CDPConnectionError):
        # max_retries=2 by default; first attempt sends + raises OSError,
        # connect() clears _ws, second attempt should hit the new guard.
        conn.call("Page.navigate", retry=True)
