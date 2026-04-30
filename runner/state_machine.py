import anyio, time, json, os
from pathlib import Path
from enum import StrEnum

from .stealth_executor import StealthExecutor
from .vision_client import VisionClient
from .prompt_kit import build_prompt
from .audit_log import AuditLog
from sin_survey_core import classify_error

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
    def __init__(self, url, profile=None):
        self.url = url
        self.pid = None
        self.executor = StealthExecutor(0, 0)
        self.vision = VisionClient()
        self.log = AuditLog(Path.home() / ".stealth_runner" / "traces.jsonl")
        self.state = State.IDLE
        self.step = 0
        self.context = {"url": url, "steps": 0, "earnings_eur": 0.0}
        self.current_screenshot = None
        self.pending_action = None
        self.recoveries = 0

    async def run(self):
        self.log.log("runner_start", url=self.url)
        while self.state != State.DONE:
            try:
                await self._transition()
            except Exception as e:
                self.log.log("runner_error", error=str(e), state=self.state)
                self.state = State.RECOVERY
        self.log.log("runner_done", stats=self.context)
        return self.context

    async def _transition(self):
        if self.state == State.IDLE:
            self.state = State.LAUNCH_BROWSER if not self.pid else State.CAPTURE
        elif self.state == State.LAUNCH_BROWSER:
            await self._launch()
        elif self.state == State.WAIT_READY:
            await self._wait_ready()
        elif self.state == State.CAPTURE:
            await self._capture()
        elif self.state == State.VISION:
            await self._vision()
        elif self.state == State.EXECUTE:
            await self._execute()
        elif self.state == State.VERIFY:
            await self._verify()
        elif self.state == State.RECOVERY:
            await self._recover()

    async def _launch(self):
        result = self.executor.run(["playstealth-cli", "launch", "--url", self.url, "--json"])
        self.pid = result["pid"]
        self.executor.pid = self.pid
        self.log.log("launch", pid=self.pid)
        self.state = State.WAIT_READY

    async def _wait_ready(self):
        self.executor.run(["skylight-cli", "screenshot", "--pid", str(self.pid), "--mode", "raw", "--out", "/tmp/wait_ready.png"])
        self.state = State.CAPTURE

    async def _capture(self):
        out = f"/tmp/step_{self.step}.png"
        self.executor.run(["skylight-cli", "screenshot", "--pid", str(self.pid), "--mode", "som", "--out", out])
        self.current_screenshot = out
        self.log.log("capture", file=out)
        self.state = State.VISION

    async def _vision(self):
        prompt = build_prompt(self.context, self.step)
        action = self.vision.get_action(self.current_screenshot, prompt)
        self.pending_action = action
        self.log.log("vision", action=action)
        self.state = State.EXECUTE

    async def _execute(self):
        act = self.pending_action
        action_type = act.get("action", "wait")
        if action_type == "click" and "element_id" in act:
            self.executor.click(element_index=act["element_id"])
        elif action_type == "type" and "text" in act:
            self.executor.type_text(act["text"])
        elif action_type == "scroll":
            self.executor.scroll(act.get("direction", "down"))
        self.log.log("execute", action=act)
        self.context["steps"] += 1
        self.state = State.VERIFY

    async def _verify(self):
        try:
            result = self.executor.run(["unmask-cli", "verify-stealth", "--pid", str(self.pid)])
            if result.get("detected"):
                self.log.log("detected", result=result)
                self.state = State.RECOVERY
                return
        except Exception:
            pass
        if self.pending_action and self.pending_action.get("action") == "done":
            self.state = State.DONE
        else:
            self.state = State.CAPTURE

    async def _recover(self):
        self.context["recoveries"] = self.context.get("recoveries", 0) + 1
        self.log.log("recovery", attempt=self.context["recoveries"])
        if self.context["recoveries"] > 3:
            self.state = State.DONE
        else:
            self.executor.run(["playstealth-cli", "rotate-profile", "--pid", str(self.pid)])
            await anyio.sleep(2)
            self.state = State.CAPTURE
