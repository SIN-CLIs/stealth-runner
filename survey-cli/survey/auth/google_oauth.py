"""GoogleOAuthFlow — HeyPiggy login via Google OAuth (CUA-ONLY).

WARUM: auto_google_login.py war 1700+ Zeilen mit CUA-Logik vermischt.
Dieses Modul isoliert den kompletten 6-Step OAuth Flow.

ARCHITEKTUR:
  flow = GoogleOAuthFlow(CuaAdapter(), LoginVerifier())
  result = flow.execute()  # -> LoginResult

FLOW:
  Step 0: Check already logged in (LoginVerifier)
  Step 1: Start Chrome (if needed)
  Step 2: Find Dashboard Window
  Step 3: Click Google Login Symbol
  Step 4: Find OAuth Window + Enter Email + Click "Weiter"
  Step 5: Click "Fortfahren" (Keychain Auto-Fill)
  Step 6: Click Final "Weiter"
  Verify: Dashboard shows logged-in state
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional

from .cua_adapter import CuaAdapter
from .login_verifier import LoginVerifier


try:
    from ..security import SecretsClient
except ImportError:
    SecretsClient = None  # type: ignore


@dataclass
class LoginResult:
    """Result of a Google OAuth login attempt."""

    status: str  # "ok" | "error" | "already_logged_in"
    pid: Optional[int] = None
    wid: Optional[int] = None
    reason: Optional[str] = None


class GoogleOAuthFlow:
    """Execute HeyPiggy Google OAuth login via CUA."""

    def __init__(
        self,
        cua: Optional[CuaAdapter] = None,
        verifier: Optional[LoginVerifier] = None,
    ):
        self.cua = cua or CuaAdapter()
        self.verifier = verifier or LoginVerifier(self.cua)

    def execute(self, pid: Optional[int] = None) -> LoginResult:
        """Run the complete OAuth login flow.

        Args:
            pid: Optional existing Chrome PID (reuses browser).

        Returns:
            LoginResult with status, pid, wid, and optional error reason.
        """
        # Step 0: Check already logged in
        epid, ewid, logged_in = self.verifier.check()
        if logged_in and ewid:
            return LoginResult(
                status="already_logged_in", pid=epid, wid=ewid
            )

        # Step 1: Start Chrome if needed (external — not handled here)
        # Caller must ensure Chrome is running with correct flags
        if pid is None:
            return LoginResult(
                status="error", reason="chrome_not_started"
            )

        # Step 2: Find Dashboard Window
        pid_d, wid_d = self.cua.find_bot_window(
            ["heypiggy", "dashboard", "verdienen"]
        )
        if not wid_d:
            # Fallback: any Chrome window
            pid_d, wid_d = self.cua.find_bot_window()
        if not wid_d:
            return LoginResult(
                status="error", reason="no_dashboard_window"
            )

        # Step 3: Click Google Login Symbol
        tree = self.cua.get_tree(pid_d, wid_d)
        idx = self.cua.find_idx(tree, "google login-symbol", ["AXLink"])
        if idx is None:
            idx = self.cua.find_idx(tree, "google", ["AXLink"])
        if idx is None:
            return LoginResult(
                status="error", reason="google_login_button_not_found"
            )
        if not self.cua.click(pid_d, wid_d, idx):
            return LoginResult(
                status="error", reason="google_login_click_failed"
            )
        time.sleep(5)

        # Step 4: Find OAuth Window + Enter Email
        pid_g, wid_g = self.cua.find_bot_window(
            ["google", "anmelden", "accounts"]
        )
        if not wid_g:
            pid_g, wid_g = self.cua.find_bot_window()
        if not wid_g:
            return LoginResult(
                status="error", reason="google_oauth_window_not_found"
            )

        tree = self.cua.get_tree(pid_g, wid_g)
        email_idx = self.cua.find_idx(
            tree, "e-mail oder telefonnummer", ["AXTextField"]
        )
        if email_idx is None:
            return LoginResult(
                status="error", reason="email_field_not_found"
            )

        # Get email from SecretsClient
        google_email = None
        if SecretsClient:
            try:
                google_email = SecretsClient.get_google_email()
            except Exception:
                pass
        if not google_email:
            return LoginResult(
                status="error", reason="missing_google_email"
            )

        if not self.cua.type(pid_g, wid_g, email_idx, google_email):
            return LoginResult(
                status="error", reason="email_type_failed"
            )

        weiter_idx = self.cua.find_idx(tree, "weiter", ["AXButton"])
        if weiter_idx is None:
            return LoginResult(
                status="error", reason="weiter_button_not_found"
            )
        if not self.cua.click(pid_g, wid_g, weiter_idx):
            return LoginResult(
                status="error", reason="weiter_click_failed"
            )
        time.sleep(5)

        # Step 5: Keychain "Fortfahren"
        pid_k, wid_k = self.cua.find_bot_window(
            ["google", "anmelden", "jeremy"]
        )
        if not wid_k:
            pid_k, wid_k = self.cua.find_bot_window(["google"])
        if not wid_k:
            return LoginResult(
                status="error", reason="fortfahren_button_not_found"
            )

        tree = self.cua.get_tree(pid_k, wid_k)
        fort_idx = self.cua.find_idx(tree, "fortfahren", ["AXButton"])
        if fort_idx is None:
            fort_idx = self.cua.find_idx(tree, "konto", ["AXButton"])
        if fort_idx is None:
            return LoginResult(
                status="error", reason="fortfahren_button_not_found"
            )
        if not self.cua.click(pid_k, wid_k, fort_idx):
            return LoginResult(
                status="error", reason="fortfahren_click_failed"
            )
        time.sleep(5)

        # Step 6: Final "Weiter"
        pid_f, wid_f = self.cua.find_bot_window(["google", "anmelden"])
        if not wid_f:
            pid_f, wid_f = self.cua.find_bot_window()
        if not wid_f:
            return LoginResult(
                status="error", reason="final_weiter_not_found"
            )

        tree = self.cua.get_tree(pid_f, wid_f)
        final_idx = self.cua.find_idx(tree, "weiter", ["AXButton"])
        if final_idx is None:
            return LoginResult(
                status="error", reason="final_weiter_not_found"
            )
        if not self.cua.click(pid_f, wid_f, final_idx):
            return LoginResult(
                status="error", reason="final_weiter_click_failed"
            )
        time.sleep(5)

        # Verify: Check logged in
        epid, ewid, logged_in = self.verifier.check()
        if logged_in and ewid:
            return LoginResult(status="ok", pid=epid, wid=ewid)

        return LoginResult(
            status="error", reason="dashboard_not_found_after_login"
        )
