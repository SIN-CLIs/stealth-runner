#!/usr/bin/env python3
"""Omni Survey Runner – Automatisierter Heypiggy-Runner mit LiveOmniMonitor.

Kein Nutzer-Chrome, kein Recovery-Mode, nur Omni + skylight-cli.
"""
from __future__ import annotations
import json
import os
import subprocess
import time
from pathlib import Path

from .live_omni_monitor import LiveOmniMonitor, OmniObservation


class OmniSurveyRunner:
    """Kompletter Survey-Durchlauf: Login → Loop → Abschluss."""

    def __init__(self, max_surveys: int = 5, debug: bool = True):
        self.max_surveys = max_surveys
        self.monitor = LiveOmniMonitor(fps=1.0, debug=debug)
        self.completed = 0
        self.earned = 0.0

    def run(self) -> dict:
        start = time.time()

        # 1. Login
        self._login()

        # 2. Monitor starten (eigene Chrome-Instanz via playstealth launch)
        self.monitor.start("https://heypiggy.com/?page=dashboard")

        try:
            # 3. Survey-Loop
            step = 0
            while self.completed < self.max_surveys and step < 500:
                frame = self.monitor.capture_frame()
                obs = self.monitor.analyze_frame(frame)

                if obs.action == "done":
                    self.completed += 1
                    print(f"✅ Survey {self.completed}/{self.max_surveys} abgeschlossen", flush=True)
                    if self.completed >= self.max_surveys:
                        break

                if obs.confidence >= 0.5 and obs.action != "wait":
                    self.monitor.execute_action(obs)
                else:
                    time.sleep(1)

                step += 1
        finally:
            self.monitor.stop()

        duration = time.time() - start
        return {
            "surveys": self.completed,
            "earned_eur": self.earned,
            "duration_s": duration,
            "eur_per_hour": (self.earned / duration * 3600) if duration > 0 else 0,
        }

    def _login(self) -> None:
        """playstealth login + heypiggy-login CLI."""
        profile = Path(__file__).resolve().parent.parent / "profiles" / "jeremy.yaml"
        if not profile.exists():
            print("⚠️ Kein Profil – Login übersprungen", flush=True)
            return

        import yaml
        data = yaml.safe_load(profile.read_text())
        email = data.get("google_email", "")
        if not email:
            print("⚠️ Keine E-Mail im Profil", flush=True)
            return

        print(f"🔐 Login {email}...", flush=True)

        # playstealth launch – Browser starten
        r = subprocess.run(
            ["playstealth", "launch", "--url", "https://heypiggy.com/?page=dashboard"],
            capture_output=True, text=True, timeout=30,
        )
        for line in reversed(r.stdout.strip().split("\n")):
            try:
                d = json.loads(line)
                pid = d.get("pid")
                break
            except json.JSONDecodeError:
                continue
        else:
            print("⚠️ playstealth launch fehlgeschlagen", flush=True)
            return

        # heypiggy-login CLI (NUR skylight-cli, kein osascript)
        subprocess.run(
            ["bash", "cli/heypiggy-login", str(pid)],
            cwd=Path(__file__).resolve().parent.parent,
            timeout=60,
        )
        print("✅ Login abgeschlossen", flush=True)


if __name__ == "__main__":
    runner = OmniSurveyRunner(max_surveys=3)
    result = runner.run()
    print(json.dumps(result, indent=2))
