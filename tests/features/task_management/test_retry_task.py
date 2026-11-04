from __future__ import annotations

from unittest import mock
from itertools import count
from threading import Event, Thread, current_thread

import pytest
from PySide2.QtCore import QTimer
from pytestqt.qtbot import QtBot

from tqm import (TQManager, TaskBuilder, TaskExecutable, TaskGroupBuilder,
                 exceptions)

from ...utils import (raise_error, assert_task_failed, failure_controller,
                      assert_task_completed)


def test_simple_task_failure_handling(qtbot: QtBot, app: TQManager):
    """
    Test basic failure handling for a simple task.

    Verifies that:
    - A task that raises an exception is properly marked as failed
    - The exception is correctly stored with the task
    - The task is not retried when no retry attempts are configured
    """
    # task event will fail immediately
    task1 = (
        TaskBuilder('TestTask1')
        .with_event(raise_error)
        .build()
    )
    app.add_tasks(task1)

    # we wait for the workers to finish
    with qtbot.wait_signal(app.executor.callbacks.system_idle):
        app.start_workers()

    # check if task has failed
    assert_task_failed(task1)

    # a failed task should have an exception
    assert isinstance(task1.exception, RuntimeError)
    assert str(task1.exception) == 'TestTask1'


def test_parent_child_task_failure_propagation(qtbot: QtBot, app: TQManager):
    """
    Test failure propagation from parent to dependent child tasks.

    Verifies that:
    - When a parent task fails, dependent child tasks are also marked as failed
    - Child tasks receive a TaskParentError exception
    """
    # task event will fail immediately
    task1 = (
        TaskBuilder('TestTask1')
        .with_event(raise_error)
        .build()
    )

    # task2 depends on the success of task1 which will fail so task 2 will also fail
    task2 = (
        TaskBuilder('TestTask2')
        .with_event(lambda t: None)
        .with_wait_for(task1)
        .build()
    )

    app.add_tasks(task1, task2)

    # we wait for the workers to finish
    with qtbot.wait_signal(app.executor.callbacks.system_idle):
        app.start_workers()

    # check if task has failed
    assert_task_failed(task1)

    # a failed task should have an exception
    assert isinstance(task1.exception, RuntimeError)
    assert str(task1.exception) == 'TestTask1'

    assert_task_failed(
        task2,
        ['inactive', 'waiting', 'blocked', 'failed']
    )

    # if parent task fails, all children fails automatically with a TaskParentError
    assert isinstance(task2.exception, exceptions.TaskParentError)
    assert str(task2.exception) == f'Parent {task1.name} failed.'


def test_single_retry_success_after_failure(qtbot: QtBot, app: TQManager):
    """
    Test that a task can retry and succeed after a single failure.

    Uses a counter to make the task fail on first attempt but succeed on the second.
    Verifies the correct state transitions through the retry process.
    """
    index = count()

    # Task fails initially (skip_error=False) but succeeds on retry (skip_error=True)
    # index = 0 -> bool(0) == False, index = 1 -> bool(1) == True
    task1 = (
        TaskBuilder('TestTask1')
        .with_event(lambda t: raise_error(t, skip_error=bool(next(index))))
        .with_retry(1, delay_seconds=0)
        .build()
    )

    app.add_tasks(task1)

    # wait for the workers to finish
    with qtbot.wait_signal(app.executor.callbacks.system_idle):
        app.start_workers()

    # task state history indicates the inactive because of the reset that happens
    # when we retry
    assert_task_completed(
        task1, [
            'inactive', 'waiting', 'running', 'retrying',
            'inactive', 'waiting', 'running', 'completed'
        ])


def test_multiple_retries_eventual_success(qtbot: QtBot, app: TQManager):
    """
    Test a task that requires multiple retries before succeeding.

    The task is configured to succeed only on the 6th attempt (index=5)
    after failing 5 times. Verifies all state transitions occur correctly.
    """
    index = count()

    # Task fails multiple times until index equals 5, then succeeds
    task1 = (
        TaskBuilder('TestTask1')
        .with_event(lambda t: raise_error(t, skip_error=next(index) == 5))
        .with_retry(5, delay_seconds=0)
        .build()
    )

    app.add_tasks(task1)

    # wait for the workers to finish
    with qtbot.wait_signal(app.executor.callbacks.system_idle):
        app.start_workers()

    # task state history indicates the inactive because of the reset that happens
    # when we retry
    assert_task_completed(
        task1,
        [
            'inactive', 'waiting', 'running', 'retrying',
            'inactive', 'waiting', 'running', 'retrying',
            'inactive', 'waiting', 'running', 'retrying',
            'inactive', 'waiting', 'running', 'retrying',
            'inactive', 'waiting', 'running', 'retrying',
            'inactive', 'waiting', 'running', 'completed'
        ]
    )


