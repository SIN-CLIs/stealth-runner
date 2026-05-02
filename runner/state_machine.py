"""State Machine — JEDER Schritt VISION (Omni-first, Multi-Frame)."""
from __future__ import annotations
import json, os, subprocess, sys
from enum import StrEnum
from pathlib import Path
import anyio
from .stealth_executor import StealthExecutor
from .vision_client import VisionClient
from .prompt_kit import build_vision_prompt, build_logic_prompt
from .model_router import ModelRouter, Task, get_router
from .audit_log import AuditLog
from .human_profile import HumanProfile
from .answer_logic import PERSONA


class State(StrEnum):
    IDLE = "idle"
    LAUNCH_BROWSER = "launch_browser"
    LOGIN = "login"
    WAIT_READY = "wait_ready"
    CAPTURE = "capture"
    VISION = "vision"
    EXECUTE = "execute"
    VERIFY = "verify"
    DONE = "done"
    RECOVERY = "recovery"


class SurveyRunner:
    MAX_RECOVERIES = 5

    def __init__(self, url: str, profile: HumanProfile | None = None):
        self.url = url
        self.pid = None
        self.profile = profile or HumanProfile.random()
        self.executor = StealthExecutor()
        self.vision = VisionClient()
        self.log = AuditLog(Path.home() / ".stealth_runner" / "traces.jsonl")
        self.state = State.IDLE
        self.step = 0
        self.context = {"url": url, "steps": 0, "earnings_eur": 0.0}
        self.current_screenshot = None
        self.pending_action = None
        self.recoveries = 0
        self.frame_history: list[str] = []
        self._load_checkpoint()

    def _load_checkpoint(self):
        cp = Path.home() / ".stealth-runner" / "checkpoint.json"
        if cp.exists():
            try:
                d = json.loads(cp.read_text())
                self.state = State(d["state"])
                self.pid = d.get("pid")
                self.step = d.get("step", 0)
                self.context = d.get("context", self.context)
                self.recoveries = d.get("recoveries", 0)
                self.frame_history = d.get("frames", [])
                cp.unlink()
            except Exception:
                cp.unlink(missing_ok=True)

    def _save_checkpoint(self):
        cp = Path.home() / ".stealth-runner" / "checkpoint.json"
        cp.parent.mkdir(parents=True, exist_ok=True)
        cp.write_text(json.dumps({
            "state": self.state.value, "pid": self.pid, "step": self.step,
            "context": self.context, "recoveries": self.recoveries,
            "frames": self.frame_history[-10:],
        }))

    async def run(self) -> dict:
        self.log.log("runner_start", url=self.url)
        print(f"� Runner: {self.url}", flush=True)
        while self.state != State.DONE:
            try:
                await self._transition()
            except Exception as e:
                print(f"❌ {e}", flush=True)
                self.log.log("error", error=str(e))
                self._save_checkpoint()
                self.state = State.RECOVERY
        print(f"💰 EUR: {self.context.get('earnings_eur', 0):.2f} | Steps: {self.step}", flush=True)
        self.log.log("runner_done", stats=self.context)
        self.log.close()
        return self.context

    async def _transition(self):
        match self.state:
            case State.IDLE:
                self.state = State.LAUNCH_BROWSER if not self.pid else State.CAPTURE
            case State.LAUNCH_BROWSER:
                await self._launch()
            case State.LOGIN:
                await self._login()
            case State.WAIT_READY:
                await self._wait_ready()
            case State.CAPTURE:
                await self._capture()
            case State.VISION:
                await self._vision()
            case State.EXECUTE:
                await self._execute()
            case State.VERIFY:
                await self._verify()
            case State.RECOVERY:
                await self._recover()

    async def _launch(self):
        print("→ Browser starten...", flush=True)
        result = self.executor.run(["playstealth", "launch", "--url", self.url])
        self.pid = result.get("pid")
        self.executor.pid = self.pid
        print(f"✓ PID={self.pid}", flush=True)
        self.log.log("launch", pid=self.pid)
        self.state = State.LOGIN

    async def _login(self):
        profile = Path("profiles/jeremy.yaml")
        email = os.environ.get("GOOGLE_EMAIL", "")
        if profile.exists() and not email:
            try:
                import yaml
                data = yaml.safe_load(profile.read_text())
                email = data.get("google_email", "")
            except Exception:
                pass
        if email:
            print(f"🔐 Login {email}...", flush=True)
            try:
                result = subprocess.run(
                    ["bash", "cli/heypiggy-login", str(self.pid)],
                    cwd=Path(__file__).parent.parent,
                    capture_output=True, text=True, timeout=120,
                )
                print(f"✅ Login: {result.stdout.strip()[-200:]}", flush=True)
            except subprocess.TimeoutExpired:
                print("⚠️ Login timeout", flush=True)
            except Exception as e:
                print(f"⚠️ Login: {e}", flush=True)
        else:
            print("⚠️ Kein Profil — ohne Login", flush=True)
        self.state = State.WAIT_READY

    async def _wait_ready(self):
        for _ in range(10):
            try:
                self.executor.run(["skylight-cli", "get-window-state", "--pid", str(self.pid)])
                break
            except Exception:
                await anyio.sleep(1)
        self.state = State.CAPTURE

    async def _capture(self):
        out = f"/tmp/step_{self.step}.png"
        s = self.executor.screenshot(out_path=out, mode="som")
        self.current_screenshot = str(s.get("file", out))
        self.frame_history.append(self.current_screenshot)
        if len(self.frame_history) > 10:
            self.frame_history = self.frame_history[-10:]
        self.context["frame_history"] = self.frame_history[-5:]
        print(f"📸 Screenshot: step_{self.step}.png", flush=True)
        self.log.log("capture", file=self.current_screenshot)
        self.state = State.VISION

    async def _vision(self):
        from .nemotron_omni import get_omni

        prompt = build_vision_prompt(self.context, self.step)
        router = get_router()

        # Multi-Frame Context wenn verfuegbar
        if len(self.frame_history) >= 2:
            try:
                omni = get_omni()
                recent = self.frame_history[-2:]
                self.pending_action = omni.analyze_frame_sequence(recent, prompt)
                if self.pending_action.get("action") in ("wait", None) and self.frame_history:
                    self.pending_action = self.vision.get_action(self.current_screenshot, prompt)
            except Exception:
                self.pending_action = self.vision.get_action(self.current_screenshot, prompt)
        else:
            self.pending_action = self.vision.get_action(self.current_screenshot, prompt)

        # Mistral Persona (task=persona) bei erkannter Frage
        question_text = self.pending_action.get("question_text") or self.pending_action.get("reason", "")
        if question_text and len(question_text) > 10:
            try:
                import json as _json
                profile_str = _json.dumps(PERSONA, indent=2, ensure_ascii=False)
                pp = (
                    f"Du bist ein Persona-basierter Survey-Assistent.\n\n"
                    f"BENUTZERPROFIL:\n{profile_str}\n\n"
                    f"FRAGE: {question_text}\n"
                    f"Seite: {self.context.get('page', 'unknown')}\n\n"
                    "Finde die passende Antwort aus dem Profil.\n"
                    "Antworte NUR mit JSON:\n"
                    '{"has_match":true/false,"answer":"...","element_id":<int>,"reason":"..."}'
                )
                resp = router.call(Task.PERSONA, pp)
                pr = ModelRouter.extract_json(resp)
                if pr.get("has_match"):
                    self.pending_action["persona_answer"] = pr
            except Exception:
                pass

        # Mistral Logic (task=logic) bei unsicherer Aktion
        if self.pending_action.get("action") in ("wait", None):
            try:
                lp = build_logic_prompt(self.context, self.step)
                resp = router.call(Task.LOGIC, lp)
                lr = ModelRouter.extract_json(resp)
                if lr.get("action") and lr["action"] != "wait":
                    self.pending_action = {**self.pending_action, **lr}
            except Exception:
                pass

        a = self.pending_action.get("action", "?")
        print(f"👁 Omni → {a}", flush=True)
        self.log.log("vision", action=self.pending_action)
        self.state = State.EXECUTE

    async def _execute(self):
        act = self.pending_action or {}
        atype = act.get("action", "wait")
        args = act.get("args", {})
        eid = act.get("element_id")

        if atype == "click":
            self.executor.click(element_index=eid)
        elif atype == "type":
            self.executor.type_text(text=args.get("text", ""), element_index=eid)
        elif atype == "scroll":
            self.executor.scroll(direction=args.get("direction", "down"))
        elif atype == "hold":
            dur = args.get("duration_ms", 3000)
            self.executor.hold(element_index=eid, duration_ms=dur)
        elif atype == "wait":
            await anyio.sleep(2)
            print("⏳ wait", flush=True)
        elif atype == "done":
            self.state = State.DONE
            print("✅ done", flush=True)
            return

        print(f"👆 {atype} [{eid}]", flush=True)
        self.step += 1
        self.context["steps"] = self.step
        self.log.log("execute", action=act, step=self.step)
        self.state = State.VERIFY

    async def _verify(self):
        try:
            if self.executor.verify_stealth().get("detected"):
                self.state = State.RECOVERY
                return
        except Exception:
            pass
        self._save_checkpoint()
        self.state = State.CAPTURE

    async def _recover(self):
        if self.recoveries >= self.MAX_RECOVERIES:
            self.state = State.DONE
            return
        self.recoveries += 1
        await anyio.sleep(2)
        self.state = State.CAPTURE
