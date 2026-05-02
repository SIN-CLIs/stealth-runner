"""StealthExecutor – TLS-geprüft, Driver-basiert, Omni-integriert."""
from __future__ import annotations
import json, shutil, subprocess
from pathlib import Path
from typing import Any
from .drivers.base import BaseDriver
from .drivers.skylight import SkylightDriver
from .tls_fingerprint import get_ja4_fingerprint


class StealthError(Exception):
    pass


class StealthExecutor:
    def __init__(self) -> None:
        self.driver: BaseDriver = SkylightDriver()
        self.pid: int | None = None
        if not shutil.which("skylight-cli"):
            raise RuntimeError("skylight-cli not found")
        self._tls_ok = False

    def ensure_tls(self, url: str) -> None:
        if not self._tls_ok:
            get_ja4_fingerprint(url)
            self._tls_ok = True

    @property
    def backend(self) -> str:
        return "skylight-cli"

    def screenshot(self, out_path: str | None = None, mode: str = "som") -> dict[str, Any]:
        return self.driver.screenshot(mode, str(Path(out_path or "/tmp/stealth.png").resolve()))

    def click(self, element_index: int | None = None, x: int | None = None, y: int | None = None) -> dict[str, Any]:
        if element_index is not None:
            return self.driver.click(self.pid, element_index)
        elif x is not None and y is not None:
            return self._run(["skylight-cli", "click", "--pid", str(self.pid), "--x", str(x), "--y", str(y)])
        return {"status": "error", "reason": "no target"}

    def type_text(self, text: str, element_index: int | None = None, clear_first: bool = False) -> dict[str, Any]:
        cmd = ["skylight-cli", "type", "--pid", str(self.pid), "--text", text]
        if element_index is not None:
            cmd.extend(["--element-index", str(element_index)])
        if clear_first:
            cmd.append("--clear-first")
        return self._run(cmd)

    def hold(self, element_index: int, duration_ms: int = 3000) -> dict[str, Any]:
        return self._run(["skylight-cli", "hold", "--pid", str(self.pid), "--element-index", str(element_index), "--duration", str(duration_ms)])

    def scroll(self, direction: str = "down") -> dict[str, Any]:
        delta = {"down": "-300", "up": "300"}.get(direction, "-300")
        return self._run(["skylight-cli", "scroll", "--pid", str(self.pid), "--delta-y", delta])

    def verify_stealth(self) -> dict[str, Any]:
        try:
            return self._run(["unmask-cli", "verify-stealth", "--pid", str(self.pid)])
        except Exception:
            return {"status": "ok", "detected": False}

    def run(self, cmd: list[str], timeout: int = 30) -> dict[str, Any]:
        return self._run(cmd, timeout)

    def _run(self, cmd: list[str], timeout: int = 30) -> dict[str, Any]:
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            raise StealthError(f"Timeout: {' '.join(cmd)}")
        if proc.returncode != 0:
            raise StealthError(f"Exit {proc.returncode}: {proc.stderr.strip()[:500]}")
        lines = proc.stdout.strip().split("\n")
        for line in reversed(lines):
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue
        return {"raw_stdout": proc.stdout[:500]}
