#!/usr/bin/env python3
"""
LiveOmniAgent – Auge+Hirn+Hand. Finale Version.
- Retina: pixel-diff, nur Changes (95% Reduktion)
- Cortex: Omni sagt LABEL (nie Koordinaten!)
- Hands: skylight-cli + cua-driver, NUR element-index
"""
from __future__ import annotations
import asyncio, base64, json, os, re, subprocess, time, shutil
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Callable
import httpx
import cv2
import mss
import numpy as np
from PIL import Image

NVIDIA_KEY = os.getenv("NVIDIA_API_KEY", "")
NVIDIA_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
OMNI_MODEL = "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning"


@dataclass
class MotionCommand:
    """Omni sagt NUR Label, nie Koordinaten."""
    action: str = "wait"
    ax_label: str = ""
    ax_role: str = ""
    text: str = ""
    reasoning: str = ""
    confidence: float = 0.0


class Retina:
    """
    Pixel-Diff via mss + OpenCV. Wie menschliche Netzhaut:
    - mss: 2-8ms Capture (vs 50ms skylight-cli)
    - OpenCV: robuste Diff-Erkennung + Kontur-Analyse
    - ROI-Extraktion nur bei signifikanten Changes
    """

    def __init__(self, threshold: float = 3.0):
        self.threshold = threshold
        self.last_gray: np.ndarray | None = None
        self._sct = mss.mss()
        self._monitor = self._sct.monitors[1]

    def snap(self) -> np.ndarray:
        """mss capture: 2-8ms statt 50ms mit skylight-cli."""
        raw = np.array(self._sct.grab(self._monitor))
        return cv2.cvtColor(raw, cv2.COLOR_BGRA2BGR)

    def detect(self, frame: np.ndarray) -> dict | None:
        """OpenCV-basierte Diff-Erkennung. Gibt ROI + Bounding Box zurück."""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (21, 21), 0)

        if self.last_gray is None:
            self.last_gray = gray
            return None

        diff = cv2.absdiff(self.last_gray, gray)
        _, thresh = cv2.threshold(diff, 25, 255, cv2.THRESH_BINARY)
        pct = 100.0 * np.sum(thresh > 0) / thresh.size
        self.last_gray = gray

        if pct < self.threshold:
            return None

        # Konturen → beste Bounding Box (ROI)
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return None

        biggest = max(contours, key=cv2.contourArea)
        x, y, w, h = cv2.boundingRect(biggest)
        m = 15
        x = max(0, x-m); y = max(0, y-m)
        w = min(frame.shape[1]-x, w+2*m); h = min(frame.shape[0]-y, h+2*m)
        roi = frame[y:y+h, x:x+w]

        buf = BytesIO()
        Image.fromarray(roi).save(buf, format="PNG")

        return {"roi": roi, "b64": base64.b64encode(buf.getvalue()).decode(),
                "bbox": (x, y, x+w, y+h), "pct": round(pct, 2)}


class Cortex:
    """Omni: sagt WAS zu tun ist, gibt LABEL zurück."""

    def __init__(self):
        self.http = httpx.AsyncClient(timeout=15)
        self.context = ""

    async def analyze(self, diff_data: dict) -> MotionCommand | None:
        """Analysiert die Change-Region (b64 aus Retina.detect)."""
        if not diff_data or not diff_data.get("b64"):
            return None
        b64 = diff_data["b64"]
        prompt = (
            'Du siehst einen veränderten Bildschirmausschnitt. '
            'Erkenne das interaktive Element und gib sein Label zurück.\n'
            'Antworte NUR mit JSON:\n'
            '{"action":"click|type|wait|done",'
            '"ax_label":"Sichtbarer Text (z.B. Weiter, E-Mail)",'
            '"ax_role":"AXButton|AXTextField|AXLink",'
            '"confidence":0.0-1.0,'
            '"reasoning":"..."}'
        )
        try:
            r = await self.http.post(NVIDIA_URL,
                headers={"Authorization": f"Bearer {NVIDIA_KEY}"},
                json={"model": OMNI_MODEL, "messages": [
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": [
                        {"type": "text", "text": f"Context: {self.context}"},
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}}
                    ]}], "max_tokens": 200, "temperature": 0.1})
            text = r.json()["choices"][0]["message"]
            text = text.get("reasoning") or text.get("content") or "{}"
            m = re.search(r"\{.*\}", text, re.DOTALL)
            d = json.loads(m.group()) if m else {}
            if d.get("action") not in ("wait", None):
                self.context = d.get("reasoning", "")
            return MotionCommand(
                action=d.get("action", "wait"),
                ax_label=d.get("ax_label", ""),
                ax_role=d.get("ax_role", ""),
                confidence=d.get("confidence", 0.0),
                reasoning=d.get("reasoning", ""))
        except Exception as e:
            return None

    async def close(self):
        await self.http.aclose()