def test_exhausted_retries_final_failure(qtbot: QtBot, app: TQManager):
    """
    Test task that exhausts all retry attempts and remains failed.

    The task is configured to succeed only on the 7th attempt (index=6),
    but only has 5 retry attempts. Verifies the task correctly transitions
    to a permanent failed state after exhausting retries.
    """
    index = count()

    # Task would only succeed on 7th attempt (index=6), but only has 5 retries
    task1 = (
        TaskBuilder('TestTask1')
        .with_event(lambda t: raise_error(t, skip_error=next(index) == 6))
        .with_retry(5, delay_seconds=0)
        .build()
    )

    app.add_tasks(task1)

    # wait for the workers to finish
    with qtbot.wait_signal(app.executor.callbacks.system_idle):
        app.start_workers()

    # because our condition to skip the error happens only on index 6 and we have
    # only 5 retries, we should fail
    assert_task_failed(
        task1,
        [
            'inactive', 'waiting', 'running', 'retrying',
            'inactive', 'waiting', 'running', 'retrying',
            'inactive', 'waiting', 'running', 'retrying',
            'inactive', 'waiting', 'running', 'retrying',
            'inactive', 'waiting', 'running', 'retrying',
            'inactive', 'waiting', 'running', 'failed'
        ]
    )


def test_dependent_task_chain_with_retry(qtbot: QtBot, app: TQManager):
    """
    Test a chain of dependent tasks with the first task requiring retry.

    Creates a chain of three dependent tasks where the first task fails once,
    then succeeds on retry. Verifies that all tasks in the chain complete
    correctly after the first task succeeds on retry.
    """
    index = count()

    # Task fails initially (skip_error=False) but succeeds on retry (skip_error=True)
    # index = 0 -> bool(0) == False, index = 1 -> bool(1) == True
    task1 = (
        TaskBuilder('TestTask1')
        .with_event(lambda t: raise_error(t, bool(next(index))))
        .with_retry(1, delay_seconds=0)
        .build()
    )

    # task2 depends on the success of task1 but task1 will fail once before succeeding
    task2 = (
        TaskBuilder('TestTask2')
        .with_event(lambda t: None)
        .with_wait_for(task1)
        .build()
    )

    # task3 depends on task2, creating a chain of dependencies
    task3 = (
        TaskBuilder('TestTask3')
        .with_event(lambda t: None)
        .with_wait_for(task2)
        .build()
    )

    app.add_tasks(task1, task2, task3)

    with qtbot.wait_signal(app.executor.callbacks.system_idle):
        app.start_workers()

    assert_task_completed(
        task1, [
            'inactive', 'waiting', 'running', 'retrying',
            'inactive', 'waiting', 'running', 'completed'
        ]
    )

    assert_task_completed(
        task2, [
            'inactive', 'waiting', 'blocked', 'waiting', 'running', 'completed'
        ]
    )

    assert_task_completed(
        task3, [
            'inactive', 'waiting', 'blocked', 'waiting', 'running', 'completed'
        ]
    )


def test_parallel_tasks_with_failures(qtbot: QtBot, app: TQManager):
    """
    Test that failing tasks don't affect unrelated parallel tasks.

    Creates three independent tasks with one failing task in the middle.
    Verifies that all tasks are executed and the failure of one task
    doesn't affect the execution of other unrelated tasks.
    """
    # Create a list to track execution order
    execution_order: list[str] = []

    # Create three independent tasks
    task1 = (
        TaskBuilder('SuccessTask1')
        .with_event(lambda t: execution_order.append('task1_executed'))
        .build()
    )

    task2 = (
        TaskBuilder('FailingTask')
        .with_event(lambda t: (
            execution_order.append('task2_executed'),
            raise_error(t, )))
        .build()
    )

    task3 = (
        TaskBuilder('SuccessTask2')
        .with_event(lambda t: execution_order.append('task3_executed'))
        .build()
    )

    app.add_tasks(task1, task2, task3)

    with qtbot.wait_signal(app.executor.callbacks.system_idle):
        app.start_workers()

    # Verify all tasks were executed
    assert 'task1_executed' in execution_order
    assert 'task2_executed' in execution_order
    assert 'task3_executed' in execution_order

    # Verify task states
    assert_task_completed(task1)
    assert_task_completed(task3)
    assert_task_failed(task2)


