from __future__ import annotations

from PySide2.QtCore import Qt
from pytestqt.qtbot import QtBot

from tqm import TQManager, TaskBuilder, TaskGroupBuilder

from ...utils import (SafeList, raise_error, assert_task_failed,
                      failure_controller, assert_task_completed)


def test_basic_group_creation(qtbot: QtBot, app: TQManager):
    """Test creating a task group and adding tasks to it."""

    execution_order = SafeList[str]()

    # Add tasks to the group
    task1 = (
        TaskBuilder('Task1')
        .with_event(lambda t: execution_order.append(t.name))
        .build()
    )

    task2 = (
        TaskBuilder('Task2')
        .with_event(lambda t: execution_order.append(t.name))
        .build()
    )
    group = (
        TaskGroupBuilder('TestGroup')
        .with_comment('Group comment')
        .with_tasks(task1, task2)
        .build()
    )

    # Add to task manager
    app.add_tasks(group)

    # Start workers and wait for completion
    with qtbot.wait_signal(app.executor.callbacks.system_idle):
        app.start_workers()

    # Verify both tasks were executed
    assert len(execution_order) == 2
    assert 'Task1' in execution_order
    assert 'Task2' in execution_order

    # Verify the tasks are associated with the group
    assert task1.group == group
    assert task2.group == group
    assert task1 in group.tasks
    assert task2 in group.tasks

    assert_task_completed(task1)
    assert_task_completed(task2)
    assert_task_completed(group)


def test_group_with_event_tasks(qtbot: QtBot, app: TQManager):
    """Test creating a group and adding tasks using add_event method."""
    execution_order = SafeList[str]()

    # Create a group directly
    with app.create_group('EventGroup') as group:
        # Add tasks with add_event inside the group context
        group.add_event(lambda t: execution_order.append(t.name), label='GroupTask1')
        group.add_event(lambda t: execution_order.append(t.name), label='GroupTask2')
        group.add_event(lambda t: execution_order.append(t.name), label='GroupTask3')

    # Start workers and wait
    with qtbot.wait_signal(app.executor.callbacks.system_idle):
        app.start_workers()

    # Verify all tasks were executed
    assert len(execution_order) == 3
    assert 'GroupTask1' in execution_order
    assert 'GroupTask2' in execution_order
    assert 'GroupTask3' in execution_order

    # Verify the group completed
    assert_task_completed(group)


def test_nested_groups(qtbot: QtBot, app: TQManager):
    """Test nested task groups hierarchy."""
    execution_order = SafeList[str]()

    # Create parent group
    parent_group = TaskGroupBuilder('ParentGroup') .build()

    # Create child group
    child_group = (
        TaskGroupBuilder('ChildGroup')
        .with_wait_for(parent_group)  # Make child wait for parent
        .build()
    )

    # Add tasks to parent group
    task1 = (
        TaskBuilder('ParentTask')
        .with_event(lambda t: execution_order.append(t.name))
        .build()
    )
    parent_group.add_tasks(task1)

    # Add tasks to child group
    task2 = (
        TaskBuilder('ChildTask')
        .with_event(lambda t: execution_order.append(t.name))
        .build()
    )
    child_group.add_tasks(task2)

    # Add both groups to the manager
    app.add_tasks(parent_group)
    app.add_tasks(child_group)

    # Start workers and wait
    with qtbot.wait_signal(app.executor.callbacks.system_idle):
        app.start_workers()

    # Verify execution order - parent group tasks should run before child group
    assert len(execution_order) == 2
    assert execution_order[0] == 'ParentTask'
    assert execution_order[1] == 'ChildTask'

    # Verify both groups completed
    assert_task_completed(parent_group)
    assert_task_completed(child_group, ['inactive', 'waiting',
                          'blocked', 'waiting', 'running', 'completed'])


def test_group_partial_failure(qtbot: QtBot, app: TQManager):
    """Test group with some failing tasks and some successful tasks."""
    execution_order = SafeList[str]()

    # Add successful tasks
    task1 = (
        TaskBuilder('SuccessTask1')
        .with_event(lambda t: execution_order.append(t.name))
        .build()
    )

    # Add failing task
    task2 = (
        TaskBuilder('FailingTask')
        .with_event(raise_error)
        .build()
    )

    # Add another successful task
    task3 = (
        TaskBuilder('SuccessTask2')
        .with_event(lambda t: execution_order.append(t.name))
        .build()
    )

    # Create group
    group = (
        TaskGroupBuilder('PartialFailureGroup')
        .with_tasks(task1, task2, task3)
        .build()
    )

    # Add group to manager
    app.add_tasks(group)

    # Start workers and wait
    with qtbot.wait_signal(app.executor.callbacks.system_idle):
        app.start_workers()

    # Verify successful tasks executed
    assert len(execution_order) == 2
    assert 'SuccessTask1' in execution_order
    assert 'SuccessTask2' in execution_order

    # Verify individual task states
    assert_task_completed(task1)
    assert_task_failed(task2)
    assert_task_completed(task3)

    assert_task_failed(group)


