#!/usr/bin/env python3
"""LiveEye v4 – PERMANENTER ffmpeg-Ringpuffer → video_url an Omni."""
from __future__ import annotations
import base64, json, os, subprocess, time
from pathlib import Path
import httpx

KEY = os.getenv("NVIDIA_API_KEY","")
URL = "https://integrate.api.nvidia.com/v1/chat/completions"
MODEL = "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning"
VIDEO = "/tmp/live_eye.mp4"
CLIP = "/tmp/live_eye_clip.mp4"


def main(pid: int):
    # ffmpeg permanent starten
    for f in [VIDEO, CLIP]:
        if Path(f).exists(): Path(f).unlink()
    
    # Bildschirm-Index finden
    r = subprocess.run(["ffmpeg","-f","avfoundation","-list_devices","true","-i",""],
                      capture_output=True, text=True, timeout=5)
    idx = "1"
    for line in r.stderr.split("\n"):
        if "Capture screen" in line:
            idx = line.split()[0].strip("[]")
            break
    print(f"Screen index: {idx}", flush=True)

    proc = subprocess.Popen(
        ["ffmpeg","-f","avfoundation","-capture_cursor","1","-r","5",
         "-video_size","1920x1080","-i",idx,
         "-c:v","libx264","-preset","ultrafast","-crf","30","-y",VIDEO],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(3)
    print("🔴 Recording aktiv", flush=True)

    try:
        for i in range(20):
            time.sleep(5)
            if not Path(VIDEO).exists() or Path(VIDEO).stat().st_size < 100000:
                print(f"[{i}] Video zu kurz...", flush=True)
                continue

            # Letzte 4s extrahieren
            if Path(CLIP).exists(): Path(CLIP).unlink()
            subprocess.run(["ffmpeg","-sseof","-4","-i",VIDEO,"-c","copy","-y",CLIP],
                          capture_output=True, timeout=10)
            if not Path(CLIP).exists() or Path(CLIP).stat().st_size < 1000:
                continue

            clip = base64.b64encode(Path(CLIP).read_bytes()).decode()
            print(f"[{i}] Clip: {len(clip)//1024}KB an Omni...", flush=True)

            r = httpx.post(URL, headers={"Authorization":f"Bearer {KEY}"},
                json={"model":MODEL, "messages":[{"role":"user","content":[
                    {"type":"video_url","video_url":{"url":f"data:video/mp4;base64,{clip}"}},
                    {"type":"text","text":"Watch this screen recording. What happened? What action next and WHERE?"}]}],
                      "max_tokens":500,"temperature":0.0,
                      "extra_body":{"media_io_kwargs":{"video":{"fps":1,"num_frames":-1}}}},
                timeout=30)
            msg = r.json()["choices"][0]["message"]
            text = msg.get("reasoning") or msg.get("content") or ""
            print(f"  → {text[:500]}", flush=True)
    finally:
        proc.terminate()
        try: proc.wait(timeout=3)
        except: proc.kill()


if __name__ == "__main__":
    import sys
    p = int(sys.argv[1]) if len(sys.argv)>1 else 0
    if not p:
        r = subprocess.run(["playstealth","launch","--url","https://heypiggy.com/?page=dashboard"],
                          capture_output=True, text=True, timeout=30)
        for l in reversed(r.stdout.strip().split("\n")):
            try: p = json.loads(l).get("pid"); break
            except: pass
        print(f"PID={p}")
        time.sleep(5)
    main(p)
