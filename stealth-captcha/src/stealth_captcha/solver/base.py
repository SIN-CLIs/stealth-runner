"""Abstract solver interface — uniform contract across captcha families.

WARUM: Jedes Captcha (text, slide, drag_drop, geetest, lemin) braucht
dieselbe Retry/Backoff-Logik und dasselbe Result-Format. Ohne gemeinsames
Interface muss jeder Solver Fehlerbehandlung und State-Management selbst
implementieren → Bugs und Inkonsistenzen.

ARCHITEKTUR: ABC (abstract base class) mit solve(session) → SolveResult.
SolveOutcome Enum (SUCCESS, FAILURE, UNKNOWN) und SolveResult dataclass
sind die universalen Rückgabetypen. Retry-Logik und Backoff werden in
der Basisklasse oder einem Decorator zentral bereitgestellt.

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

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum

from stealth_captcha.cdp.client import CDPSession


class SolveOutcome(Enum):
    """
    ================================================================================
    Ergebnis eines Captcha-Solve-Versuchs.

    Wird von allen Solver-Backends (Text, GeeTest, Lemin) zurückgegeben
    um den Outcome einheitlich zu klassifizieren.

    Werte:
      SUCCESS  - Captcha erfolgreich gelöst
      FAILURE  - Lösung fehlgeschlagen (falsches Ergebnis, Timeout, etc.)
      UNKNOWN  - Status nicht bestimmbar (z.B. Netzwerkfehler ohne Retry)

    Nutzung:
      result = await solver.solve(...)
      if result.outcome == SolveOutcome.SUCCESS:
          # Weiter mit Survey
    ================================================================================
    """
    SUCCESS = "success"
    FAILURE = "failure"
    UNKNOWN = "unknown"


@dataclass(slots=True)
class SolveResult:
    """Result of a captcha solve attempt.

    Attributes:
        outcome: SUCCESS, FAILURE, or UNKNOWN.
        attempts: Number of retries used.
        duration_s: Wall-clock time of the entire solve.
        detail: Optional human-readable detail (e.g., OCR text, error msg).
    """

    outcome: SolveOutcome
    attempts: int
    duration_s: float
    detail: str | None = None


class BaseSolver(ABC):
    """Abstract captcha solver.

    Subclasses implement solve() for their specific captcha type.
    The base provides no retry logic — subclasses use tenacity directly.
    """

    @abstractmethod
    async def solve(self, session: CDPSession) -> SolveResult:
        """Solve the captcha in the given CDP session.

        Args:
            session: CDP session attached to the page containing the captcha.

        Returns:
            SolveResult with the outcome and metadata.
        """
        ...
