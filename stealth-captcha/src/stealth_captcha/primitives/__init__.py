"""Low-level primitives for captcha interaction.

WARUM: Jeder Captcha-Solver braucht die gleichen Bausteine:
menschenähnliche Bewegung, Overlay-Neutralisierung, Gap-Messung,
Erfolgs-Verifikation. Diese Primitives sind provider-agnostisch
und wiederverwendbar für GoCaptcha, NetEase, GeeTest, FunCaptcha, etc.

ARCHITEKTUR: Package-Root. Exportiert TrajectoryGenerator, HitTester,
GapDetector, Verifier und deren Result-Typen. Jede Klasse ist stateless
und thread-safe (keine Singletons). Reine Logik, keine CDP-Abhängigkeiten
außer Verifier (DOM-Polling via CDPSession).

BANNED METHODS — NIEMALS VERWENDEN:
❌ playstealth launch
❌ webauto-nodriver — ABSOLUT BANNED
❌ cua-driver click (raw index)
❌ --remote-allow-origins=* (ohne Quotes)
❌ /tmp/heypiggy-bot (fixed profile)
❌ Hardcoded PIDs
❌ pkill -f "Google Chrome"
❌ killall Google Chrome
❌ skylight-cli click --element-index
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
