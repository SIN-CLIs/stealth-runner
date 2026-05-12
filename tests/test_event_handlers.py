"""Tests für #93 (OOPIF Auto-Attach) und #94 (JS-Dialog-Handler).

Beide Issues teilen sich die Event-Handler-Chain in ``cdp_client.py``. Wir
testen daher zusammen, dass:

  1. ``CDPConnection`` Events von Antworten korrekt trennt (event_handler-
     Dispatch UND _recv_until_id ignoriert Events).
  2. ``drain_events`` mehrere gestapelte Events synchron abarbeitet.
  3. ``JsDialogHandler`` ``Page.javascriptDialogOpening`` automatisch
     beantwortet und in ``self.events`` loggt.
  4. ``OopifRegistry`` ``Target.attachedToTarget`` als neue Session merkt
     und ``Target.detachedFromTarget`` sie wieder entfernt.
  5. Mehrere Subscriber chainen sich (Reihenfolge bleibt erhalten, Handler-
     Crashes werden geschluckt).

Alle Tests laufen OHNE echten Chrome — wir benutzen ein ``FakeWS``-Mock,
das wir manuell mit JSON-Messages füttern. Das hält die Tests deterministisch
und sub-millisecond schnell (CI-tauglich).
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from survey.cdp_client import CDPConnection
from survey.js_dialog_handler import JsDialogHandler, default_policy
from survey.oopif_registry import OopifRegistry


# ── Fake WebSocket ─────────────────────────────────────────────────────────


class FakeWS:
    """Minimaler Stand-in für ``websocket.WebSocket``.

    - ``send(payload)`` parst die Outgoing-Message und queued automatisch
      eine passende Response (``id`` matched) hinten an ``self.incoming``.
    - ``recv()`` poppt vorne. Tests dürfen direkt in ``self.incoming``
      schreiben, um Events einzufügen (z. B. vor der Antwort).
    - ``settimeout``/``gettimeout`` werden noops, aber lösen kein recv-
      timeout aus, weil unser ``drain_events`` einen leeren ``recv()`` als
      "fertig" interpretiert (FakeWS gibt ``""`` zurück, wenn die Queue
      leer ist).
    """

    def __init__(self) -> None:
        self.incoming: list[str] = []
        self.outgoing: list[dict[str, Any]] = []
        # Auto-Reply: für jede Outgoing-Message wird eine Erfolgsantwort
        # generiert, sofern Tests nicht explizit eine Antwort vorher in
        # ``incoming`` gestellt haben.
        self.auto_reply: bool = True
        self.closed: bool = False

    def send(self, payload: str) -> None:
        try:
            msg = json.loads(payload)
        except json.JSONDecodeError:
            return
        self.outgoing.append(msg)
        if self.auto_reply:
            reply: dict[str, Any] = {"id": msg["id"], "result": {}}
            if "sessionId" in msg:
                reply["sessionId"] = msg["sessionId"]
            self.incoming.append(json.dumps(reply))

    def recv(self) -> str:
        if not self.incoming:
            # Drain-Loop erkennt "" als "keine weiteren Events".
            raise TimeoutError("no message")
        return self.incoming.pop(0)

    def close(self) -> None:
        self.closed = True

    def settimeout(self, _t: float) -> None:
        return

    def gettimeout(self) -> float:
        return 0.0


def _wire(cdp: CDPConnection, ws: FakeWS) -> None:
    """Injects the fake WebSocket and marks the connection as established
    so ``call()`` won't try to dial out."""
    cdp._ws = ws  # type: ignore[attr-defined]


# ── 1. Event vs. Response Separation ───────────────────────────────────────


