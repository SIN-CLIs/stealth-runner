"""SR-194 C1+C2 regression tests — guard against phantom-module-attribute bugs.

These tests don't exercise the application; they pin down the upstream APIs
that survey/learn/apply.py and survey/safe_executor.py depend on. If a future
library upgrade renames or removes these surfaces, this test fails first —
loudly — instead of the failure manifesting as a silent AttributeError deep
inside a retry loop or an except clause.

Why this matters:
  - SR-194 A1 was time.mgmtime (typo for gmtime) — undetected because the
    recovery path was rare.
  - SR-194 C1 was tokenize.TokenizeError (should be TokenError) — undetected
    because tokenize errors are rare on AST-massaged source.
  - SR-194 C2 was websocket.STATUS_CONNECTED (never existed) — undetected
    because the comparison short-circuited via AttributeError, which the
    surrounding `if not self._ws or ...` swallowed in some flows.

The pattern: dotted-name attribute access against a third-party / stdlib
module, where the name is plausible-looking but wrong. mypy catches it at
type-check time; this test catches it at import time.
"""
from __future__ import annotations

import tokenize

import pytest


# ============================================================================
# C1 — stdlib tokenize
# ============================================================================

class TestTokenizeModule:
    """SR-194 C1: assert the correct exception name, forbid the typo."""

    def test_tokenize_token_error_exists(self) -> None:
        """tokenize.TokenError is the documented exception class."""
        assert hasattr(tokenize, "TokenError")
        assert issubclass(tokenize.TokenError, Exception)

    def test_tokenize_tokenize_error_does_not_exist(self) -> None:
        """tokenize.TokenizeError has never existed; regression guard."""
        assert not hasattr(tokenize, "TokenizeError"), (
            "If Python ever adds tokenize.TokenizeError, revisit SR-194 C1 — "
            "the apply.py except clause may need to catch both."
        )

    def test_tokenize_token_error_is_raised_on_malformed_input(self) -> None:
        """End-to-end: malformed input must raise tokenize.TokenError specifically."""
        import io

        # Unterminated triple-quoted string — guaranteed to trip the tokenizer.
        bad_source = '"""unterminated'
        with pytest.raises(tokenize.TokenError):
            list(tokenize.generate_tokens(io.StringIO(bad_source).readline))


# ============================================================================
# C2 — websocket-client (sync)
# ============================================================================

class TestWebsocketModule:
    """SR-194 C2: assert the correct connection-state attribute, forbid the phantom."""

    def test_websocket_module_has_websocket_class(self) -> None:
        import websocket

        assert hasattr(websocket, "WebSocket")

    def test_websocket_instance_has_connected_attr_default_false(self) -> None:
        """WebSocket().connected is the documented bool attr; defaults to False."""
        import websocket

        ws = websocket.WebSocket()
        assert hasattr(ws, "connected")
        assert ws.connected is False

    def test_websocket_module_has_no_status_connected_constant(self) -> None:
        """websocket.STATUS_CONNECTED was always a phantom; regression guard."""
        import websocket

        assert not hasattr(websocket, "STATUS_CONNECTED"), (
            "If websocket-client ever adds STATUS_CONNECTED, revisit SR-194 C2 — "
            "but prefer the .connected boolean over module constants for "
            "live-state checks (.status is HTTP handshake code, not live state)."
        )

    def test_websocket_status_is_http_handshake_not_connection_state(self) -> None:
        """Document why .status is the wrong attribute for liveness checks."""
        import websocket

        ws = websocket.WebSocket()
        # Before connect(): handshake_response is None, getstatus() returns None.
        # Crucially: .status is NOT a bool, it's an Optional[int] HTTP code.
        # Comparing it to a constant for connection-state was always wrong.
        assert ws.status is None
