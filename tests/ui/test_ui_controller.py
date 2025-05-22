from __future__ import annotations

from typing import Optional

from PySide2.QtCore import Qt, QItemSelectionModel
from pytestqt.qtbot import QtBot

from tqm import TQManager, TaskBuilder
from tqm._ui.ui_view_model import TaskTreeView

from ..utils import (raise_error, assert_task_failed, failure_controller,
                     assert_task_completed)


def select_task(view: TaskTreeView, row_index: int, child_index: Optional[int] = None):
    """Helper method for testing that selects a specific row.

    Args:
        view: The TreeView containing the tasks
        row_index: The row index of the task or group
        child_index: If provided, selects a child task within a group at the given row_index
    """
    if child_index is None:
        # Select a top-level task
        index = view.proxy_model.index(row_index, 0)
    else:
        # Select a child task within a group
        parent_index = view.proxy_model.index(row_index, 0)
        index = view.proxy_model.index(child_index, 0, parent_index)

    view.selectionModel().select(index, QItemSelectionModel.Select | QItemSelectionModel.Rows)


def test_add_task_to_view(qtbot: QtBot, app: TQManager):
    """Test that a task is properly added to the view."""
    # Create a task
    task = TaskBuilder('ViewTask') .build()

    # Add to the task manager
    app.add_tasks(task)

    # Verify the task was added to the view
    assert task.item is not None
    assert task in app._controller.get_all_tasks()


def test_remove_task_from_view(qtbot: QtBot, app: TQManager):
    """Test that a task is properly removed from the view."""
    # Create and add a task
    task = TaskBuilder('RemoveTask').build()
    app.add_tasks(task)

    # Verify task is in view
    assert task.item is not None

    # Remove the task
    app.remove_tasks(task)
    assert task not in app._controller.get_all_tasks()


def test_selected_task_removal(qtbot: QtBot, app: TQManager):
    """Test removing a selected task."""
    # Create and add tasks
    task1 = TaskBuilder('Task1').build()
    task2 = TaskBuilder('Task2').build()
    app.add_tasks(task1, task2)

    # Select task1
    view = app._view.tree_view
    select_task(view, 1)

    # Emit signal to remove selected tasks
    view.selected_task_removed.emit()

    # Verify task1 was removed
    assert task1 not in app._controller.get_all_tasks()

    # Verify task1 was not removed
    assert task2 in app._controller.get_all_tasks()


def test_selected_multi_task_removal(qtbot: QtBot, app: TQManager):
    """Test removing a multiple selected task."""
    # Create and add tasks
    task1 = TaskBuilder('Task1').build()
    task2 = TaskBuilder('Task2').build()
    app.add_tasks(task1, task2)

    # Select task1
    view = app._view.tree_view
    select_task(view, 0)
    select_task(view, 1)

    # Emit signal to remove selected tasks
    view.selected_task_removed.emit()

    assert task1 not in app._controller.get_all_tasks()
    assert task2 not in app._controller.get_all_tasks()


def test_selected_child_task_removal(qtbot: QtBot, app: TQManager):
    """Test removing a selected task with its children."""
    # Create and add tasks
    task1 = TaskBuilder('Task1').build()
    task2 = TaskBuilder('Task2').with_wait_for(task1).build()
    task3 = TaskBuilder('Task3').with_wait_for(task2).build()
    task4 = TaskBuilder('Task4').build()
    app.add_tasks(task1, task2, task3, task4)

    # Select task1
    view = app._view.tree_view
    first_task_index = 3
    select_task(view, first_task_index)

    # Emit signal to remove selected tasks
    view.selected_task_removed.emit()

    all_tasks = app._controller.get_all_tasks()

    assert task1 not in all_tasks
    assert task2 not in all_tasks
    assert task3 not in all_tasks
    assert task4 in all_tasks


def test_update_task_progress(qtbot: QtBot, app: TQManager):
    """Test updating a task's progress."""
    # Create a task with progress
    task = TaskBuilder('ProgressTask') .build()

    # Add to task manager
    app.add_tasks(task)

    # Simulate progress update
    task.emit_progress(75)

    # Verify progress was updated in view
    model = app._view.tree_view.tasks_model
    progress_column = model.columns['Progress']

    tasks = app._controller.get_all_tasks()
    assert tasks, 'Ui should contain one task'

    task_item = task.item
    assert task_item, 'Task object should have an item assigned'

    # Check progress value
    progress_item = model.item(task_item.row(), progress_column)
    assert progress_item.data(Qt.DisplayRole) == 75, 'Progress should be updated to 75'


