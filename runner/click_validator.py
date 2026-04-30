"""Strict click contract enforcement — blocks raw coordinates."""
from __future__ import annotations
import re

class ClickValidationError(Exception):
    pass

def validate_click_command(cmd: list[str]) -> list[str]:
    if not cmd or "click" not in cmd:
        return cmd
    for i, arg in enumerate(cmd):
        if arg in ("--x", "--y") and i+1 < len(cmd) and re.match(r"^-?\d+$", cmd[i+1]):
            raise ClickValidationError(
                "RAW COORDINATES DETECTED. Use --element-index ONLY."
            )
    if "--element-index" not in cmd and "--label" not in cmd:
        raise ClickValidationError(
            "Missing --element-index or --label."
        )
    if "--no-primer" in cmd:
        cmd.remove("--no-primer")
    return cmd
