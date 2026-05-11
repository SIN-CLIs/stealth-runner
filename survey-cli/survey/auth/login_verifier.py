"""LoginVerifier — Detect HeyPiggy dashboard login state via CUA/AX-Tree.

WARUM: auto_google_login.py hatte Login-Detection direkt im Flow.
Dieses Modul isoliert die Erkennung in eine testbare Klasse.

ARCHITEKTUR:
  verifier = LoginVerifier(CuaAdapter())
  pid, wid, is_logged_in = verifier.check()
"""

from __future__ import annotations

from typing import Tuple, Optional

from .cua_adapter import CuaAdapter


class LoginVerifier:
    """Detect if HeyPiggy dashboard is already logged in."""

    def __init__(self, cua: Optional[CuaAdapter] = None):
        self.cua = cua or CuaAdapter()

    def check(self) -> Tuple[Optional[int], Optional[int], bool]:
        """Check if HeyPiggy is logged in.

        Returns:
            (pid, wid, logged_in) — (None, None, False) if not found.
        """
        windows = self.cua.list_windows()
        windows.sort(key=lambda w: w.get("z_index", 0), reverse=True)

        for w in windows:
            b = w.get("bounds", {})
            t = (w.get("title") or "").lower()
            n = (w.get("app_name") or "").lower()
            pid = w.get("pid")

            if b.get("height", 0) < 100:
                continue
            if "chrome" not in n:
                continue

            # Strong indicators (only visible when logged in)
            if any(k in t for k in ["umfragen", "auszahlung", "abmelden"]):
                return pid, w.get("window_id"), True

            # Ambiguous title → check AX-Tree
            if any(k in t for k in ["heypiggy", "verdienen", "dashboard"]):
                tree = self.cua.get_tree(pid, w.get("window_id"))
                if any("abmelden" in line_text.lower() for line_text in tree):
                    return pid, w.get("window_id"), True

        return None, None, False
