from __future__ import annotations

import contextlib
from typing import Any, List, Iterable, Optional
from pathlib import Path

from PySide2.QtCore import Qt, Slot, Signal, QObject
from PySide2.QtWidgets import QInputDialog

from .._core.task import TaskUnit, TaskGroup, TaskExecutable
from .ui_view_model import TaskManagerView
from ..exceptions import TaskError
from .._core.settings import open_settings
from .._core.task_executor import TaskExecutor


class _TaskButtonsController(QObject):
    """The buttons controller for the tasks widget.

    The buttons controller is responsible for handling the signals emitted by the buttons.

    Signals:
        remove_task: Signal emitted when the remove task button is clicked.
        retry_task: Signal emitted when the retry task button is clicked.
        start_workers: Signal emitted when the run all tasks button is clicked.

    """

    max_workers_updated = Signal(int)

    def __init__(
        self,
        view: TaskManagerView,
        executor: TaskExecutor,
        controller: TaskManagerController,
        settings_path: Path,
        parent: Optional[QObject] = None
    ) -> None:
        super().__init__(parent)

        self._view = view
        self._executor = executor
        self._controller = controller
        self._settings_path = settings_path

        view.toolbar.retry_all_btn.clicked.connect(self.retry_all_failed)

        clear_tasks = self._view.toolbar.clear_tasks
        clear_tasks.completed_tasks_removed.connect(self.clear_completed_tasks)
        clear_tasks.failed_tasks_removed.connect(self.clear_failed_tasks)
        clear_tasks.waiting_tasks_removed.connect(self.clear_waiting_tasks)
        clear_tasks.all_tasks_removed.connect(self.clear_all_tasks)

        table_ops = self._view.toolbar.table_options
        table_ops.reset_layout.triggered.connect(self.reset_layout)
        table_ops.resize_columns.triggered.connect(self.resize_columns)
        table_ops.expand_all.triggered.connect(self._view.tree_view.expandAll)
        table_ops.set_max_workers.triggered.connect(self.set_max_workers)

    @Slot()
    def set_max_workers(self, value: int = 0) -> None:
        """
        Sets the maximum number of workers for the application.

        If a value is provided, it emits a signal to update the maximum workers
        and optionally stores the value. If no value is provided, it prompts the
        user for a new value, starting from the executor's current maximum.

        Args:
            value (int, optional): The number of workers to set. 0 asks the user.

        Emits:
            max_workers_updated (int): Signal emitted with the new value.

        """
        if not value:
            value, ok = QInputDialog.getInt(
                self._view, 'Set Max Workers',
                'Enter the number of workers (min 2)',
                value=self._executor.max_workers, minValue=2
            )
            if not ok:
                return

        value = max(2, value)
        self.max_workers_updated.emit(value)

        with open_settings('w', json_file_path=self._settings_path) as s:
            s.max_workers = value

    @Slot()
    def reset_layout(self) -> None:
        self._view.tree_view.reset_table_state()

    @Slot()
    def resize_columns(self) -> None:
        for i in range(self._view.tree_view.tasks_model.columnCount()):
            self._view.tree_view.setColumnWidth(i, 250)

    @Slot()
    def retry_all_failed(self) -> None:
        for task in self._controller.get_all_tasks():
            if task.state.is_failed:
                self._executor.retry_task(task)

    @Slot()
    def clear_completed_tasks(self) -> None:
        self._controller.remove_tasks(t for t in self._controller.get_all_tasks() if t.state.is_completed)

    @Slot()
    def clear_failed_tasks(self) -> None:
        self._controller.remove_tasks(t for t in self._controller.get_all_tasks() if t.state.is_failed)

    @Slot()
    def clear_waiting_tasks(self) -> None:
        self._controller.remove_tasks(t for t in self._controller.get_all_tasks() if t.state.is_waiting)

    @Slot()
    def clear_all_tasks(self) -> None:
        self._controller.remove_tasks(self._controller.get_all_tasks())


