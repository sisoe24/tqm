from __future__ import annotations

import os
from typing import Any, Callable, Optional, Generator
from contextlib import contextmanager

from PySide2.QtCore import Qt
from PySide2.QtWidgets import QWidget, QSplitter, QMainWindow, QMessageBox

from ._core.task import TaskUnit, TaskGroup, TaskExecutable
from ._core.logger import LOGGER, USER_LEVEL, remove_handlers, add_file_handler
from ._ui.tab_logs import TasksLog
from ._core.settings import get_qss_path, open_settings, get_config_path
from ._ui.ui_controller import TaskManagerController, _TaskButtonsController
from ._ui.ui_view_model import TaskManagerView
from ._core.task_builder import TaskBuilder, TaskGroupBuilder
from ._core.task_executor import TaskExecutor, _ExecutorCallbacks
from .widgets.help_widget import show_help

TaskGroupGenerator = Generator[TaskGroup, Any, None]


class TQManager(QMainWindow):
    """TQManager.

    This class is the main entry point for the TQManager. It provides a simple
    interface for adding tasks to a queue and executing them.

    >>> widget = TQManager('my_app')
    >>> with widget.create_group('Group') as group:
    ...    group.add_event(lambda t: None, label='Dummy Task', comment='Does nothing')
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

        try:
            self.setStyleSheet(get_qss_path(config_path).read_text())
        except OSError as e:
            print('[tqm error]: Cannot read the style sheet.', e)

        settings_path = config_path / 'settings.json'
        with open_settings(json_file_path=settings_path) as s:
            settings = s

        # logs
        self._logs = TasksLog(settings_path, settings.wrap_lines, settings.enable_debug)
        handlers = (self._logs.handler, add_file_handler(config_path))
        LOGGER.addHandler(self._logs.handler)
        self.destroyed.connect(lambda: remove_handlers(*handlers))
        LOGGER.info('Initializing TQManager')

        # core logic
        self.executor = TaskExecutor(settings.max_workers, parent=self)
        signals = self.executor._runner_signals
        self._logs.handler.addFilter(lambda r: getattr(r, 'tqm_signals', None) in (None, signals))

        # widgets logic
        self._view = TaskManagerView(self.executor, settings_path, parent)
        self._view.toolbar.table_options.help.triggered.connect(
            lambda: show_help(config_path=str(config_path))
        )
        self.executor.callbacks.system_idle.connect(self._view.tree_view.stop_animation)

        self.executor.callbacks.status_updated.connect(self._view.update_status)

        self._controller = TaskManagerController(self._view, self.executor, settings_path, self)
        self._controller.ops.max_workers_updated.connect(self.executor.set_max_workers)
        self._view.tree_view.selectionModel().selectionChanged.connect(
            lambda: self._logs.show_tasks(self._controller.get_selected_tasks())
        )

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

    def log(self, text: str) -> None:
        """Write a message to this manager's log panel and log file.

        ```
        task_manager.log('Polling started...')
        ```
        """
        LOGGER.log(USER_LEVEL, text, extra={'tqm_signals': self.executor._runner_signals})

    def add_tasks(self, *tasks: TaskUnit) -> None:
        """Add a group of tasks to the queue.

        ```
        task = TaskBuilder().build()
        group = TaskGroupBuilder().with_tasks(TaskBuilder().build()).build()
        task_manager.add_tasks(group, task)
        ```

        Raises:
            TaskError: If called from another thread than the one that created the manager,
                or if a task was removed before.

        """
        for task in tasks:
            self.executor.add_task(task)

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
            comment (str, optional): Comment of the task. Defaults to ''.

        ```
        add_event(
           execute=lambda task: print(task.name),
           show_progress=True,
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
        """Ask the user, then shut down without waiting.

        The question does not block: this returns at once, and the shutdown runs on Yes.
        With no task running or queued there is nothing to lose, so it does not ask.
        Tasks that have not started end deleted. Running tasks finish without retries.
        """
        if self.executor.status_tracker.is_idle():
            self.executor.shutdown()
            return

        dialog = QMessageBox(
            QMessageBox.Question,
            'Shutdown',
            'Are you sure you want to shutdown the workers? '
            'Note: In-progress tasks will not be terminated.',
            QMessageBox.Yes | QMessageBox.No,
            self
        )
        dialog.setAttribute(Qt.WA_DeleteOnClose)
        dialog.button(QMessageBox.Yes).clicked.connect(self.executor.shutdown)
        dialog.open()
