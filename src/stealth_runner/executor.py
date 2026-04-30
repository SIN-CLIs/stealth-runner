from __future__ import annotations
import asyncio, json
from typing import Any

class StealthRunnerError(Exception): pass
class RetryableError(StealthRunnerError): pass
class FatalError(StealthRunnerError): pass

async def run_cli_atomic(cmd: list[str], timeout: float = 8.0) -> dict[str, Any]:
    proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    try: stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError as exc: proc.kill(); raise RetryableError(f"Timeout: {' '.join(cmd)}") from exc
    if proc.returncode == 0:
        lines = stdout.decode().strip().splitlines()
        return json.loads(lines[-1]) if lines else {}
    if proc.returncode == 1: raise RetryableError(stderr.decode())
    raise FatalError(f"Exit {proc.returncode}: {stderr.decode()}")
