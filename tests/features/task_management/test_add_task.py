from __future__ import annotations

import pytest
from pytestqt.qtbot import QtBot

from tqm import TQManager, TaskBuilder, TaskExecutable, exceptions

from ...utils import (SafeList, raise_error, assert_task_failed,
                      assert_task_completed)


def test_add_task_object(qtbot: QtBot, app: TQManager):
    """Test that a basic task executes successfully."""

    execution_order = SafeList[str]()

    def record_execution(task: TaskExecutable):
        execution_order.append(task.name)

    task = TaskBuilder('TestTask').with_event(record_execution).build()
    app.add_tasks(task)

    with qtbot.wait_signal(app.executor.callbacks.system_idle):
        app.start_workers()

    assert 'TestTask' in execution_order

    assert_task_completed(task)


def test_tasks_multiple_executions(qtbot: QtBot, app: TQManager):
    """Test that a multiple task objects are executes successfully."""

    execution_order = SafeList[str]()

    def record_execution(task: TaskExecutable):
        execution_order.append(task.name)

    task1 = (
        TaskBuilder('TestTask1')
        .with_event(record_execution)
        .build()
    )
    task2 = (
        TaskBuilder('TestTask2')
        .with_event(record_execution)
        .build()
    )

    app.add_tasks(task1, task2)

    with qtbot.wait_signal(app.executor.callbacks.system_idle):
        app.start_workers()

    assert 'TestTask1' in execution_order
    assert 'TestTask2' in execution_order

    assert_task_completed(task1)
    assert_task_completed(task2)


def test_tasks_execution_with_error(qtbot: QtBot, app: TQManager):
    """Test that a multiple task objects are executes but one fails."""

    execution_order = SafeList[str]()

    def record_execution(task: TaskExecutable):
        execution_order.append(task.name)

    task1 = (
        TaskBuilder('TestTask1')
        .with_event(record_execution)
        .build()
    )
    task2 = (
        TaskBuilder('TestTask2')
        .with_event(raise_error)
        .build()
    )

    app.add_tasks(task1, task2)

    with qtbot.wait_signal(app.executor.callbacks.system_idle):
        app.start_workers()

    assert len(execution_order) == 1
    assert execution_order[0] == 'TestTask1'
    assert 'TestTask2'not in execution_order

    assert_task_completed(task1)
    assert_task_failed(task2)


def test_tasks_execution_multiple_errors(qtbot: QtBot, app: TQManager):
    """Test that a multiple task objects are executes but all fail."""

    task1 = (
        TaskBuilder('TestTask1')
        .with_event(raise_error)
        .build()
    )
    task2 = (
        TaskBuilder('TestTask2')
        .with_event(raise_error)
        .build()
    )

    app.add_tasks(task1, task2)

    with qtbot.wait_signal(app.executor.callbacks.system_idle):
        app.start_workers()

    assert_task_failed(task1)
    assert_task_failed(task2)


def test_add_same_task_twice_raises(qtbot: QtBot, app: TQManager):
    """Test that a task already in the queue is rejected and still runs only once."""

    execution_order = SafeList[str]()

    task = (
        TaskBuilder('TestTask')
        .with_event(lambda t: execution_order.append(t.name))
        .build()
    )

    app.add_tasks(task)

    with pytest.raises(exceptions.TaskAlreadyInQueue):
        app.add_tasks(task)

    app.start_workers()
    qtbot.wait_until(lambda: task.state.is_completed)

    assert execution_order.to_list() == ['TestTask']
    assert_task_completed(task)
