from __future__ import annotations

from unittest.mock import patch

import pytest
from PySide2.QtCore import Qt, QTimer
from pytestqt.qtbot import QtBot
from PySide2.QtWidgets import QTreeView, QStyleOptionProgressBar

from tqm import TQManager, TaskBuilder
from tqm._core.task import TaskGroup, TaskExecutable
from tqm._ui.ui_view_model import TaskTreeView
from tqm._core.task_builder import TaskGroupBuilder
from tqm._ui.progress_bar_delegate import (ProgressBarAnimator,
                                           ProgressBarDelegate,
                                           ProgressBarRenderer)

RANDINT = 'tqm._ui.progress_bar_delegate.random.randint'


@pytest.fixture
def tree_view(qtbot: QtBot) -> QTreeView:
    """Create a basic tree view for testing."""
    return QTreeView()


@pytest.fixture
def animator(tree_view: QTreeView):
    """Create a progress bar animator for testing."""
    return ProgressBarAnimator(tree_view)


@pytest.fixture
def renderer(qtbot: QtBot) -> ProgressBarRenderer:
    """Create a progress bar renderer for testing."""
    return ProgressBarRenderer()


@pytest.fixture
def delegate(tree_view: QTreeView) -> ProgressBarDelegate:
    """Create a progress bar delegate for testing."""
    return ProgressBarDelegate(progress_column=2, parent=tree_view)


@pytest.fixture
def pbar_option() -> QStyleOptionProgressBar:
    """Create a progress bar option for testing."""
    return QStyleOptionProgressBar()


@pytest.fixture
def task() -> TaskExecutable:
    """Create a basic task for testing."""
    return TaskBuilder('TestTask').build()


@pytest.fixture
def completed_task(task: TaskExecutable) -> TaskExecutable:
    """Create a completed task for testing."""
    task.state.set_completed()
    return task


@pytest.fixture
def failed_task(task: TaskExecutable) -> TaskExecutable:
    """Create a failed task for testing."""
    task.state.set_failed('Error')
    return task


@pytest.fixture
def task_group(qtbot: QtBot) -> TaskGroup:
    """Create a task group for testing."""
    group = TaskGroupBuilder('TestGroup').build()
    group.add_event(lambda t: None, label='Task1')
    group.add_event(lambda t: None, label='Task2')
    return group


class TestProgressBarAnimator:
    def test_animation_control(self, animator: ProgressBarAnimator):
        """Test starting and stopping animation."""
        timer = animator.findChild(QTimer)

        # Start animation
        animator.start_animation()
        assert timer.isActive()

        # Stop animation
        animator.stop_animation()
        assert not timer.isActive()

    def test_task_animation_values(self, animator: ProgressBarAnimator, task: TaskExecutable):
        """Test a task keeps its random offset."""
        with patch(RANDINT, side_effect=[10, 90]):
            assert animator.get_task_animation_value(task) == 10
            assert animator.get_task_animation_value(task) == 10

    def test_cleanup(self, animator: ProgressBarAnimator, task: TaskExecutable):
        """Test cleanup stops the timer and forgets the offsets."""
        animator.start_animation()

        with patch(RANDINT, side_effect=[10, 90]):
            animator.get_task_animation_value(task)
            animator.cleanup()
            assert animator.get_task_animation_value(task) == 90

        assert not animator.findChild(QTimer).isActive()


