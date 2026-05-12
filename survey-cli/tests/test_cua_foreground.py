#!/usr/bin/env python3
"""Test (Issue #80): CDP-Level Foreground vor CUA-Fallback.

Verifiziert die zwei Eintrittspunkte für Tab-Foreground-Aktivierung:

  1. ``Actuator.bring_tab_to_foreground()`` — innerhalb der bestehenden
     CDPConnection.
  2. ``cua_fallback.bring_cdp_tab_to_foreground()`` — standalone via
     eigenem WebSocket-Roundtrip (für Top-Level-CUA-Pfad).

Beide MÜSSEN ``Page.bringToFront`` versuchen UND ``Target.activateTarget``
als Belt-and-Braces wenn ein targetId verfügbar ist. Tests laufen ohne
echten Chrome — wir mocken die CDP-Schicht.

Pflicht-Kontext: SR-80 / AGENTS.md Deep-Dive "Issue #80".
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).parent.parent))


# ─────────────────────────────────────────────────────────────────────────────
# Teil 1: Actuator.bring_tab_to_foreground (in-connection)
# ─────────────────────────────────────────────────────────────────────────────


class _FakeCDP:
    """Minimaler CDPConnection-Stand-in: zählt Calls und kann Fehler werfen."""

    def __init__(self, target_id: str = "", fail_methods: set[str] | None = None):
        self.target_id = target_id
        self.fail_methods = fail_methods or set()
        self.calls: list[tuple[str, dict]] = []

    def call(self, method: str, params: dict) -> dict:
        self.calls.append((method, params))
        if method in self.fail_methods:
            from survey.cdp_client import CDPError

            raise CDPError(f"mocked failure: {method}")
        return {}


def test_actuator_foreground_calls_bringtofront_and_activate():
    """Mit target_id müssen BEIDE CDP-Methoden gerufen werden."""
    from survey.cdp_actuator import Actuator

    # __init__ ruft JsDialogHandler.install() → wir mocken den Init weg.
    with mock.patch.object(Actuator, "__init__", lambda self, cdp: None):
        actu = Actuator(None)  # type: ignore[arg-type]
        actu.cdp = _FakeCDP(target_id="TARGET-XYZ")
        ok = actu.bring_tab_to_foreground()

    assert ok is True
    methods = [m for m, _ in actu.cdp.calls]
    assert "Page.bringToFront" in methods
    assert "Target.activateTarget" in methods
    # Reihenfolge: erst bringToFront, dann activateTarget
    assert methods.index("Page.bringToFront") < methods.index("Target.activateTarget")


def test_actuator_foreground_without_target_id_skips_activate():
    """Ohne targetId NUR Page.bringToFront — kein Target.activateTarget."""
    from survey.cdp_actuator import Actuator

    with mock.patch.object(Actuator, "__init__", lambda self, cdp: None):
        actu = Actuator(None)  # type: ignore[arg-type]
        actu.cdp = _FakeCDP(target_id="")
        ok = actu.bring_tab_to_foreground()

    assert ok is True
    methods = [m for m, _ in actu.cdp.calls]
    assert methods == ["Page.bringToFront"]


def test_actuator_foreground_bringtofront_fails_returns_false_then_recovers():
    """Wenn bringToFront fehlschlägt UND keine target_id → False."""
    from survey.cdp_actuator import Actuator

    with mock.patch.object(Actuator, "__init__", lambda self, cdp: None):
        actu = Actuator(None)  # type: ignore[arg-type]
        actu.cdp = _FakeCDP(target_id="", fail_methods={"Page.bringToFront"})
        ok = actu.bring_tab_to_foreground()

    assert ok is False


def test_actuator_foreground_activate_recovers_failed_bringtofront():
    """Wenn bringToFront fehlschlägt aber activateTarget OK → True (best-effort)."""
    from survey.cdp_actuator import Actuator

    with mock.patch.object(Actuator, "__init__", lambda self, cdp: None):
        actu = Actuator(None)  # type: ignore[arg-type]
        actu.cdp = _FakeCDP(
            target_id="TARGET-XYZ",
            fail_methods={"Page.bringToFront"},
        )
        ok = actu.bring_tab_to_foreground()

    assert ok is True


# ─────────────────────────────────────────────────────────────────────────────
# Teil 2: cua_fallback.bring_cdp_tab_to_foreground (standalone via WS)
# ─────────────────────────────────────────────────────────────────────────────


class _FakeWS:
    """Minimaler websocket-Mock."""

    def __init__(self, replies: list[dict]):
        self._replies = list(replies)
        self.sent: list[dict] = []
        self.closed = False

    def send(self, payload: str) -> None:
        self.sent.append(json.loads(payload))

    def recv(self) -> str:
        if not self._replies:
            return json.dumps({"id": 99, "result": {}})
        return json.dumps(self._replies.pop(0))

    def close(self) -> None:
        self.closed = True


def test_standalone_foreground_sends_bringtofront():
    """Standalone-Helper sendet Page.bringToFront."""
    from survey import cua_fallback

    fake = _FakeWS(replies=[{"id": 1, "result": {}}])
    with (
        mock.patch.object(cua_fallback, "__name__", cua_fallback.__name__),
        mock.patch.dict(
            sys.modules,
            {"websocket": mock.MagicMock(create_connection=mock.MagicMock(return_value=fake))},
        ),
    ):
        ok = cua_fallback.bring_cdp_tab_to_foreground(
            "ws://127.0.0.1:9999/devtools/page/abc",
        )

    assert ok is True
    assert any(m["method"] == "Page.bringToFront" for m in fake.sent)
    assert fake.closed is True


def test_standalone_foreground_with_target_id_sends_activate_target():
    """Mit target_id wird AUCH Target.activateTarget gesendet."""
    from survey import cua_fallback

    fake = _FakeWS(
        replies=[
            {"id": 1, "result": {}},
            {"id": 2, "result": {}},
        ]
    )
    with mock.patch.dict(
        sys.modules,
        {"websocket": mock.MagicMock(create_connection=mock.MagicMock(return_value=fake))},
    ):
        ok = cua_fallback.bring_cdp_tab_to_foreground(
            "ws://127.0.0.1:9999/devtools/page/abc",
            target_id="TARGET-XYZ",
        )

    assert ok is True
    methods = [m["method"] for m in fake.sent]
    assert "Page.bringToFront" in methods
    assert "Target.activateTarget" in methods
    # activateTarget enthält die targetId.
    activate = next(m for m in fake.sent if m["method"] == "Target.activateTarget")
    assert activate["params"]["targetId"] == "TARGET-XYZ"


def test_standalone_foreground_swallows_ws_errors():
    """WS-Connect-Fehler → returnt False, NICHT raised."""
    from survey import cua_fallback

    def boom(*a, **kw):
        raise OSError("connection refused")

    with mock.patch.dict(
        sys.modules,
        {"websocket": mock.MagicMock(create_connection=mock.MagicMock(side_effect=boom))},
    ):
        ok = cua_fallback.bring_cdp_tab_to_foreground(
            "ws://127.0.0.1:9999/devtools/page/abc",
        )
    assert ok is False


def test_standalone_foreground_handles_cdp_error_response():
    """CDP antwortet mit error-Feld → wir loggen, returnt False."""
    from survey import cua_fallback

    fake = _FakeWS(
        replies=[
            {"id": 1, "error": {"code": -32000, "message": "Page domain not enabled"}},
        ]
    )
    with mock.patch.dict(
        sys.modules,
        {"websocket": mock.MagicMock(create_connection=mock.MagicMock(return_value=fake))},
    ):
        ok = cua_fallback.bring_cdp_tab_to_foreground(
            "ws://127.0.0.1:9999/devtools/page/abc",
        )

    assert ok is False
    assert any(m["method"] == "Page.bringToFront" for m in fake.sent)


if __name__ == "__main__":
    test_actuator_foreground_calls_bringtofront_and_activate()
    test_actuator_foreground_without_target_id_skips_activate()
    test_actuator_foreground_bringtofront_fails_returns_false_then_recovers()
    test_actuator_foreground_activate_recovers_failed_bringtofront()
    test_standalone_foreground_sends_bringtofront()
    test_standalone_foreground_with_target_id_sends_activate_target()
    test_standalone_foreground_swallows_ws_errors()
    test_standalone_foreground_handles_cdp_error_response()
    print("ALL FOREGROUND TESTS PASSED")
