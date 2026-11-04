from __future__ import annotations

import time
from typing import Callable
from itertools import count
from threading import Event

import pytest
from pytestqt.qtbot import QtBot

from tqm import TQManager, TaskBuilder, exceptions

from ...utils import assert_task_failed, assert_task_completed


def test_predicate_blocks_task_execution(qtbot: QtBot, app: TQManager):
    """
    Test that a task with a failing predicate and no attempts fails at once.

    Verifies that:
    - A task with a predicate that returns False is never executed
    - The task fails with TaskPredicateError without ever retrying
    - The task does not stay in the deferred queue
    """
    # Condition that will always be False
    predicate_condition = False

    # Create a task with a predicate that will always fail
    task = (
        TaskBuilder('PredicateTask')
        .with_event(lambda t: t.log('This should never execute'))
        .with_predicate(lambda: predicate_condition, max_attempts=0, delay_ms=0)
        .build()
    )

    app.add_tasks(task)

    with qtbot.wait_signal(app.executor.callbacks.system_idle):
        app.start_workers()

    # Verify the task failed due to predicate condition
    assert_task_failed(
        task,
        ['inactive', 'waiting', 'blocked', 'failed']
    )

    assert isinstance(task.exception, exceptions.TaskPredicateError)
    assert task.id not in app.executor.queue.deferred


def test_predicate_blocks_until_condition_met(qtbot: QtBot, app: TQManager):
    """
    Test that a task with a predicate is only executed when the condition is met.

    Creates a task with a predicate that initially fails but becomes true
    during retry attempts. Verifies the task eventually executes and completes.
    """
    counter = count()

    # Create a task with a predicate that will fail at first
    task = (
        TaskBuilder('EventuallyExecutedTask')
        .with_event(lambda t: t.log('Task executed successfully'))
        .with_predicate(
            lambda: next(counter) == 2,
            max_attempts=3,
            delay_ms=0)
        .build()
    )

    app.add_tasks(task)

    with qtbot.wait_signal(app.executor.callbacks.system_idle):
        app.start_workers()

    # there should be an attempt left
    assert task.predicate.retry_left == 1

    # task should complete on the third attempt
    assert_task_completed(
        task,
        [
            'inactive',
            'waiting', 'blocked',
            'retrying', 'retrying',
            'running', 'completed',
        ]
    )


def test_predicate_exhausts_attempts(qtbot: QtBot, app: TQManager):
    """Test that a predicate that stays False fails the task after its attempts."""
    executed: list[str] = []

    task = (
        TaskBuilder('NeverExecutedTask')
        .with_event(lambda t: executed.append(t.name))
        .with_predicate(lambda: False, max_attempts=2, delay_ms=0)
        .build()
    )

    app.add_tasks(task)
    app.start_workers()

    qtbot.wait_until(lambda: task.state.is_failed or task.state.is_completed)

    assert executed == []
    assert_task_failed(
        task,
        ['inactive', 'waiting', 'blocked', 'retrying', 'retrying', 'failed']
    )
    assert isinstance(task.exception, exceptions.TaskPredicateError)


def test_predicate_waits_for_interval(qtbot: QtBot, app: TQManager):
    """Test that predicate attempts are spaced by delay_ms."""
    checks: list[float] = []

    def condition() -> bool:
        checks.append(time.monotonic())
        return False

    task = (
        TaskBuilder('IntervalTask')
        .with_event(lambda t: None)
        .with_predicate(condition, max_attempts=2, delay_ms=100)
        .build()
    )

    app.add_tasks(task)
    app.start_workers()

    qtbot.wait_until(lambda: task.state.is_failed)

    # A coarse QTimer may fire up to 5% early; load can only widen the gaps.
    assert len(checks) == 3
    assert checks[1] - checks[0] >= 0.09
    assert checks[2] - checks[1] >= 0.09


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason='tqm-nav.7.7'
)
def test_predicate_waits_for_slow_parent(qtbot: QtBot, app: TQManager, gate: Callable[[], Event]):
    """Test that a parent still running does not use up the child's predicate attempts."""
    release = gate()

    parent = (
        TaskBuilder('SlowParent')
        .with_event(lambda t: release.wait())
        .build()
    )
    child = (
        TaskBuilder('Child')
        .with_event(lambda t: None)
        .with_wait_for(parent)
        .with_predicate(lambda: parent.state.is_completed, max_attempts=2, delay_ms=1)
        .build()
    )

    app.add_tasks(parent, child)
    app.start_workers()

    qtbot.wait_until(lambda: parent.state.is_running)

    # Each poll spins the event loop for 10ms, so a 1ms timer gets every attempt it can burn.
    polls = count()
    qtbot.wait_until(lambda: next(polls) == 5)

    release.set()
    qtbot.wait_until(lambda: child.state.is_completed or child.state.is_failed)

    assert child.state.is_completed


def test_predicate_for_task_with_parent(qtbot: QtBot, app: TQManager):
    """
    Test interaction between task predicates and parent task dependencies.

    Creates a parent task and a child task with a predicate. Verifies that
    both the parent dependency and the predicate must be satisfied for
    the child task to execute. The child's history is not pinned because
    the order of the two checks is still undecided.
    """

    counter = count()

    execution_order: list[str] = []

    # Parent task
    task1 = (
        TaskBuilder('Task1')
        .with_event(lambda t: execution_order.append(t.name))
        .build()
    )

    # Child task with parent dependency and predicate
    task2 = (
        TaskBuilder('Task2')
        .with_event(lambda t: execution_order.append(t.name))
        .with_wait_for(task1)
        .with_predicate(
            lambda: next(counter) == 3,
            max_attempts=5,
            delay_ms=1)
        .build()
    )

    task3 = (
        TaskBuilder('Task3')
        .with_event(lambda t: execution_order.append(t.name))
        .with_wait_for(task2)
        .build()
    )

    app.add_tasks(task1, task2, task3)
    app.start_workers()

    qtbot.wait_until(lambda: task3.state.is_completed or task3.state.is_failed)

    assert execution_order == ['Task1', 'Task2', 'Task3']

    assert_task_completed(task1)
    assert task2.state.is_completed

    # task3 is blocked until task2 completes
    assert_task_completed(
        task3,
        ['inactive', 'waiting', 'blocked', 'waiting', 'running', 'completed']
    )
