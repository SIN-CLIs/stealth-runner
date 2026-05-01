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
    """Pixel-Diff: nur veränderte Pixel erkennen, 95% Reduktion."""

    def __init__(self, threshold: float = 3.0):
        self.threshold = threshold
        self.last_frame: np.ndarray | None = None
        self._last_bounds = (0, 0, 0, 0)

    def detect(self, current: np.ndarray) -> np.ndarray | None:
        if self.last_frame is None:
            self.last_frame = current.copy()
            return current
        diff = np.abs(current.astype(np.int16) - self.last_frame.astype(np.int16))
        mask = np.max(diff, axis=2) > 25
        ratio = 100.0 * np.sum(mask) / mask.size
        if ratio >= self.threshold:
            self.last_frame = current.copy()
            return self._extract_roi(current, mask)
        return None

    def _extract_roi(self, frame: np.ndarray, mask: np.ndarray) -> np.ndarray:
        coords = np.argwhere(mask)
        y0, x0 = coords.min(axis=0)
        y1, x1 = coords.max(axis=0)
        m = 15
        y0 = max(0, y0-m); x0 = max(0, x0-m)
        y1 = min(frame.shape[0], y1+m); x1 = min(frame.shape[1], x1+m)
        self._last_bounds = (x0, y0, x1, y1)
        return frame[y0:y1, x0:x1]

    @staticmethod
    def to_png(arr: np.ndarray) -> bytes:
        buf = BytesIO(); Image.fromarray(arr).save(buf, format="PNG")
        return buf.getvalue()


class Cortex:
    """Omni: sagt WAS zu tun ist, gibt LABEL zurück."""

    def __init__(self):
        self.http = httpx.AsyncClient(timeout=15)
        self.context = ""

    async def analyze(self, roi: bytes) -> MotionCommand | None:
        b64 = base64.b64encode(roi).decode()
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

    async def find_in_popup(self, label: str) -> tuple[int, int] | None:
        """cua-driver list_windows + get_window_state → Popup-Element finden."""
        out = await self._run(["cua-driver", "call", "list_windows"])
        try:
            for w in json.loads(out).get("windows", []):
                if w.get("pid") != self.pid or not w.get("is_on_screen", False): continue
                wid = w["window_id"]
                r2 = await self._run(["cua-driver", "call", "get_window_state", json.dumps({"pid": self.pid, "window_id": wid})])
                if not r2: continue
                tree = json.loads(r2).get("tree_markdown", "")
                for line in tree.split("\n"):
                    if label.lower() in line.lower():
                        m = re.search(r"\[(\d+)\]", line)
                        if m: return (wid, int(m.group(1)))
        except: pass
        return None

    async def click(self, label: str) -> bool:
        """Popup-first → Fallback. NUR element-index."""
        p = await self.find_in_popup(label)
        idx = p[1] if p else await self.find_by_label(label, "AXButton") or await self.find_by_label(label, "AXLink")
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

    async def _screenshot(self) -> np.ndarray | None:
        """Async screenshot mit --output Bug Workaround."""
        cwd = Path("skylight_screenshot.png")
        if cwd.exists(): cwd.unlink()
        await self.hands._run(["skylight-cli", "screenshot", "--pid", str(self.pid), "--mode", "som", "--output", "/tmp/live_frame.png"])
        if cwd.exists():
            shutil.copy2(str(cwd), "/tmp/live_frame.png")
            cwd.unlink()
        try:
            return np.array(Image.open("/tmp/live_frame.png"))
        except: return None

    async def run(self):
        await self.start()
        frames = changes = 0
        t0 = time.time()
        try:
            while self.running:
                t1 = time.time()
                frame = await self._screenshot()
                if frame is None:
                    await asyncio.sleep(self.interval)
                    continue
                frames += 1
                roi = self.retina.detect(frame)
                if roi is not None:
                    changes += 1
                    cmd = await self.cortex.analyze(Retina.to_png(roi))
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
