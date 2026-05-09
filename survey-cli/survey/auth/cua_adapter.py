"""CuaAdapter — Tiny seam over cua-driver CLI.

WARUM: auto_google_login.py war 1700+ Zeilen weil CUA-Logik mit Login-Flow
vermischt war. Dieses Modul isoliert ALLE cua-driver Interaktionen.

ARCHITEKTUR:
  adapter = CuaAdapter()
  windows = adapter.list_windows()
  tree = adapter.get_tree(pid, wid)
  idx = adapter.find_idx(tree, "weiter", ["AXButton"])
  adapter.click(pid, wid, idx)
  adapter.type(pid, wid, idx, "text")
"""

from __future__ import annotations

import json
import re
import subprocess
from typing import List, Tuple, Optional


class CuaResult:
    """Result of a cua-driver call."""

    def __init__(self, stdout: str = "", stderr: str = "", returncode: int = 0):
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode

    def json(self) -> dict:
        """Parse stdout as JSON, return {} on failure."""
        try:
            if self.stdout:
                return json.loads(self.stdout)
        except Exception:
            pass
        return {}


class CuaAdapter:
    """Low-level wrapper for cua-driver binary."""

    def __init__(self, timeout: int = 15):
        self.timeout = timeout

    def run(self, cmd: list[str], input_: str | None = None) -> CuaResult:
        """Execute cua-driver command with optional stdin input."""
        kwargs = {
            "capture_output": True,
            "text": True,
            "timeout": self.timeout,
        }
        if input_:
            kwargs["input"] = input_
        result = subprocess.run(cmd, **kwargs)
        return CuaResult(
            stdout=result.stdout,
            stderr=result.stderr,
            returncode=result.returncode,
        )

    def list_windows(self) -> List[dict]:
        """List all windows via cua-driver."""
        r = self.run(["cua-driver", "call", "list_windows"])
        return r.json().get("windows", [])

    def call(self, pid: int, wid: int, method: str,
             params: Optional[dict] = None) -> dict:
        """Call cua-driver method with JSON parameters."""
        p = dict(params or {})
        p["pid"] = pid
        p["window_id"] = wid
        r = self.run(["cua-driver", "call", method], json.dumps(p))
        return r.json()

    def get_tree(self, pid: int, wid: int) -> List[str]:
        """Get AX-Tree as list of lines."""
        d = self.call(pid, wid, "get_window_state")
        if isinstance(d, dict):
            return d.get("tree_markdown", "").split("\n")
        return []

    def find_idx(self, tree: List[str], keyword: str,
                 roles: Optional[List[str]] = None) -> Optional[int]:
        """Find element_index by keyword and role in AX-Tree."""
        if roles is None:
            roles = ["AXButton", "AXLink", "AXTextField"]
        for role in roles:
            for line in tree:
                if keyword.lower() in line.lower() and role in line:
                    m = re.search(r'- \[(\d+)\]', line)
                    if m:
                        return int(m.group(1))
        return None

    def click(self, pid: int, wid: int, idx: Optional[int]) -> bool:
        """Click element via cua-driver AXPress."""
        if idx is None:
            return False
        r = self.call(pid, wid, "click", {"element_index": idx})
        stdout = r.get("stdout", "")
        stderr = r.get("stderr", "")
        return "performed" in stdout.lower() or "performed" in stderr.lower()

    def type(self, pid: int, wid: int, idx: Optional[int],
             value: str) -> bool:
        """Type text into AXTextField via cua-driver set_value."""
        if idx is None:
            return False
        r = self.call(pid, wid, "set_value",
                      {"element_index": idx, "value": value})
        stdout = r.get("stdout", "")
        return "performed" in stdout.lower() or "set" in stdout.lower()

    def find_bot_window(
        self,
        keywords: Optional[List[str]] = None,
    ) -> Tuple[Optional[int], Optional[int]]:
        """Find bot Chrome window by keywords.

        Returns:
            (pid, wid) tuple or (None, None)
        """
        for w in self.list_windows():
            b = w.get("bounds", {})
            t = (w.get("title") or "").lower()
            n = (w.get("app_name") or "").lower()
            pid = w.get("pid")

            if b.get("height", 0) < 100:
                continue
            if "chrome" not in n:
                continue

            if keywords:
                if any(k in t for k in keywords):
                    return pid, w.get("window_id")
            else:
                return pid, w.get("window_id")

        return None, None
