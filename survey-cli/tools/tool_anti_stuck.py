#!/usr/bin/env python3
"""
================================================================================
TOOL: anti_stuck
================================================================================
Prueft ob Loop stuck ist via DOM-Hash Vergleich.
Threshold: 3x gleicher Hash = stuck.

BEREITS FUNKTIONIERT: ✓ Getestet mit Qualtrics Language Loop

USAGE:
    from tools.tool_anti_stuck import AntiStuck
    checker = AntiStuck(threshold=3)
    while True:
        hash = get_dom_hash(ws_url)
        if checker.is_stuck(hash):
            print("STUCK!")
            break

NICHT AENDERN! Dieser Flow funktioniert.
================================================================================
"""

from typing import List

__version__ = "1.0.0"
__frozen__ = True


class AntiStuck:
    def __init__(self, threshold: int = 3):
        self.threshold = threshold
        self.history: List[str] = []

    def is_stuck(self, current_hash: str) -> bool:
        self.history.append(current_hash)
        if len(self.history) < self.threshold:
            return False
        recent = self.history[-self.threshold:]
        return len(set(recent)) == 1

    def reset(self):
        self.history = []

    @property
    def count(self) -> int:
        if not self.history:
            return 0
        current = self.history[-1]
        c = 0
        for h in reversed(self.history):
            if h == current:
                c += 1
            else:
                break
        return c


def check_stuck(history: List[str], current: str, threshold: int = 3) -> bool:
    if len(history) < threshold - 1:
        return False
    recent = history[-(threshold - 1):] + [current]
    return len(set(recent)) == 1


if __name__ == "__main__":
    checker = AntiStuck(threshold=3)
    for h in ["abc", "abc", "abc", "def", "def", "def"]:
        stuck = checker.is_stuck(h)
        print("Hash: {0}, Stuck: {1}, Count: {2}".format(h, stuck, checker.count))
