"""HumanProfile mit echten statistischen Verteilungen (scipy)."""
from __future__ import annotations
import random, anyio
from dataclasses import dataclass, field
from scipy import stats

DIST_DWELL = stats.gamma(a=5, scale=200)
DIST_FLIGHT = stats.norm(loc=400, scale=100)
DIST_TYPING = stats.norm(loc=180, scale=40)

@dataclass
class HumanProfile:
    profile_name: str = "sota"
    min_delay: float = field(init=False)
    max_delay: float = field(init=False)
    typing_speed: int = field(init=False)
    click_jitter_px: int = 4
    hover_ms: int = 80

    def __post_init__(self):
        self.min_delay = max(2.0, DIST_DWELL.rvs()/1000.0)
        self.max_delay = max(self.min_delay+3, DIST_DWELL.rvs()*1.5/1000.0)
        self.typing_speed = int(max(60, DIST_TYPING.rvs()))

    async def click_delay(self) -> None:
        await anyio.sleep(random.uniform(self.min_delay, self.max_delay))

    async def type_delay(self, text: str) -> None:
        await anyio.sleep(len(text) / (self.typing_speed/60) * random.uniform(0.8, 1.2))

    @classmethod
    def random(cls, name: str = "sota") -> "HumanProfile":
        return cls(profile_name=name)
