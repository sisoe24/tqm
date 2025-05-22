from __future__ import annotations

from pytestqt.qtbot import QtBot

from tqm import TQManager, TaskBuilder, TaskExecutable

from ...utils import (SafeList, raise_error, assert_task_failed,
                      assert_task_completed)


def test_add_task_with_parent_dependency(qtbot: QtBot, app: TQManager):
    """Test adding a task with a parent dependency. The child task should wait
    for the parent task to complete before execution."""

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
        .with_wait_for(task1)
        .build()
    )

    app.add_tasks(task2, task1)

    with qtbot.wait_signal(app.executor.callbacks.system_idle):
        app.start_workers()

    # task1 should be first
    assert execution_order[0] == 'TestTask1'
    assert execution_order[1] == 'TestTask2'

    assert_task_completed(task1)
    assert_task_completed(
        task2, ['inactive', 'waiting', 'blocked', 'waiting', 'running', 'completed']
    )


def test_add_task_with_failing_parent(qtbot: QtBot, app: TQManager):
    """Test adding a task with a parent that fails. The child task should also
    fail as a result of the parent's failure."""

    execution_order = SafeList[str]()

    def record_execution(task: TaskExecutable):
        execution_order.append(task.name)

    task1 = (
        TaskBuilder('TestTask1')
        .with_event(raise_error)
        .build()
    )
    task2 = (
        TaskBuilder('TestTask2')
        .with_event(record_execution)
        .with_wait_for(task1)
        .build()
    )

    app.add_tasks(task2, task1)

    with qtbot.wait_signal(app.executor.callbacks.system_idle):
        app.start_workers()

    # no task should be in the execution order
    assert len(execution_order) == 0

    assert_task_failed(task1)

    # task2 goes directly into failure mode if parent fails
    assert_task_failed(task2, ['inactive', 'waiting', 'blocked', 'failed'])


def test_unrelated_task_execution_with_failing_parent(qtbot: QtBot, app: TQManager):
    """Test adding a task with a failing parent and an unrelated task. The unrelated
    task should execute successfully, while the child task fails due to the parent's failure."""

    execution_order = SafeList[str]()

    def record_execution(task: TaskExecutable):
        execution_order.append(task.name)

    task1 = (
        TaskBuilder('TestTask1')
        .with_event(raise_error)
        .build()
    )
    task2 = (
        TaskBuilder('TestTask2')
        .with_event(record_execution)
        .with_wait_for(task1)
        .build()
    )
    task3 = (
        TaskBuilder('TestTask3')
        .with_event(record_execution)
        .build()
    )

    app.add_tasks(task2, task1, task3)

    with qtbot.wait_signal(app.executor.callbacks.system_idle):
        app.start_workers()

    assert len(execution_order) == 1
    assert execution_order[0] == 'TestTask3'

    assert_task_failed(task1)

    # task2 goes directly into failure mode if parent fails
    assert_task_failed(task2, ['inactive', 'waiting', 'blocked', 'failed'])

    assert_task_completed(task3)


def test_task_execution_with_parent_chain(qtbot: QtBot, app: TQManager):
    """Test adding a chain of tasks with parent dependencies. Each task in the chain
    should execute in the correct order after its parent completes."""

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
        .with_wait_for(task1)
        .build()
    )
    task3 = (
        TaskBuilder('TestTask3')
        .with_event(record_execution)
        .with_wait_for(task2)
        .build()
    )

    app.add_tasks(task2, task1, task3)

    with qtbot.wait_signal(app.executor.callbacks.system_idle):
        app.start_workers()

    assert execution_order[0] == 'TestTask1'
    assert execution_order[1] == 'TestTask2'
    assert execution_order[2] == 'TestTask3'

    assert_task_completed(task1)

    expected_history = ['inactive', 'waiting', 'blocked', 'waiting', 'running', 'completed']
    assert_task_completed(task2, expected_history)
    assert_task_completed(task3, expected_history)


def test_task_failure_in_parent_chain(qtbot: QtBot, app: TQManager):
    """Test adding a chain of tasks where the first task fails. All subsequent tasks
    in the chain should fail as a result."""

    execution_order = SafeList[str]()

    def record_execution(task: TaskExecutable):
        execution_order.append(task.name)

    task1 = (
        TaskBuilder('TestTask1')
        .with_event(raise_error)
        .build()
    )
    task2 = (
        TaskBuilder('TestTask2')
        .with_event(record_execution)
        .with_wait_for(task1)
        .build()
    )
    task3 = (
        TaskBuilder('TestTask3')
        .with_event(record_execution)
        .with_wait_for(task2)
        .build()
    )

    app.add_tasks(task2, task1, task3)

    with qtbot.wait_signal(app.executor.callbacks.system_idle):
        app.start_workers()

    assert not execution_order

    assert_task_failed(task1)

    expected_history = ['inactive', 'waiting', 'blocked', 'failed']
    assert_task_failed(task2, expected_history)
    assert_task_failed(task3, expected_history)


def test_partial_execution_with_failing_parent(qtbot: QtBot, app: TQManager):
    """Test adding a chain of tasks where the first task fails, but some tasks
    without dependencies execute successfully."""

    execution_order = SafeList[str]()

    def record_execution(task: TaskExecutable):
        execution_order.append(task.name)

    task1 = (
        TaskBuilder('TestTask1')
        .with_event(raise_error)
        .build()
    )
    task2 = (
        TaskBuilder('TestTask2')
        .with_event(record_execution)
        .build()
    )
    task3 = (
        TaskBuilder('TestTask3')
        .with_event(record_execution)
        .with_wait_for(task2)
        .build()
    )

    app.add_tasks(task2, task1, task3)

    with qtbot.wait_signal(app.executor.callbacks.system_idle):
        app.start_workers()

    assert execution_order[0] == 'TestTask2'
    assert execution_order[1] == 'TestTask3'

    assert_task_failed(task1)
    assert_task_completed(task2)
    assert_task_completed(task3, ['inactive', 'waiting', 'blocked',
                          'waiting', 'running', 'completed'])
