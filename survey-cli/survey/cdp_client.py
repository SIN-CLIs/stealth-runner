"""================================================================================
CDP WEBSOCKET CLIENT — Synchron, Retry, Reconnect, ID Routing
================================================================================

WAS IST DAS?
  Leichtgewichtiger synchroner CDP WebSocket Client.
  Löst Kernprobleme OHNE async/await Refactor:
  1. ID-basiertes Response-Routing (verhindert "response consumed" Fehler)
  2. Exponentieller Backoff Retry (5 Versuche bei transienten Fehlern)
  3. Auto-Reconnect bei "No such target" Fehlern
  4. Drop-in Replacement für ws.send()/ws.recv() Patterns

ARCHITEKTUR:
  ┌─────────────────────┐
  │  CDPConnection      │
  │  (Klasse)           │
  └─────────────────────┘
         │
    ┌────┴────────┬────────┬────────┐
    ▼             ▼        ▼        ▼
  connect()    send()   recv()   close()
    │             │        │        │
    ▼             ▼        ▼        ▼
  WebSocket   Request   Response  Cleanup
    │             │        │
    └─────────────┴────────┘
              │
              ▼
         ID Routing
         (request_id)

WARUM Synchron statt Async?
  - Einfachheit: Keine async/await im gesamten Code
  - Kompatibilität: Funktioniert mit allen existierenden Tools
  - Performance: Für Survey-Automation ist async nicht nötig
  → 99% der Operationen sind sequentiell (Snapshot → Decision → Execute).

WARUM ID-basiertes Routing?
  CDP WebSocket ist bidirektional. Antworten kommen asynchron.
  Ohne ID-Routing: recv() konsumiert falsche Antwort (z.B. Console-Log
  statt Runtime.evaluate Ergebnis).
  → request_id matching = zuverlässige Antwort-Zuordnung.

WARUM Exponentieller Backoff?
  Transiente Fehler (Netzwerk, Chrome-Restart) sollten retryed werden.
  - Versuch 1: sofort
  - Versuch 2: 1s warten
  - Versuch 3: 2s warten
  - Versuch 4: 4s warten
  - Versuch 5: 8s warten
  → Vermeidet Overload bei schnellen Retries.

DEPENDENZEN:
  - websocket-client (pip install websocket-client)

BANNED METHODS — NIEMALS VERWENDEN (siehe /banned.md):
  ❌ playstealth launch
  ❌ webauto-nodriver — ABSOLUT BANNED
  ❌ cua-driver click (raw index)
  ❌ --remote-allow-origins=* (ohne Quotes)
  ❌ /tmp/heypiggy-bot (fixed profile)
  ❌ Hardcoded PIDs
  ❌ pkill -f "Google Chrome"
  ❌ killall Google Chrome
  ❌ skylight-cli click --element-index
================================================================================"""

from __future__ import annotations

import json
import time
from typing import Any

import websocket


class CDPError(Exception):
    """CDP command returned an error."""
    pass


class CDPConnectionError(Exception):
    """CDP WebSocket connection failed after retries."""
    pass


