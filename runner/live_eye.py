#!/usr/bin/env python3
"""
LiveOmniEye – REGELMÄSSIG Omni-Analyse, nicht nur bei pixel-diff.
Wie ein Mensch: schaut alle paar Sekunden auf den Bildschirm.
"""
from __future__ import annotations
import asyncio, base64, json, os, re, subprocess, time
from io import BytesIO
from pathlib import Path
import cv2, httpx, mss, numpy as np
from PIL import Image

NVIDIA_KEY = os.getenv("NVIDIA_API_KEY", "")
NVIDIA_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
OMNI_MODEL = "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning"


class LiveOmniEye:
    """Alle 5s: Screenshot → Omni → Aktion. Plus pixel-diff für schnelle Changes."""

    def __init__(self, pid: int):
        self.pid = pid
        self.sct = mss.mss()
        self.mon = self.sct.monitors[1]
        self.last_gray = None
        self.http = httpx.Client(timeout=15)
        self.context = ""

    def snap(self) -> np.ndarray:
        raw = np.array(self.sct.grab(self.mon))
        return cv2.cvtColor(raw, cv2.COLOR_BGRA2BGR)

    def to_b64(self, img: np.ndarray) -> str:
        buf = BytesIO()
        Image.fromarray(img).save(buf, format="PNG")
        return base64.b64encode(buf.getvalue()).decode()

    def has_change(self, frame: np.ndarray) -> bool:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (21, 21), 0)
        if self.last_gray is None:
            self.last_gray = gray
            return True
        diff = cv2.absdiff(self.last_gray, gray)
        _, thresh = cv2.threshold(diff, 25, 255, cv2.THRESH_BINARY)
        pct = 100.0 * np.sum(thresh > 0) / thresh.size
        self.last_gray = gray
        return pct > 1.0

    def ask_omni(self, img: np.ndarray) -> dict:
        """Schnellster Pfad: runterskaliertes Bild + 1 Wort Antwort + greedy."""
        try:
            # Bild runterskalieren von 1920x1080 auf ~640x360 (Faktor 3) 
            h, w = img.shape[:2]
            scale = 360 / h
            small = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
            buf = BytesIO()
            Image.fromarray(small).save(buf, format="PNG")
            b64 = base64.b64encode(buf.getvalue()).decode()

            r = self.http.post(NVIDIA_URL, headers={"Authorization": f"Bearer {NVIDIA_KEY}"},
                json={"model": OMNI_MODEL, "messages": [{"role": "user", "content": [
                    {"type": "text", "text": "1 word: heypiggy | google_popup | dashboard"},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}}]}],
                    "max_tokens": 5, "temperature": 0.0}, timeout=10)
            msg = r.json()["choices"][0]["message"]
            text = (msg.get("reasoning") or msg.get("content") or "").lower()
            page = "heypiggy" if "heypiggy" in text else "google_popup" if "google" in text else "dashboard" if "dashboard" in text else "unknown"
            return {"page": page, "action": "wait" if page in ("heypiggy", "dashboard") else "click",
                    "element_label": "Weiter" if page == "google_popup" else ""}
        except:
            return {"page": "unknown", "action": "wait", "element_label": ""}

    def click_label(self, label: str) -> bool:
        """skylight-cli: find AXButton by label → click."""
        r = subprocess.run(["skylight-cli", "list-elements", "--pid", str(self.pid)],
                          capture_output=True, text=True, timeout=10)
        try:
            for e in json.loads(r.stdout).get("elements", []):
                if label.lower() in str(e.get("label", "")).lower() and e.get("role") in ("AXButton", "AXLink"):
                    idx = e["index"]
                    subprocess.run(["skylight-cli", "click", "--pid", str(self.pid), "--element-index", str(idx)],
                                  capture_output=True, timeout=10)
                    print(f"      🖱 [{idx}] '{label}'", flush=True)
                    return True
        except: pass
        print(f"      ⚠️ '{label}' nicht gefunden", flush=True)
        return False

    def run(self, cycles: int = 20):
        for i in range(cycles):
            frame = self.snap()
            changed = self.has_change(frame)

            if changed or i % 3 == 0:
                decision = self.ask_omni(frame)
                action = decision.get("action", "wait")
                label = decision.get("element_label", "")

                print(f"  👁 [{i}] {decision.get('page','?')} popup={decision.get('popup')} → {action} '{label}'", flush=True)

                if action == "click" and label:
                    self.click_label(label)
                elif action == "done":
                    print("  ✅ Fertig!", flush=True)
                    break
                elif action == "wait":
                    pass

            time.sleep(2)


if __name__ == "__main__":
    import sys
    pid = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    if not pid:
        # playstealth launch
        r = subprocess.run(["playstealth", "launch", "--url", "https://heypiggy.com/?page=dashboard"],
                          capture_output=True, text=True, timeout=30)
        for line in reversed(r.stdout.strip().split("\n")):
            try: pid = json.loads(line).get("pid"); break
            except: pass
        print(f"PID={pid}")
        subprocess.run(["bash", "cli/heypiggy-login", str(pid)], timeout=60)
    LiveOmniEye(pid).run()
