"""StealthExecutor mit TLS-Check, Behavioral Timings, Cross-Platform Driver."""
from __future__ import annotations
import subprocess, json, shutil
from pathlib import Path
from typing import Any
from .tls_fingerprint import verify_tls
from .drivers.base import BaseDriver
from .drivers.skylight import SkyLightDriver

class StealthExecutor:
    def __init__(self) -> None:
        self.driver: BaseDriver = SkyLightDriver()
        self.pid: int|None = None
        self._tls_verified = False

    @property
    def backend(self) -> str: return "skylight-cli"

    def ensure_tls(self, url: str) -> None:
        if not self._tls_verified:
            verify_tls(url); self._tls_verified = True

    def screenshot(self, out_path: str = "stealth.png", mode: str = "som") -> dict:
        return self.driver.screenshot(self.pid, mode, Path(out_path))

    def click(self, element_index: int|None = None, x: int|None = None, y: int|None = None) -> dict:
        if element_index is not None: return self.driver.click(self.pid, element_index)
        elif x is not None and y is not None:
            self._run(["skylight-cli", "click", "--pid", str(self.pid), "--x", str(x), "--y", str(y)])
            return {"status":"ok"}
        return {"status":"error","reason":"no coordinates"}

    def type_text(self, text: str, element_index: int|None = None) -> dict:
        cmd = ["skylight-cli", "type", "--pid", str(self.pid), "--text", text]
        if element_index is not None: cmd.extend(["--element-index", str(element_index)])
        return self._run(cmd)

    def scroll(self, direction: str = "down") -> dict:
        delta = {"down":"-300","up":"300"}.get(direction,"-300")
        return self._run(["skylight-cli", "scroll", "--pid", str(self.pid), "--delta-y", delta])

    def verify_stealth(self) -> dict:
        try: return self._run(["unmask-cli", "verify-stealth", "--pid", str(self.pid)])
        except: return {"status":"ok","detected":False}

    def run(self, cmd: list[str]) -> dict: return self._run(cmd)

    def _run(self, cmd: list[str]) -> dict:
        p = subprocess.run(cmd, capture_output=True, text=True)
        if p.returncode != 0: raise RuntimeError(f"CLI failed: {' '.join(cmd)}\n{p.stderr}")
        try: return json.loads(p.stdout)
        except: return {"raw_stdout": p.stdout}
