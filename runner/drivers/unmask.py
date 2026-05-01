"""UnmaskDriver – DOM-Scan via unmask-cli für Vision-free Fast Path."""
from __future__ import annotations
import json, subprocess
from typing import Any


class UnmaskDriver:
    def dom_scan(self, url: str, timeout: int = 30) -> list[dict[str, Any]]:
        try:
            proc = subprocess.run(
                ["unmask", "dom", url, "--wait-ms", "2000"],
                capture_output=True, text=True, timeout=timeout,
            )
            if proc.returncode != 0:
                return []
            return json.loads(proc.stdout)
        except (FileNotFoundError, subprocess.TimeoutExpired, json.JSONDecodeError):
            return []

    def network_capture(self, url: str, timeout: int = 30) -> list[dict[str, Any]]:
        try:
            proc = subprocess.run(
                ["unmask", "network", url],
                capture_output=True, text=True, timeout=timeout,
            )
            if proc.returncode != 0:
                return []
            return json.loads(proc.stdout)
        except (FileNotFoundError, subprocess.TimeoutExpired, json.JSONDecodeError):
            return []

    def inspect(self, url: str, timeout: int = 30) -> dict[str, Any]:
        try:
            proc = subprocess.run(
                ["unmask", "inspect", url],
                capture_output=True, text=True, timeout=timeout,
            )
            if proc.returncode != 0:
                return {"status": "error", "error": proc.stderr.strip()[:300]}
            return json.loads(proc.stdout)
        except (FileNotFoundError, subprocess.TimeoutExpired, json.JSONDecodeError) as e:
            return {"status": "error", "error": str(e)}
