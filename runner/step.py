#!/usr/bin/env python3
"""EIN Schritt: Capture -> Vision -> Execute -> Print. Agent ruft in Schleife auf."""
from __future__ import annotations
import json, sys, os
from pathlib import Path
from runner.stealth_executor import StealthExecutor
from runner.vision_client import VisionClient
from runner.prompt_kit import build_prompt

STEP_FILE = Path("/tmp/stealth_step.json")

def load_state() -> dict:
    if STEP_FILE.exists():
        try: return json.loads(STEP_FILE.read_text())
        except: pass
    return {"step": 0, "pid": None, "url": "", "eur": 0.0}

def save_state(state: dict):
    STEP_FILE.write_text(json.dumps(state))

def main():
    state = load_state(); step = state.get("step", 0); pid = state.get("pid")
    url = sys.argv[1] if len(sys.argv) > 1 else state.get("url", "https://heypiggy.com/?page=dashboard")
    executor = StealthExecutor(); vision = VisionClient()

    if pid is None:
        print("→ Browser starten...", flush=True)
        result = executor.run(["playstealth", "launch", "--url", url])
        pid = result.get("pid"); executor.pid = pid
        state.update({"pid": pid, "url": url}); save_state(state)
        print(json.dumps({"step": 0, "action": "launch", "pid": pid, "status": "ok"}))
        return

    executor.pid = pid
    out = f"/tmp/step_{step}.png"
    executor.screenshot(out_path=out, mode="som")
    print(f"📸 step_{step}.png", flush=True)
    action = vision.get_action(out, build_prompt(state, step))
    atype = action.get("action", "wait"); eid = action.get("element_id"); args = action.get("args", {})

    if atype == "click": executor.click(element_index=eid)
    elif atype == "type": executor.type_text(text=args.get("text", ""), element_index=eid)
    elif atype == "scroll": executor.scroll(direction=args.get("direction", "down"))
    elif atype == "done": STEP_FILE.unlink(missing_ok=True); print(json.dumps({"step": step, "status": "done"})); return

    try: executor.verify_stealth()
    except: pass
    state["step"] = step + 1; save_state(state)
    print(json.dumps({"step": step, "action": atype, "element": eid, "status": "ok", "next": step + 1}))

if __name__ == "__main__":
    main()
