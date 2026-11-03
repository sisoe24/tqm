from __future__ import annotations

from typing import Any, Set

import pytest
from PySide2.QtCore import Qt, QModelIndex, QItemSelectionModel
from pytestqt.qtbot import QtBot
from PySide2.QtWidgets import QLineEdit

from tqm import TQManager, TaskBuilder
from tqm._ui.ui_view_model import TaskTreeView

from ..utils import (raise_error, assert_task_failed, failure_controller,
                     assert_task_completed)


def find_row(view: TaskTreeView, name: str) -> QModelIndex:
    """Find the row of a task or a group child by its name."""
    model = view.model()
    flags = Qt.MatchExactly | Qt.MatchRecursive
    return model.match(model.index(0, 0), Qt.DisplayRole, name, 1, flags)[0]


def row_names(view: TaskTreeView) -> Set[str]:
    """Get the name of every visible row, group children included."""
    model = view.model()
    flags = Qt.MatchWildcard | Qt.MatchRecursive
    return {i.data() for i in model.match(model.index(0, 0), Qt.DisplayRole, '*', -1, flags)}


def cell_data(view: TaskTreeView, name: str, column: str) -> Any:
    return find_row(view, name).siblingAtColumn(view.get_column_index(column)).data()


def select_task(view: TaskTreeView, name: str):
    """Helper method for testing that selects the row of a task by its name."""
    index = find_row(view, name)
    view.selectionModel().select(index, QItemSelectionModel.Select | QItemSelectionModel.Rows)


def test_add_task_to_view(qtbot: QtBot, app: TQManager):
    """Test that a task is properly added to the view."""
    # Create a task
    task = TaskBuilder('ViewTask') .build()

    # Add to the task manager
    app.add_tasks(task)

    # Verify the task was added to the view
    assert task.item is not None
    assert row_names(app.findChild(TaskTreeView)) == {'ViewTask'}


def test_remove_task_from_view(qtbot: QtBot, app: TQManager):
    """Test that a task is properly removed from the view."""
    # Create and add a task
    task = TaskBuilder('RemoveTask').build()
    app.add_tasks(task)

    # Verify task is in view
    view = app.findChild(TaskTreeView)
    assert row_names(view) == {'RemoveTask'}

    # Remove the task
    app.remove_tasks(task)
    assert not row_names(view)


def test_selected_task_removal(qtbot: QtBot, app: TQManager):
    """Test removing a selected task."""
    # Create and add tasks
    task1 = TaskBuilder('Task1').build()
    task2 = TaskBuilder('Task2').build()
    app.add_tasks(task1, task2)

    # Select task1
    view = app.findChild(TaskTreeView)
    select_task(view, 'Task1')

    # Emit signal to remove selected tasks
    view.selected_task_removed.emit()

    # Verify only task1 was removed
    assert row_names(view) == {'Task2'}


def test_selected_multi_task_removal(qtbot: QtBot, app: TQManager):
    """Test removing a multiple selected task."""
    # Create and add tasks
    task1 = TaskBuilder('Task1').build()
    task2 = TaskBuilder('Task2').build()
    task3 = TaskBuilder('Task3').build()
    app.add_tasks(task1, task2, task3)

    view = app.findChild(TaskTreeView)
    select_task(view, 'Task1')
    select_task(view, 'Task2')

    # Emit signal to remove selected tasks
    view.selected_task_removed.emit()

    assert row_names(view) == {'Task3'}


def test_selected_child_task_removal(qtbot: QtBot, app: TQManager):
    """Test removing a selected task with its children."""
    # Create and add tasks
    task1 = TaskBuilder('Task1').build()
    task2 = TaskBuilder('Task2').with_wait_for(task1).build()
    task3 = TaskBuilder('Task3').with_wait_for(task2).build()
    task4 = TaskBuilder('Task4').build()
    app.add_tasks(task1, task2, task3, task4)

    # Select task1
    view = app.findChild(TaskTreeView)
    select_task(view, 'Task1')

    # Emit signal to remove selected tasks
    view.selected_task_removed.emit()

    assert row_names(view) == {'Task4'}


def test_update_task_progress(qtbot: QtBot, app: TQManager):
    """Test updating a task's progress."""
    # Create a task with progress
    task = TaskBuilder('ProgressTask') .build()

    # Add to task manager
    app.add_tasks(task)

    # Simulate progress update
    task.emit_progress(75)

    # Check progress value
    view = app.findChild(TaskTreeView)
    assert cell_data(view, 'ProgressTask', 'Progress') == 75, 'Progress should be updated to 75'


