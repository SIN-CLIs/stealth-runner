#!/usr/bin/env python3
"""
LiveEye v7 – MEMORY-RINGPUFFER + video_url an Omni.
KEINE Disk-Writes. PyAV captured + encodiert in Echtzeit.

OPTIMIERUNGEN v6 (2026-05-01):
1. PNG → JPEG quality=50 → ~80% weniger Payload
2. SSE Streaming → tokenweise Antwort (niedrigste Latenz)
3. JSON-enforced Prompt → strukturierte Antwort statt Prosa

OPTIMIERUNGEN v7 (2026-05-01):
4. Adaptive FPS via Motion Detection → CRF 28-40
5. Frame-Differencing → identische Frames überspringen
6. Conv3D num_frames Optimierung → weniger Tokens bei low motion
7. CRF Auto-Adjustment → mehr Qualität bei Bewegung, weniger bei Stillstand

NICHT VERGESSEN: Das aktive Modell ist nvidia/nemotron-3-nano-omni-30b-a3b-reasoning
Siehe AGENTS.md für Architektur-Überblick.
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

# Motion Detection Constants
MOTION_HIGH_THRESH = 15.0   # MSE threshold for "high motion" (scrolling, page transitions)
MOTION_LOW_THRESH = 2.0     # Below this = virtually identical frames
MOTION_CRF_MAP = {
    "high": 28,   # High motion → more quality, lower CRF
    "mid":  35,   # Default
    "low":  40,   # Static → high compression, CRF 40
}
MOTION_NUM_FRAMES_MAP = {
    "high": -1,   # Auto: all frames for high motion
    "mid":  8,    # Every 2nd frame
    "low":  4,    # Every 5th frame (static screens need fewer temporal cues)
}

# Rolling motion level (last N measurements, decays when static)
_motion_level = 0.0
_motion_count = 0


class RingBuffer:
    """Memory-Ringpuffer: Letzte N Frames im RAM, kein Disk I/O.
    v7: Motion Detection + Frame-Differencing + CRF Auto-Adjustment.
    """
    
    def __init__(self, maxlen: int = MAX_FRAMES):
        self.frames: collections.deque[bytes] = collections.deque(maxlen=maxlen)
        self.sct = mss.mss()
        self.mon = self.sct.monitors[1]
        self._prev_frame: np.ndarray | None = None
        self._mse: float = 0.0
        self._motion_class: str = "low"
        self._skipped_frames: int = 0

    def snap(self) -> np.ndarray:
        """mss capture → numpy (3ms)."""
        raw = np.array(self.sct.grab(self.mon))
        return cv2.cvtColor(raw, cv2.COLOR_BGRA2BGR)

    def _detect_motion(self, frame: np.ndarray) -> float:
        """Frame-Differencing via MSE. 0 = identisch, >15 = high motion."""
        if self._prev_frame is None:
            self._prev_frame = frame
            return 0.0
        # Downscale for comparison (faster, still accurate)
        small_frame = cv2.resize(frame, (320, 180))
        small_prev = cv2.resize(self._prev_frame, (320, 180))
        diff = cv2.absdiff(small_frame, small_prev)
        mse = np.mean(diff ** 2)
        self._prev_frame = frame
        self._mse = mse
        return mse

    def _classify_motion(self, mse: float) -> str:
        """Motion Class: 'high' / 'mid' / 'low'."""
        if mse > MOTION_HIGH_THRESH:
            return "high"
        elif mse > MOTION_LOW_THRESH:
            return "mid"
        return "low"

    def add_frame(self, frame: np.ndarray | None = None):
        """Frame mit Motion-Detection + Differencing in den Ringpuffer.
        - Statische Frames (MSE < MOTION_LOW_THRESH): werden übersprungen
        - Leichte Bewegung: normal capturen
        - Hohe Bewegung: sofort capturen (page transition)
        """
        if frame is None:
            frame = self.snap()
        
        motion_mse = self._detect_motion(frame)
        motion_class = self._classify_motion(motion_mse)
        self._motion_class = motion_class
        
        # Frame-Differencing: statische Frames überspringen
        if motion_class == "low" and len(self.frames) > 0:
            self._skipped_frames += 1
            return  # kein neuer Frame nötig
        
        self._skipped_frames = 0
        buf = BytesIO()
        img = Image.fromarray(frame)
        img.convert("RGB").save(buf, format="JPEG", quality=50)
        self.frames.append(buf.getvalue())

    def get_crf(self) -> int:
        """CRF Auto-Adjustment: mehr Qualität bei Motion, weniger bei Stillstand."""
        return MOTION_CRF_MAP.get(self._motion_class, 35)

    def get_num_frames(self) -> int:
        """Conv3D Token-Optimierung: weniger Frames bei low motion = weniger Tokens."""
        return MOTION_NUM_FRAMES_MAP.get(self._motion_class, -1)

    def get_motion_stats(self) -> dict:
        return {
            "mse": round(self._mse, 1),
            "motion_class": self._motion_class,
            "skipped_frames": self._skipped_frames,
            "buffer_frames": len(self.frames),
            "crf": self.get_crf(),
            "num_frames": self.get_num_frames(),
        }

    def encode_video(self) -> bytes | None:
        """Ringpuffer → mp4 im Speicher. CRF dynamisch je nach Motion."""
        if len(self.frames) < 5:
            return None
        try:
            crf = self.get_crf()
            output = BytesIO()
            output.name = "clip.mp4"
            container = av.open(output, mode="w", format="mp4")
            stream = container.add_stream(
                "libx264", rate=min(FPS, len(self.frames)),
                options={"preset": "ultrafast", "crf": str(crf)},
            )
            stream.width = 960
            stream.height = 540
            stream.pix_fmt = "yuv420p"

            for jpeg_bytes in list(self.frames)[-MAX_FRAMES:]:
                img = Image.open(BytesIO(jpeg_bytes)).resize((960, 540))
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
        """Video-Clip aus Ringbuffer → Omni (SSE Streaming) → Entscheidung.
        
        WHY SSE Streaming: Statt auf komplette Antwort zu warten (kann 15s+ dauern),
        kommen Tokens chunk-by-chunk. Erster Token in <1s. JSON-enforced Prompt
        statt Prosa-Parsing.
        
        v7: Conv3D num_frames dynamisch je nach Motion-Level.
        """
        mp4 = self.buf.encode_video()
        if not mp4:
            return None
        
        motion = self.buf.get_motion_stats()
        num_frames = motion["num_frames"]
        
        b64 = base64.b64encode(mp4).decode()
        prompt = (
            "Watch this screen recording. Output ONLY JSON:\n"
            '{"page_type":"survey|consent|trap|dashboard|payout",'
            '"action":"click|type|scroll|wait|done",'
            '"element_index":<int>,'
            '"label":"...",'
            '"confidence":0.0-1.0,'
            '"reasoning":"..."}\n'
            "What happened? Describe ALL windows. "
            "Is there a Google sign-in popup? What action next and in which window?"
        )

        content = ""
        async with self.http.stream("POST", URL,
            headers={
                "Authorization": f"Bearer {KEY}",
                "Accept": "text/event-stream",
                "Content-Type": "application/json",
            },
            json={"model": MODEL, "messages": [{"role": "user", "content": [
                {"type": "video_url", "video_url": {"url": f"data:video/mp4;base64,{b64}"}},
                {"type": "text", "text": prompt}]}],
                  "max_tokens": 500, "temperature": 0.0, "stream": True,
                  "extra_body": {"media_io_kwargs": {"video": {"fps": 1, "num_frames": num_frames}}}},
            timeout=30,
        ) as response:
            async for line in response.aiter_lines():
                if line.startswith("data: ") and "DONE" not in line:
                    try:
                        chunk = json.loads(line[6:])
                        delta = chunk.get("choices", [{}])[0].get("delta", {})
                        tok = delta.get("content") or delta.get("reasoning") or ""
                        if tok:
                            content += tok
                    except Exception:
                        continue
        
        if not content:
            return None
        return {"raw": content[:2000], "len": len(mp4), "motion": motion}

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
                motion = result.get("motion", {})
                mse = motion.get("mse", 0)
                cls = motion.get("motion_class", "?")
                crf = motion.get("crf", 35)
                nf = motion.get("num_frames", -1)
                skip = motion.get("skipped_frames", 0)
                kb = result['len'] // 1024
                print(f"[{i}] {t:.1f}s ({kb}KB) MSE={mse} class={cls} CRF={crf} nf={nf} skip={skip}: {result['raw'][:120]}", flush=True)
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
