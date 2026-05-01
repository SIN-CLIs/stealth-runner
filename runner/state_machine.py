"""State Machine — JEDER Schritt VISION (kein DOM-Prescan)."""
from __future__ import annotations
import json, sys
from enum import StrEnum
from pathlib import Path
import anyio
from .stealth_executor import StealthExecutor
from .vision_client import VisionClient
from .prompt_kit import build_prompt
from .audit_log import AuditLog
from .human_profile import HumanProfile

class State(StrEnum):
    IDLE="idle"; LAUNCH_BROWSER="launch_browser"; WAIT_READY="wait_ready"
    CAPTURE="capture"; VISION="vision"; EXECUTE="execute"; VERIFY="verify"
    DONE="done"; RECOVERY="recovery"

class SurveyRunner:
    MAX_RECOVERIES = 5
    def __init__(self, url: str, profile: HumanProfile|None=None):
        self.url = url; self.pid = None; self.profile = profile or HumanProfile.random()
        self.executor = StealthExecutor(); self.vision = VisionClient()
        self.log = AuditLog(Path.home()/".stealth_runner"/"traces.jsonl")
        self.state = State.IDLE; self.step = 0
        self.context = {"url":url,"steps":0,"earnings_eur":0.0}
        self.current_screenshot = None; self.pending_action = None; self.recoveries = 0
        self._load_checkpoint()
    def _load_checkpoint(self):
        cp = Path.home()/".stealth-runner"/"checkpoint.json"
        if cp.exists():
            try:
                d = json.loads(cp.read_text())
                self.state = State(d["state"]); self.pid = d.get("pid")
                self.step = d.get("step",0); self.context = d.get("context",self.context)
                self.recoveries = d.get("recoveries",0); cp.unlink()
            except: cp.unlink(missing_ok=True)
    def _save_checkpoint(self):
        cp = Path.home()/".stealth-runner"/"checkpoint.json"
        cp.parent.mkdir(parents=True, exist_ok=True)
        cp.write_text(json.dumps({"state":self.state.value,"pid":self.pid,"step":self.step,"context":self.context,"recoveries":self.recoveries}))
    async def run(self) -> dict:
        self.log.log("runner_start",url=self.url)
        while self.state != State.DONE:
            try: await self._transition()
            except Exception as e: self.log.log("error",error=str(e)); self._save_checkpoint(); self.state = State.RECOVERY
        self.log.log("runner_done",stats=self.context); self.log.close()
        return self.context
    async def _transition(self):
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
        result = self.executor.run(["playstealth","launch","--url",self.url])
        self.pid = result.get("pid"); self.executor.pid = self.pid
        self.log.log("launch",pid=self.pid); self.state = State.WAIT_READY
    async def _wait_ready(self):
        for _ in range(10):
            try:
                self.executor.run(["skylight-cli","get-window-state","--pid",str(self.pid)])
                break
            except: await anyio.sleep(1)
        self.state = State.CAPTURE
    async def _capture(self):
        out = f"/tmp/step_{self.step}.png"
        self.executor.screenshot(out_path=out, mode="som")
        self.current_screenshot = out; self.log.log("capture",file=out)
        self.state = State.VISION
    async def _vision(self):
        self.pending_action = self.vision.get_action(self.current_screenshot, build_prompt(self.context,self.step))
        self.log.log("vision",action=self.pending_action); self.state = State.EXECUTE
    async def _execute(self):
        act = self.pending_action or {}; atype = act.get("action","wait"); args = act.get("args",{}); eid = act.get("element_id")
        if atype=="click": self.executor.click(element_index=eid)
        elif atype=="type": self.executor.type_text(text=args.get("text",""), element_index=eid)
        elif atype=="scroll": self.executor.scroll(direction=args.get("direction","down"))
        elif atype=="wait": await anyio.sleep(2)
        elif atype=="done": self.state = State.DONE; return
        self.step += 1; self.context["steps"] = self.step; self.log.log("execute",action=act,step=self.step)
        self.state = State.VERIFY
    async def _verify(self):
        try:
            if self.executor.verify_stealth().get("detected"): self.state = State.RECOVERY; return
        except: pass
        self._save_checkpoint(); self.state = State.CAPTURE
    async def _recover(self):
        if self.recoveries >= self.MAX_RECOVERIES: self.state = State.DONE; return
        self.recoveries += 1; await anyio.sleep(2); self.state = State.CAPTURE

def main():
    if len(sys.argv)!=2: print("Usage: python main.py <URL>", file=sys.stderr); sys.exit(1)
    anyio.run(SurveyRunner(sys.argv[1]).run)
if __name__=="__main__": main()