def test_clear_completed_tasks(qtbot: QtBot, app: TQManager):
    """Test clearing completed tasks."""
    # Create tasks
    completed_task = TaskBuilder('CompletedTask').with_event(lambda t: None).build()
    error_task = TaskBuilder('ErrorTask').with_event(raise_error).build()

    # Add tasks
    app.add_tasks(completed_task, error_task)

    app.start_workers()
    qtbot.wait_until(lambda: completed_task.state.is_completed and error_task.state.is_failed)

    # Clear completed tasks
    app.operations.clear_completed_tasks()

    assert row_names(app.findChild(TaskTreeView)) == {'ErrorTask'}


def test_clear_all_tasks(qtbot: QtBot, app: TQManager):
    """Test clearing all tasks."""
    # Create and add tasks
    task1 = TaskBuilder('Task1').build()
    task2 = TaskBuilder('Task2').build()
    app.add_tasks(task1, task2)

    # Clear all tasks
    app.operations.clear_all_tasks()

    # Verify all tasks were removed
    assert not row_names(app.findChild(TaskTreeView))


def test_clear_all_waiting_tasks(qtbot: QtBot, app: TQManager):
    """Test clearing all waiting tasks."""
    # Create and add tasks
    task1 = TaskBuilder('Task1').build()
    task2 = TaskBuilder('Task2').with_event(raise_error).build()
    app.add_tasks(task1, task2)

    app.start_workers()
    qtbot.wait_until(lambda: task2.state.is_failed and task1.state.is_completed)

    task3 = TaskBuilder('Task3').build()
    app.add_tasks(task3)

    # Clear all waiting tasks
    app.operations.clear_waiting_tasks()

    assert row_names(app.findChild(TaskTreeView)) == {'Task1', 'Task2'}


def test_clear_all_failed_tasks(qtbot: QtBot, app: TQManager):
    """Test clearing all failed tasks."""
    # Create and add tasks
    task1 = TaskBuilder('Task1').with_event(lambda t: None).build()
    task2 = TaskBuilder('Task2').with_event(raise_error).build()
    task3 = TaskBuilder('Task3').with_event(raise_error).build()
    app.add_tasks(task1, task2, task3)

    app.start_workers()
    qtbot.wait_until(
        lambda: task1.state.is_completed and task2.state.is_failed and task3.state.is_failed
    )

    # Clear all failed tasks
    app.operations.clear_failed_tasks()

    assert row_names(app.findChild(TaskTreeView)) == {'Task1'}


def test_ui_callbacks_on_task_state_changes(qtbot: QtBot, app: TQManager):
    """Test UI callbacks on task state changes."""
    # Create a task
    task = TaskBuilder('CallbackTask').with_event(lambda t: None).build()

    # Add to manager
    app.add_tasks(task)

    # Verify the task item has no start time initially
    view = app.findChild(TaskTreeView)
    assert cell_data(view, 'CallbackTask', 'Started') == '', 'Start time should be empty initially'
    assert cell_data(view, 'CallbackTask', 'Completed') == '', \
        'Completion time should be empty initially'

    app.start_workers()
    qtbot.wait_until(lambda: task.state.is_completed)

    # V19 covers which entry Started should be: test_started_column_shows_running_timestamp
    history = [entry.timestamp for entry in task.state.history]
    assert cell_data(view, 'CallbackTask', 'Started') in history

    assert cell_data(view, 'CallbackTask', 'Completed') == task.state.get_last().timestamp


@pytest.mark.xfail(strict=True, raises=AssertionError, reason='V19')
def test_started_column_shows_running_timestamp(qtbot: QtBot, app: TQManager):
    task = TaskBuilder('StartedTask').with_event(lambda t: None).build()
    app.add_tasks(task)

    app.start_workers()
    qtbot.wait_until(lambda: task.state.is_completed)

    running = [e.timestamp for e in task.state.history if e.active_state == 'running']
    assert cell_data(app.findChild(TaskTreeView), 'StartedTask', 'Started') == running[0]


