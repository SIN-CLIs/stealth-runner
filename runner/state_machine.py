"""State Machine – 10 Zustände + OpenTelemetry Tracing."""
from __future__ import annotations
import sys
from enum import StrEnum
from pathlib import Path
import anyio
from .stealth_executor import StealthExecutor
from .vision_client import VisionClient
from .prompt_kit import build_prompt
from .audit_log import AuditLog
from .human_profile import HumanProfile
from .apm import start_trace

class State(StrEnum):
    IDLE = "idle"; LAUNCH_BROWSER = "launch_browser"; WAIT_READY = "wait_ready"
    CAPTURE = "capture"; VISION = "vision"; EXECUTE = "execute"; VERIFY = "verify"
    DONE = "done"; RECOVERY = "recovery"

class SurveyRunner:
    MAX_RECOVERIES = 5
    def __init__(self, url: str) -> None:
        self.url = url; self.pid: int|None = None
        self.executor = StealthExecutor(); self.vision = VisionClient()
        self.log = AuditLog(Path.home()/".stealth_runner"/"traces.jsonl")
        self.state = State.IDLE; self.step = 0; self.recoveries = 0
        self.context = {"url":url,"steps":0,"earnings_eur":0.0}
        self.current_screenshot: str|None = None
        self.pending_action: dict|None = None

    async def run(self) -> dict:
        with start_trace("survey-runner"):
            while self.state != State.DONE:
                try: await self._transition()
                except Exception as e: self.log.log("error", error=str(e)); self.state = State.RECOVERY
        self.log.close(); return self.context

    async def _transition(self):
        with start_trace(f"state:{self.state}"):
            match self.state:
                case State.IDLE: self.state = State.LAUNCH_BROWSER if not self.pid else State.CAPTURE
                case State.LAUNCH_BROWSER: await self._launch()
                case State.WAIT_READY: await self._wait_ready()
                case State.CAPTURE: await self._capture()
                case State.VISION: await self._vision()
                case State.EXECUTE: await self._execute()
                case State.VERIFY: await self._verify()
                case State.RECOVERY: await self._recover()

    async def _launch(self):
        self.executor.ensure_tls(self.url)
        r = self.executor.run(["playstealth-cli","launch","--url",self.url,"--json"])
        self.pid = r["pid"]; self.executor.pid = self.pid; self.state = State.WAIT_READY

    async def _wait_ready(self):
        for _ in range(10):
            r = self.executor.run(["skylight-cli","screenshot","--pid",str(self.pid),"--mode","raw","--out","/tmp/wait_ready.png"])
            if len(r.get("elements",[])) > 3: break
            await anyio.sleep(1)
        self.state = State.CAPTURE

    async def _capture(self):
        out = f"/tmp/step_{self.step}.png"
        self.executor.screenshot(out_path=out, mode="som")
        self.current_screenshot = out; self.state = State.VISION

    async def _vision(self):
        prompt = build_prompt(self.context, self.step)
        self.pending_action = self.vision.get_action(self.current_screenshot, prompt)
        self.state = State.EXECUTE

    async def _execute(self):
        act = self.pending_action or {}; at = act.get("action","wait")
        if at == "click": self.executor.click(element_index=act.get("element_id"))
        elif at == "type": self.executor.type_text(text=act.get("args",{}).get("text",""), element_index=act.get("element_id"))
        elif at == "scroll": self.executor.scroll()
        elif at == "done": self.state = State.DONE; return
        self.step += 1; self.state = State.VERIFY

    async def _verify(self):
        try:
            if self.executor.verify_stealth().get("detected"): self.state = State.RECOVERY; return
        except: pass
        self.state = State.CAPTURE

    async def _recover(self):
        if self.recoveries >= self.MAX_RECOVERIES: self.state = State.DONE; return
        self.recoveries += 1
        self.executor.run(["playstealth-cli","rotate-profile","--pid",str(self.pid)])
        await anyio.sleep(2); self.state = State.CAPTURE

def main():
    if len(sys.argv) != 2: print("Usage: python main.py <URL>"); sys.exit(1)
    anyio.run(SurveyRunner(sys.argv[1]).run)