def test_recv_until_id_skips_events_and_dispatches() -> None:
    """``_recv_until_id`` darf Events NICHT als Antwort liefern, aber MUSS
    den ``event_handler`` aufrufen."""
    cdp = CDPConnection("ws://test")
    ws = FakeWS()
    ws.auto_reply = False
    _wire(cdp, ws)

    seen: list[tuple[str, dict, str | None]] = []
    cdp.event_handler = lambda m, p, s: seen.append((m, p, s))

    # 2 Events VOR der eigentlichen Antwort, plus eine Antwort mit id=42.
    ws.incoming = [
        json.dumps({"method": "Page.loadEventFired", "params": {"timestamp": 1}}),
        json.dumps({"method": "Target.attachedToTarget", "params": {"x": 1}}),
        json.dumps({"id": 42, "result": {"ok": True}}),
    ]
    # Manueller Call mit fixer ID
    cdp._id_counter = 42
    response = cdp.call("Runtime.evaluate", {"expression": "1"})
    assert response["result"] == {"ok": True}
    assert [m for (m, _, _) in seen] == [
        "Page.loadEventFired",
        "Target.attachedToTarget",
    ]


def test_event_handler_exceptions_are_swallowed() -> None:
    """Buggy Subscriber dürfen die Request-Schleife nie crashen."""
    cdp = CDPConnection("ws://test")
    ws = FakeWS()
    ws.auto_reply = False
    _wire(cdp, ws)

    def boom(_m: str, _p: dict, _s: str | None) -> None:
        raise RuntimeError("subscriber bug")

    cdp.event_handler = boom
    ws.incoming = [
        json.dumps({"method": "Page.loadEventFired", "params": {}}),
        json.dumps({"id": 7, "result": {"ok": True}}),
    ]
    cdp._id_counter = 7
    response = cdp.call("Runtime.evaluate", {"expression": "1"})
    assert response["result"] == {"ok": True}


def test_drain_events_processes_multiple_events() -> None:
    cdp = CDPConnection("ws://test")
    ws = FakeWS()
    ws.auto_reply = False
    _wire(cdp, ws)

    seen: list[str] = []
    cdp.event_handler = lambda m, _p, _s: seen.append(m)

    ws.incoming = [
        json.dumps({"method": "A", "params": {}}),
        json.dumps({"method": "B", "params": {}}),
        json.dumps({"method": "C", "params": {}}),
    ]
    count = cdp.drain_events(timeout=0.0)
    assert count == 3
    assert seen == ["A", "B", "C"]


# ── 2. JsDialogHandler (#94) ───────────────────────────────────────────────


def test_js_dialog_handler_dismisses_alert() -> None:
    cdp = CDPConnection("ws://test")
    ws = FakeWS()
    _wire(cdp, ws)

    handler = JsDialogHandler(cdp)
    handler.install()

    # Setup: Drain einmal, damit die ``Page.enable`` / ``addScriptToEvalu...``-
    # Antworten weg sind. Danach: Event simulieren.
    cdp.drain_events(timeout=0.0)
    ws.incoming.append(
        json.dumps(
            {
                "method": "Page.javascriptDialogOpening",
                "params": {
                    "type": "alert",
                    "message": "Are you sure?",
                    "url": "https://example.com",
                },
            }
        )
    )
    cdp.drain_events(timeout=0.0)

    events = handler.peek()
    assert len(events) == 1
    assert events[0].type == "alert"
    assert events[0].accepted is True

    # Outgoing musste ``Page.handleJavaScriptDialog`` enthalten.
    methods = [m.get("method") for m in ws.outgoing]
    assert "Page.handleJavaScriptDialog" in methods


def test_default_policy_accepts_unless_pii() -> None:
    """Policy default: accept alert/confirm, prompt mit leerem String —
    aber wir wollen NICHT versehentlich auf gefährliche Confirm-Texte
    'Ja' antworten. Aktueller Default akzeptiert pauschal — der Test
    dokumentiert das Verhalten, damit eine Änderung bewusst gemacht wird.
    """
    assert default_policy("alert", "x") == (True, "")
    assert default_policy("confirm", "leave?") == (True, "")
    accept, text = default_policy("prompt", "name?")
    assert accept is True
    assert text == ""


