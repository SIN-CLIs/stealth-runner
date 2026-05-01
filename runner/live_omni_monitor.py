"""Live Omni Screen Monitor – NVIDIA NIM httpx + playstealth launch + skylight-cli.

ARCHITEKTUR-KONFORM:
- httpx direkt an NVIDIA NIM (kein OpenAI-Client)
- playstealth launch für isolierte Chrome-Instanz (nie Nutzer-Chrome)
- skylight-cli --element-index (nie Mauskoordinaten)
"""
from __future__ import annotations
import asyncio
import base64
import json
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import httpx

NVIDIA_KEY = os.environ.get("NVIDIA_API_KEY")
NVIDIA_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
OMNI_MODEL = "nvidia/nvidia/nemotron-3-nano-omni-30b-a3b-reasoning"
TMP = Path("/tmp")


@dataclass
class ScreenFrame:
    timestamp: float
    image_path: str
    image_base64: str = ""


@dataclass
class OmniObservation:
    frame: ScreenFrame
    page_type: str = "unknown"
    action: str = "wait"
    element_index: int = 0
    label: str = ""
    confidence: float = 0.0
    reasoning: str = ""


class LiveOmniMonitor:
    """Capture → Omni Vision → skylight-cli Execute in Echtzeit."""

    def __init__(self, fps: float = 1.0, debug: bool = False):
        if not NVIDIA_KEY:
            raise RuntimeError("NVIDIA_API_KEY not set")
        self.fps = fps
        self.debug = debug
        self.pid: int | None = None
        self.running = False
        self.observations: list[OmniObservation] = []
        self._session = httpx.Client(timeout=60)

    # ── Lifecycle ───────────────────────────────────────────────

    def start(self, url: str = "https://heypiggy.com/?page=dashboard") -> None:
        """playstealth launch → eigene isolierte Chrome-Instanz."""
        result = self._run_cmd(["playstealth", "launch", "--url", url])
        self.pid = result.get("pid")
        if not self.pid:
            raise RuntimeError(f"playstealth launch failed: {result}")
        self.running = True
        if self.debug:
            print(f"🔴 Monitor gestartet: PID={self.pid}", flush=True)

    def stop(self) -> None:
        self.running = False
        self._session.close()
        if self.debug:
            print("⏹ Monitor gestoppt", flush=True)

    # ── Capture ─────────────────────────────────────────────────

    def capture_frame(self) -> ScreenFrame:
        """skylight-cli screenshot → Temp-Datei → Base64."""
        ts = time.time()
        out = TMP / f"omni_frame_{int(ts)}.png"
        self._run_skylight(["screenshot", "--pid", str(self.pid), "--mode", "som", "--output", str(out)])
        if self.debug:
            print(f"📸 Frame: {out.name}", flush=True)
        return ScreenFrame(timestamp=ts, image_path=str(out))

    def _frame_to_b64(self, frame: ScreenFrame) -> str:
        if not frame.image_base64:
            frame.image_base64 = base64.b64encode(Path(frame.image_path).read_bytes()).decode()
        return frame.image_base64

    # ── Omni Vision ─────────────────────────────────────────────

    def analyze_frame(self, frame: ScreenFrame, prompt: str | None = None) -> OmniObservation:
        """NVIDIA NIM httpx Call – 1 Call statt 3 (Vision+OCR+LLM)."""
        b64 = self._frame_to_b64(frame)
        if prompt is None:
            prompt = (
                "You are a survey automation agent. Analyze this screenshot. "
                "Output ONLY JSON:\n"
                '{"page_type":"survey|consent|trap|dashboard|payout",'
                '"action":"click|type|scroll|wait|done",'
                '"element_index":<int>,'
                '"label":"...",'
                '"confidence":0.0-1.0,'
                '"reasoning":"..."}'
            )
        try:
            r = self._session.post(
                NVIDIA_URL,
                headers={"Authorization": f"Bearer {NVIDIA_KEY}"},
                json={
                    "model": OMNI_MODEL,
                    "messages": [{
                        "role": "user",
                        "content": [
                            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
                            {"type": "text", "text": prompt},
                        ],
                    }],
                    "max_tokens": 300,
                    "temperature": 0.1,
                },
            )
            content = r.json()["choices"][0]["message"]["content"]
            result = json.loads(self._extract_json(content))

            obs = OmniObservation(
                frame=frame,
                page_type=result.get("page_type", "unknown"),
                action=result.get("action", "wait"),
                element_index=result.get("element_index", 0),
                label=result.get("label", ""),
                confidence=result.get("confidence", 0.0),
                reasoning=result.get("reasoning", ""),
            )
            self.observations.append(obs)
            if self.debug:
                print(f"👁 Omni → {obs.action} [{obs.element_index}] ({obs.confidence:.2f})", flush=True)
            return obs

        except Exception as e:
            if self.debug:
                print(f"⚠️ Omni: {e}", flush=True)
            return OmniObservation(frame=frame, reasoning=str(e))

    # ── Execute ─────────────────────────────────────────────────

    def execute_action(self, obs: OmniObservation) -> None:
        """skylight-cli click/type – keine Mausbewegung."""
        if not self.pid:
            return
        if obs.action == "click" and obs.element_index >= 0:
            self._run_skylight(["click", "--pid", str(self.pid), "--element-index", str(obs.element_index)])
            if self.debug:
                print(f"🖱 click [{obs.element_index}]", flush=True)
        elif obs.action == "type" and obs.element_index >= 0 and obs.label:
            self._run_skylight(["type", "--pid", str(self.pid), "--element-index", str(obs.element_index), "--text", obs.label])
            if self.debug:
                print(f"⌨ type [{obs.element_index}]: '{obs.label[:30]}'", flush=True)

    # ── Continuous Loop ─────────────────────────────────────────

    def run_continuous(self, max_steps: int = 100, on_action: Callable | None = None) -> None:
        """Capture → Omni → Execute in Endlosschleife (oder bis done/max_steps)."""
        interval = 1.0 / self.fps
        step = 0
        try:
            while self.running and step < max_steps:
                t0 = time.time()
                frame = self.capture_frame()
                obs = self.analyze_frame(frame)

                if obs.action == "done":
                    print("✅ Omni sagt: done – Survey abgeschlossen", flush=True)
                    break

                if obs.confidence >= 0.6:
                    self.execute_action(obs)
                    if on_action:
                        on_action(obs)
                else:
                    if self.debug:
                        print(f"⏳ niedrige confidence ({obs.confidence:.2f}) – warte", flush=True)

                elapsed = time.time() - t0
                remaining = interval - elapsed
                if remaining > 0:
                    time.sleep(remaining)
                step += 1
        finally:
            self.stop()

    # ── Internals ───────────────────────────────────────────────

    def _run_skylight(self, cmd: list[str]) -> dict[str, Any]:
        full = ["skylight-cli"] + cmd
        return self._run_cmd(full)

    def _run_cmd(self, cmd: list[str]) -> dict[str, Any]:
        import subprocess
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        except subprocess.TimeoutExpired:
            return {"status": "error", "reason": "timeout"}
        if r.returncode != 0:
            return {"status": "error", "reason": r.stderr.strip()[:200]}
        for line in reversed(r.stdout.strip().split("\n")):
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue
        return {"raw": r.stdout.strip()[:200]}

    @staticmethod
    def _extract_json(text: str) -> str:
        m = re.search(r"\{.*\}", text, re.DOTALL)
        return m.group() if m else text
