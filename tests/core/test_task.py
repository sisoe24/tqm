from __future__ import annotations

import pytest

from tqm import TaskBuilder
from tqm._core.task_state import format_duration


def test_reset_can_restore_the_retry_budget():
    task = TaskBuilder().with_retry(3, 0).build()
    task.retry_policy.attempt = 2

    task.reset(reset_attempts=True)

    assert task.retry_policy.attempt == 0


def test_reset_restores_the_predicate_budget():
    task = TaskBuilder().with_predicate(lambda: False, max_attempts=3, delay_ms=5).build()
    task.predicate.retry_left = 0

    task.reset()

    assert task.predicate.retry_left == 3


def test_delete_detaches_from_the_parent():
    parent = TaskBuilder().build()
    child = TaskBuilder().with_wait_for(parent).build()

    child.delete()

    assert child not in parent.children
    assert child.parent is None


def test_delete_releases_the_callbacks():
    task = (
        TaskBuilder()
        .with_on_start(lambda t: None)
        .with_on_finish(lambda t: None)
        .with_on_failed(lambda t: None)
        .with_on_completed(lambda t: None)
        .build()
    )

    task.delete()

    callbacks = task.callbacks
    assert not (
        callbacks.on_start or callbacks.on_finish or callbacks.on_failed or callbacks.on_completed
    )


def test_is_active_states():
    state = TaskBuilder().build().state

    for set_state, expected in [
        (state.set_running, True),
        (state.set_retrying, True),
        (state.set_blocked, True),
        (state.set_waiting, False),
        (state.set_completed, False),
    ]:
        set_state()
        assert state.is_active is expected


@pytest.mark.parametrize('seconds, expected', [(0.05, '+50ms'), (3700, '+1h 1m')])
def test_format_duration(seconds: float, expected: str):
    assert format_duration(seconds) == expected
