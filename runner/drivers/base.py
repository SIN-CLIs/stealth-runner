from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

class BaseDriver(ABC):
    @abstractmethod
    def screenshot(self, pid: int, mode: str, out: Path) -> dict[str, Any]: pass
    @abstractmethod
    def click(self, pid: int, idx: int) -> dict[str, Any]: pass
