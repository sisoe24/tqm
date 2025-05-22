from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from PySide2.QtGui import QPainter
from pytestqt.qtbot import QtBot
from PySide2.QtWidgets import (QTreeView, QApplication, QStyleOptionViewItem,
                               QStyleOptionProgressBar)

from tqm import TaskBuilder
from tqm._main import TQManager
from tqm._core.task import TaskGroup, TaskExecutable
from tqm._core.task_options import ProgressMode
from tqm._ui.progress_bar_delegate import (ProgressBarAnimator,
                                           ProgressBarDelegate,
                                           ProgressBarRenderer)


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
def view_option(qtbot: QtBot) -> QStyleOptionViewItem:
    """Create a view option for testing."""
    option = QStyleOptionViewItem()
    option.rect.setRect(0, 0, 100, 20)
    return option


@pytest.fixture
def pbar_option() -> QStyleOptionProgressBar:
    """Create a progress bar option for testing."""
    return QStyleOptionProgressBar()


@pytest.fixture
def task() -> TaskExecutable:
    """Create a basic task for testing."""
    return TaskBuilder('TestTask').build()


@pytest.fixture
def running_task(task: TaskExecutable) -> TaskExecutable:
    """Create a running task for testing."""
    task.state.set_running()
    return task


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
    with TQManager(app_name='test_app').create_group('TestGroup') as group:
        group.add_event(lambda t: None, label='Task1')
        group.add_event(lambda t: None, label='Task2')
    return group


class TestProgressBarAnimator:
    def test_initialization(self, animator: ProgressBarAnimator):
        """Test animator initializes with correct values."""
        assert animator._animation_counter == 0
        assert len(animator._task_offsets) == 0
        assert not animator._animation_timer.isActive()

    def test_animation_control(self, animator: ProgressBarAnimator):
        """Test starting and stopping animation."""
        # Start animation
        animator.start_animation()
        assert animator._animation_timer.isActive()

        # Stop animation
        animator.stop_animation()
        assert not animator._animation_timer.isActive()

    def test_animation_update(self, animator: ProgressBarAnimator):
        """Test animation counter updates correctly."""
        # Set up mock for viewport update
        parent_mock = MagicMock()
        parent_mock.viewport = MagicMock()
        animator._parent = parent_mock

        initial_counter = animator._animation_counter
        animator._update_animation()

        # Counter should advance by 3
        assert animator._animation_counter == (initial_counter + 3) % 200
        parent_mock.viewport().update.assert_called_once()

    def test_task_animation_values(self, animator: ProgressBarAnimator, task: TaskExecutable):
        """Test animation values for tasks."""
        # First call assigns an offset
        value1 = animator.get_task_animation_value(task)
        assert task.id in animator._task_offsets
        assert 0 <= value1 <= 100

        # Same task gets consistent values
        value2 = animator.get_task_animation_value(task)
        assert value1 == value2

        # Different tasks get different offsets
        task2 = TaskBuilder('AnotherTask').build()
        animator.get_task_animation_value(task2)
        assert animator._task_offsets[task.id] != animator._task_offsets[task2.id]

    def test_cleanup(self, animator: ProgressBarAnimator, task: TaskExecutable):
        """Test cleanup releases resources."""
        # Set up state
        animator.start_animation()
        animator.get_task_animation_value(task)
        assert animator._animation_timer.isActive()
        assert len(animator._task_offsets) > 0

        # Cleanup
        animator.cleanup()
        assert not animator._animation_timer.isActive()
        assert len(animator._task_offsets) == 0


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
    def test_initialization(self, delegate: ProgressBarDelegate):
        """Test delegate initializes correctly."""
        assert delegate.progress_column == 2
        assert isinstance(delegate._animator, ProgressBarAnimator)
        assert isinstance(delegate._renderer, ProgressBarRenderer)

    def test_animation_control(self, delegate: ProgressBarDelegate):
        """Test animation control methods."""
        # Start animation
        delegate.start_animation()
        assert delegate._animator._animation_timer.isActive()

        # Stop animation
        delegate.stop_animation()
        assert not delegate._animator._animation_timer.isActive()

    @patch.object(ProgressBarRenderer, 'handle_determinate_progress')
    @patch.object(QApplication, 'style')
    def test_paint_determinate_progress(
        self,
        mock_style,
        mock_handle,
        delegate: ProgressBarDelegate,
        view_option: QStyleOptionViewItem
    ):
        """Test painting determinate progress."""
        # Setup
        task = TaskBuilder('DeterminateTask').build()
        task.state.set_running()
        task.progress_bar.mode = ProgressMode.DETERMINATE

        index = MagicMock()
        index.data.return_value = 75
        painter = MagicMock(spec=QPainter)

        # Execute
        delegate.paint_progress_bar(painter, view_option, index, task)

        # Verify
        mock_handle.assert_called_once()
        mock_style.return_value.drawControl.assert_called_once()

    @patch.object(ProgressBarRenderer, 'handle_indeterminate_progress')
    @patch.object(ProgressBarAnimator, 'get_task_animation_value')
    @patch.object(ProgressBarAnimator, 'start_animation')
    @patch.object(QApplication, 'style')
    def test_paint_indeterminate_progress(
        self,
        mock_style,
        mock_start,
        mock_get_value,
        mock_handle,
        delegate: ProgressBarDelegate,
        view_option: QStyleOptionViewItem
    ):
        """Test painting indeterminate progress."""
        # Setup
        task = TaskBuilder('IndeterminateTask').build()
        task.state.set_running()
        task.progress_bar.mode = ProgressMode.INDETERMINATE
        mock_get_value.return_value = 42

        index = MagicMock()
        painter = MagicMock(spec=QPainter)

        # Execute
        delegate.paint_progress_bar(painter, view_option, index, task)

        # Verify
        mock_get_value.assert_called_once_with(task)
        mock_handle.assert_called_once()
        mock_start.assert_called_once()
        mock_style.return_value.drawControl.assert_called_once()

    @patch.object(ProgressBarRenderer, 'handle_completed_state')
    @patch.object(QApplication, 'style')
    def test_paint_completed_state(
        self,
        mock_style,
        mock_handle,
        delegate: ProgressBarDelegate,
        view_option: QStyleOptionViewItem,
        completed_task: TaskExecutable
    ):
        """Test painting completed task."""
        # Setup
        index = MagicMock()
        index.data.return_value = 100
        painter = MagicMock(spec=QPainter)

        # Execute
        delegate.paint_progress_bar(painter, view_option, index, completed_task)

        # Verify
        mock_handle.assert_called_once()
        mock_style.return_value.drawControl.assert_called_once()

    @patch('tqm._ui.progress_bar_delegate.ProgressBarDelegate.paint_progress_bar')
    def test_delegate_paint_dispatching(
        self, mock_paint_progress,
        delegate: ProgressBarDelegate,
        view_option: QStyleOptionViewItem
    ):
        """Test the delegate dispatches to correct paint method based on column."""
        # Setup
        task = TaskBuilder('TestTask').build()

        # Mock progress column index
        index = MagicMock()
        index.column.return_value = delegate.progress_column
        index.siblingAtColumn.return_value.data.return_value = task

        painter = MagicMock(spec=QPainter)

        # Execute
        delegate.paint(painter, view_option, index)

        # Verify
        mock_paint_progress.assert_called_once()

    def test_cleanup(self, delegate: ProgressBarDelegate):
        """Test delegate cleanup."""
        with patch.object(ProgressBarAnimator, 'cleanup') as mock_cleanup:
            delegate.cleanup()
            mock_cleanup.assert_called_once()
