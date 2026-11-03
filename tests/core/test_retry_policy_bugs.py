from __future__ import annotations


import pytest

from tqm import TaskBuilder, TaskGroupBuilder, retry_policy
from tqm.exceptions import TqmError
from tqm._core.retry_policy import fixed_retry
from tqm._core.retry_policy.retry_policy import RetryStatus, RetryContext
from tqm._core.retry_policy.delay_strategy import FixedDelay
from tqm._core.retry_policy.factory_methods import exceptions_retry

from ..utils import must_raise


@pytest.mark.xfail(strict=True, raises=AssertionError, reason='V22')
def test_never_retry_on_alone_retries_other_exceptions():
    policy = exceptions_retry(2, FixedDelay(0), never_retry_on=[ValueError])
    context = RetryContext(task=TaskBuilder().build(), exception=RuntimeError('x'))

    assert policy.should_retry(context) == RetryStatus.RETRY


@pytest.mark.xfail(strict=True, raises=AssertionError, reason='V23')
def test_tasks_do_not_share_a_policy():
    policy = fixed_retry(2, 0)
    first = TaskBuilder().with_retry_policy(policy).build()
    second = TaskBuilder().with_retry_policy(policy).build()

    assert first.retry_policy is not second.retry_policy


@pytest.mark.xfail(strict=True, raises=AssertionError, reason='V23')
def test_building_twice_does_not_share_state():
    builder = TaskBuilder().with_retry(2, 0).with_data(key=[])
    first, second = builder.build(), builder.build()

    assert first.retry_policy is not second.retry_policy
    assert first.data is not second.data


@pytest.mark.xfail(strict=True, raises=AssertionError, reason='V24')
def test_group_builder_keeps_data():
    group = TaskGroupBuilder('G').with_data(key=1).build()

    assert group.data == {'key': 1}


@pytest.mark.xfail(strict=True, raises=AssertionError, reason='V24')
def test_group_builder_does_not_drop_the_retry_policy():
    builder = TaskGroupBuilder('G').with_retry(3, 0)

    try:
        group = builder.build()
    except TqmError:
        return

    assert group.retry_policy.max_attempts == 3


@pytest.mark.xfail(strict=True, raises=AssertionError, reason='V55')
@pytest.mark.parametrize('name', ['ConditionalRetryPolicy', 'RetryStatus'])
def test_policy_names_are_exported(name: str):
    assert hasattr(retry_policy, name)


@pytest.mark.xfail(strict=True, raises=AssertionError, reason='V55')
def test_none_retry_policy_is_rejected():
    with must_raise(Exception):
        TaskBuilder().with_retry_policy(None).build()
