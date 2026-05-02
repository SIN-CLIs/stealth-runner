#!/usr/bin/env python3
"""Run the survey with voiceover for each action."""
import os
import sys
import time
from subprocess import run, CalledProcessError

# Add the current directory to the path so we can import runner
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from runner.live_omni_monitor import LiveOmniMonitor

def speak(text):
    """Use macOS say command to speak text."""
    try:
        run(["say", text], check=False)
    except Exception:
        pass  # Ignore if say is not available

def main():
    # Set NVIDIA API key from .env
    env_path = os.path.join(os.path.dirname(__file__), '.env')
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                if line.startswith('NVIDIA_API_KEY='):
                    key = line.strip().split('=', 1)[1]
                    os.environ['NVIDIA_API_KEY'] = key
                    break

    if not os.environ.get('NVIDIA_API_KEY'):
        print("Error: NVIDIA_API_KEY not set in .env")
        sys.exit(1)

    url = "https://heypiggy.com/?page=dashboard"
    monitor = LiveOmniMonitor(fps=1.0, buffer_seconds=4, debug=True)

    def on_action(obs):
        """Callback for each action executed."""
        action = obs.action
        element_index = obs.element_index
        label = obs.label
        if action != "wait":
            message = f"Performing action {action} on element {element_index}"
            if label:
                message += f": {label}"
            speak(message)
            print(f"🔊 {message}", flush=True)

    try:
        print("🚀 Starting survey with voiceover...", flush=True)
        monitor.start(url=url)
        monitor.run_continuous(max_steps=1000, on_action=on_action)
        speak("Survey completed")
        print("✅ Survey completed", flush=True)
    except KeyboardInterrupt:
        speak("Survey stopped by user")
        print("\n🛑 Survey stopped by user", flush=True)
    except Exception as e:
        speak(f"Error: {str(e)}")
        print(f"❌ Error: {e}", flush=True)
    finally:
        monitor.stop()

if __name__ == "__main__":
    main()
