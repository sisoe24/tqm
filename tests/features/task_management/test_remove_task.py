from __future__ import annotations

import pytest
from pytestqt.qtbot import QtBot

from tqm import (TQManager, TaskBuilder, TaskExecutable, TaskGroupBuilder,
                 exceptions)

from ...utils import SafeList, raise_error


def test_remove_single_task(qtbot: QtBot, app: TQManager):
    """Test removing a single task from the queue."""
    # Create a task
    task = (
        TaskBuilder('RemovableTask')
        .with_event(lambda t: None)
        .build()
    )

    # Add to task manager but don't start it
    app.add_tasks(task)

    # Verify task is in the queue but not started
    assert task in app.executor.get_all_tasks()
    assert task.state.is_waiting

    # Remove the task
    app.executor.remove_task(task)

    # Verify task is removed from the queue
    assert task not in app.executor.get_all_tasks()

    # Verify task state is deleted
    assert task.state.is_deleted


def test_remove_running_task_fails(qtbot: QtBot, app: TQManager):
    """Test that removing a running task raises an exception."""
    execution_reached = SafeList[bool]()

    def slow_task(t: TaskExecutable):
        # Mark that execution started
        execution_reached.append(True)
        # Wait for signal to continue
        qtbot.wait(100)  # Small delay

    # Create a task
    task = (
        TaskBuilder('SlowTask')
        .with_event(slow_task)
        .build()
    )

    # Add task and start execution
    app.add_tasks(task)
    app.start_workers()

    # Wait until task starts executing
    qtbot.wait_until(lambda: len(execution_reached) > 0)

    # Try to remove the task - should do nothing
    with pytest.raises(exceptions.TaskError):
        app.executor.remove_task(task)


def test_remove_task_with_dependencies(qtbot: QtBot, app: TQManager):
    """Test removing a task with dependent child tasks."""
    # Create a parent task
    parent_task = (
        TaskBuilder('ParentTask')
        .with_event(lambda t: None)
        .build()
    )

    # Create a child task dependent on parent
    child_task = (
        TaskBuilder('ChildTask')
        .with_event(lambda t: None)
        .with_wait_for(parent_task)
        .build()
    )

    # Add both tasks to manager
    app.add_tasks(parent_task)
    app.add_tasks(child_task)

    # Verify both tasks are in queue
    assert parent_task in app.executor.get_all_tasks()
    assert child_task in app.executor.get_all_tasks()

    # Remove the parent task - this should also remove the child task
    app.executor.remove_task(parent_task)

    # Verify both tasks are removed
    assert parent_task not in app.executor.get_all_tasks()
    assert child_task not in app.executor.get_all_tasks()

    # Verify both tasks have the correct state
    assert parent_task.state.is_deleted
    assert child_task.state.is_deleted


def test_remove_task_after_completion(qtbot: QtBot, app: TQManager):
    """Test removing a task after it has completed."""
    executed = SafeList[bool]()

    # Create a task
    task = (
        TaskBuilder('CompleteTask')
        .with_event(lambda t: executed.append(True))
        .build()
    )

    # Add task and execute
    app.add_tasks(task)

    # Start workers and wait for completion
    with qtbot.wait_signal(app.executor.callbacks.system_idle):
        app.start_workers()

    # Verify task executed and completed
    assert len(executed) == 1
    assert task.state.is_completed

    # Removing a completed task should do nothing
    app.executor.remove_task(task)
    assert task not in app.executor.get_all_tasks()


def test_remove_failed_task(qtbot: QtBot, app: TQManager):
    """Test removing a task that has failed."""
    # Create a task that will fail
    task = (
        TaskBuilder('FailingTask')
        .with_event(raise_error)
        .build()
    )

    # Add task and execute
    app.add_tasks(task)

    # Start workers and wait for completion
    with qtbot.wait_signal(app.executor.callbacks.system_idle):
        app.start_workers()

    # Verify task failed
    assert task.state.is_failed

    # Remove the task
    app.executor.remove_task(task)

    # Verify task is removed
    assert task not in app.executor.get_all_tasks()
    assert task.state.is_deleted


