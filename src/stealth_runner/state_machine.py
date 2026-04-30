from __future__ import annotations
import asyncio, signal
from enum import StrEnum, auto
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from .config import StealthConfig, SurveyConfig
from .audit_logger import AuditLogger
from .executor import run_cli_atomic, FatalError, RetryableError
from .vision_client import call_vision_llm

class State(StrEnum):
    IDLE = auto(); LAUNCH_BROWSER = auto(); WAIT_READY = auto()
    CAPTURE = auto(); VISION = auto(); EXECUTE = auto(); VERIFY = auto()
    RECOVERY = auto(); DONE = auto()

@dataclass
class Context:
    cfg: StealthConfig; survey: SurveyConfig; audit: AuditLogger
    pid: int | None = None; loop_count: int = 0; recovery_count: int = 0
    screenshot_path: Path = Path("capture.png")
    vision_decision: Any = None; abort_reason: str | None = None

class AsyncStateMachine:
    def __init__(self, ctx: Context): self.ctx = ctx; self.state = State.IDLE

    async def run(self) -> None:
        while self.state != State.DONE:
            try: await self._transition()
            except FatalError as e: self.ctx.abort_reason = str(e); self.state = State.DONE
            except Exception: self.state = State.RECOVERY
        self.ctx.audit.close()

    async def _transition(self) -> None:
        match self.state:
            case State.IDLE: self.state = State.LAUNCH_BROWSER
            case State.LAUNCH_BROWSER:
                res = await run_cli_atomic(["playstealth-cli", "launch", "--json"]); self.ctx.pid = res.get("pid"); self.state = State.WAIT_READY
            case State.WAIT_READY: self.state = State.CAPTURE
            case State.CAPTURE:
                await run_cli_atomic(["skylight-cli", "capture", "--pid", str(self.ctx.pid), "--out", str(self.ctx.screenshot_path)])
                self.state = State.VISION
            case State.VISION:
                self.ctx.vision_decision = await call_vision_llm(self.ctx.screenshot_path); self.state = State.EXECUTE
            case State.EXECUTE:
                if not self.ctx.cfg.dry_run:
                    await run_cli_atomic(["skylight-cli", "act", "--pid", str(self.ctx.pid), "--action", self.ctx.vision_decision.action])
                self.state = State.VERIFY
            case State.VERIFY:
                if self.ctx.vision_decision.action == "done": self.state = State.DONE
                else:
                    self.ctx.loop_count += 1
                    self.state = State.DONE if self.ctx.loop_count >= self.ctx.survey.max_loops else State.CAPTURE
            case State.RECOVERY:
                self.ctx.recovery_count += 1
                self.state = State.DONE if self.ctx.recovery_count >= self.ctx.survey.recovery_limit else State.CAPTURE