def test_group_callbacks(qtbot: QtBot, app: TQManager):
    """Test that group callbacks are correctly triggered."""
    callback_sequence: list[str] = []

    # Create a group with callbacks
    group = (
        TaskGroupBuilder('CallbackGroup')
        .with_on_start(lambda g: callback_sequence.append('group_start'))
        .with_on_completed(lambda g: callback_sequence.append('group_completed'))
        .with_on_finish(lambda g: callback_sequence.append('group_finish'))
        .build()
    )

    # Add tasks with callbacks
    task1 = (
        TaskBuilder('CallbackTask1')
        .with_event(lambda t: None)
        .with_on_start(lambda t: callback_sequence.append('task1_start'))
        .with_on_completed(lambda t: callback_sequence.append('task1_completed'))
        .with_on_finish(lambda t: callback_sequence.append('task1_finish'))
        .build()
    )

    task2 = (
        TaskBuilder('CallbackTask2')
        .with_event(lambda t: None)
        .with_on_start(lambda t: callback_sequence.append('task2_start'))
        .with_on_completed(lambda t: callback_sequence.append('task2_completed'))
        .with_on_finish(lambda t: callback_sequence.append('task2_finish'))
        .build()
    )

    # Add tasks to group
    group.add_tasks(task1, task2)

    # Add group to manager
    app.add_tasks(group)

    # Start workers and wait
    with qtbot.wait_signal(app.executor.callbacks.system_idle):
        app.start_workers()

    # Verify callback sequence
    assert 'group_start' in callback_sequence
    assert 'task1_start' in callback_sequence
    assert 'task2_start' in callback_sequence
    assert 'task1_completed' in callback_sequence
    assert 'task2_completed' in callback_sequence
    assert 'task1_finish' in callback_sequence
    assert 'task2_finish' in callback_sequence
    assert 'group_completed' in callback_sequence
    assert 'group_finish' in callback_sequence

    # The group callbacks should be at expected positions
    assert callback_sequence.index('group_start') < callback_sequence.index('task1_start')
    assert callback_sequence.index('task2_finish') < callback_sequence.index('group_completed')
    assert callback_sequence.index('group_completed') < callback_sequence.index('group_finish')


def test_group_progress_tracking(qtbot: QtBot, app: TQManager):
    """Test that group progress is correctly updated based on task completions."""
    # Create tasks with progress tracking
    task1 = (
        TaskBuilder('ProgressTask1')
        .with_event(lambda t: t.emit_progress(50))
        .build()
    )

    task2 = (
        TaskBuilder('ProgressTask2')
        .with_event(lambda t: t.emit_progress(75))
        .build()
    )

    # Create a group with these tasks
    group = (
        TaskGroupBuilder('ProgressGroup')
        .with_tasks(task1, task2)
        .build()
    )

    # Add group to manager
    app.add_tasks(group)

    # Start workers and wait
    with qtbot.wait_signal(app.executor.callbacks.system_idle):
        app.start_workers()

    assert group.item

    # XXX: this can fail if we change the columns order
    progress_column_index = 1

    progress_column_item = group.item.index().siblingAtColumn(progress_column_index)
    assert progress_column_item.data(Qt.DisplayRole) == 2  # 2 completed tasks

    # Verify task and group states
    assert_task_completed(task1)
    assert_task_completed(task2)
    assert_task_completed(group)


def test_group_with_retry(qtbot: QtBot, app: TQManager):
    """Test group with a task that needs retry."""
    execution_order = SafeList[str]()

    # Create a task that fails once then succeeds
    retry_task = (
        TaskBuilder('RetryTask')
        .with_event(lambda t: failure_controller(t, fail_count=1))
        .with_retry_failed(1)  # Allow one retry
        .build()
    )

    # Create regular task
    regular_task = (
        TaskBuilder('RegularTask')
        .with_event(lambda t: execution_order.append(t.name))
        .build()
    )

    # Create a group
    group = (
        TaskGroupBuilder('RetryGroup')
        .with_tasks(retry_task, regular_task)
        .build()
    )

    # Add group to manager
    app.add_tasks(group)

    # Start workers and wait
    with qtbot.wait_signal(app.executor.callbacks.system_idle):
        app.start_workers()

    # Verify retry behavior
    assert execution_order.to_list() == ['RegularTask']  # Only the regular task ran normally

    # Verify task states
    assert_task_completed(retry_task, [
        'inactive', 'waiting', 'running', 'inactive', 'waiting', 'running', 'completed'
    ])
    assert_task_completed(regular_task)
    assert_task_completed(group)
