"""CashOutTrigger — navigate to cash-out page when balance target reached.

WARUM: runner.py hatte ~60 Zeilen Cash-Out-Logik mit cua-driver.
CashOutTrigger isoliert ALLES was mit "Guthaben auszahlen" zu tun hat.

CEO-WAVE-1 (SR-237) — IDEMPOTENCY LEDGER:
  Cash-out is a real-money side effect. Without an idempotency key, a
  retry that crashes mid-flow (e.g. cua-driver hangs after the click but
  before log_session) can re-trigger the auszahlung against the same
  balance target on the next run. We append every attempt to an
  append-only JSONL ledger with a stable key derived from the balance
  target. trigger() refuses to fire when the same key already has a
  successful outcome on disk.

  WHY APPEND-ONLY JSONL not SQLite?
    - The rest of survey-cli already uses JSONL via autodoc (sessions/,
      earnings/, errors/). Consistency wins.
    - cash-out fires at most ~1× per day per account; we don't need
      indexed queries, just "did this key succeed before?"
    - Atomic appends survive crashes — partial writes leave the file
      readable up to the last \\n, the next attempt re-tries cleanly.

  WHAT IS THE KEY?
    Default: f"{provider_account}:{round(balance_target,2)}"
    Caller may pass an explicit `idempotency_key` to override (e.g. for
    testing or for multi-account fleets where the trigger is called per
    account in the same process).

BANNED METHODS — NIEMALS VERWENDEN:
  ❌ playstealth launch
  ❌ webauto-nodriver — ABSOLUT BANNED
  ❌ cua-driver click (raw index)
  ❌ Hardcoded PIDs
"""

import json
import os
import re
import subprocess
import time
from pathlib import Path
from typing import Optional

from .autodoc import log_session

# Ledger path policy
# ------------------
# Honour STATE_DIR env var if set (test conftest does this), otherwise
# fall back to <package>/state/ next to autodoc.py's logs/ tree. The
# ledger lives in state/, not logs/, because state/ is meant to be
# durable across runs while logs/ is rotated.
_DEFAULT_STATE_DIR = Path(__file__).parent.parent / "state"


def _ledger_path() -> Path:
    base = Path(os.environ.get("STATE_DIR") or _DEFAULT_STATE_DIR)
    base.mkdir(parents=True, exist_ok=True)
    return base / "cash_out_ledger.jsonl"


def _default_idempotency_key(balance_target: float, account: str | None = None) -> str:
    """Stable key for de-duplication. Account is optional so single-
    account deployments stay terse."""
    rounded = round(float(balance_target), 2)
    if account:
        return f"{account}:cash_out:{rounded:.2f}"
    return f"cash_out:{rounded:.2f}"


def _has_successful_attempt(key: str) -> bool:
    """Scan the ledger for a prior successful attempt with this key.

    Append-only JSONL: O(n) scan is fine, n grows by 1 per cash-out.
    """
    path = _ledger_path()
    if not path.exists():
        return False
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    # Corrupt line — skip, do not block. The ledger is a
                    # best-effort guard; a corrupt entry means we cannot
                    # *prove* a prior success, so the safer move is to
                    # let the next attempt run and append a fresh row.
                    continue
                if entry.get("key") == key and entry.get("status") == "success":
                    return True
    except OSError:
        return False
    return False


def _append_ledger(entry: dict) -> None:
    """Atomic append. open(...,'a') + write+flush is atomic for small
    payloads on POSIX (write < PIPE_BUF). The newline anchors the line
    so a partial write at most loses the trailing record."""
    path = _ledger_path()
    payload = json.dumps(entry, sort_keys=True) + "\n"
    with open(path, "a", encoding="utf-8") as f:
        f.write(payload)
        f.flush()
        try:
            os.fsync(f.fileno())
        except OSError:
            # On platforms where fsync is not supported (some test
            # tmpfs), proceed — the JSONL append is already at least
            # at-most-once-durable.
            pass


class CashOutTrigger:
    """Trigger cash-out flow via cua-driver AX-Tree navigation."""

    def __init__(self, debug: bool = False):
        self.debug = debug

    def trigger(
        self,
        balance_target: float,
        *,
        idempotency_key: Optional[str] = None,
        account: Optional[str] = None,
    ) -> bool:
        """Navigate to cash-out page by clicking 'Auszahlung' in sidebar.

        Uses cua-driver to find the HeyPiggy window, get AX-Tree,
        locate the 'Auszahlung' link, and click it.

        SR-237 idempotency:
          * If an idempotency_key (or default key derived from
            balance_target + optional account) has a 'success' record in
            the ledger, this call is a no-op and returns True. The
            audit trail still gets a 'replay-skip' entry so we can see
            in retro why no clicks happened.
          * Every attempt — success or failure — appends a JSONL row
            with the key, balance_target, ts, attempt_id and outcome.

        Args:
            balance_target: Current balance target that triggered this.
            idempotency_key: Override the auto-derived key. Pass when
                caller has its own dedup scheme (test, multi-account).
            account: Optional account identifier mixed into the default
                key so multi-account fleets do not collide.

        Returns:
            True if cash-out was clicked successfully OR if a previous
                attempt already succeeded for this key (idempotent).
            False on any failure path.
        """
        key = idempotency_key or _default_idempotency_key(balance_target, account)

        # Idempotency short-circuit BEFORE any side effect.
        if _has_successful_attempt(key):
            print(f"[CASH] idempotency-skip: key={key} already succeeded")
            try:
                _append_ledger({
                    "ts": time.time(),
                    "key": key,
                    "balance_target": float(balance_target),
                    "status": "replay-skip",
                    "attempt_id": f"{int(time.time()*1000)}",
                    "account": account,
                })
            except OSError:
                pass
            log_session(
                "cash_out", "replay-skip",
                {"balance_target": balance_target, "key": key},
            )
            return True

        attempt_id = f"{int(time.time()*1000)}-{os.getpid()}"
        attempt_record = {
            "ts": time.time(),
            "key": key,
            "balance_target": float(balance_target),
            "attempt_id": attempt_id,
            "account": account,
        }

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
                print("[CASH] HeyPiggy window not found")
                _append_ledger({**attempt_record, "status": "no-window"})
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
                print("[CASH] Auszahlung element not found in AX tree")
                _append_ledger({**attempt_record, "status": "no-target"})
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
            print(f"[CASH] Clicked Auszahlung sidebar: {result.stdout[:100]}")

            # Persist BEFORE log_session so a crash between the two only
            # leaves a 'success' in the ledger (which is the safe state)
            # instead of a 'success' in the session log without the
            # idempotency guard.
            _append_ledger({**attempt_record, "status": "success"})

            log_session(
                "cash_out", "triggered", {"balance_target": balance_target}
            )
            return True

        except Exception as e:
            print(f"[CASH] Cash-out trigger failed: {e}")
            try:
                _append_ledger({
                    **attempt_record,
                    "status": "error",
                    "error": str(e)[:200],
                })
            except OSError:
                pass
            return False
