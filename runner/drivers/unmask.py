"""UnmaskDriver – DOM-Scan via unmask-cli für Vision-free Fast Path."""
from __future__ import annotations
import json, subprocess
from typing import Any


class UnmaskDriver:
    """Calls `unmask-cli dom` to get structured element data without Vision."""

    def dom_scan(self, url: str, timeout: int = 30) -> dict[str, Any]:
        """Scan DOM and return structured elements with selectors."""
        try:
            proc = subprocess.run(
                ["unmask", "dom", url, "--format", "json"],
                capture_output=True, text=True, timeout=timeout,
            )
            if proc.returncode != 0:
                return {"status": "error", "error": proc.stderr.strip()[:300]}
            return json.loads(proc.stdout)
        except FileNotFoundError:
            return {"status": "error", "error": "unmask-cli not installed"}
        except subprocess.TimeoutExpired:
            return {"status": "error", "error": "timeout"}
        except json.JSONDecodeError:
            return {"status": "error", "error": "invalid JSON from unmask"}

    def network_capture(self, url: str, timeout: int = 30) -> dict[str, Any]:
        """Capture network activity via unmask-cli."""
        try:
            proc = subprocess.run(
                ["unmask", "network", url, "--format", "json"],
                capture_output=True, text=True, timeout=timeout,
            )
            if proc.returncode != 0:
                return {"status": "error", "error": proc.stderr.strip()[:300]}
            return json.loads(proc.stdout)
        except (FileNotFoundError, subprocess.TimeoutExpired, json.JSONDecodeError) as e:
            return {"status": "error", "error": str(e)}

    def inspect(self, url: str, timeout: int = 30) -> dict[str, Any]:
        """Full X-ray: DOM + network + console."""
        try:
            proc = subprocess.run(
                ["unmask", "inspect", url, "--format", "json"],
                capture_output=True, text=True, timeout=timeout,
            )
            if proc.returncode != 0:
                return {"status": "error", "error": proc.stderr.strip()[:300]}
            return json.loads(proc.stdout)
        except (FileNotFoundError, subprocess.TimeoutExpired, json.JSONDecodeError) as e:
            return {"status": "error", "error": str(e)}
