import time
from runner.stealth_executor import StealthExecutor
from runner.vision_client import VisionClient
from runner.audit_log import AuditLog

class StealthRunner:
    def __init__(self, pid, wid, vision_client, audit_log):
        self.executor = StealthExecutor(pid, wid)
        self.vision = vision_client
        self.audit = audit_log
        self.state = "IDLE"
        self.session = {"steps": 0, "earnings_eur": 0.0}

    async def run(self):
        self.audit.log("runner_start", pid=self.executor.pid, wid=self.executor.wid)

        while self.state != "DONE":
            if self.state == "IDLE":
                await self._idle()
            elif self.state == "CAPTURE":
                await self._capture()
            elif self.state == "VISION":
                await self._vision()
            elif self.state == "EXECUTE":
                await self._execute()
            elif self.state == "VERIFY":
                await self._verify()
            elif self.state == "RECOVERY":
                await self._recover()

        self.audit.log("runner_done", stats=self.session)
        return self.session

    async def _idle(self):
        self.state = "CAPTURE"

    async def _capture(self):
        result = self.executor.screenshot()
        self.audit.log("capture", screenshot=result["file"])
        self.current_screenshot = result["file"]
        self.state = "VISION"

    async def _vision(self):
        action = self.vision.analyze(self.current_screenshot, self.session)
        self.audit.log("vision", action=action)
        self.current_action = action
        self.state = "EXECUTE"

    async def _execute(self):
        action = self.current_action
        result = {}
        if action["type"] == "click":
            result = self.executor.click(element_id=action.get("element_id"))
        elif action["type"] == "type":
            result = self.executor.type_text(action.get("text", ""))
        elif action["type"] == "scroll":
            result = self.executor.scroll(action.get("direction", "down"))
        self.audit.log("execute", action_type=action["type"], result=result)
        self.session["steps"] += 1
        time.sleep(1)
        self.state = "VERIFY"

    async def _verify(self):
        ws = self.executor.get_window_state()
        page_state = self.vision.detect_state(ws)
        self.audit.log("verify", page_state=page_state)
        if page_state == "survey_end":
            eur = self.vision.extract_earnings()
            self.session["earnings_eur"] += eur
            self.audit.log("earnings", eur=eur)
            self.state = "DONE"
        elif page_state == "dq":
            self.state = "DONE"
        else:
            self.state = "CAPTURE"

    async def _recover(self):
        self.audit.log("recovery")
        self.state = "CAPTURE"