class TestProgressBarRenderer:
    @pytest.mark.parametrize('progress_value, expected_text', [
        (75, '75%'),
        (25, '25%'),
        (100, '100%')
    ])
    def test_determinate_progress_for_task(
        self,
        renderer: ProgressBarRenderer,
        pbar_option: QStyleOptionProgressBar,
        task: TaskExecutable,
        progress_value: int, expected_text: str
    ):
        """Test determinate progress configuration for tasks."""
        renderer.handle_determinate_progress(pbar_option, progress_value, task)
        assert pbar_option.progress == progress_value
        assert pbar_option.text == expected_text

    def test_determinate_progress_for_group(
        self,
        renderer: ProgressBarRenderer,
        pbar_option: QStyleOptionProgressBar,
        task_group: TaskGroup
    ):
        """Test determinate progress configuration for task groups."""
        renderer.handle_determinate_progress(pbar_option, 1, task_group)
        assert pbar_option.progress == 1
        assert pbar_option.text == '1/2'

    def test_indeterminate_progress(
        self,
        renderer: ProgressBarRenderer,
        pbar_option: QStyleOptionProgressBar,
        task: TaskExecutable
    ):
        """Test indeterminate progress configuration."""
        task.progress_bar.working_text = 'Processing...'
        renderer.handle_indeterminate_progress(pbar_option, 42, task)

        assert pbar_option.minimum == 0
        assert pbar_option.maximum == 100
        assert pbar_option.progress == 42
        assert pbar_option.text == 'Processing...'

    def test_completed_state(
        self,
        renderer: ProgressBarRenderer,
        pbar_option: QStyleOptionProgressBar,
        completed_task: TaskExecutable
    ):
        """Test completed state configuration."""
        renderer.handle_completed_state(pbar_option, completed_task, 100)
        assert pbar_option.text == 'Completed'
        assert pbar_option.maximum == completed_task.progress_bar.maximum

    def test_failed_state(
        self,
        renderer: ProgressBarRenderer,
        pbar_option: QStyleOptionProgressBar,
        failed_task: TaskExecutable
    ):
        """Test failed state configuration."""
        renderer.handle_completed_state(pbar_option, failed_task, 50)
        assert pbar_option.text == 'Failed'

    def test_group_state(
        self,
        renderer: ProgressBarRenderer,
        pbar_option: QStyleOptionProgressBar,
        task_group: TaskGroup
    ):
        """Test group state configuration."""
        task_group.state.set_running()
        renderer.handle_completed_state(pbar_option, task_group, 1)

        assert 'Group:' in pbar_option.text
        assert '1/2' in pbar_option.text


class TestProgressBarDelegate:
    def test_animation_control(self, delegate: ProgressBarDelegate, tree_view: QTreeView):
        """Test animation control methods."""
        timer = tree_view.findChild(QTimer)

        # Start animation
        delegate.start_animation()
        assert timer.isActive()

        # Stop animation
        delegate.stop_animation()
        assert not timer.isActive()

    def test_cleanup(self, delegate: ProgressBarDelegate, tree_view: QTreeView):
        """Test delegate cleanup stops the animation."""
        delegate.start_animation()
        delegate.cleanup()
        assert not tree_view.findChild(QTimer).isActive()

    def test_paint(self, app: TQManager, task_group: TaskGroup):
        """Test a real paint of every state: an exception in paint fails the test."""
        view = app.findChild(TaskTreeView)
        view.resize(800, 300)

        progress_column = view.get_column_index('Progress')
        view.setColumnWidth(progress_column, 300)

        determinate = TaskBuilder('Determinate').with_event(
            lambda t: None, show_progress=True
        ).build()
        indeterminate = TaskBuilder('Indeterminate').build()
        completed = TaskBuilder('Completed').build()
        failed = TaskBuilder('Failed').build()

        tasks = (determinate, indeterminate, completed, failed, task_group)
        for task in tasks:
            view.tasks_model.add_task(task)
        view.expandAll()

        determinate.state.set_running()
        indeterminate.state.set_running()
        completed.state.set_completed()
        failed.state.set_failed('Error')

        timer = view.findChild(ProgressBarAnimator).findChild(QTimer)
        assert not timer.isActive()

        def grab_progress(value: int):
            source = view.tasks_model.index(determinate.item.row(), progress_column)
            view.tasks_model.setData(source, value, Qt.DisplayRole)
            rect = view.visualRect(view.proxy_model.mapFromSource(source))
            return view.viewport().grab(rect).toImage()

        low = grab_progress(25)
        high = grab_progress(75)

        # right of the centered text: empty bar at 25%, filled bar at 75%
        x = low.width() * 6 // 10
        assert any(low.pixel(x, y) != high.pixel(x, y) for y in range(low.height()))

        # painting a running indeterminate task starts the animation
        view.grab()
        assert timer.isActive()
        view.stop_animation()
