"""StealthExecutor – Zustandslose Brücke zu den CLI-Tools der Stealth-Triade."""
from __future__ import annotations
import json, shutil, subprocess
from pathlib import Path
from typing import Any

class StealthError(Exception):
    pass

class StealthExecutor:
    def __init__(self) -> None:
        self.pid: int | None = None
        if not shutil.which("skylight-cli"):
            raise RuntimeError("skylight-cli not found. Install from https://github.com/SIN-CLIs/skylight-cli")

    @property
    def backend(self) -> str: return "skylight-cli"

    @property
    def has_unmask(self) -> bool: return any(shutil.which(t) for t in ("unmask", "unmask-cli"))

    def screenshot(self, out_path: str | None = None, mode: str = "som") -> dict[str, Any]:
        path = Path(out_path or f"/tmp/stealth_screenshot.png").resolve()
        result = subprocess.run(["skylight-cli", "screenshot", "--pid", str(self.pid), "--mode", mode, "--out", str(path)], capture_output=True, text=True, timeout=15)
        if result.returncode != 0: raise StealthError(f"screenshot failed: {result.stderr.strip()}")
        try: data = json.loads(result.stdout)
        except json.JSONDecodeError: data = {"raw": result.stdout[:500]}
        return {"status": "ok", "file": str(path), "mode": mode, **data}

    def click(self, element_index: int | None = None, x: int | None = None, y: int | None = None) -> dict[str, Any]:
        if element_index is not None: cmd = ["skylight-cli", "click", "--pid", str(self.pid), "--element-index", str(element_index)]
        elif x is not None and y is not None: cmd = ["skylight-cli", "click", "--pid", str(self.pid), "--x", str(x), "--y", str(y)]
        else: return {"status": "error", "reason": "No element_index or coordinates"}
        return {"status": "ok", "raw": self._run(cmd)}

    def type_text(self, text: str, element_index: int | None = None, clear_first: bool = False) -> dict[str, Any]:
        cmd = ["skylight-cli", "type", "--pid", str(self.pid), "--text", text]
        if element_index is not None: cmd.extend(["--element-index", str(element_index)])
        if clear_first: cmd.append("--clear-first")
        return {"status": "ok", "raw": self._run(cmd)}

    def scroll(self, direction: str = "down") -> dict[str, Any]:
        delta = {"down": "-300", "up": "300"}.get(direction, "-300")
        return {"status": "ok", "raw": self._run(["skylight-cli", "scroll", "--pid", str(self.pid), "--delta-y", delta])}

    def verify_stealth(self) -> dict[str, Any]:
        if not self.has_unmask: return {"status": "ok", "detected": False, "backend": "none"}
        tool = next(t for t in ("unmask", "unmask-cli") if shutil.which(t))
        result = self._run([tool, "verify-stealth", "--pid", str(self.pid)])
        return {"status": "ok", "detected": result.get("detected", False), "backend": tool}

    def list_elements(self) -> dict[str, Any]:
        result = self._run(["skylight-cli", "screenshot", "--pid", str(self.pid), "--mode", "som", "--include-tree"])
        return {"status": "ok", "elements": result.get("elements", [])}

    def run(self, cmd: list[str], timeout: int = 30) -> dict[str, Any]: return self._run(cmd, timeout)

    def _run(self, cmd: list[str], timeout: int = 30) -> dict[str, Any]:
        try: result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        except subprocess.TimeoutExpired: raise StealthError(f"Timeout after {timeout}s: {' '.join(cmd)}")
        if result.returncode != 0: raise StealthError(f"Failed (exit {result.returncode}): {' '.join(cmd)}\n{result.stderr.strip()[:500]}")
        try: return json.loads(result.stdout)
        except json.JSONDecodeError: return {"raw_stdout": result.stdout[:500], "raw_stderr": result.stderr[:500]}
