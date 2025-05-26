from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum, auto
from typing import TYPE_CHECKING, Any, Dict, List, Type, Callable, Optional
from dataclasses import dataclass

if TYPE_CHECKING:
    from ..task import TaskUnit

from .delay_strategy import FixedDelay, DelayStrategy


class RetryStatus(Enum):
    SUCCESS = auto()
    RETRY = auto()
    FAIL = auto()


@dataclass
class RetryContext:
    """Context information for retry decisions."""
    task: TaskUnit
    exception: Exception


class RetryPolicy(ABC):
    """Base class for retry decision policies."""

    def __init__(self, max_attempts: int, delay_strategy: DelayStrategy):
        self.delay_strategy = delay_strategy
        self.max_attempts = max_attempts

        self.attempt = 0

    def __str__(self) -> str:
        return self.__class__.__name__

    @abstractmethod
    def should_retry(self, context: RetryContext) -> RetryStatus:
        """Should we retry this failure?"""

    def get_delay(self, context: RetryContext) -> int:
        """How long to wait before retry (delegates to delay strategy)."""
        return self.delay_strategy.get_delay(self.attempt)

    def reset(self) -> None:
        self.attempt = 0
        return None

    def inspect(self) -> Dict[str, Any]:
        return {
            'name': str(self),
            'attempt': self.attempt,
            'max_attempts': self.max_attempts,
            'delay_strategy': self.delay_strategy.inspect()
        }


class NoRetryPolicy(RetryPolicy):
    """Policy that never retries."""

    def __init__(self):
        super().__init__(max_attempts=0, delay_strategy=FixedDelay(0))

    def should_retry(self, context: RetryContext) -> RetryStatus:
        return RetryStatus.SUCCESS


class SimpleRetryPolicy(RetryPolicy):
    """Basic retry policy: retry up to max_attempts."""

    def __init__(self, max_attempts: int, delay_strategy: DelayStrategy):
        super().__init__(max_attempts, delay_strategy)

    def should_retry(self, context: RetryContext) -> RetryStatus:
        if self.attempt < self.max_attempts:
            return RetryStatus.RETRY
        return RetryStatus.FAIL


class ConditionalRetryPolicy(RetryPolicy):
    """Retry policy that considers a callable"""

    def __init__(
        self,
        max_attempts: int,
        delay_strategy: DelayStrategy,
        condition: Callable[..., bool]
    ):
        super().__init__(max_attempts, delay_strategy)
        self.condition = condition

    def should_retry(self, context: RetryContext) -> RetryStatus:
        if self.attempt >= self.max_attempts:
            return RetryStatus.FAIL

        try:
            return RetryStatus.SUCCESS if self.condition() else RetryStatus.RETRY
        except Exception as e:
            return RetryStatus.FAIL


class ExceptionBasedRetryPolicy(RetryPolicy):
    """Retry policy that considers exception types."""

    def __init__(
        self,
        max_attempts: int,
        delay_strategy: DelayStrategy,
        retry_on: Optional[List[Type[Exception]]] = None,
        never_retry_on: Optional[List[Type[Exception]]] = None
    ) -> None:
        super().__init__(max_attempts, delay_strategy)
        self.retry_on = retry_on or []
        self.never_retry_on = never_retry_on or []

    def _matches_exception_list(
        self,
        exception: Exception,
        exception_types: List[Type[Exception]]
    ) -> bool:
        """Check if exception matches any type in the list."""
        return any(isinstance(exception, exc_type) for exc_type in exception_types)

    def should_retry(self, context: RetryContext) -> RetryStatus:
        if self.attempt >= self.max_attempts:
            return RetryStatus.FAIL

        # Never retry certain exceptions
        if self._matches_exception_list(context.exception, self.never_retry_on):
            return RetryStatus.FAIL

        # If retry_on is specified, only retry those exceptions
        if self._matches_exception_list(context.exception, self.retry_on):
            return RetryStatus.RETRY

        return RetryStatus.FAIL
