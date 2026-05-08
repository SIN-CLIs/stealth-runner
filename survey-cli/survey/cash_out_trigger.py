"""CashOutTrigger — navigate to cash-out page when balance target reached.

WARUM: runner.py hatte ~60 Zeilen Cash-Out-Logik mit cua-driver.
CashOutTrigger isoliert ALLES was mit "Guthaben auszahlen" zu tun hat.

BANNED METHODS — NIEMALS VERWENDEN:
  ❌ playstealth launch
  ❌ webauto-nodriver — ABSOLUT BANNED
  ❌ cua-driver click (raw index)
  ❌ Hardcoded PIDs
"""

import json
import re
import subprocess
from typing import Optional

from .autodoc import log_session
from .observability.logger import get_logger


class CashOutTrigger:
    """Trigger cash-out flow via cua-driver AX-Tree navigation."""

    def __init__(self, debug: bool = False):
        self.debug = debug

    def trigger(self, balance_target: float) -> bool:
        """Navigate to cash-out page by clicking 'Auszahlung' in sidebar.

        Uses cua-driver to find the HeyPiggy window, get AX-Tree,
        locate the 'Auszahlung' link, and click it.

        Args:
            balance_target: Current balance target that triggered this.

        Returns:
            True if cash-out clicked successfully, False otherwise.
        """
        try:
            # 1. List windows
            result = subprocess.run(
                ["cua-driver", "call", "list_windows"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            windows = json.loads(result.stdout)
            hp_window = next(
                (
                    w
                    for w in windows.get("windows", [])
                    if "HeyPiggy" in w.get("title", "")
                ),
                None,
            )
            if not hp_window:
                get_logger().warn("[CASH] HeyPiggy window not found",
                                  context="cash_out_window_not_found")
                return False

            pid = hp_window["pid"]
            wid = hp_window["window_id"]

            # 2. Get AX tree
            result = subprocess.run(
                ["cua-driver", "call", "get_window_state"],
                input=json.dumps({"pid": pid, "window_id": wid}).encode(),
                capture_output=True,
                text=True,
                timeout=15,
            )
            state = json.loads(result.stdout)

            # 3. Find 'Auszahlung' in AX tree (depth > 5 = content)
            tree = state.get("tree_markdown", "")
            lines = tree.split("\n")
            idx = None
            for line in lines:
                if re.search(r"\[(\d+)\].*Auszahlung", line):
                    m = re.search(r"\[(\d+)\]", line)
                    if m:
                        idx = int(m.group(1))
                        break

            if idx is None:
                get_logger().warn("[CASH] Auszahlung element not found in AX tree",
                                  context="cash_out_element_not_found")
                return False

            # 4. Click
            result = subprocess.run(
                ["cua-driver", "call", "click"],
                input=json.dumps(
                    {"pid": pid, "window_id": wid, "element_index": idx}
                ).encode(),
                capture_output=True,
                text=True,
                timeout=15,
            )
            get_logger().info(f"[CASH] Clicked Auszahlung sidebar: {result.stdout[:100]}",
                  context="cash_out_success")
            log_session(
                "cash_out", "triggered", {"balance_target": balance_target}
            )
            return True

        except Exception as e:
            get_logger().warn(f"[CASH] Cash-out trigger failed: {e}",
                              context="cash_out_failed")
            return False
