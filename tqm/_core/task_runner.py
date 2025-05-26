from __future__ import annotations

import time
from typing import TYPE_CHECKING

from PySide2.QtCore import Slot, Signal, QObject, QRunnable

from .logger import LOGGER
from ..exceptions import TaskEventError

if TYPE_CHECKING:
    from .task import TaskGroup, TaskExecutable


class RunnerSignals(QObject):
    """
    Signals emitted by the BaseRunner class.
    """

    runner_completed = Signal(object)
    runner_failed = Signal(object, Exception)
    runner_started = Signal(object)

    # progress is used by the user if needed
    task_progress_updated = Signal(int)

    # when group needs to add its tasks
    group_task_added = Signal(object)


class BaseRunner(QRunnable):

    def __init__(self) -> None:
        super().__init__()
        self.signals = RunnerSignals()
        self.setAutoDelete(True)

    def __str__(self) -> str:
        return f'<{self.__class__.__name__} {hex(id(self))}>'


class GroupRunner(BaseRunner):
    """
    Represents a task that can be executed in a separate thread.
    """

    def __init__(self, group: TaskGroup) -> None:
        super().__init__()
        self.group = group

    @Slot()
    def run(self) -> None:
        LOGGER.debug('%s: Started', self.group.name)
        self.signals.runner_started.emit(self.group)

        # add all tasks from the main thread
        self.signals.group_task_added.emit(self.group.tasks)

        # Block until all tasks are complete
        while not all(task.state.is_completed or task.state.is_failed for task in self.group.tasks):
            time.sleep(0.1)  # sleep to avoid CPU thrashing

        if all(task.state.is_completed for task in self.group.tasks):
            LOGGER.debug('%s: Completed', self.group.name)
            self.signals.runner_completed.emit(self.group)

        elif any(task.state.is_failed for task in self.group.tasks):
            LOGGER.debug('%s: Failed. Some tasks failed.', self.group.name)
            self.signals.runner_failed.emit(self.group, TaskEventError('Some tasks failed'))


class TaskRunner(BaseRunner):
    """
    Represents a task that can be executed in a separate thread.
    """

    def __init__(self, task: TaskExecutable) -> None:
        super().__init__()
        self.task = task

    @Slot()
    def run(self) -> None:

        try:
            LOGGER.debug('%s: Started', self.task.name)
            self.signals.runner_started.emit(self.task)
            self.task.execute(self.task)

        except Exception as e:
            LOGGER.debug('%s: Failed. Exception: %s', self.task.name, str(e))
            self.signals.runner_failed.emit(self.task, e)

        else:
            LOGGER.debug('%s: Completed', self.task.name)
            self.signals.runner_completed.emit(self.task)
