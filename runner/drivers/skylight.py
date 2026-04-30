from pathlib import Path
from typing import Any
from .base import BaseDriver
import subprocess, json

class SkyLightDriver(BaseDriver):
    def screenshot(self, pid, mode, out):
        res = subprocess.run(["skylight-cli", "screenshot", "--pid", str(pid), "--mode", mode, "--out", str(out)], capture_output=True, text=True)
        if res.returncode != 0: raise RuntimeError(f"skylight-cli failed: {res.stderr}")
        return json.loads(res.stdout)

    def click(self, pid, idx):
        res = subprocess.run(["skylight-cli", "click", "--pid", str(pid), "--element-index", str(idx)], capture_output=True, text=True)
        if res.returncode != 0: raise RuntimeError(f"skylight-cli failed: {res.stderr}")
        return json.loads(res.stdout)
