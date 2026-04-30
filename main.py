#!/usr/bin/env python3
"""Main entry point for the stealth-runner. Usage: python main.py <URL>"""
from __future__ import annotations
import sys
import anyio
from runner.config import CF_API_TOKEN
from runner.state_machine import SurveyRunner

def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: python main.py <URL>")
        sys.exit(1)
    anyio.run(SurveyRunner(sys.argv[1]).run)

if __name__ == "__main__":
    main()