class CDPConnection:
    """Synchronous CDP client that wraps a WebSocket connection.

    Usage:
        with CDPConnection(ws_url) as cdp:
            result = cdp.call("Runtime.evaluate", {"expression": "1+1"})
            print(result["result"]["result"]["value"])  # → 2

    Auto-retries with exponential backoff on:
    - Connection failures
    - "No such target" errors (reconnects to a new WS)
    - Transient WebSocket errors
    """

    def __init__(
        self,
        ws_url: str,
        *,
        max_retries: int = 5,
        backoff_base: float = 0.3,
        backoff_max: float = 5.0,
        timeout: float = 15.0,
        reconnect_url_fn=None,
    ):
        """Initialize CDP connection.

        Args:
            ws_url: WebSocket debugger URL (e.g. ws://127.0.0.1:9999/devtools/page/42)
            max_retries: Maximum retry attempts per call
            backoff_base: Initial backoff in seconds
            backoff_max: Maximum backoff in seconds
            timeout: Connection timeout per attempt
            reconnect_url_fn: Callable that returns a fresh WS URL on reconnect
        """
        self.ws_url = ws_url
        self.max_retries = max_retries
        self.backoff_base = backoff_base
        self.backoff_max = backoff_max
        self.timeout = timeout
        self.reconnect_url_fn = reconnect_url_fn
        self._ws: websocket.WebSocket | None = None
        self._id_counter = 1
        self._call_count = 0

    def connect(self) -> None:
        """Connect to the CDP WebSocket with retry."""
        last_error = None
        for attempt in range(self.max_retries):
            try:
                self._ws = websocket.create_connection(
                    self.ws_url, timeout=self.timeout
                )
                # settimeout may not exist on mock objects
                if hasattr(self._ws, 'settimeout'):
                    self._ws.settimeout(self.timeout)
                return
            except Exception as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    wait = min(
                        self.backoff_base * (2 ** attempt),
                        self.backoff_max,
                    )
                    time.sleep(wait)
        raise CDPConnectionError(
            f"Failed to connect to {self.ws_url} after {self.max_retries} attempts: {last_error}"
        )

    def close(self) -> None:
        """Close the WebSocket connection."""
        if self._ws:
            try:
                self._ws.close()
            except Exception:
                pass
            self._ws = None

    def __enter__(self) -> CDPConnection:
        self.connect()
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def call(
        self,
        method: str,
        params: dict[str, Any] | None = None,
        *,
        retry: bool = True,
    ) -> dict[str, Any]:
        """Send a CDP command and return the result dict.

        Args:
            method: CDP method name (e.g. "Runtime.evaluate")
            params: Command parameters
            retry: Whether to retry on transient failures

        Returns:
            The full CDP response dict.

        Raises:
            CDPError: If the CDP command returned an error.
            CDPConnectionError: After max_retries failed attempts.
        """
        if self._ws is None:
            self.connect()

        msg_id = self._id_counter
        self._id_counter += 1
        self._call_count += 1

        payload = json.dumps({
            "id": msg_id,
            "method": method,
            "params": params or {},
        })

        max_attempts = self.max_retries if retry else 1
        last_error = None

        for attempt in range(max_attempts):
            try:
                self._ws.send(payload)
                response = self._recv_until_id(msg_id)
                response_data = json.loads(response)

                # Check for CDP error
                if "error" in response_data:
                    raise CDPError(
                        f"CDP command {method} failed: {response_data['error']}"
                    )

                return response_data

            except (websocket.WebSocketException, OSError) as e:
                last_error = e
                error_str = str(e)

                # Always try to reconnect on WebSocket failure
                if attempt < max_attempts - 1:
                    # Handle "No such target" → get fresh URL
                    if "No such target" in error_str and self.reconnect_url_fn:
                        try:
                            self.ws_url = self.reconnect_url_fn()
                        except Exception:
                            pass
                    # Close and reconnect
                    try:
                        self.close()
                        self.connect()
                    except Exception:
                        pass
                    # Wait with backoff before retry
                    wait = min(
                        self.backoff_base * (2 ** attempt),
                        self.backoff_max,
                    )
                    time.sleep(wait)

            except CDPError:
                raise  # Don't retry CDP command errors

        raise CDPConnectionError(
            f"CDP call {method} failed after {max_attempts} attempts: {last_error}"
        )

    def _recv_until_id(self, target_id: int) -> str:
        """Read WebSocket messages until we find one with the matching ID.

        This solves the "response consumed" problem: messages for other IDs
        (events, other callers) are skipped, and the correct response is
        returned to the caller.
        """
        while True:
            raw = self._ws.recv()
            try:
                data = json.loads(raw)
                # Event messages have no 'id' field
                if "id" in data and data["id"] == target_id:
                    return raw
                # Events are ignored — they'd be handled by an event loop
                # in a more complex client, but for synchronous use we skip them
            except json.JSONDecodeError:
                continue

    def call_result(
        self,
        method: str,
        params: dict[str, Any] | None = None,
        **kwargs,
    ) -> dict[str, Any]:
        """Send a CDP command and return 'result' dict directly.

        Shorthand for: send(method, params)["result"]
        """
        response = self.call(method, params, **kwargs)
        return response.get("result", {})


# ── Convenience factory ──────────────────────────────────────────


def create_cdp(ws_url: str, **kwargs) -> CDPConnection:
    """Create and connect a CDPConnection."""
    cdp = CDPConnection(ws_url, **kwargs)
    cdp.connect()
    return cdp