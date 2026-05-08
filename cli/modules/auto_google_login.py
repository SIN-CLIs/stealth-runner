#!/usr/bin/env python3
"""auto_google_login.py — DEPRECATED wrapper for survey.auth.google_oauth.

WARUM: Die komplette Auth-Logik wurde in survey/auth/ modularisiert:
  - CuaAdapter: Low-level CUA-Driver Wrapper
  - LoginVerifier: Login-State Detection
  - GoogleOAuthFlow: 6-Step OAuth Flow

Diese Datei ist nur ein backward-compatible Wrapper für bestehende
Importe (z.B. in api/main.py, tools). Neue Code sollte direkt
survey.auth.google_oauth.GoogleOAuthFlow nutzen.

SOTA: survey.auth.GoogleOAuthFlow ist getestet und wartbar.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure survey-cli is importable
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "survey-cli"))

from survey.auth.google_oauth import GoogleOAuthFlow, LoginResult
from survey.auth.login_verifier import LoginVerifier
from survey.auth.cua_adapter import CuaAdapter


def execute(pid: int | None = None, url: str = "https://heypiggy.com/?page=dashboard") -> dict:
    """HeyPiggy Google OAuth Login (backward-compatible wrapper).

    Args:
        pid: Optional existing Chrome PID.
        url: Dashboard URL (kept for API compat, not used).

    Returns:
        {"status": "ok", "pid": int, "wid": int} on success
        {"status": "error", "reason": str} on failure
    """
    flow = GoogleOAuthFlow(CuaAdapter(), LoginVerifier())
    result = flow.execute(pid=pid)

    if result.status in ("ok", "already_logged_in"):
        return {"status": "ok", "pid": result.pid, "wid": result.wid}
    return {"status": "error", "reason": result.reason or "unknown_error"}


# Backward-compatible aliases for internal functions
# DEPRECATED: Use survey.auth.cua_adapter.CuaAdapter directly
def _find_idx(tree, keyword, roles=None):
    """DEPRECATED: Use CuaAdapter.find_idx()"""
    return CuaAdapter().find_idx(tree, keyword, roles)


def _click(pid, wid, idx):
    """DEPRECATED: Use CuaAdapter.click()"""
    return CuaAdapter().click(pid, wid, idx)


def _type(pid, wid, idx, value):
    """DEPRECATED: Use CuaAdapter.type()"""
    return CuaAdapter().type(pid, wid, idx, value)


def _tree(pid, wid):
    """DEPRECATED: Use CuaAdapter.get_tree()"""
    return CuaAdapter().get_tree(pid, wid)


def _find_bot_wid(keywords=None):
    """DEPRECATED: Use CuaAdapter.find_bot_window()"""
    return CuaAdapter().find_bot_window(keywords or [])


def _find_logged_in_heypiggy():
    """DEPRECATED: Use LoginVerifier.check()"""
    return LoginVerifier(CuaAdapter()).check()


__all__ = ["execute"]