def test_dialog_handler_chains_with_existing_subscriber() -> None:
    cdp = CDPConnection("ws://test")
    ws = FakeWS()
    _wire(cdp, ws)

    other_seen: list[str] = []
    cdp.event_handler = lambda m, _p, _s: other_seen.append(m)

    handler = JsDialogHandler(cdp)
    handler.install()

    cdp.drain_events(timeout=0.0)
    ws.incoming.append(
        json.dumps(
            {
                "method": "Page.javascriptDialogOpening",
                "params": {"type": "alert", "message": "x"},
            }
        )
    )
    ws.incoming.append(
        json.dumps({"method": "Page.loadEventFired", "params": {}})
    )
    cdp.drain_events(timeout=0.0)

    # Dialog wurde von uns gehandled
    assert len(handler.peek()) == 1
    # Vorher-Subscriber hat BEIDE Events gesehen (Chaining funktioniert)
    assert "Page.javascriptDialogOpening" in other_seen
    assert "Page.loadEventFired" in other_seen


# ── 3. OopifRegistry (#93) ─────────────────────────────────────────────────


def test_oopif_registry_tracks_attach_and_detach() -> None:
    cdp = CDPConnection("ws://test")
    ws = FakeWS()
    _wire(cdp, ws)

    reg = OopifRegistry(cdp)
    reg.enable()
    cdp.drain_events(timeout=0.0)

    ws.incoming.append(
        json.dumps(
            {
                "method": "Target.attachedToTarget",
                "params": {
                    "sessionId": "S1",
                    "targetInfo": {
                        "targetId": "T1",
                        "type": "iframe",
                        "url": "https://cdn.example/captcha",
                    },
                    "waitingForDebugger": False,
                },
            }
        )
    )
    cdp.drain_events(timeout=0.0)

    snap = reg.snapshot()
    assert len(snap) == 1
    assert snap[0].session_id == "S1"
    assert snap[0].url.endswith("/captcha")

    ws.incoming.append(
        json.dumps(
            {
                "method": "Target.detachedFromTarget",
                "params": {"sessionId": "S1"},
            }
        )
    )
    cdp.drain_events(timeout=0.0)
    assert reg.snapshot() == []


def test_oopif_registry_ignores_non_iframe_targets() -> None:
    cdp = CDPConnection("ws://test")
    ws = FakeWS()
    _wire(cdp, ws)
    reg = OopifRegistry(cdp)
    reg.enable()
    cdp.drain_events(timeout=0.0)

    # Worker / Service-Worker dürfen NICHT in die Registry, sonst pollen
    # wir AX-Trees auf Targets, die gar keinen DOM haben.
    ws.incoming.append(
        json.dumps(
            {
                "method": "Target.attachedToTarget",
                "params": {
                    "sessionId": "S2",
                    "targetInfo": {
                        "targetId": "T2",
                        "type": "service_worker",
                        "url": "https://example.com/sw.js",
                    },
                },
            }
        )
    )
    cdp.drain_events(timeout=0.0)
    assert reg.snapshot() == []


def test_oopif_and_dialog_subscribers_coexist() -> None:
    """End-to-End: beide Subscriber gleichzeitig aktiv, beide reagieren."""
    cdp = CDPConnection("ws://test")
    ws = FakeWS()
    _wire(cdp, ws)

    reg = OopifRegistry(cdp)
    reg.enable()
    dlg = JsDialogHandler(cdp)
    dlg.install()
    cdp.drain_events(timeout=0.0)

    ws.incoming.append(
        json.dumps(
            {
                "method": "Target.attachedToTarget",
                "params": {
                    "sessionId": "S9",
                    "targetInfo": {
                        "targetId": "T9",
                        "type": "iframe",
                        "url": "https://x.test/frame",
                    },
                },
            }
        )
    )
    ws.incoming.append(
        json.dumps(
            {
                "method": "Page.javascriptDialogOpening",
                "params": {"type": "confirm", "message": "really?"},
            }
        )
    )
    cdp.drain_events(timeout=0.0)

    assert len(reg.snapshot()) == 1
    assert len(dlg.peek()) == 1
