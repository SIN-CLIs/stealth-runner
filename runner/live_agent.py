#!/usr/bin/env python3
"""
LiveOmniAgent – Menschliches Auge für den stealth-runner.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RETINA (pixel-diff) → NUR Veränderungen erkennen
CORTEX (Omni) → sagt WAS (Label), nicht WO (Pixel)
HANDS (skylight-cli + cua-driver) → findet element_index + clickt
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
KEINE Pixel-Koordinaten für Aktionen! Nur AX-element-index.
"""
from __future__ import annotations
import asyncio, base64, json, os, re, subprocess, time
from io import BytesIO
from typing import Any, Callable
import httpx
import numpy as np
from PIL import Image

NVIDIA_KEY = os.getenv("NVIDIA_API_KEY", "")
NVIDIA_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
OMNI_MODEL = "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning"


class Retina:
    """Pixel-Diff ≙ Menschliche Netzhaut – nur SIGNALE (Änderungen) senden."""

    def __init__(self, pid: int, threshold: float = 3.0):
        self.pid = pid
        self.threshold = threshold
        self.last_frame: np.ndarray | None = None
        self.frame_count = 0

    def snap(self) -> np.ndarray:
        """cua-driver screenshot → numpy array."""
        r = subprocess.run(["cua-driver", "call", "screenshot", json.dumps({"pid": self.pid}),
                           "--compact", "--no-daemon"], capture_output=True, text=True, timeout=15)
        try:
            d = json.loads(r.stdout)
            b64 = d.get("screenshot_base64", "")
            if b64: return np.array(Image.open(BytesIO(base64.b64decode(b64))))
        except: pass
        # Fallback: RAW PNG auf stdout
        r = subprocess.run(["cua-driver", "call", "screenshot", json.dumps({"pid": self.pid}), "--raw"],
                          capture_output=True, timeout=15)
        return np.array(Image.open(BytesIO(r.stdout)))

    def diff(self, frame: np.ndarray) -> dict | None:
        """Vergleich: nur veränderte Pixel → 95% Datenreduktion."""
        self.frame_count += 1
        if self.last_frame is None:
            self.last_frame = frame
            return None
        if frame.shape != self.last_frame.shape:
            self.last_frame = frame; return None

        diff = np.abs(frame.astype(np.int16) - self.last_frame.astype(np.int16))
        mask = np.max(diff, axis=2) > 20
        self.last_frame = frame

        if not np.any(mask):
            return {"changed": False, "pct": 0.0}

        rows, cols = np.where(mask)
        y0, y1 = int(rows.min()), int(rows.max())
        x0, x1 = int(cols.min()), int(cols.max())
        pct = round(100.0 * float(np.sum(mask)) / float(mask.size), 2)
        m = 8
        region = frame[max(0,y0-m):min(frame.shape[0],y1+m), max(0,x0-m):min(frame.shape[1],x1+m)]

        return {"changed": True, "pct": pct, "bbox": (x0, y0, x1, y1),
                "region": region, "b64": self._to_b64(region)}

    def _to_b64(self, arr: np.ndarray) -> str:
        buf = BytesIO(); Image.fromarray(arr).save(buf, format="PNG")
        return base64.b64encode(buf.getvalue()).decode()

    def full_b64(self, frame: np.ndarray) -> str:
        buf = BytesIO(); Image.fromarray(frame).save(buf, format="PNG")
        return base64.b64encode(buf.getvalue()).decode()


