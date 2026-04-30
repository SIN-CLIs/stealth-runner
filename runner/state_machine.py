"""State Machine – 10-Zustands-Orchestrator für die Stealth-Triade."""
from __future__ import annotations
import sys
from enum import StrEnum
from pathlib import Path
import anyio
from .stealth_executor import StealthExecutor, StealthError
from .vision_client import VisionClient
from .prompt_kit import build_prompt
from .audit_log import AuditLog
from .human_profile import HumanProfile

class State(StrEnum):
    IDLE = "idle"
    LAUNCH_BROWSER = "launch_browser"
    WAIT_READY = "wait_ready"
    CAPTURE = "capture"
    VISION = "vision"
    EXECUTE = "execute"
    VERIFY = "verify"
    DONE = "done"
    RECOVERY = "recovery"

class SurveyRunner:
    MAX_RECOVERIES = 5
    def __init__(self, url: str, profile: HumanProfile | None = None) -> None:
        self.url = url
        self.pid: int | None = None
        self.profile = profile or HumanProfile.random()
        self.executor = StealthExecutor()
        self.vision = VisionClient()
        self.log = AuditLog(Path.home() / ".stealth_runner" / "traces.jsonl")
        self.state = State.IDLE
        self.step = 0
        self.context: dict = {"url": url, "steps": 0, "earnings_eur": 0.0}
        self.current_screenshot: str | None = None
        self.pending_action: dict | None = None
        self.recoveries = 0

    async def run(self) -> dict:
        self.log.log("runner_start", url=self.url)
        while self.state != State.DONE:
            try: await self._transition()
            except Exception as e:
                self.log.log("runner_error", error=str(e), state=self.state)
                self.state = State.RECOVERY
        self.log.log("runner_done", stats=self.context)
        self.log.close()
        return self.context

    async def _transition(self) -> None:
        match self.state:
            case State.IDLE: self.state = State.LAUNCH_BROWSER if not self.pid else State.CAPTURE
            case State.LAUNCH_BROWSER: await self._launch()
            case State.WAIT_READY: await self._wait_ready()
            case State.CAPTURE: await self._capture()
            case State.VISION: await self._vision()
            case State.EXECUTE: await self._execute()
            case State.VERIFY: await self._verify()
            case State.RECOVERY: await self._recover()

    async def _launch(self) -> None:
        result = self.executor.run(["playstealth-cli", "launch", "--url", self.url, "--json"])
        self.pid = result["pid"]
        self.executor.pid = self.pid
        self.log.log("launch", pid=self.pid)
        self.state = State.WAIT_READY

    async def _wait_ready(self) -> None:
        for _ in range(10):
            result = self.executor.run(["skylight-cli", "screenshot", "--pid", str(self.pid), "--mode", "raw", "--out", "/tmp/wait_ready.png"])
            if result.get("elements") and len(result.get("elements", [])) > 3: break
            await anyio.sleep(1.0)
        else: self.log.log("wait_ready_timeout", pid=self.pid)
        self.state = State.CAPTURE

    async def _capture(self) -> None:
        out = f"/tmp/step_{self.step}.png"
        self.executor.screenshot(out_path=out, mode="som")
        self.current_screenshot = out
        self.log.log("capture", file=out)
        self.state = State.VISION

    async def _vision(self) -> None:
        prompt = build_prompt(self.context, self.step)
        action = self.vision.get_action(self.current_screenshot, prompt)
        self.pending_action = action
        self.log.log("vision", action=action)
        self.state = State.EXECUTE

    async def _execute(self) -> None:
        act = self.pending_action or {}
        action_type = act.get("action", "wait")
        args = act.get("args", {})
        element_id = act.get("element_id")
        if action_type == "click": self.executor.click(element_index=element_id)
        elif action_type == "type": self.executor.type_text(text=args.get("text", act.get("text", "")), element_index=element_id, clear_first=args.get("clear_first", False))
        elif action_type == "scroll": self.executor.scroll(direction=args.get("direction", "down"))
        elif action_type == "wait": await anyio.sleep(2.0)
        elif action_type == "done": self.state = State.DONE; return
        self.step += 1
        self.context["steps"] = self.step
        self.log.log("execute", action=act, step=self.step)
        self.state = State.VERIFY if action_type != "done" else State.DONE

    async def _verify(self) -> None:
        if self.state == State.DONE: return
        try:
            result = self.executor.verify_stealth()
            if result.get("detected"): self.log.log("detected", result=result); self.state = State.RECOVERY; return
        except Exception: pass
        self.state = State.CAPTURE

    async def _recover(self) -> None:
        if self.recoveries >= self.MAX_RECOVERIES: self.log.log("max_recoveries"); self.state = State.DONE; return
        self.recoveries += 1
        self.log.log("recovery", attempt=self.recoveries)
        self.executor.run(["playstealth-cli", "rotate-profile", "--pid", str(self.pid)])
        await anyio.sleep(2.0)
        self.state = State.CAPTURE

def main():
    if len(sys.argv) != 2: print("Usage: python -m runner.state_machine <URL>"); sys.exit(1)
    anyio.run(SurveyRunner(sys.argv[1]).run)
