"""Erweiterte State Machine mit Exit-Code-Routing & Stealth-Scoring."""
from __future__ import annotations
from enum import StrEnum

class ExtendedState(StrEnum):
    IDLE = "idle"; LAUNCH_BROWSER = "launch_browser"; WAIT_READY = "wait_ready"
    CAPTURE = "capture"; VISION = "vision"; EXECUTE = "execute"; VERIFY = "verify"
    DONE = "done"; RECOVERY = "recovery"
    VISION_RETRY = "vision_retry"; STEALTH_DEGRADED = "stealth_degraded"; UNCLEAN_SHUTDOWN = "unclean_shutdown"

EXIT_CODE_ROUTING: dict[int, ExtendedState] = {0: ExtendedState.VERIFY, 1: ExtendedState.VISION_RETRY, 2: ExtendedState.RECOVERY, 3: ExtendedState.STEALTH_DEGRADED}
