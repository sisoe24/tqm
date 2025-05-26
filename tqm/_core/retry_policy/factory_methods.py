from __future__ import annotations

from typing import List, Type, Callable, Optional

from .retry_policy import (SimpleRetryPolicy, ConditionalRetryPolicy,
                           ExceptionBasedRetryPolicy)
from .delay_strategy import (FixedDelay, DelayStrategy, LinearBackoff,
                             ExponentialBackoff)


def fixed_retry(attempts: int, delay_seconds: int) -> SimpleRetryPolicy:
    """Create simple retry with fixed delay."""
    return SimpleRetryPolicy(attempts, FixedDelay(delay_seconds))


def linear_retry(attempts: int, delay_seconds: int) -> SimpleRetryPolicy:
    """Create simple retry with fixed delay."""
    return SimpleRetryPolicy(attempts, LinearBackoff(delay_seconds))


def conditional_retry(
    attempts: int,
    delay_strategy: DelayStrategy,
    retry_if: Callable[..., bool],
) -> ConditionalRetryPolicy:
    """Create conditional retry with custom delay strategy."""
    return ConditionalRetryPolicy(attempts, delay_strategy, retry_if)


def exponential_retry(
    attempts: int,
    base_delay: int = 1,
    max_delay: int = 60
) -> SimpleRetryPolicy:
    """Create simple retry with exponential backoff."""
    delay_strategy = ExponentialBackoff(base_delay, 2, max_delay)
    return SimpleRetryPolicy(attempts, delay_strategy)


def exceptions_retry(
    attempts: int,
    delay_strategy: DelayStrategy,
    retry_on: Optional[List[Type[Exception]]] = None,
    never_retry_on: Optional[List[Type[Exception]]] = None
) -> ExceptionBasedRetryPolicy:
    """Create a retry policy with exception based filtering."""
    return ExceptionBasedRetryPolicy(attempts, delay_strategy, retry_on, never_retry_on)
