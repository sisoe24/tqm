from __future__ import annotations

from itertools import count

from pytestqt.qtbot import QtBot

from tqm import TQManager, TaskBuilder, exceptions

from ...utils import assert_task_failed, assert_task_completed


def test_predicate_blocks_task_execution(qtbot: QtBot, app: TQManager):
    """
    Test that a task with a failing predicate is blocked from execution.

    Verifies that:
    - A task with a predicate that returns False is never executed
    - The task is correctly placed in the deferred queue
    - The task state transitions to 'retrying' when the predicate fails
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


def test_predicate_for_task_with_parent(qtbot: QtBot, app: TQManager):
    """
    Test interaction between task predicates and parent task dependencies.

    Creates a parent task and a child task with a predicate. Verifies that
    both the parent dependency and the predicate must be satisfied for
    the child task to execute.
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
            delay_ms=100)
        .build()
    )

    task3 = (
        TaskBuilder('Task3')
        .with_event(lambda t: execution_order.append(t.name))
        .with_wait_for(task2)
        .build()
    )

    app.add_tasks(task1, task2, task3)

    with qtbot.wait_signal(app.executor.callbacks.system_idle):
        app.start_workers()

    assert execution_order == ['Task1', 'Task2', 'Task3']

    assert_task_completed(task1)

    # The task starts on waiting but is blocked due to the parent dependency.
    # Once the parent task completes, it transitions back to waiting.
    # The task is then blocked again due to the predicate condition and retries twice
    # (until counter == 3, first time is the block check and then the predicate checks)
    # before being unblocked, running, and completing successfully.
    assert_task_completed(
        task2,
        [
            'inactive',
            'waiting', 'blocked', 'waiting', 'blocked',
            'retrying', 'retrying', 'running', 'completed'
        ]
    )

    # task3 is blocked until task2 completes
    assert_task_completed(
        task3,
        ['inactive', 'waiting', 'blocked', 'waiting', 'running', 'completed']
    )