class TaskManagerController(QObject):
    def __init__(
        self,
        view: TaskManagerView,
        executor: TaskExecutor,
        settings_path: Path,
        parent: Optional[QObject] = None
    ) -> None:
        super().__init__(parent)

        self.view = view
        self._executor = executor

        view.toolbar.run_all_tasks.clicked.connect(executor.start_workers)

        executor.callbacks.task_added.connect(self.add_task)
        executor.callbacks.task_finished.connect(self._on_task_finished)
        executor.callbacks.runner_completed.connect(self._on_task_completed)
        executor.callbacks.runner_started.connect(self._on_task_started)
        executor.callbacks.task_removed.connect(self.remove_task)
        executor.callbacks.task_progress_updated.connect(self._on_task_update_progress)
        executor.callbacks.task_logged.connect(
            lambda task, text: self._update_item_data(task, 'Last message', text.partition('\n')[0])
        )

        self.ops = _TaskButtonsController(self.view, executor, self, settings_path, self)

        self.view.tree_view.selected_task_removed.connect(self._on_remove_selected_tasks)
        self.view.tree_view.selected_task_retried.connect(self._on_retry_selected)
        self.view.tree_view.selected_task_cancelled.connect(self._on_cancel_selected)

    def _update_item_data(
        self,
        task: TaskUnit,
        column_name: str,
        value: Any,
        role: Qt.ItemDataRole = Qt.DisplayRole
    ) -> None:
        """Set data to a task item."""
        if not task.item:
            return

        parent = task.item.parent()
        item = parent.child if parent else self.view.tree_view.tasks_model.item
        column = self.view.tree_view.get_column_index(column_name)
        item(task.item.row(), column).setData(value, role)

    @Slot(object, int)
    def _on_task_update_progress(self, task: TaskUnit, value: float) -> None:
        """Update the progress bar of a task."""
        self._update_item_data(task, 'Progress', round(value, 2))

    @Slot(object)
    def _on_task_completed(self, task: TaskExecutable, *args: Any, **kwargs: Any) -> None:
        self._on_task_update_progress(task, task.progress_bar.maximum)
        self._update_item_data(task, 'Completed', task.state.get_last().timestamp)

    @Slot(object)
    def _on_task_finished(self, task: TaskUnit) -> None:
        if not isinstance(task, TaskExecutable):
            return

        group = task.group
        if not group:
            return

        completed_tasks = len(list(filter(lambda t: t.state.is_completed, group.tasks)))
        self._update_item_data(group, 'Progress', completed_tasks)

    @Slot(object)
    def _on_task_started(self, task: TaskUnit) -> None:
        self._update_item_data(task, 'Started', task.state.get_last().timestamp)

    @Slot(object)
    def _on_retry_selected(self, task: TaskUnit) -> None:
        if task.state.is_retryable:
            self._executor.retry_task(task)

    def add_task(self, task: TaskUnit) -> None:
        task.item = self.view.tree_view.tasks_model.add_task(task)

    def remove_task(self, task: TaskUnit) -> None:
        """
        Removes a task from the tasks model and its associated tree view.

        Args:
            task (TqmTaskUnit): The task to be removed. It must have an associated
                item in the tree view.

        Behavior:
            - If the task has no associated item (`task.item` is None), the method
              returns immediately without performing any action.
            - If the task's item has a parent group (`group_parent`), the task's
              item is removed from its parent group. The executor removes a group
              left empty.
            - If the task's item does not have a parent group, it is removed
              directly from the tasks model.
        """
        if not task.item:
            return

        remove_row = task.item.row()

        group_parent = task.item.parent()

        if group_parent:
            group_parent.removeRow(remove_row)
            group = task.group
            group.progress_bar.maximum = len(group.tasks)
            self._on_task_finished(task)
        else:
            self.view.tree_view.tasks_model.removeRow(remove_row)

    @Slot()
    def _on_cancel_selected(self) -> None:
        for task in self.get_selected_tasks():
            self._executor.cancel_task(task)
            # The task stays running until its callable returns.
            if task.state.is_running:
                self._update_item_data(task, 'Last message', 'Stopping...')

    @Slot()
    def _on_remove_selected_tasks(self) -> None:
        self.remove_tasks(self.get_selected_tasks())

    def remove_tasks(self, tasks: Iterable[TaskUnit]) -> None:
        """Remove the tasks, skipping those that are running or have a running child."""
        for task in list(tasks):
            with contextlib.suppress(TaskError):
                self._executor.remove_task(task)

    def get_all_tasks(self) -> List[TaskUnit]:
        """Get a list of all tasks in the tree view."""
        tasks: List[TaskUnit] = []
        for i in range(self.view.tree_view.tasks_model.rowCount()):
            item = self.view.tree_view.tasks_model.item(i, 0).data(Qt.UserRole)
            tasks.append(item)
            if isinstance(item, TaskGroup):
                tasks.extend(item.tasks)
        return tasks

    def get_selected_tasks(self) -> List[TaskUnit]:
        """Get a list of selected tasks in the tree view."""
        return [item.data(Qt.UserRole) for item in self.view.tree_view.get_selected_items()]
