"""HumanProfile – Realistische menschliche Verhaltensparameter."""
from __future__ import annotations
import random
from dataclasses import dataclass, field
import anyio

@dataclass
class HumanProfile:
    profile_name: str = "default"
    min_delay: float = field(default_factory=lambda: random.uniform(2.0, 4.0))
    max_delay: float = field(default_factory=lambda: random.uniform(5.0, 9.0))
    typing_speed: int = field(default_factory=lambda: random.randint(180, 300))
    scroll_jitter: float = field(default_factory=lambda: random.uniform(0.5, 1.5))
    click_jitter_px: int = field(default_factory=lambda: random.randint(2, 6))
    hover_before_click_ms: int = field(default_factory=lambda: random.randint(50, 250))

    async def type_delay(self, text: str) -> None:
        chars_per_second = self.typing_speed / 60.0
        total_delay = len(text) / chars_per_second
        jittered = total_delay * random.uniform(0.7, 1.3)
        await anyio.sleep(max(jittered, 0.05))

    async def click_delay(self) -> None:
        delay = random.uniform(self.min_delay, self.max_delay)
        await anyio.sleep(delay)

    async def scroll_pause(self) -> None:
        await anyio.sleep(random.uniform(0.8, 2.5))

    @classmethod
    def random(cls, profile_name: str | None = None) -> "HumanProfile":
        return cls(profile_name=profile_name or "random")
