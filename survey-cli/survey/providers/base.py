"""ProviderAdapter interface for provider-specific survey behavior.

The engine should ask an adapter what commands and completion markers apply;
it should not spread provider-specific selectors across runner code.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass(frozen=True)
class CompletionState:
    """Provider completion classification."""

    status: str
    reason: str = ""


@dataclass
class ProviderAdapter:
    """Base adapter with URL matching, commands, and completion detection."""

    name: str
    url_patterns: List[str] = field(default_factory=list)
    commands: Dict[str, str] = field(default_factory=dict)
    completion_markers: List[str] = field(default_factory=list)
    screen_out_markers: List[str] = field(default_factory=lambda: [
        "screen out",
        "you do not qualify",
        "you are not eligible",
        "leider passen sie nicht",
        "nicht für diese umfrage qualifiziert",
        "thank you for your interest",
    ])
    blocked_markers: List[str] = field(default_factory=lambda: [
        "captcha",
        "not a robot",
        "human verification",
        "access denied",
    ])

    def matches(self, url: str = "", text: str = "") -> bool:
        """Return True if this adapter owns the URL or page text."""
        haystack = f"{url} {text}".lower()
        return any(pattern.lower() in haystack for pattern in self.url_patterns)

    def get_commands(self) -> Dict[str, str]:
        """Return CDP command templates for this provider."""
        return dict(self.commands)

    def detect_completion(self, text: str, url: str = "") -> CompletionState:
        """Classify provider page text into completion/screen-out/blocked/running."""
        haystack = f"{url} {text}".lower()
        for marker in self.completion_markers:
            if marker.lower() in haystack:
                return CompletionState("completed", marker)
        for marker in self.screen_out_markers:
            if marker.lower() in haystack:
                return CompletionState("screen_out", marker)
        for marker in self.blocked_markers:
            if marker.lower() in haystack:
                return CompletionState("blocked", marker)
        return CompletionState("running", "")
