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
from typing import Any, Callable

import websocket


# Signatur für die Event-Handler-Chain. Wird aufgerufen, sobald CDP ein
# Event-Message liefert (also eine Message OHNE ``id``-Feld).
#
#   handler(method, params, session_id) -> None
#
# - ``method``:     CDP-Methoden-Name, z. B. ``"Page.javascriptDialogOpening"``
# - ``params``:     Event-Parameter-Dict (kann leer sein, nie None)
# - ``session_id``: ``None`` für Events vom Top-Target; gesetzt für OOPIF-
#                   Sub-Sessions, wenn ``Target.setAutoAttach(flatten=True)``
#                   aktiv ist (siehe ``oopif_registry.py``).
#
# Mehrere Subscriber chainen sich via ``prev = cdp.event_handler`` /
# ``cdp.event_handler = my_chained_handler`` selbst. Siehe
# ``js_dialog_handler.py`` und ``oopif_registry.py`` für Beispiele.
EventHandler = Callable[[str, "dict[str, Any]", "str | None"], None]


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
        event_handler: EventHandler | None = None,
    ):
        """Initialize CDP connection.

        Args:
            ws_url: WebSocket debugger URL (e.g. ws://127.0.0.1:9999/devtools/page/42)
            max_retries: Maximum retry attempts per call
            backoff_base: Initial backoff in seconds
            backoff_max: Maximum backoff in seconds
            timeout: Connection timeout per attempt
            reconnect_url_fn: Callable that returns a fresh WS URL on reconnect
            event_handler: Optional callback for CDP events (messages without
                ``id``). Signature ``(method, params, session_id) -> None``.
                Wird aus ``_recv_until_id`` und ``drain_events`` aufgerufen.
                Exceptions im Handler werden geschluckt — die Request-
                Schleife darf nie crashen. Subscriber chainen sich via
                ``prev = cdp.event_handler`` / ``cdp.event_handler = ...``.
                Siehe ``js_dialog_handler.py`` (#94) und ``oopif_registry.py``
                (#93).
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
        # Public attribute: Subscriber dürfen es lesen und ersetzen (chaining).
        self.event_handler: EventHandler | None = event_handler

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
        session_id: str | None = None,
    ) -> dict[str, Any]:
        """Send a CDP command and return the result dict.

        Args:
            method: CDP method name (e.g. "Runtime.evaluate")
            params: Command parameters
            retry: Whether to retry on transient failures
            session_id: Optional CDP ``sessionId`` for multiplexed sub-targets
                (OOPIFs unter ``Target.setAutoAttach(flatten=True)``). Wenn
                gesetzt, wird das Feld ``sessionId`` ins Outgoing-Message
                gemergt; die CDP-Antwort enthält dieselbe ``sessionId`` und
                wird durch ``_recv_until_id`` korrekt zugeordnet. Wenn
                ``None``: Top-Target.

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

        msg: dict[str, Any] = {
            "id": msg_id,
            "method": method,
            "params": params or {},
        }
        if session_id:
            msg["sessionId"] = session_id
        payload = json.dumps(msg)

        max_attempts = self.max_retries if retry else 1
        last_error = None

        for attempt in range(max_attempts):
            try:
                if self._ws is None:
                    raise CDPError("WebSocket disconnected during send")
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

        Events (messages WITHOUT ``id``) are dispatched to
        ``self.event_handler`` falls dieser registriert ist. So können
        Subscriber wie ``JsDialogHandler`` (#94) und ``OopifRegistry`` (#93)
        auf CDP-Events reagieren, ohne dass wir den Sync-Client um eine
        async Event-Loop erweitern müssen.
        """
        while True:
            if self._ws is None:
                raise CDPError("WebSocket disconnected during recv")
            raw = self._ws.recv()
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue
            # Antwort auf unseren Request → fertig
            if "id" in data and data["id"] == target_id:
                return raw
            # Event-Message (kein "id") → an Handler dispatchen
            if "method" in data:
                self._dispatch_event(data)

    def _dispatch_event(self, data: dict[str, Any]) -> None:
        """Schickt eine Event-Message an den registrierten ``event_handler``.

        Schluckt JEDE Exception aus dem Handler — die Request-Schleife darf
        nie wegen eines bug-gy Subscribers crashen.
        """
        handler = self.event_handler
        if handler is None:
            return
        try:
            handler(
                str(data.get("method") or ""),
                data.get("params") or {},
                data.get("sessionId"),
            )
        except Exception:
            # Bewusst geschluckt: Event-Subscriber-Crashes dürfen nie die
            # Sync-Request-Schleife killen. Wer Logging will, soll im
            # eigenen Handler try/except + log machen.
            pass

    def drain_events(self, timeout: float = 0.05) -> int:
        """Non-blocking Event-Drain: holt alle pending Events ab.

        Im Sync-Client kommen Events nur als Beifang zwischen Request-Antworten
        an. Wer aktiv Events erwarten muss (z. B. ``Target.attachedToTarget``
        direkt nach ``setAutoAttach``, oder ``Page.javascriptDialogOpening``
        nach einem Klick auf einen Submit-Button), ruft diese Methode auf, um
        die WebSocket-Queue ohne Blocking abzubauen.

        Args:
            timeout: Pro-recv-Timeout in Sekunden. 0 = unverzüglicher Abbruch
                wenn die Queue leer ist; 0.05–0.1s ist ein guter Default,
                wenn man wartet bis Chrome geantwortet hat.

        Returns:
            Anzahl der gedrainten Events (für Tests/Debug).
        """
        if self._ws is None:
            return 0
        prev_timeout: float | None = None
        # Nur Real-Sockets unterstützen settimeout; Tests mit Mock-Objekten
        # nicht.
        has_settimeout = hasattr(self._ws, "settimeout") and hasattr(
            self._ws, "gettimeout"
        )
        if has_settimeout:
            try:
                prev_timeout = self._ws.gettimeout()
            except Exception:
                prev_timeout = None
            try:
                self._ws.settimeout(timeout)
            except Exception:
                pass
        count = 0
        try:
            while True:
                try:
                    if self._ws is None:
                        raise CDPError("WebSocket disconnected during recv")
                    raw = self._ws.recv()
                except Exception:
                    # Timeout oder closed → fertig. Wir unterscheiden hier
                    # NICHT zwischen Timeout und echtem Fehler — beides
                    # bedeutet "keine weiteren Events grad".
                    break
                if not raw:
                    break
                try:
                    data = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                if "method" in data:
                    self._dispatch_event(data)
                    count += 1
                # Späte Request-Antworten (ID, aber falsche ID): ignorieren.
                # Sollte praktisch nie vorkommen, weil _recv_until_id strikt
                # alles vor der erwarteten ID konsumiert.
        finally:
            if has_settimeout and prev_timeout is not None:
                try:
                    self._ws.settimeout(prev_timeout)
                except Exception:
                    pass
        return count

    def call_result(
        self,
        method: str,
        params: dict[str, Any] | None = None,
        **kwargs,
    ) -> dict[str, Any]:
        """Send a CDP command and return 'result' dict directly.

        Shorthand for: send(method, params)["result"]
        Akzeptiert dieselben kwargs wie ``call`` (inkl. ``session_id``).
        """
        response = self.call(method, params, **kwargs)
        return response.get("result", {})


# ── Convenience factory ──────���───────────────────────────────────


def create_cdp(ws_url: str, **kwargs) -> CDPConnection:
    """Create and connect a CDPConnection."""
    cdp = CDPConnection(ws_url, **kwargs)
    cdp.connect()
    return cdp
