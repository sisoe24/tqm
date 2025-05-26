from __future__ import annotations

import os
from typing import Any, Callable, Optional, Generator
from contextlib import contextmanager

from PySide2.QtCore import Qt
from PySide2.QtWidgets import QWidget, QSplitter, QMainWindow, QMessageBox

from ._core.task import TaskUnit, TaskGroup, TaskExecutable
from ._core.logger import LOGGER, WidgetLogHandler, log_file_handler
from ._ui.tab_logs import TasksLog
from ._core.settings import get_qss_path, open_settings, get_config_path
from ._ui.ui_controller import TaskManagerController, _TaskButtonsController
from ._ui.ui_view_model import TaskManagerView
from ._core.task_builder import TaskBuilder, TaskGroupBuilder
from ._core.task_executor import TaskExecutor, _ExecutorCallbacks

TaskGroupGenerator = Generator[TaskGroup, Any, None]


class TQManager(QMainWindow):
    """TQManager.

    This class is the main entry point for the TQManager. It provides a simple
    interface for adding tasks to a queue and executing them.

    >>> widget = TQManager()
    >>> with widget.begin_task_insert() as tasks:
    ...    tasks.add_event(lambda t: None, label='Dummy Task', comment='Does nothing')
    >>> widget.start_workers()
    """

    def __init__(self, app_name: str, parent: Optional[QWidget] = None) -> None:
        """Initialize the TQManager.

        Args:
            app_name (str): The name of the application. This is most useful when
            running multiple instances of the TQManager so differentiate between
            them.
        """
        super().__init__(parent)

        config_path = get_config_path(app_name)
        config_path.mkdir(exist_ok=True, parents=True)

        self.setStyleSheet(get_qss_path(config_path).read_text())

        with open_settings() as s:
            settings = s

        # logs
        self._logs = TasksLog()
        LOGGER.widget = WidgetLogHandler(self._logs, settings.enable_debug)
        LOGGER.info('Initializing TQManager')
        LOGGER.addHandler(log_file_handler(config_path))

        # core logic
        self.executor = TaskExecutor(settings.max_workers)

        # widgets logic
        self._view = TaskManagerView(self.executor, parent)
        self.executor.callbacks.system_idle.connect(self._view.tree_view.stop_animation)

        self.executor.callbacks.status_updated.connect(self._view.update_status)

        self._controller = TaskManagerController(self._view, self.executor, settings)
        self._controller.ops.max_workers_updated.connect(self.executor.set_max_workers)

        splitter = QSplitter(Qt.Vertical)
        splitter.addWidget(self._view)
        splitter.addWidget(self._logs)

        if os.getenv('DEV_MODE') != '1':
            splitter.setSizes([100, 0])

        self.setCentralWidget(splitter)

    @property
    def callbacks(self) -> _ExecutorCallbacks:
        return self.executor.callbacks

    @property
    def operations(self) -> _TaskButtonsController:
        return self._controller.ops

    def status_message(self, text: str, timeout: int = 5000) -> None:
        self.statusBar().showMessage(text, timeout)

    def start_workers(self) -> None:
        """Start the workers."""
        self.executor.start_workers()

    def set_max_workers(self, workers: int) -> None:
        """Set the maximum number of worker threads for the executor."""
        self.executor.set_max_workers(workers)

    def remove_tasks(self, *tasks: TaskUnit) -> None:
        for task in tasks:
            self.executor.remove_task(task)

    def add_tasks(self, *tasks: TaskUnit) -> None:
        """Add a group of tasks to the queue.

        ```
        task = TaskBuilder().build()
        group = TaskGroupBuilder().build()
        task_manager.add(group, task)
        ```

        """
        for task in tasks:
            self.executor.add_task(task)
            self.callbacks.task_added.emit(task)

    def add_event(
        self,
        execute: Callable[[TaskExecutable], Any],
        *,
        show_progress: bool = False,
        label: str = '',
        comment: str = ''
    ) -> TaskExecutable:
        """Create a simple task.

        Args:
            execute (Callable[[Task], Any]): The event to be executed. The first argument
            is the task itself.
            show_progress (bool): If the task should show a progress.
            label (Optional[str], optional): The label of the task. If not provided,
                a default label will be generated.
            details (Optional[str], optional): Comment of the task. Defaults to ''.

        ```
        add_event(
           execute=lambda task: print(task.name),
           progress=True,
           label='My task',
           comment='Comment of the task'
        )
        ```
        """
        task = (
            TaskBuilder(name=label)
            .with_event(execute, show_progress=show_progress)
            .with_comment(comment)
            .build()
        )
        self.add_tasks(task)
        return task

    @contextmanager
    def create_group(self, group_name: str) -> TaskGroupGenerator:
        """Add a simple group to the queue.

        ```
        with create_group('My Group') as group:
            group.add_tasks(task1, task2)
            group.add_event(lambda t: t.log('hello'))
        ```
        """
        group = TaskGroupBuilder(name=group_name).build()
        yield group
        self.add_tasks(group)

    def shutdown(self) -> None:
        """Shutdown the workers."""
        if QMessageBox.question(
            None,
            'Shutdown',
            'Are you sure you want to shutdown the workers? '
            'Note: In-progress tasks will not be terminated.',
            QMessageBox.Yes | QMessageBox.No
        ) != QMessageBox.Yes:
            return

        self.executor.shutdown()