def test_retry_waits_for_policy_delay(qtbot: QtBot, app: TQManager):
    """Test that a nonzero retry delay is passed to the timer in milliseconds."""
    task = (
        TaskBuilder('DelayedTask')
        .with_event(raise_error)
        .with_retry(1, delay_seconds=3)
        .build()
    )

    app.add_tasks(task)

    with mock.patch.object(QTimer, 'singleShot') as single_shot:
        app.start_workers()
        qtbot.wait_until(lambda: task.state.is_retrying)

    single_shot.assert_called_once()
    assert single_shot.call_args[0][0] == 3000


def test_retry_cascades_to_failed_child(qtbot: QtBot, app: TQManager):
    """Test that retrying a failed parent also retries the child that failed with it."""
    index = count()

    parent = (
        TaskBuilder('Parent')
        .with_event(lambda t: raise_error(t, skip_error=bool(next(index))))
        .build()
    )
    child = (
        TaskBuilder('Child')
        .with_event(lambda t: None)
        .with_wait_for(parent)
        .build()
    )

    app.add_tasks(parent, child)
    app.start_workers()

    qtbot.wait_until(lambda: parent.state.is_failed)
    assert child.state.is_failed

    app.executor.retry_task(parent)
    qtbot.wait_until(lambda: child.state.is_completed or child.state.is_failed)

    assert parent.state.is_completed
    assert child.state.is_completed
    assert child.exception is None


def test_retry_cascades_to_failed_group(qtbot: QtBot, app: TQManager):
    """Test that retrying a failed group member also retries the group."""
    index = count()

    task = (
        TaskBuilder('Member')
        .with_event(lambda t: raise_error(t, skip_error=bool(next(index))))
        .build()
    )
    group = TaskGroupBuilder('Group').with_tasks(task).build()

    app.add_tasks(group)
    app.start_workers()

    qtbot.wait_until(lambda: group.state.is_failed)

    app.executor.retry_task(task)
    qtbot.wait_until(lambda: group.state.is_completed or group.state.is_failed)

    assert task.state.is_completed
    assert group.state.is_completed


@pytest.mark.xfail(strict=True, raises=AssertionError, reason='V56')
def test_callbacks_during_retries(qtbot: QtBot, app: TQManager):
    """
    Test that task callbacks are properly triggered during retry cycles.

    Creates a task with callbacks for all lifecycle events and verifies
    that on_start runs before the first execution and on main, and that
    on_completed and on_finish fire once, at the end of the retry cycle.
    """
    callback_sequence: list[str] = []
    main_thread = current_thread()
    on_start_threads: list[Thread] = []
    first_execution = Event()

    def record_callback(name: str):
        callback_sequence.append(name)

    def on_start(t: TaskExecutable):
        on_start_threads.append(current_thread())
        record_callback('on_start')

    def failing_task(task: TaskExecutable):
        callback_sequence.append('execute')
        first_execution.set()
        return next(counter) < 2

    counter = count()

    # Create a task with all possible callbacks
    task = (
        TaskBuilder('CallbackTask')
        .with_event(lambda t: failure_controller(t, fail_if=lambda: failing_task(t)))
        .with_retry(3, delay_seconds=0)
        .with_on_start(on_start)
        .with_on_failed(lambda t: record_callback('on_failed'))
        .with_on_completed(lambda t: record_callback('on_completed'))
        .with_on_finish(lambda t: record_callback('on_finish'))
        .build()
    )

    app.add_tasks(task)
    app.start_workers()

    # Hold the main thread so an on_start still queued behind the event cannot overtake it.
    assert first_execution.wait(timeout=5)

    qtbot.wait_until(lambda: task.state.is_completed or task.state.is_failed)

    # The expected sequence of callbacks:
    expected_sequence = [
        'on_start', 'execute', 'execute', 'execute', 'on_completed', 'on_finish'
    ]

    assert callback_sequence == expected_sequence
    assert on_start_threads == [main_thread]