def test_search_functionality(qtbot: QtBot, app: TQManager):
    """Test the search functionality."""
    # Create and add tasks with different names
    task1 = TaskBuilder('AppleTask').build()
    task2 = TaskBuilder('BananaTask').build()
    task3 = TaskBuilder('ChocolateTask').build()
    app.add_tasks(task1, task2, task3)

    # Set search filter
    search_bar = app.findChild(QLineEdit, 'TqmSearchBar')
    search_bar.setText('Apple')

    # Check that only AppleTask is visible
    view = app.findChild(TaskTreeView)
    assert row_names(view) == {'AppleTask'}, 'Only AppleTask should be visible'

    # Clear search
    search_bar.clear()

    # Verify all tasks are visible again
    assert row_names(view) == {'AppleTask', 'BananaTask', 'ChocolateTask'}


def test_task_group_progress_tracking(qtbot: QtBot, app: TQManager):
    """Test task group progress tracking in UI."""
    # Create a task group
    with app.create_group('ProgressGroup') as group:
        group.add_event(lambda t: None, label='GroupTask1')
        group.add_event(raise_error, label='GroupTask2')

    # Complete one task
    app.start_workers()
    qtbot.wait_until(lambda: group.state.is_failed)

    # Verify group progress shows 1/2 completed
    view = app.findChild(TaskTreeView)
    assert cell_data(view, 'ProgressGroup', 'Progress') == 1, \
        'Group progress should show 1 completed task'


def test_task_group_remove(qtbot: QtBot, app: TQManager):
    """Test task group should be removed if no has no tasks tracking in UI."""
    # Create a task group
    task1 = TaskBuilder('Task1').with_event(lambda t: None).build()
    task2 = TaskBuilder('Task2').with_event(lambda t: None).with_wait_for(task1).build()
    task3 = TaskBuilder('Task3').with_event(lambda t: None).with_wait_for(task2).build()
    task4 = TaskBuilder('Task4').with_event(lambda t: None).build()

    with app.create_group('ProgressGroup') as group:
        group.add_tasks(task1, task2, task3)

    app.add_tasks(task4)

    # Complete every task
    app.start_workers()
    qtbot.wait_until(lambda: group.state.is_completed and task4.state.is_completed)

    view = app.findChild(TaskTreeView)

    select_task(view, 'Task1')

    selected_items = view.get_selected_items()
    assert [item.data(Qt.UserRole).name for item in selected_items] == ['Task1']

    view.selected_task_removed.emit()

    assert row_names(view) == {'Task4'}


def test_retry_selected_task(qtbot: QtBot, app: TQManager):
    """Test retrying the selected failed task leaves other failed tasks alone."""
    task = (
        TaskBuilder('SelectedTask')
        .with_event(lambda t: failure_controller(t, fail_count=1))
        .build()
    )
    other = TaskBuilder('OtherTask').with_event(raise_error).build()
    app.add_tasks(task, other)

    app.start_workers()
    qtbot.wait_until(lambda: task.state.is_failed and other.state.is_failed)

    view = app.findChild(TaskTreeView)
    select_task(view, 'SelectedTask')

    # Emit signal to retry
    view.selected_task_retried.emit(task)
    qtbot.wait_until(lambda: task.state.is_completed)

    assert_task_completed(task, [
        'inactive', 'waiting', 'running', 'failed',
        'inactive', 'waiting', 'running', 'completed',
    ])
    assert_task_failed(other)


def test_retry_all_failed(qtbot: QtBot, app: TQManager):
    """Test retrying all failed tasks."""
    # Create tasks
    task1 = TaskBuilder('Task1').with_event(lambda t: None).build()
    task2 = TaskBuilder('Task2').with_event(raise_error).build()
    task3 = TaskBuilder('Task3').with_event(
        lambda t: failure_controller(t, fail_count=1)
    ).build()

    # Add tasks
    app.add_tasks(task1, task2, task3)

    app.start_workers()
    qtbot.wait_until(
        lambda: task1.state.is_completed and task2.state.is_failed and task3.state.is_failed
    )

    # A retried task stops being failed before this call returns
    app.operations.retry_all_failed()
    qtbot.wait_until(lambda: task2.state.is_failed and task3.state.is_completed)

    assert_task_completed(task1)
    assert_task_failed(task2, [
        'inactive', 'waiting', 'running', 'failed',
        'inactive', 'waiting', 'running', 'failed',
    ])
    assert_task_completed(task3, [
        'inactive', 'waiting', 'running', 'failed',
        'inactive', 'waiting', 'running', 'completed',
    ])
