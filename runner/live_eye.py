#!/usr/bin/env python3
"""
LiveEye v5 – MEMORY-RINGPUFFER + video_url an Omni.
KEINE Disk-Writes. PyAV captured + encodiert in Echtzeit.
"""
from __future__ import annotations
import asyncio, base64, collections, json, os, re, time
from io import BytesIO
import av, cv2, httpx, mss, numpy as np
from PIL import Image

KEY = os.getenv("NVIDIA_API_KEY", "")
URL = "https://integrate.api.nvidia.com/v1/chat/completions"
MODEL = "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning"

# gRPC (fuer eigene NIM-Deployments)
# Public Nemotron Omni: REST only (502 bei gRPC)
# Eigener NIM + function-id = gRPC Bidirectional Streaming
GRPC_HOST = "grpc.nvcf.nvidia.com:443"
GRPC_FUNCTION_ID = "c4ed50ff-b5c3-409d-ab57-b79c33f5bb39"
HAS_GRPC = False
FPS = 5
BUFFER_SECS = 4
MAX_FRAMES = FPS * BUFFER_SECS  # 20 Frames


class RingBuffer:
    """Memory-Ringpuffer: Letzte N Frames im RAM, kein Disk I/O."""
    
    def __init__(self, maxlen: int = MAX_FRAMES):
        self.frames: collections.deque[bytes] = collections.deque(maxlen=maxlen)
        self.sct = mss.mss()
        self.mon = self.sct.monitors[1]

    def snap(self) -> np.ndarray:
        """mss capture → numpy (3ms)."""
        raw = np.array(self.sct.grab(self.mon))
        return cv2.cvtColor(raw, cv2.COLOR_BGRA2BGR)

    def add_frame(self, frame: np.ndarray | None = None):
        """Frame als PNG in den Ringpuffer (kein Disk I/O)."""
        if frame is None:
            frame = self.snap()
        buf = BytesIO()
        Image.fromarray(frame).save(buf, format="PNG")
        self.frames.append(buf.getvalue())

    def encode_video(self) -> bytes | None:
        """Ringpuffer → mp4 im Speicher. Nur die letzten N Sekunden."""
        if len(self.frames) < 5:
            return None
        try:
            output = BytesIO()
            output.name = "clip.mp4"
            container = av.open(output, mode="w", format="mp4")
            stream = container.add_stream("libx264", rate=min(FPS, len(self.frames)), options={"preset":"ultrafast","crf":"35"})
            stream.width = 960
            stream.height = 540
            stream.pix_fmt = "yuv420p"

            for png_bytes in list(self.frames)[-MAX_FRAMES:]:
                img = Image.open(BytesIO(png_bytes)).resize((960, 540))
                frame = av.VideoFrame.from_image(img)
                for packet in stream.encode(frame):
                    container.mux(packet)
            for packet in stream.encode():
                container.mux(packet)
            container.close()
            return output.getvalue()
        except Exception as e:
            print(f"  ⚠️ Encode: {e}", flush=True)
            return None


class LiveEye:
    """Live-Video-Auge: Ringbuffer → Omni → Aktion."""

    def __init__(self, pid: int):
        self.pid = pid
        self.buf = RingBuffer()
        self.http = httpx.AsyncClient(timeout=30)

    async def analyze(self) -> dict | None:
        """Video-Clip aus Ringbuffer → Omni → Entscheidung."""
        mp4 = self.buf.encode_video()
        if not mp4:
            return None
        
        b64 = base64.b64encode(mp4).decode()
        prompt = ("Watch this screen recording. What happened? Describe ALL windows. "
                  "Is there a Google sign-in popup? What action next and in which window?")

        r = await self.http.post(URL, headers={"Authorization": f"Bearer {KEY}"},
            json={"model": MODEL, "messages": [{"role": "user", "content": [
                {"type": "video_url", "video_url": {"url": f"data:video/mp4;base64,{b64}"}},
                {"type": "text", "text": prompt}]}],
                  "max_tokens": 500, "temperature": 0.0,
                  "extra_body": {"media_io_kwargs": {"video": {"fps": 1, "num_frames": -1}}}},
            timeout=30)
        msg = r.json()["choices"][0]["message"]
        text = msg.get("reasoning") or msg.get("content") or ""
        return {"raw": text[:2000], "len": len(mp4)}

    async def run(self, steps: int = 10):
        """Live-Loop: capture → buffer → Omni → analyze → repeat."""
        # Ringbuffer füllen
        for _ in range(MAX_FRAMES):
            self.buf.add_frame()
            await asyncio.sleep(1.0 / FPS)

        for i in range(steps):
            # Neue Frames
            for _ in range(FPS * 2):  # 2s neue Frames
                self.buf.add_frame()
                await asyncio.sleep(1.0 / FPS)

            t0 = time.time()
            result = await self.analyze()
            t = time.time() - t0
            if result:
                print(f"[{i}] {t:.1f}s ({result['len']//1024}KB): {result['raw'][:200]}", flush=True)
            else:
                print(f"[{i}] Buffer zu kurz", flush=True)
        await self.http.aclose()


if __name__ == "__main__":
    import subprocess, sys
    p = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    if not p:
        r = subprocess.run(["playstealth","launch","--url","https://heypiggy.com/?page=dashboard"],
                          capture_output=True, text=True, timeout=30)
        for l in reversed(r.stdout.strip().split("\n")):
            try: p = json.loads(l).get("pid"); break
            except: pass
        print(f"PID={p}")
    asyncio.run(LiveEye(p).run())
