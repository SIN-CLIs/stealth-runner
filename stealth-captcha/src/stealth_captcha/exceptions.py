"""Exception hierarchy — every failure mode gets its own type for precise error handling.

WARUM: Fangen mit bare except oder generischem Exception verliert Kontext.
Jeder Fehler (CDP-Timeout, Captcha-Fail, Verbindungsabbruch) braucht
einen eigenen Typ damit Caller gezielt reagieren können (Retry, Abort,
oder Fallback). Zentrale Exception-Hierarchy verhindert divergente
Fehlerbehandlung über das Repo verteilt.

ARCHITEKTUR: CaptchaError als Basisklasse. CDPConnectionError,
CDPCommandError, StealthError etc. als Spezialisierungen.
Keine Business-Logik — nur Typ-Deklarationen. Alle Exceptions sind
Exception-sicher (kein State, keine Side-Effects beim Raise).

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

from __future__ import annotations


class CaptchaError(Exception):
    """Base for all captcha-related failures."""


class CDPConnectionError(CaptchaError):
    """Failed to connect to Chrome DevTools Protocol WebSocket."""


class CDPCommandError(CaptchaError):
    """A CDP command returned an error or timed out."""


class StealthInjectionError(CaptchaError):
    """Failed to inject one or more stealth patches into the page."""


class HitTestError(CaptchaError):
    """The captcha block element is not the topmost at hit-test coordinates.

    Typically means an SVG/canvas overlay is intercepting events.
    """


class GapDetectionError(CaptchaError):
    """Could not determine the slide-target gap from the DOM."""


class TrajectoryError(CaptchaError):
    """Bezier trajectory generation produced an invalid sequence."""


class VerifyTimeoutError(CaptchaError):
    """Captcha verification did not resolve to success or failure within timeout."""


class SolverFailedError(CaptchaError):
    """Solver exhausted all retries without a successful solve."""
