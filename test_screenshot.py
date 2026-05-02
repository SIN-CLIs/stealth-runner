#!/usr/bin/env python3
import sys
sys.path.insert(0, '.')
from runner.live_omni_monitor import LiveOmniMonitor
import os

# Set the PID to the one we saw earlier (or we can launch a new one)
# For testing, let's use the PID from the state file if it exists, otherwise we'll launch.
pid = None
state_file = '/tmp/stealth_step.json'
if os.path.exists(state_file):
    import json
    with open(state_file) as f:
        data = json.load(f)
        pid = data.get('pid')
        print(f"Using PID from state file: {pid}")

if pid is None:
    # Launch a new one
    from runner.stealth_executor import StealthExecutor
    executor = StealthExecutor()
    result = executor.run(["playstealth", "launch", "--url", "https://heypiggy.com/?page=dashboard", "--json"])
    pid = result.get("pid")
    print(f"Launched new PID: {pid}")

monitor = LiveOmniMonitor(fps=1.0, buffer_seconds=4, debug=True)
monitor.pid = pid
monitor.running = True

print("Calling capture_frame...")
frame = monitor.capture_frame()
print(f"Frame captured: {frame}")
print(f"Image path: {frame.image_path}")
print(f"Does file exist? {os.path.exists(frame.image_path)}")