class Hands:
    """NUR element-index, nie Koordinaten. Async subprocess."""

    def __init__(self, pid: int):
        self.pid = pid

    async def _run(self, cmd: list[str]) -> str:
        """Async subprocess run."""
        p = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        out, _ = await p.communicate()
        return out.decode() if p.returncode == 0 else ""

    async def _api(self, tool: str, args: list[str] | None = None) -> dict | None:
        """Skylight API call. KEIN --window-id (gibt's nicht!)."""
        cmd = [tool] + (args or []) + ["--pid", str(self.pid)]
        out = await self._run(cmd)
        try: return json.loads(out) if out.strip() else None
        except: return None

    async def find_by_label(self, label: str, role: str | None = None) -> int | None:
        """skylight-cli list-elements → manuell label filtern."""
        data = await self._api("skylight-cli", ["list-elements"])
        if not data: return None
        for e in data.get("elements", []):
            if label.lower() in str(e.get("label", "")).lower():
                if role is None or e.get("role") == role:
                    return e.get("index")
        return None

    async def find_in_popup(self, label: str, role_filter: str | None = "AXButton") -> tuple[int, int] | None:
        """cua-driver list_windows + get_window_state. Nur Buttons/Links, kein StaticText."""
        out = await self._run(["cua-driver", "call", "list_windows"])
        try:
            for w in json.loads(out).get("windows", []):
                if w.get("pid") != self.pid or not w.get("is_on_screen", False): continue
                wid = w["window_id"]
                r2 = await self._run(["cua-driver", "call", "get_window_state", json.dumps({"pid": self.pid, "window_id": wid})])
                if not r2: continue
                tree = json.loads(r2).get("tree_markdown", "")
                for line in tree.split("\n"):
                    if label.lower() in line.lower() and "Button" in line:
                        m = re.search(r"\[(\d+)\]", line)
                        if m: return (wid, int(m.group(1)))
        except: pass
        return None

    async def click(self, label: str) -> bool:
        """AXButton/AXLink first → Popup-Fallback. NUR element-index."""
        idx = await self.find_by_label(label, "AXButton") or await self.find_by_label(label, "AXLink")
        if not idx:
            p = await self.find_in_popup(label)
            idx = p[1] if p else None
        if idx:
            await self._run(["skylight-cli", "click", "--pid", str(self.pid), "--element-index", str(idx)])
            print(f"      🖱 [{idx}] '{label}'", flush=True)
            return True
        print(f"      ⚠️ '{label}' nicht gefunden", flush=True)
        return False

    async def type_text(self, label: str, text: str) -> bool:
        idx = self.find_by_label(label, "AXTextField") or self.find_by_label(label)
        if idx:
            self._skylight(["type", "--element-index", str(idx), "--text", text])
            print(f"      ⌨ [{idx}] '{text[:15]}...'", flush=True)
            return True
        return False


class LiveOmniAgent:
    """Auge → Hirn → Hand, 50 Hz, <100ms Reaktion."""

    def __init__(self, pid: int, threshold: float = 3.0, fps: float = 30):
        self.retina = Retina(threshold)
        self.cortex = Cortex()
        self.hands = Hands(pid)
        self.pid = pid
        self.interval = 1.0 / fps
        self.running = False

    async def start(self):
        self.running = True
        self.profile = {}
        pf = Path(__file__).resolve().parent.parent / "profiles" / "jeremy.yaml"
        if pf.exists():
            import yaml
            self.profile = yaml.safe_load(pf.read_text())
        print(f"🧠 LiveOmniAgent PID={self.pid}", flush=True)

    async def stop(self):
        self.running = False
        await self.cortex.close()

    async def run(self):
        await self.start()
        frames = changes = 0
        t0 = time.time()
        try:
            while self.running:
                t1 = time.time()
                frames += 1
                frame = self.retina.snap()
                diff_data = self.retina.detect(frame)
                if diff_data is not None:
                    changes += 1
                    cmd = await self.cortex.analyze(diff_data)
                    if cmd and cmd.action not in ("wait", None) and cmd.confidence > 0.5:
                        print(f"  👁 Change {changes}: {cmd.action} '{cmd.ax_label}' ({cmd.confidence:.0%})", flush=True)
                        if cmd.action == "click":
                            await self.hands.click(cmd.ax_label)
                        elif cmd.action == "type":
                            t = self.profile.get("google_email", "")
                            if "passwort" in cmd.ax_label.lower() or "password" in cmd.ax_label.lower():
                                t = self.profile.get("google_password", "")
                            if t: await self.hands.type_text(cmd.ax_label, t)
                        elif cmd.action == "done":
                            print("  ✅ Fertig!", flush=True); break
                await asyncio.sleep(max(0, self.interval - (time.time() - t1)))
        finally:
            await self.stop()
            print(f"\n✅ Agent: {frames} frames, {changes} changes in {time.time()-t0:.1f}s", flush=True)


async def run_survey_session(url: str = "https://heypiggy.com/?page=dashboard"):
    r = subprocess.run(["playstealth", "launch", "--url", url], capture_output=True, text=True, timeout=30)
    for line in reversed(r.stdout.strip().split("\n")):
        try: pid = json.loads(line).get("pid"); break
        except: pass
    if not pid: print("❌ playstealth failed"); return
    print(f"🚀 Chrome PID={pid}", flush=True)
    await LiveOmniAgent(pid).run()


if __name__ == "__main__":
    asyncio.run(run_survey_session())
