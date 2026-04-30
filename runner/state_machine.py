import time, json, os
from runner.stealth_executor import StealthExecutor
from runner.vision_client import VisionClient
from runner.audit_log import AuditLog
from sin_survey_core import classify_error

RECOVERY_MAX_RETRIES = 3
STATE_FILE = os.path.expanduser("~/.stealth_runner/state.json")

class StealthRunner:
    def __init__(self, pid, wid, vision_client, audit_log):
        self.executor = StealthExecutor(pid, wid)
        self.vision = vision_client
        self.audit = audit_log
        self.state = self._load_state() or "IDLE"
        self.session = {"steps": 0, "earnings_eur": 0.0, "recoveries": 0}
        self.current_screenshot = None
        self.current_action = None

    def _save_state(self):
        os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
        with open(STATE_FILE, "w") as f:
            json.dump({"state": self.state, "session": self.session,
                        "screenshot": self.current_screenshot}, f)

    def _load_state(self):
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE) as f:
                try:
                    data = json.load(f)
                    return data.get("state")
                except json.JSONDecodeError:
                    pass
        return None

    async def run(self):
        self.audit.log("runner_start", pid=self.executor.pid, wid=self.executor.wid)

        while self.state != "DONE":
            try:
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
                self._save_state()
            except Exception as e:
                self.audit.log("runner_error", error=str(e), state=self.state)
                self.state = "RECOVERY"

        os.remove(STATE_FILE) if os.path.exists(STATE_FILE) else None
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
        action_type = action.get("action") or action.get("type", "")
        if action_type == "click":
            result = self.executor.click(element_id=action.get("element_id"))
        elif action_type == "type":
            result = self.executor.type_text(action.get("text", ""))
        elif action_type == "scroll":
            result = self.executor.scroll(action.get("direction", "down"))
        self.audit.log("execute", action_type=action_type, result=result)
        self.session["steps"] += 1
        time.sleep(1)
        self.state = "VERIFY"

    async def _verify(self):
        ws = self.executor.get_window_state()
        page_state = self.vision.detect_state(ws)
        error_type = classify_error(ws.get("tree_markdown", ""))

        stealth = self.executor.verify_stealth()
        if stealth.get("detected"):
            self.audit.log("stealth_breach", fingerprint=stealth.get("fingerprint"))
            self.state = "RECOVERY"
            return

        self.audit.log("verify", page_state=page_state, error_type=error_type,
                       stealth_ok=not stealth.get("detected"))
        if page_state == "survey_end":
            eur = self.vision.extract_earnings(page_text=ws.get("tree_markdown", ""))
            self.session["earnings_eur"] += eur
            self.audit.log("earnings", eur=eur)
            self.state = "DONE"
        elif page_state == "dq" or error_type != "unknown":
            self.audit.log("disqualified", reason=error_type)
            self.state = "DONE"
        else:
            self.state = "CAPTURE"

    async def _recover(self):
        self.session["recoveries"] += 1
        self.audit.log("recovery", attempt=self.session["recoveries"])
        if self.session["recoveries"] > RECOVERY_MAX_RETRIES:
            self.state = "DONE"
        else:
            time.sleep(3)
            self.state = "CAPTURE"
