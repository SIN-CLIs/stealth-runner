#!/usr/bin/env python3
"""
Live Omni Agent – Wie menschliches Auge.
Pixel-Diff → nur veränderte Pixel → Omni → sofortige Aktion.
KEIN Accessibility-Tree. KEIN 250ms Polling. Nur Changes.
"""
from __future__ import annotations
import asyncio, base64, json, os, subprocess, time, re, struct
from pathlib import Path
from typing import Any
import httpx
import numpy as np
from PIL import Image
from io import BytesIO

NVIDIA_KEY = os.getenv("NVIDIA_API_KEY", "")
NVIDIA_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
OMNI_MODEL = "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning"


class Retina:
    """Pixel-Diff Retina: Nur Veränderungen erkennen – wie menschliches Auge."""

    def __init__(self, pid: int):
        self.pid = pid
        self.last_frame: np.ndarray | None = None
        self.frame_count = 0

    def capture(self) -> np.ndarray:
        """cua-driver screenshot → numpy array."""
        r = subprocess.run(["cua-driver", "call", "screenshot", json.dumps({"pid": self.pid}),
                           "--compact", "--no-daemon"],
                          capture_output=True, text=True, timeout=15)
        # screenshot gibt Base64 zurück
        try:
            data = json.loads(r.stdout)
            img_b64 = data.get("screenshot_base64", "")
            if not img_b64:
                # Oder aus Datei lesen
                return self.frame_from_file()
            raw = base64.b64decode(img_b64)
            img = Image.open(BytesIO(raw))
            return np.array(img)
        except:
            return self.frame_from_file()

    def frame_from_file(self) -> np.ndarray:
        """Fallback: cua-driver screenshot --raw gibt PNG-Daten auf stdout."""
        r = subprocess.run(["cua-driver", "call", "screenshot", json.dumps({"pid": self.pid}), "--raw"],
                          capture_output=True, timeout=15)
        img = Image.open(BytesIO(r.stdout))
        return np.array(img)

    def diff(self, frame: np.ndarray) -> dict | None:
        """Vergleicht Frame mit letztem → nur Veränderung zurück."""
        self.frame_count += 1
        if self.last_frame is None:
            self.last_frame = frame
            return None  # Erster Frame = Baseline

        if frame.shape != self.last_frame.shape:
            self.last_frame = frame
            return None

        # Pixel-Diff berechnen
        diff = np.abs(frame.astype(np.int16) - self.last_frame.astype(np.int16))
        changed_mask = np.max(diff, axis=2) > 15  # Schwellwert 15/255

        if not np.any(changed_mask):
            self.last_frame = frame
            return {"changed": False, "pixels_changed": 0, "pct": 0.0}

        # Veränderte Region finden (Bounding Box)
        rows = np.any(changed_mask, axis=1)
        cols = np.any(changed_mask, axis=0)
        y_min, y_max = np.where(rows)[0][[0, -1]]
        x_min, x_max = np.where(cols)[0][[0, -1]]

        changed_region = frame[y_min:y_max + 1, x_min:x_max + 1]
        changed_pct = 100.0 * np.sum(changed_mask) / changed_mask.size

        self.last_frame = frame

        return {
            "changed": True,
            "pixels_changed": int(np.sum(changed_mask)),
            "pct": round(changed_pct, 2),
            "bbox": (int(x_min), int(y_min), int(x_max), int(y_max)),
            "region": changed_region,
            "region_b64": self._region_to_b64(changed_region),
        }

    def _region_to_b64(self, region: np.ndarray) -> str:
        img = Image.fromarray(region)
        buf = BytesIO()
        img.save(buf, format="PNG")
        return base64.b64encode(buf.getvalue()).decode()

    def full_frame_b64(self, frame: np.ndarray) -> str:
        img = Image.fromarray(frame)
        buf = BytesIO()
        img.save(buf, format="PNG")
        return base64.b64encode(buf.getvalue()).decode()


