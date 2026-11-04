from __future__ import annotations

from typing import List

import pytest

from tqm._core.retry_policy import (FixedDelay, LinearBackoff, ExponentialBackoff,
                                    ExceptionBasedRetryPolicy, linear_retry,
                                    exponential_retry)
from tqm._core.retry_policy.retry_policy import (RetryStatus, RetryContext,
                                                 ConditionalRetryPolicy)


def context(exception: Exception) -> RetryContext:
    return RetryContext(task=None, exception=exception)


def test_exception_policy_retries_only_listed_exceptions():
    policy = ExceptionBasedRetryPolicy(2, FixedDelay(0), retry_on=[ValueError])

    assert policy.should_retry(context(ValueError())) == RetryStatus.RETRY
    assert policy.should_retry(context(OSError())) == RetryStatus.FAIL


def test_exception_policy_never_retry_wins():
    policy = ExceptionBasedRetryPolicy(
        2, FixedDelay(0), retry_on=[Exception], never_retry_on=[KeyError]
    )

    assert policy.should_retry(context(KeyError())) == RetryStatus.FAIL


@pytest.mark.xfail(strict=True, raises=AssertionError, reason='V21')
def test_conditional_policy_retries_when_the_condition_is_true():
    error = ValueError()
    seen: List[Exception] = []

    def retry_if(exception: Exception) -> bool:
        seen.append(exception)
        return True

    policy = ConditionalRetryPolicy(1, FixedDelay(0), retry_if)

    assert policy.should_retry(context(error)) == RetryStatus.RETRY
    assert seen == [error]


def test_conditional_policy_fails_when_the_condition_raises():
    policy = ConditionalRetryPolicy(1, FixedDelay(0), lambda *_: 1 / 0)

    assert policy.should_retry(context(ValueError())) == RetryStatus.FAIL


@pytest.mark.parametrize('attempt, expected', [(0, 5), (1, 10), (9, 12)])
def test_linear_backoff(attempt: int, expected: int):
    assert LinearBackoff(5, max_delay=12).get_delay(attempt) == expected


@pytest.mark.parametrize('attempt, expected', [(0, 1), (1, 2), (2, 4), (3, 5)])
def test_exponential_backoff(attempt: int, expected: int):
    assert ExponentialBackoff(1, 2, 5).get_delay(attempt) == expected


def test_factories_pick_their_strategy():
    assert isinstance(linear_retry(1, 1).delay_strategy, LinearBackoff)
    assert exponential_retry(3, 1, 60).delay_strategy.get_delay(3) == 8
