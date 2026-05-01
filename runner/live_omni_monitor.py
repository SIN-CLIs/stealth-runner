"""Live Omni Screen Monitor – Rolling Video Buffer + Screenshot Hybrid.

ARCHITEKTUR-KONFORM:
- httpx direkt an NVIDIA NIM (kein OpenAI-Client)
- playstealth launch für isolierte Chrome-Instanz
- skylight-cli --element-index (nie Mauskoordinaten)

ZWEI ANALYSE-MODI:
1. Screenshot-Modus (schnell, für sofortige Entscheidungen)
2. Rolling-Video-Buffer (temporal, erkennt Seitenübergänge)
"""
from __future__ import annotations
import base64
import json
import os
import re
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import httpx

NVIDIA_KEY = os.environ.get("NVIDIA_API_KEY")
NVIDIA_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
OMNI_MODEL = "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning"
TMP = Path("/tmp")
VIDEO_BUF = TMP / "omni_rolling.mp4"
VIDEO_CLIP = TMP / "omni_clip.mp4"


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
    temporal: bool = False


class LiveOmniMonitor:
    """Screenshot + Rolling Video Buffer → Omni → skylight-cli Execute."""

    def __init__(self, fps: float = 1.0, buffer_seconds: int = 4, debug: bool = False):
        if not NVIDIA_KEY:
            raise RuntimeError("NVIDIA_API_KEY not set")
        self.fps = fps
        self.buffer_seconds = buffer_seconds
        self.debug = debug
        self.pid: int | None = None
        self.running = False
        self.observations: list[OmniObservation] = []
        self._session = httpx.Client(timeout=60)
        self._video_proc: subprocess.Popen | None = None
        self._frame_count = 0

    # ── Lifecycle ───────────────────────────────────────────────

    def start(self, url: str = "https://heypiggy.com/?page=dashboard") -> None:
        result = self._run_cmd(["playstealth", "launch", "--url", url])
        self.pid = result.get("pid")
        if not self.pid:
            raise RuntimeError(f"playstealth launch failed: {result}")
        self._start_video_recording()
        self.running = True
        if self.debug:
            print(f"🔴 Monitor PID={self.pid}, Video={VIDEO_BUF}", flush=True)

    def stop(self) -> None:
        self.running = False
        self._session.close()
        self._stop_video_recording()
        if self.debug:
            print("⏹ Monitor gestoppt", flush=True)

    def _start_video_recording(self) -> None:
        """screen-follow record --video im Hintergrund."""
        import subprocess
        if VIDEO_BUF.exists():
            VIDEO_BUF.unlink()
        try:
            self._video_proc = subprocess.Popen(
                ["screen-follow", "record", "--video", "--output", str(VIDEO_BUF)],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            time.sleep(1)
        except FileNotFoundError:
            if self.debug:
                print("⚠️ screen-follow nicht gefunden – Video deaktiviert", flush=True)

    def _stop_video_recording(self) -> None:
        if self._video_proc:
            self._video_proc.terminate()
            try:
                self._video_proc.wait(timeout=3)
            except Exception:
                self._video_proc.kill()
            self._video_proc = None

    # ── Capture (Screenshot) ────────────────────────────────────

    def capture_frame(self) -> ScreenFrame:
        ts = time.time()
        png_path = TMP / f"omni_frame_{int(ts)}.png"
        self._run_skylight(["screenshot", "--pid", str(self.pid), "--mode", "som", "--output", str(png_path)])
        # PNG → JPEG quality=50: ~80% weniger Payload bei gleicher Erkennungsqualität
        jpg_path = TMP / f"omni_frame_{int(ts)}.jpg"
        try:
            from PIL import Image
            img = Image.open(png_path).convert("RGB")
            img.save(jpg_path, format="JPEG", quality=50)
            png_path.unlink(missing_ok=True)
            out = jpg_path
        except Exception:
            out = png_path  # Fallback auf PNG wenn PIL fehlt
        self._frame_count += 1
        if self.debug:
            print(f"📸 Frame {self._frame_count}: {out.name}", flush=True)
        return ScreenFrame(timestamp=ts, image_path=str(out))

    # ── Rolling Video Buffer ────────────────────────────────────

    def _extract_video_clip(self) -> str | None:
        """Extrahiert die letzten N Sekunden als base64-mp4."""
        if not VIDEO_BUF.exists() or VIDEO_BUF.stat().st_size < 10000:
            return None
        if VIDEO_CLIP.exists():
            VIDEO_CLIP.unlink()
        try:
            subprocess.run(
                ["ffmpeg", "-sseof", f"-{self.buffer_seconds}", "-i", str(VIDEO_BUF),
                 "-c", "copy", "-y", str(VIDEO_CLIP)],
                capture_output=True, text=True, timeout=10,
            )
            if VIDEO_CLIP.exists() and VIDEO_CLIP.stat().st_size > 1000:
                return base64.b64encode(VIDEO_CLIP.read_bytes()).decode()
        except Exception:
            pass
        return None

    def _frame_to_b64(self, frame: ScreenFrame) -> str:
        if not frame.image_base64:
            frame.image_base64 = base64.b64encode(Path(frame.image_path).read_bytes()).decode()
        return frame.image_base64

    # ── Omni Vision ─────────────────────────────────────────────

    def analyze_frame(self, frame: ScreenFrame, use_video: bool = False,
                      prompt: str | None = None) -> OmniObservation:
        """Screenshot (schnell) oder Rolling-Video-Clip (temporal) an Omni.
        Nutzt SSE (stream: true) für tokenweise Antwort – niedrigste Latenz.
        """
        if prompt is None:
            prompt = self._default_prompt(use_video)

        messages = self._build_messages(frame, use_video, prompt)

        try:
            payload = {
                "model": OMNI_MODEL,
                "messages": messages,
                "max_tokens": 300,
                "temperature": 0.1,
                "stream": True,
            }
            if use_video:
                payload["extra_body"] = {"media_io_kwargs": {"video": {"fps": 1.0, "num_frames": -1}}}

            content = ""
            with self._session.stream(
                "POST", NVIDIA_URL,
                headers={
                    "Authorization": f"Bearer {NVIDIA_KEY}",
                    "Accept": "text/event-stream",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=60,
            ) as response:
                for line in response.iter_lines():
                    if line.startswith("data: ") and "DONE" not in line:
                        try:
                            import json as _j
                            chunk = _j.loads(line[6:])
                            delta = chunk.get("choices", [{}])[0].get("delta", {})
                            # Omni schreibt ins reasoning-Feld statt content
                            tok = delta.get("content") or delta.get("reasoning") or ""
                            if tok:
                                content += tok
                        except Exception:
                            continue

            result = json.loads(self._extract_json(content))

            obs = OmniObservation(
                frame=frame,
                page_type=result.get("page_type", "unknown"),
                action=result.get("action", "wait"),
                element_index=result.get("element_index", 0),
                label=result.get("label", ""),
                confidence=result.get("confidence", 0.0),
                reasoning=result.get("reasoning", ""),
                temporal=use_video,
            )
            self.observations.append(obs)
            mode = "🎬" if use_video else "📸"
            if self.debug:
                print(f"{mode} Omni → {obs.action} [{obs.element_index}] ({obs.confidence:.2f})", flush=True)
            return obs

        except Exception as e:
            if self.debug:
                print(f"⚠️ Omni: {e}", flush=True)
            return OmniObservation(frame=frame, reasoning=str(e))

    def _build_messages(self, frame: ScreenFrame, use_video: bool, prompt: str) -> list:
        if use_video:
            clip = self._extract_video_clip()
            if clip:
                return [{
                    "role": "user",
                    "content": [
                        {"type": "video_url", "video_url": {"url": f"data:video/mp4;base64,{clip}"}},
                        {"type": "text", "text": prompt},
                    ],
                }]
        b64 = self._frame_to_b64(frame)
        return [{
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
                {"type": "text", "text": prompt},
            ],
        }]

    def _default_prompt(self, use_video: bool) -> str:
        if use_video:
            return (
                "You are a survey automation agent. This is a short video clip "
                "of the last few seconds of screen activity. "
                "Did the page transition? Is there a new element? "
                "Output ONLY JSON:\n"
                '{"page_type":"survey|consent|trap|dashboard|payout",'
                '"action":"click|type|scroll|wait|done",'
                '"element_index":<int>,'
                '"label":"...",'
                '"page_changed":true|false,'
                '"confidence":0.0-1.0,'
                '"reasoning":"..."}'
            )
        return (
            "You are a survey automation agent. Analyze this screenshot. "
            "Output ONLY JSON:\n"
            '{"page_type":"survey|consent|trap|dashboard|payout",'
            '"action":"click|type|scroll|wait|done",'
            '"element_index":<int>,'
            '"label":"...",'
            '"confidence":0.0-1.0,'
            '"reasoning":"..."}'
        )

    # ── Execute ─────────────────────────────────────────────────

    def execute_action(self, obs: OmniObservation) -> None:
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
        """Hybrid Loop: Screenshot (schnell) + Video (alle 5 Schritte temporal)."""
        interval = 1.0 / self.fps
        step = 0
        try:
            while self.running and step < max_steps:
                t0 = time.time()
                frame = self.capture_frame()

                # Alle 5 Schritte: Video-Clip für temporales Verständnis
                use_video = (step > 0 and step % 5 == 0)
                obs = self.analyze_frame(frame, use_video=use_video)

                if obs.action == "done":
                    print("✅ Omni: Survey abgeschlossen", flush=True)
                    break

                if obs.confidence >= 0.5:
                    self.execute_action(obs)
                    if on_action:
                        on_action(obs)
                else:
                    if self.debug:
                        print(f"⏳ confidence={obs.confidence:.2f}", flush=True)
                    time.sleep(1)

                elapsed = time.time() - t0
                remaining = interval - elapsed
                if remaining > 0:
                    time.sleep(remaining)
                step += 1
        finally:
            self.stop()

    # ── Internals ───────────────────────────────────────────────

    def _run_skylight(self, cmd: list[str]) -> dict[str, Any]:
        return self._run_cmd(["skylight-cli"] + cmd)

    def _run_cmd(self, cmd: list[str]) -> dict[str, Any]:
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
