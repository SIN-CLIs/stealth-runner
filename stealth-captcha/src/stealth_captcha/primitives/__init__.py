"""Low-level primitives for captcha interaction.

These are the building blocks:
  - TrajectoryGenerator: human-like Bezier mouse movement
  - HitTester: ensures elementFromPoint() resolves to the captcha block
  - GapDetector: DOM-based gap measurement (100x more accurate than vision)
  - Verifier: DOM polling for success/failure signals
"""

from stealth_captcha.primitives.gap_detector import GapDetector, GapGeometry
from stealth_captcha.primitives.hit_test import HitTester, HitTestResult, NeutralizedOverlay
from stealth_captcha.primitives.trajectory import TrajectoryGenerator, TrajectoryPoint
from stealth_captcha.primitives.verify import Verifier, VerifyOutcome

__all__ = [
    "TrajectoryGenerator",
    "TrajectoryPoint",
    "HitTester",
    "HitTestResult",
    "NeutralizedOverlay",
    "GapDetector",
    "GapGeometry",
    "Verifier",
    "VerifyOutcome",
]
