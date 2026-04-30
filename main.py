#!/usr/bin/env python3
"""Main entry point for the stealth-runner."""
import sys
import anyio
from runner.state_machine import SurveyRunner

def main():
    if len(sys.argv) != 2:
        print("Usage: python main.py <URL>")
        sys.exit(1)
    url = sys.argv[1]
    runner = SurveyRunner(url)
    result = anyio.run(runner.run)
    print(f"Survey completed. Context: {result}")

if __name__ == "__main__":
    main()
