"""Async CLI-Executor mit Timeout, Exit-Code-Mapping & Zombie-Cleanup."""
from __future__ import annotations
import asyncio, json, logging
from typing import Any

class RetryableCLIError(Exception): pass
class FatalCLIError(Exception): pass
class StealthDegradedError(Exception): pass

EXIT_MAP: dict[int, type[Exception]] = {1: RetryableCLIError, 2: FatalCLIError, 3: StealthDegradedError}

async def run_cli_atomic(cmd: list[str], timeout: float = 8.0) -> dict[str, Any]:
    proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    try: stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError: proc.kill(); await proc.wait(); raise RuntimeError(f"Timeout: {' '.join(cmd)}")
    if proc.returncode == 0:
        lines = stdout.decode().strip().split("\n")
        return json.loads(lines[-1]) if lines else {"status": "ok"}
    error_class = EXIT_MAP.get(proc.returncode, FatalCLIError)
    raise error_class(f"Exit {proc.returncode}: {stderr.decode().strip()[:500]}")

async def cleanup_browser(pid: int) -> None:
    try: proc = await asyncio.create_subprocess_exec("kill", str(pid), stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL); await proc.wait()
    except Exception: pass
