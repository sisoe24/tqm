from __future__ import annotations

from typing import List

import pytest
from pytestqt.qtbot import QtBot

from tqm import TaskBuilder
from tqm._core.task_state import format_duration
from tqm._core.task_predicate import PredicateEventType


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


@pytest.mark.parametrize('seconds, expected', [(0.05, '+50ms'), (3700, '+1h 1m')])
def test_format_duration(seconds: float, expected: str):
    assert format_duration(seconds) == expected


def test_predicate_stops_its_timer_when_attempts_run_out(qtbot: QtBot):
    task = TaskBuilder().with_predicate(lambda: False, max_attempts=1, delay_ms=1).build()
    events: List[PredicateEventType] = []

    task.predicate.evaluate(events.append)
    qtbot.wait_until(lambda: PredicateEventType.FAIL in events)

    assert task.predicate.timer is None
