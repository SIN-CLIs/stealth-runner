"""BalanceTracker — centralized balance reading + earnings calculation.

WARUM: runner.py hatte balance-Logik inline (vor Survey, nach Survey,
earnings berechnen). BalanceTracker konsolidiert ALLES was mit
"Wie viel Guthaben?" und "Wie viel verdient?" zu tun hat.

ARCHITEKTUR:
  tracker = BalanceTracker(cdp_port=9223)
  before = tracker.read_balance()          -> float
  after  = tracker.read_balance()          -> float
  earned = tracker.calculate_earned(before, after) -> float

BANNED METHODS — NIEMALS VERWENDEN:
  ❌ playstealth launch
  ❌ webauto-nodriver — ABSOLUT BANNED
  ❌ cua-driver click (raw index)
  ❌ Hardcoded PIDs
"""

from .observability.logger import get_logger
from .scanner import read_balance_with_backoff


class BalanceTracker:
    """Read dashboard balance with backoff and calculate earnings."""

    def __init__(self, cdp_port: int = 8888, debug: bool = False):
        self.cdp_port = cdp_port
        self.debug = debug

    # ── Public API ──────────────────────────────────────────────

    def read_balance(self) -> float:
        """Read current balance with exponential backoff.

        Dashboard DOM updates async after page load. Without backoff,
        first read returns 0.00€ → false negative on payout detection.
        """
        try:
            balance = read_balance_with_backoff(self.cdp_port)
            if self.debug:
                get_logger().info(f"[BALANCE] Read: {balance}€", context="balance_read",
                                  balance=balance)
            return balance
        except Exception as e:
            if self.debug:
                get_logger().warn(f"[BALANCE] Read failed: {e}", context="balance_read_failed")
            return 0.0

    @staticmethod
    def calculate_earned(before: float, after: float) -> float:
        """Calculate earnings from before/after balance.

        Returns max(0, after - before) to never report negative earnings.
        """
        return max(0.0, round(after - before, 2))
