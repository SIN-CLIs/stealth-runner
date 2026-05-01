#!/usr/bin/env python3
"""Video-Analyzer: Screen-Follow-Aufnahmen mit Nemotron Omni analysieren.

Features:
- Vollständige Survey-Durchläufe als Video analysieren
- Fehler erkennen (captchas, timeouts, falsche Klicks)
- CAPTCHA-Lösungen aus Video extrahieren
- Zeitliche Abläufe verstehen
- Survey-Flow vorhersagen
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

from .nemotron_omni import get_omni


def analyze_recording(video_path: str, question: str = "") -> dict:
    omni = get_omni()
    prompts = {
        "errors": (
            "Watch this screen recording of a survey automation. "
            "List every error: wrong clicks, missed buttons, "
            "CAPTCHA failures, page timeouts, unexpected popups. "
            "Output JSON: {\"errors\": [...], \"success\": false}"
        ),
        "captcha": (
            "Watch this screen recording. A CAPTCHA may have appeared. "
            "Describe the CAPTCHA type and how it was handled. "
            "Output JSON: {\"captcha_type\": \"turnstile|recaptcha|hcaptcha|none\", "
            "\"solved\": true|false, \"method\": \"auto|manual|failed\"}"
        ),
        "flow": (
            "Watch this complete survey recording. Describe the entire flow: "
            "which pages were visited, what actions were taken, the result. "
            "Output JSON: {\"pages\": [...], \"actions\": [...], "
            "\"result\": \"completed|disqualified|error\"}"
        ),
    }
    prompt = prompts.get(question, (
        "Analyze this screen recording. What happened? "
        "Output JSON with findings."
    ))
    return omni.analyze_video(video_path, prompt)


def analyze_last_recording(question: str = "errors") -> dict:
    dirs = [
        Path("/tmp/heypiggy-canary/recordings"),
        Path.home() / "Desktop" / "screen-follow",
        Path("/tmp"),
    ]
    for d in dirs:
        if d.exists():
            recordings = sorted(d.glob("*.mp4"), key=lambda p: p.stat().st_mtime, reverse=True)
            if recordings:
                return analyze_recording(str(recordings[0]), question)
    return {"error": "No recordings found"}


def compare_frames(before_path: str, after_path: str) -> dict:
    omni = get_omni()
    return omni.analyze_frame_sequence(
        [before_path, after_path],
        prompt=(
            "Compare these two screenshots. Did the page change? "
            "Did the click work? Is a new element visible? "
            "Output JSON: {\"changed\": true|false, "
            "\"page_transition\": true|false, "
            "\"new_elements\": [...], "
            "\"next_action\": \"...\"}"
        ),
    )


def predict_next_state(image_paths: list[str]) -> dict:
    omni = get_omni()
    return omni.analyze_frame_sequence(
        image_paths,
        prompt=(
            "These are sequential screenshots from a survey in progress. "
            "Based on the pattern so far, predict what should happen next: "
            "which button to click, what text to enter, or if the survey "
            "is complete. "
            "Output JSON: {\"predicted_action\": \"click|type|scroll|done\", "
            "\"target_element\": \"...\", "
            "\"reasoning\": \"...\", "
            "\"confidence\": 0.0-1.0}"
        ),
    )


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        print("\nUsage:")
        print("  python -m runner.video_analyzer <video.mp4> [errors|captcha|flow]")
        print("  python -m runner.video_analyzer --last [errors|captcha|flow]")
        print("  python -m runner.video_analyzer --compare <before.png> <after.png>")
        sys.exit(1)

    if sys.argv[1] == "--last":
        q = sys.argv[2] if len(sys.argv) > 2 else "errors"
        result = analyze_last_recording(q)
    elif sys.argv[1] == "--compare":
        result = compare_frames(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "")
    else:
        q = sys.argv[2] if len(sys.argv) > 2 else ""
        result = analyze_recording(sys.argv[1], q)

    print(json.dumps(result, indent=2, ensure_ascii=False))