def test_clear_completed_tasks(qtbot: QtBot, app: TQManager):
    """Test clearing completed tasks."""
    # Create tasks
    completed_task = TaskBuilder('CompletedTask').with_event(lambda t: None).build()
    error_task = TaskBuilder('ErrorTask').with_event(raise_error).build()

    # Add tasks
    app.add_tasks(completed_task, error_task)

    with qtbot.wait_signal(app.executor.callbacks.system_idle):
        app.start_workers()

    # Clear completed tasks
    app._controller.ops.clear_completed_tasks()

    all_tasks = app._controller.get_all_tasks()
    assert completed_task not in all_tasks
    assert error_task in all_tasks


def test_clear_all_tasks(qtbot: QtBot, app: TQManager):
    """Test clearing all tasks."""
    # Create and add tasks
    task1 = TaskBuilder('Task1').build()
    task2 = TaskBuilder('Task2').build()
    app.add_tasks(task1, task2)

    # Clear all tasks
    app._controller.ops.clear_all_tasks()

    # Verify all tasks were removed
    assert not app._controller.get_all_tasks()


def test_clear_all_waiting_tasks(qtbot: QtBot, app: TQManager):
    """Test clearing all waiting tasks."""
    # Create and add tasks
    task1 = TaskBuilder('Task1').build()
    task2 = TaskBuilder('Task2').build()
    app.add_tasks(task1, task2)

    # Clear all waiting tasks
    app._controller.ops.clear_waiting_tasks()

    # Verify all tasks were removed
    assert not app._controller.get_all_tasks()


def test_clear_all_failed_tasks(qtbot: QtBot, app: TQManager):
    """Test clearing all failed tasks."""
    # Create and add tasks
    task1 = TaskBuilder('Task1').build()
    task2 = TaskBuilder('Task2').with_event(raise_error).build()
    task3 = TaskBuilder('Task3').with_event(raise_error).build()
    app.add_tasks(task1, task2, task3)

    with qtbot.wait_signal(app.executor.callbacks.system_idle):
        app.start_workers()

    # Clear all tasks
    app._controller.ops.clear_failed_tasks()

    # Verify all tasks were removed
    all_tasks = app._controller.get_all_tasks()
    assert task1 in all_tasks
    assert task2 not in all_tasks
    assert task3 not in all_tasks


def test_ui_callbacks_on_task_state_changes(qtbot: QtBot, app: TQManager):
    """Test UI callbacks on task state changes."""
    # Create a task
    task = TaskBuilder('CallbackTask').build()

    # Add to manager
    app.add_tasks(task)

    # Verify the task item has no start time initially
    model = app._view.tree_view.tasks_model
    started_column = model.columns['Started']
    completed_column = model.columns['Completed']

    row = 0
    assert model.item(row, started_column).text() == '', 'Start time should be empty initially'
    assert model.item(row, completed_column).text(
    ) == '', 'Completion time should be empty initially'

    app.start_workers()

    # Start the task
    with qtbot.wait_signal(app.executor.callbacks.runner_completed):
        task.state.set_completed()

    # Verify start time was updated
    assert model.item(row, started_column).text() != '', 'Start time should be set'

    # # Verify completion time was updated
    assert model.item(row, completed_column).text() != '', 'Completion time should be set'


def test_search_functionality(qtbot: QtBot, app: TQManager):
    """Test the search functionality."""
    # Create and add tasks with different names
    task1 = TaskBuilder('AppleTask').build()
    task2 = TaskBuilder('BananaTask').build()
    task3 = TaskBuilder('ChocolateTask').build()
    app.add_tasks(task1, task2, task3)

    # Set search filter
    app._view.toolbar.search_bar.setText('Apple')

    # Check that only AppleTask is visible
    view = app._view.tree_view
    assert view.proxy_model.rowCount() == 1, 'Only one task should be visible'

    visible_task = view.proxy_model.index(0, 0).data(Qt.UserRole)
    assert visible_task == task1, 'Only AppleTask should be visible'

    # Clear search
    app._view.toolbar.search_bar.clear()

    # Verify all tasks are visible again
    assert view.proxy_model.rowCount() == 3, 'All tasks should be visible'


