from __future__ import annotations

import random
from uuid import UUID
from typing import TYPE_CHECKING, Dict

from PySide2.QtGui import QPainter, QPalette
from PySide2.QtCore import Qt, QTimer, QObject, QModelIndex
from PySide2.QtWidgets import (QStyle, QApplication, QStyledItemDelegate,
                               QStyleOptionViewItem, QStyleOptionProgressBar)

from .._core.task import TaskUnit, TaskGroup
from .._core.task_options import ProgressMode

if TYPE_CHECKING:
    from .ui_view_model import TaskTreeView


class ProgressBarAnimator(QObject):
    """Handles animation state for progress bars"""

    def __init__(self, parent: TaskTreeView) -> None:
        super().__init__(parent)
        self._parent = parent

        self._animation_counter = 0
        self._task_offsets: Dict[UUID, int] = {}

        self._animation_timer = QTimer(self)
        self._animation_timer.setInterval(50)  # 50ms = 20fps
        self._animation_timer.timeout.connect(self._update_animation)

    def start_animation(self) -> None:
        """Start the animation timer if not already running"""
        if not self._animation_timer.isActive():
            self._animation_timer.start()

    def stop_animation(self) -> None:
        """Stop the animation timer if running"""
        if self._animation_timer.isActive():
            self._animation_timer.stop()

    def _update_animation(self) -> None:
        """Update the animation counter on timer tick."""
        self._animation_counter = (self._animation_counter + 3) % 200
        self._parent.viewport().update()

    def get_task_animation_value(self, task: TaskUnit) -> int:
        """Get animation value for a specific task, with random offset for variety."""

        # Generate a random offset for this task if it doesn't exist
        if task.id not in self._task_offsets:
            self._task_offsets[task.id] = random.randint(0, 100)

        animation_value = (self._animation_counter + self._task_offsets[task.id]) % 200
        if animation_value > 100:
            animation_value = 200 - animation_value  # reverse direction after 100

        return animation_value

    def cleanup(self) -> None:
        """Stop timer and clear resources"""
        self.stop_animation()
        self._task_offsets.clear()


class ProgressBarRenderer:
    """Handles rendering logic for progress bars"""

    @staticmethod
    def handle_determinate_progress(
        pbar_options: QStyleOptionProgressBar,
        progress: int,
        task: TaskUnit
    ) -> None:
        """Configure progress bar options for determinate progress"""
        pbar_options.progress = progress

        if isinstance(task, TaskGroup):
            text = f"{progress}/{len(task.tasks)}"
        else:
            text = f"{progress}%"

        pbar_options.text = text

    @staticmethod
    def handle_indeterminate_progress(
        pbar_options: QStyleOptionProgressBar,
        animation_value: int,
        task: TaskUnit
    ) -> None:
        """Configure progress bar options for indeterminate progress"""
        pbar_options.minimum = 0
        pbar_options.maximum = 100
        pbar_options.progress = animation_value
        pbar_options.text = task.progress_bar.working_text

    @staticmethod
    def handle_completed_state(
        pbar_options: QStyleOptionProgressBar,
        task: TaskUnit,
        progress: int
    ) -> None:
        """Configure progress bar options for completed/inactive tasks"""
        text = task.state.current.title()
        color = task.state.color

        if isinstance(task, TaskGroup):
            text = f'Group: {text} - {progress}/{len(task.tasks)}'
            color = color.darker()

        if task.state.is_completed:
            pbar_options.maximum = task.progress_bar.maximum

        pbar_options.palette.setColor(QPalette.Base, color)
        pbar_options.text = text


class ProgressBarDelegate(QStyledItemDelegate):
    """A delegate that renders progress bars for tasks"""

    def __init__(self, progress_column: int, parent: TaskTreeView) -> None:
        super().__init__(parent)
        self.progress_column = progress_column

        self._animator = ProgressBarAnimator(parent)
        self._renderer = ProgressBarRenderer()

    def start_animation(self) -> None:
        """Start the animation timer"""
        self._animator.start_animation()

    def stop_animation(self) -> None:
        """Stop the animation timer"""
        self._animator.stop_animation()

    def paint_progress_bar(
        self,
        painter: QPainter,
        option: QStyleOptionViewItem,
        index: QModelIndex,
        task: TaskUnit
    ) -> None:
        """Paint the progress bar for a task"""
        pbar_options = QStyleOptionProgressBar()
        pbar_options.rect = option.rect
        pbar_options.textVisible = True

        pbar_options.minimum = task.progress_bar.minimum
        pbar_options.maximum = task.progress_bar.maximum

        progress = index.data()

        if task.state.is_running:
            if task.progress_bar.mode == ProgressMode.DETERMINATE:
                self._renderer.handle_determinate_progress(pbar_options, progress, task)
            else:
                animation_value = self._animator.get_task_animation_value(task)
                self._renderer.handle_indeterminate_progress(pbar_options, animation_value, task)
                # Start animation if not already running
                self._animator.start_animation()
        else:
            self._renderer.handle_completed_state(pbar_options, task, progress)

        QApplication.style().drawControl(QStyle.CE_ProgressBar, pbar_options, painter)

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex) -> None:
        task: TaskUnit = index.siblingAtColumn(0).data(Qt.UserRole)

        if index.column() == self.progress_column:
            self.paint_progress_bar(painter, option, index, task)
            return

        super().paint(painter, option, index)

    def cleanup(self) -> None:
        """Clean up resources and stop the animation timer"""
        self._animator.cleanup()
