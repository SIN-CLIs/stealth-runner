"""Abstract solver interface — uniform contract across captcha families.

Every solver implements solve(session) → SolveResult following the same
pipeline with the same retry/backoff semantics.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum

from stealth_captcha.cdp.client import CDPSession


class SolveOutcome(Enum):
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
