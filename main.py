#!/usr/bin/env python3
import asyncio
import sys
from runner.state_machine import StealthRunner

def main():
    if len(sys.argv) != 2:
        print("Usage: python -m runner.state_machine <URL>")
        sys.exit(1)
    url = sys.argv[1]
    asyncio.run(StealthRunner(url).run())

if __name__ == "__main__":
    main()