class VisualCortex:
    """Omni + UGround: Analysiert nur veränderte Regionen."""

    def __init__(self):
        self.context = "starting"

    def analyze_change(self, diff_data: dict, full_b64: str) -> dict:
        """Omni analysiert die Veränderung und sagt was zu tun ist."""
        if not diff_data or not diff_data.get("changed"):
            return {"action": "wait"}

        region_b64 = diff_data.get("region_b64", full_b64)
        bbox = diff_data.get("bbox", (0, 0, 0, 0))
        pct = diff_data.get("pct", 0)

        if pct < 0.1:
            return {"action": "wait"}

        prompt = f"""You are a browser automation agent. You see a SCREEN REGION that JUST CHANGED ({(pct)}% of screen).

Context: {self.context}

This changed region is at position [{bbox[0]},{bbox[1]} to {bbox[2]},{bbox[3]}].

What happened? What button appeared? What action is needed?
Output ONLY valid JSON:
{{"event":"popup_appeared|button_appeared|page_changed|text_changed|loading",
  "action":"click|type|scroll|wait|done",
  "element_label":"...",
  "reasoning":"..."}}"""

        try:
            r = httpx.post(NVIDIA_URL, headers={"Authorization": f"Bearer {NVIDIA_KEY}"},
                          json={"model": OMNI_MODEL, "messages": [{"role": "user", "content": [
                              {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{region_b64}"}},
                              {"type": "text", "text": prompt}]}],
                                "max_tokens": 200, "temperature": 0.1}, timeout=15)
            msg = r.json()["choices"][0]["message"]
            text = msg.get("reasoning") or msg.get("content") or "{}"
            m = re.search(r"\{.*\}", text, re.DOTALL)
            result = json.loads(m.group()) if m else {"action": "wait"}
            if result.get("action") != "wait":
                self.context = result.get("reasoning", str(result)[:100])
            return result
        except Exception as e:
            return {"action": "wait", "reasoning": str(e)}


class Hands:
    """Führt Aktionen aus basierend auf Omni-Entscheidungen."""

    def __init__(self, pid: int):
        self.pid = pid

    def click(self, x: int, y: int) -> None:
        """cua-driver click per Koordinate (VISION-gesteuert, nicht geraten!)."""
        subprocess.run(["cua-driver", "call", "click", json.dumps({"pid": self.pid, "x": x, "y": y})],
                      capture_output=True, timeout=10)

    def click_index(self, window_id: int, index: int) -> None:
        """cua-driver click per element-index (Popup-sicher)."""
        subprocess.run(["cua-driver", "call", "click", json.dumps({"pid": self.pid, "window_id": window_id, "element_index": index})],
                      capture_output=True, timeout=10)

    def type_text(self, text: str, window_id: int = 0, index: int = 0) -> None:
        """cua-driver set_value für Texteingabe."""
        args = {"pid": self.pid, "window_id": window_id, "element_index": index, "value": text}
        subprocess.run(["cua-driver", "call", "set_value", json.dumps(args)],
                      capture_output=True, timeout=10)


class LiveOmniAgent:
    """Der komplette Live-Agent: Auge → Hirn → Hand in Echtzeit."""

    def __init__(self, pid: int, fps: float = 30):
        self.retina = Retina(pid)
        self.cortex = VisualCortex()
        self.hands = Hands(pid)
        self.fps = fps
        self.running = False
        self.frame_interval = 1.0 / fps

    async def run(self):
        """Live-Loop: Nur Änderungen verarbeiten, sonst nichts tun."""
        self.running = True
        print(f"🧠 LIVE OMIN AGENT: PID={self.pid}, {self.fps} FPS\n", flush=True)
        start = time.time()
        frames = 0
        changes = 0

        while self.running:
            loop_start = time.time()

            # 1. RETINA: Frame erfassen + diff berechnen
            frame = self.retina.capture()
            diff_data = self.retina.diff(frame)
            frames += 1

            if diff_data and diff_data.get("changed"):
                changes += 1
                pct = diff_data["pct"]
                bbox = diff_data["bbox"]

                # 2. CORTEX: Nur Veränderung analysieren
                full_b64 = self.retina.full_frame_b64(frame)
                decision = self.cortex.analyze_change(diff_data, full_b64)
                action = decision.get("action", "wait")

                if action != "wait":
                    print(f"  👁 Change {changes}: {pct}% bei {bbox} → {action}", flush=True)

                    # 3. HANDS: Aktion sofort ausführen
                    if action == "click":
                        # Versuche Element-Index aus get_window_state
                        try:
                            r = subprocess.run(["cua-driver", "call", "get_window_state",
                                               json.dumps({"pid": self.pid})],
                                              capture_output=True, text=True, timeout=10)
                            # Finde "Weiter" Button im aktuellen Fenster
                            tree = json.loads(r.stdout).get("tree_markdown", "")
                            for line in tree.split("\n"):
                                if "Button" in line and "Weiter" in line:
                                    import re
                                    m = re.search(r"\[(\d+)\]", line)
                                    if m:
                                        self.hands.click_index(0, int(m.group(1)))
                                        break
                        except:
                            pass
                    elif action == "done":
                        print(f"  ✅ Fertig!", flush=True)
                        break

            # Framerate einhalten
            elapsed = time.time() - loop_start
            remaining = self.frame_interval - elapsed
            if remaining > 0:
                await asyncio.sleep(remaining)

        duration = time.time() - start
        print(f"\n✅ Agent beendet: {frames} Frames, {changes} Changes in {duration:.1f}s", flush=True)


if __name__ == "__main__":
    import sys
    pid = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    if not pid:
        print("Usage: python live_agent.py <PID>")
        sys.exit(1)
    asyncio.run(LiveOmniAgent(pid).run())
