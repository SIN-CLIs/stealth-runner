#!/usr/bin/env python3
"""EIN Schritt: Capture → Omni Vision → Execute → Verify → Print."""
from __future__ import annotations
import json
import subprocess
import sys
from pathlib import Path

from runner.stealth_executor import StealthExecutor
from runner.vision_client import VisionClient
from runner.prompt_kit import build_prompt

STEP_FILE = Path("/tmp/stealth_step.json")


def load_state() -> dict:
    if STEP_FILE.exists():
        try:
            return json.loads(STEP_FILE.read_text())
        except Exception:
            pass
    return {"step": 0, "pid": None, "url": "", "eur": 0.0, "images": [], "prev_actions": []}


def save_state(state: dict):
    STEP_FILE.write_text(json.dumps(state))


def main():
    state = load_state()
    step = state.get("step", 0)
    pid = state.get("pid")
    url = sys.argv[1] if len(sys.argv) > 1 else state.get("url", "https://heypiggy.com/?page=dashboard")

    executor = StealthExecutor()
    vision = VisionClient()

    if pid is None:
        print("→ Browser starten...", flush=True)
        result = executor.run(["playstealth", "--json", "launch", "--url", url])
        pid = result.get("pid")
        executor.pid = pid
        state["pid"] = pid
        state["url"] = url
        state["images"] = []
        state["prev_actions"] = []
        save_state(state)
        try:
            subprocess.run(
                ["bash", "cli/heypiggy-login", str(pid)],
                cwd=Path(__file__).parent.parent,
                timeout=60,
            )
        except Exception:
            pass
        print(json.dumps({"step": 0, "action": "launch", "pid": pid, "status": "ok"}))
        return

    executor.pid = pid

    # Capture screenshot
    out = f"/tmp/step_{step}.png"
    executor.screenshot(out_path=out, mode="som")
    print(f"📸 Screenshot: step_{step}.png", flush=True)

    # Detect current page
    page = "unknown"
    try:
        elements = json.loads(subprocess.run(
            ["skylight-cli", "list-elements", "--pid", str(pid)],
            capture_output=True, text=True, timeout=10
        ).stdout)
        for e in elements.get("elements", []):
            if e["role"] == "AXWebArea":
                page = e["label"]
            elif e["role"] == "AXRadioButton" and page == "unknown":
                page = e["label"]
        if "PureSpectrum" in page:
            page = "PureSpectrum"
        elif "HeyPiggy" in page:
            page = "HeyPiggy"
    except Exception:
        pass
    state["page"] = page

    # Multi-Frame Context (letzte 5)
    images = state.get("images", [])
    images.append(out)
    if len(images) > 5:
        images = images[-5:]
    state["images"] = images

    # Omni Vision mit Multi-Frame Context wenn verfuegbar
    if len(images) >= 2:
        from runner.nemotron_omni import get_omni
        try:
            omni = get_omni()
            action = omni.analyze_frame_sequence(
                images[-2:],
                prompt=build_prompt(state, step),
            )
            if action.get("action") == "wait" and action.get("reasoning") == "parse_failed":
                action = vision.get_action(out, build_prompt(state, step))
        except Exception:
            action = vision.get_action(out, build_prompt(state, step))
    else:
        action = vision.get_action(out, build_prompt(state, step))

    # Execute
    atype = action.get("action", "wait")
    eid = action.get("element_id")
    args = action.get("args", {})

    prev_actions = state.get("prev_actions", [])
    prev_actions.append({"step": step, "action": atype, "element": eid})

    if atype == "click":
        print(f"👁 Omni → click [{eid}]", flush=True)
        executor.click(element_index=eid)
    elif atype == "type":
        print(f"👁 Omni → type [{eid}]: '{args.get('text','')}'", flush=True)
        executor.type_text(text=args.get("text", ""), element_index=eid)
    elif atype == "scroll":
        print(f"👁 Omni → scroll", flush=True)
        executor.scroll(direction=args.get("direction", "down"))
    elif atype == "hold":
        dur = args.get("duration_ms", 3000)
        print(f"👁 Omni → hold [{eid}] {dur}ms", flush=True)
        executor.run(["skylight-cli", "hold", "--pid", str(pid), "--element-index", str(eid), "--duration", str(dur)])
    elif atype == "done":
        print(json.dumps({"step": step, "status": "done", "message": "Survey complete"}))
        # Video-Analyse nach Abschluss
        try:
            from runner.video_analyzer import analyze_last_recording
            flow = analyze_last_recording("flow")
            print(f"📊 Flow: {json.dumps(flow, ensure_ascii=False)[:200]}", flush=True)
        except Exception:
            pass
        STEP_FILE.unlink(missing_ok=True)
        return
    else:
        print(f"👁 Omni → wait", flush=True)

    try:
        executor.verify_stealth()
    except Exception:
        pass

    state["step"] = step + 1
    save_state(state)
    print(json.dumps({"step": step, "action": atype, "element": eid, "status": "ok", "next": step + 1}))


if __name__ == "__main__":
    main()
