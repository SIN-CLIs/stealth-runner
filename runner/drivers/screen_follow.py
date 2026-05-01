"""ScreenFollowDriver – Bildschirmaufnahme via screen-follow CLI."""
from __future__ import annotations
import subprocess, json
from typing import Any


class ScreenFollowDriver:
    def start_recording(self, video: bool = True, out_dir: str = "/tmp/screen-follow") -> dict[str, Any]:
        cmd = ["screen-follow", "record"]
        if video: cmd.append("--video")
        cmd.extend(["--out", out_dir])
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            if proc.returncode != 0:
                return {"status": "error", "error": proc.stderr.strip()[:300]}
            return json.loads(proc.stdout) if proc.stdout.strip().startswith("{") else {"status": "ok", "raw": proc.stdout.strip()}
        except FileNotFoundError:
            return {"status": "error", "error": "screen-follow not installed"}
        except subprocess.TimeoutExpired:
            return {"status": "error", "error": "timeout"}

    def stop_recording(self) -> dict[str, Any]:
        try:
            proc = subprocess.run(["screen-follow", "stop"], capture_output=True, text=True, timeout=10)
            if proc.returncode != 0:
                return {"status": "error", "error": proc.stderr.strip()[:300]}
            return json.loads(proc.stdout) if proc.stdout.strip().startswith("{") else {"status": "ok", "raw": proc.stdout.strip()}
        except (FileNotFoundError, subprocess.TimeoutExpired) as e:
            return {"status": "error", "error": str(e)}

    def get_status(self) -> dict[str, Any]:
        try:
            proc = subprocess.run(["screen-follow", "status"], capture_output=True, text=True, timeout=5)
            return json.loads(proc.stdout) if proc.stdout.strip().startswith("{") else {"status": "ok"}
        except (FileNotFoundError, subprocess.TimeoutExpired, json.JSONDecodeError):
            return {"status": "unknown"}