class Cortex:
    """Omni ≙ Sehrinde – analysiert NUR Veränderungen, sagt WAS zu tun ist."""

    def __init__(self):
        self.context = ""
        self.http = httpx.Client(timeout=15)

    def analyze(self, diff_data: dict) -> dict:
        """Nur die Change-Region an Omni schicken → Label + Action bekommen."""
        if not diff_data or not diff_data.get("changed") or diff_data["pct"] < 0.5:
            return {"action": "wait"}

        prompt = f"""You see a CHANGED screen region ({diff_data['pct']}% of screen changed).
Context: {self.context}

What UI element appeared? Give me the EXACT visible text label.
I will use Accessibility API to find and click it by LABEL.

Output ONLY JSON:
{{"action":"click|type|scroll|wait|done",
  "element_label":"exact visible text (e.g. 'Weiter', 'E-Mail', 'Umfrage starten')",
  "reasoning":"..."}}"""

        try:
            r = self.http.post(NVIDIA_URL, headers={"Authorization": f"Bearer {NVIDIA_KEY}"},
                              json={"model": OMNI_MODEL, "messages": [{"role": "user", "content": [
                                  {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{diff_data['b64']}"}},
                                  {"type": "text", "text": prompt}]}],
                                    "max_tokens": 200, "temperature": 0.1})
            text = r.json()["choices"][0]["message"]
            text = text.get("reasoning") or text.get("content") or "{}"
            m = re.search(r"\{.*\}", text, re.DOTALL)
            result = json.loads(m.group()) if m else {"action": "wait"}
            if result.get("action") != "wait":
                self.context = result.get("reasoning", str(result)[:100])
            return result
        except Exception as e:
            return {"action": "wait", "reasoning": str(e)}


class Hands:
    """Hände ≙ skylight-cli + cua-driver – NUR element-index, nie Pixel."""

    def __init__(self, pid: int):
        self.pid = pid

    def find_anywhere(self, label: str, role: str = "AXButton") -> tuple | None:
        """Findet element_index für ein Label – POPUP-FIRST, Fallback normales Fenster."""
        # 1. Popup-Fenster durchsuchen (cua-driver get_window_state)
        try:
            r = subprocess.run(["cua-driver", "call", "list_windows"], capture_output=True, text=True, timeout=10)
            windows = json.loads(r.stdout).get("windows", [])
            for w in windows:
                if w.get("pid") != self.pid or not w.get("is_on_screen", False):
                    continue
                wid = w["window_id"]
                r2 = subprocess.run(["cua-driver", "call", "get_window_state",
                                    json.dumps({"pid": self.pid, "window_id": wid})],
                                   capture_output=True, text=True, timeout=10)
                tree = json.loads(r2.stdout).get("tree_markdown", "")
                for line in tree.split("\n"):
                    if label.lower() in line.lower():
                        m = re.search(r"\[(\d+)\]", line)
                        if m: return (wid, int(m.group(1)))
        except: pass

        # 2. skylight-cli Fallback (1 Fenster)
        try:
            r = subprocess.run(["skylight-cli", "list-elements", "--pid", str(self.pid)],
                              capture_output=True, text=True, timeout=10)
            for e in json.loads(r.stdout).get("elements", []):
                if label.lower() in str(e.get("label", "")).lower():
                    return (0, e["index"])
        except: pass
        return None

    def click(self, label: str) -> bool:
        """NUR element-index über skylight-cli (kein cua-driver, kein Daemon nötig)."""
        found = self.find_anywhere(label, "AXButton")
        if not found:
            found = self.find_anywhere(label, "AXLink")
        if found:
            wid, idx = found
            subprocess.run(["skylight-cli", "click", "--pid", str(self.pid), "--element-index", str(idx)],
                          capture_output=True, timeout=10)
            print(f"      🖱 Klick [{idx}] '{label}' (popup={bool(wid)})", flush=True)
            return True
        print(f"      ⚠️ '{label}' nicht gefunden", flush=True)
        return False

    def type_text(self, label: str, text: str) -> bool:
        """Fokussiert per click, tippt per skylight-cli type."""
        found = self.find_anywhere(label, "AXTextField")
        if not found:
            found = self.find_anywhere(label, "AXTextArea")
        if found:
            wid, idx = found
            subprocess.run(["skylight-cli", "type", "--pid", str(self.pid),
                           "--element-index", str(idx), "--text", text], capture_output=True, timeout=10)
            print(f"      ⌨ Getippt [{idx}] '{text[:20]}...'", flush=True)
            return True
        return False


class LiveOmniAgent:
    """Der komplette Live-Agent: Auge → Hirn → Hand in einem Loop."""

    def __init__(self, pid: int, fps: float = 30, threshold: float = 3.0, profile_path: str = "profiles/jeremy.yaml"):
        self.retina = Retina(pid, threshold)
        self.cortex = Cortex()
        self.hands = Hands(pid)
        self.fps = fps
        self.running = False
        self.interval = 1.0 / fps

    async def start(self) -> None:
        self.running = True
        import yaml
        p = Path(__file__).resolve().parent.parent / "profiles" / "jeremy.yaml"
        if p.exists():
            self.profile = yaml.safe_load(p.read_text())
        else:
            self.profile = {}
        print(f"🧠 LiveOmniAgent PID={self.pid} {self.fps}fps threshold={self.retina.threshold}%", flush=True)

    async def stop(self) -> None:
        self.running = False

    async def run(self, callback: Callable | None = None) -> None:
        await self.start()
        frames = changes = 0
        t0 = time.time()
        try:
            while self.running:
                loop_start = time.time()

                # Auge: Frame erfassen + Diff
                frame = self.retina.snap()
                diff_data = self.retina.diff(frame)
                frames += 1

                if diff_data and diff_data.get("changed"):
                    changes += 1
                    # Hirn: Omni analysiert Change
                    decision = self.cortex.analyze(diff_data)
                    action = decision.get("action", "wait")
                    label = decision.get("element_label", "")

                    if action != "wait" and label:
                        print(f"  👁 Change {changes}: {diff_data['pct']}% → '{label}' ({action})", flush=True)

                        # Hand: Aktion via element-index (nie Pixel!)
                        if action == "click":
                            self.hands.click(label)
                        elif action == "type":
                            email = self.profile.get("google_email", "")
                            pw = self.profile.get("google_password", "")
                            t = email if "email" in label.lower() else pw
                            if t:
                                self.hands.type_text(label, t)
                        elif action == "done":
                            print(f"  ✅ Survey abgeschlossen!", flush=True)
                            break

                    if callback:
                        callback(decision)

                # 50 Hz Framerate
                elapsed = time.time() - loop_start
                remaining = self.interval - elapsed
                if remaining > 0:
                    await asyncio.sleep(remaining)

        finally:
            await self.stop()
            dur = time.time() - t0
            print(f"\n✅ Agent: {frames} frames, {changes} changes in {dur:.1f}s", flush=True)


if __name__ == "__main__":
    import sys
    pid = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    if not pid: print("Usage: python live_agent.py <PID>"); sys.exit(1)
    asyncio.run(LiveOmniAgent(pid).run())