def test_remove_task_from_group(qtbot: QtBot, app: TQManager):
    """Test removing a task that belongs to a group."""

    # Create tasks
    task1 = (
        TaskBuilder('Task1')
        .with_event(lambda t: None)
        .build()
    )

    task2 = (
        TaskBuilder('Task2')
        .with_event(lambda t: None)
        .build()
    )
    # Create a group
    group = (
        TaskGroupBuilder('Group')
        .with_tasks(task1, task2)
        .build()
    )

    # Add group to manager
    app.add_tasks(group)
    # Before starting, check that both tasks are in the group
    assert task1 in group.tasks
    assert task2 in group.tasks

    # Try to remove task1 from the queue
    app.executor.remove_task(task1)

    # Verify task1 is removed from the group
    assert task1 not in group.tasks

    # # Start workers and verify remaining task completes
    with qtbot.wait_signal(app.executor.callbacks.system_idle):
        app.start_workers()

    # # Verify task2 executed and completed
    assert task2.state.is_completed
    assert group.state.is_completed


def test_remove_complex_dependency_chain(qtbot: QtBot, app: TQManager):
    """Test removing a task in a complex dependency chain."""
    # Create a linear chain of tasks: A -> B -> C -> D
    task_a = TaskBuilder('TaskA').with_event(lambda t: None).build()
    task_b = TaskBuilder('TaskB').with_event(lambda t: None).with_wait_for(task_a).build()
    task_c = TaskBuilder('TaskC').with_event(lambda t: None).with_wait_for(task_b).build()
    task_d = TaskBuilder('TaskD').with_event(lambda t: None).with_wait_for(task_c).build()

    # Create a parallel branch: A -> E
    task_e = TaskBuilder('TaskE').with_event(lambda t: None).with_wait_for(task_a).build()

    # Add all tasks to manager
    app.add_tasks(task_a, task_b, task_c, task_d, task_e)

    # Remove task_b - should also remove task_c and task_d
    app.executor.remove_task(task_b)

    # Task A and E should remain, B, C, D should be removed
    assert task_a in app.executor.get_all_tasks()
    assert task_e in app.executor.get_all_tasks()
    assert task_b not in app.executor.get_all_tasks()
    assert task_c not in app.executor.get_all_tasks()
    assert task_d not in app.executor.get_all_tasks()

    # Start workers and verify remaining tasks complete
    with qtbot.wait_signal(app.executor.callbacks.system_idle):
        app.start_workers()

    # Verify task_a and task_e completed
    assert task_a.state.is_completed
    assert task_e.state.is_completed

    # Verify other tasks are in deleted state
    assert task_b.state.is_deleted
    assert task_c.state.is_deleted
    assert task_d.state.is_deleted


def test_remove_all_tasks(qtbot: QtBot, app: TQManager):
    """Test removing all tasks from the queue."""
    # Create several tasks
    tasks = [
        TaskBuilder(f'Task{i}').with_event(lambda t: None).build()
        for i in range(5)
    ]

    # Add all tasks to manager
    app.add_tasks(*tasks)

    # Verify all tasks are in queue
    all_tasks = app.executor.get_all_tasks()
    assert all(task in all_tasks for task in tasks)

    # Remove all tasks
    for task in tasks.copy():  # Use copy to avoid modifying during iteration
        app.executor.remove_task(task)

    # Verify queue is empty
    assert len(app.executor.get_all_tasks()) == 0

    # Verify all tasks are in deleted state
    assert all(task.state.is_deleted for task in tasks)


def test_remove_and_add_same_task(qtbot: QtBot, app: TQManager):
    """Test removing a task and then trying to add it again."""
    # Create a task
    task = (
        TaskBuilder('ReusableTask')
        .with_event(lambda t: None)
        .build()
    )

    # Add to task manager
    app.add_tasks(task)

    # Verify task is in queue
    assert task in app.executor.get_all_tasks()

    # Remove the task
    app.executor.remove_task(task)

    # Verify task is removed
    assert task not in app.executor.get_all_tasks()

    # Try to add the same task again - should not raise TaskAlreadyInQueue
    app.add_tasks(task)

    assert task in app.executor.get_all_tasks()