def test_task_group_progress_tracking(qtbot: QtBot, app: TQManager):
    """Test task group progress tracking in UI."""
    # Create a task group
    with app.create_group('ProgressGroup') as group:
        task1 = group.add_event(lambda t: None, label='GroupTask1')
        task2 = group.add_event(raise_error, label='GroupTask2')

    # Complete one task
    with qtbot.wait_signal(app.executor.callbacks.system_idle):
        app.start_workers()

    # Verify group progress shows 1/2 completed
    model = app._view.tree_view.tasks_model
    progress_column = model.columns['Progress']

    # Find the group row
    group_row = 0  # Assuming it's the first row
    group_item = model.item(group_row, progress_column)
    group_progress = group_item.data(Qt.DisplayRole)

    assert group_progress == 1, 'Group progress should show 1 completed task'


def test_task_group_remove(qtbot: QtBot, app: TQManager):
    """Test task group should be removed if no has no tasks tracking in UI."""
    # Create a task group
    task1 = TaskBuilder('Task1').build()
    task2 = TaskBuilder('Task2').with_wait_for(task1).build()
    task3 = TaskBuilder('Task3').with_wait_for(task2).build()
    task4 = TaskBuilder('Task4').build()

    # group is index 1
    with app.create_group('ProgressGroup') as group:
        group.add_tasks(task1, task2, task3)

    # task4 is index 0 because is the last added
    app.add_tasks(task4)

    # Complete one task
    with qtbot.wait_signal(app.executor.callbacks.system_idle):
        app.start_workers()

    view = app._view.tree_view

    select_task(view, 1, 2)

    selected_tasks = app._controller.get_selected_tasks()
    assert selected_tasks, 'Should have a selected task'

    task = selected_tasks[0]
    assert task.item, 'Task should have a QStandardItem assigned'
    assert task.name == 'Task1', 'Must selected Task1'

    app._controller._on_remove_selected_tasks()

    all_tasks = app._controller.get_all_tasks()

    assert len(all_tasks) == 1
    assert group not in all_tasks
    assert task1 not in all_tasks
    assert task2 not in all_tasks
    assert task3 not in all_tasks
    assert task4 in all_tasks


def test_retry_failed_task(qtbot: QtBot, app: TQManager):
    """Test retrying a failed task."""
    # Create a task that will be marked as failed
    failed_task = (
        TaskBuilder('FailedTask')
        .with_event(raise_error)
        .with_retry_failed(1)  # Allow one retry
        .build()
    )

    # Add to manager
    app.add_tasks(failed_task)

    # Mark as failed
    failed_task.state.set_failed('Test failure')

    # Select the failed task
    view = app._view.tree_view
    select_task(view, 0)

    # Emit signal to retry
    view.selected_task_retried.emit(failed_task)

    # # Verify task state was reset
    assert failed_task.state.is_waiting or failed_task.state.is_running, \
        'Failed task should be reset to waiting or running state'


def test_retry_failed_task(qtbot: QtBot, app: TQManager):
    """Test retrying a failed task."""
    """Test clearing completed tasks."""
    # Create tasks
    task1 = TaskBuilder('Task1').build()
    task2 = TaskBuilder('Task2').with_event(raise_error).build()
    task3 = TaskBuilder('Task3').with_event(
        lambda t: failure_controller(t, fail_count=1)
    ).build()

    # Add tasks
    app.add_tasks(task1, task2, task3)

    with qtbot.wait_signal(app.executor.callbacks.system_idle):
        app.start_workers()

    # Clear completed tasks
    with qtbot.wait_signal(app.executor.callbacks.system_idle):
        app._controller.ops.retry_all_failed()

    assert_task_completed(task1)
    assert_task_failed(task2, [
        'inactive', 'waiting', 'running', 'failed',
        'inactive', 'waiting', 'running', 'failed',
    ])
    assert_task_completed(task3, [
        'inactive', 'waiting', 'running', 'failed',
        'inactive', 'waiting', 'running', 'completed',
    ])
