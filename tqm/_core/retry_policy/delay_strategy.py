from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict


class DelayStrategy(ABC):
    """Base class for retry delay strategies."""

    def __init__(self, delay_seconds: int) -> None:
        super().__init__()
        self.delay_seconds = delay_seconds

    @abstractmethod
    def get_delay(self, attempt: int) -> int:
        """Get delay in seconds for the given attempt number (0-indexed)."""

    def inspect(self) -> Dict[str, Any]:
        return {
            'name': self.__class__.__name__,
            'delay_seconds': self.delay_seconds
        }


class FixedDelay(DelayStrategy):
    """Fixed delay between retries."""

    def __init__(self, delay_seconds: int) -> None:
        super().__init__(delay_seconds)

    def get_delay(self, attempt: int) -> int:
        return self.delay_seconds


class LinearBackoff(DelayStrategy):
    """Linear increase in delay: base + (base * attempt)."""

    def __init__(self, delay_seconds: int, max_delay: int = 300) -> None:
        super().__init__(delay_seconds)
        self.max_delay = max_delay

    def get_delay(self, attempt: int) -> int:
        delay = self.delay_seconds + (self.delay_seconds * attempt)
        return min(delay, self.max_delay)


class ExponentialBackoff(DelayStrategy):
    """Exponential backoff: base * (multiplier ^ attempt)."""

    def __init__(
        self,
        delay_seconds: int,
        multiplier: int = 2,
        max_delay: int = 60,
    ) -> None:
        super().__init__(delay_seconds)
        self.multiplier = multiplier
        self.max_delay = max_delay

    def get_delay(self, attempt: int) -> int:
        delay = self.delay_seconds * (self.multiplier ** attempt)
        return min(delay, self.max_delay)
