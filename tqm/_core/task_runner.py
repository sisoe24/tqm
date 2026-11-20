from __future__ import annotations

from typing import TYPE_CHECKING

from PySide2.QtCore import Slot, Signal, QObject, QRunnable

from .logger import LOGGER

if TYPE_CHECKING:
    from .task import TaskExecutable


class RunnerSignals(QObject):
    """
    Signals emitted by the TaskRunner class. The executor shares one between its tasks.
    """

    runner_completed = Signal(object)
    runner_failed = Signal(object, Exception)
    runner_started = Signal(object)

    # progress is used by the user if needed
    task_progress_updated = Signal(object, float)
    task_logged = Signal(object, str)


class TaskRunner(QRunnable):
    """
    Runs a task once in a separate thread. Qt deletes it after the run.
    """

    def __init__(self, task: TaskExecutable) -> None:
        super().__init__()
        self.task = task

    def __str__(self) -> str:
        return f'<{self.__class__.__name__} {hex(id(self))}>'

    @Slot()
    def run(self) -> None:

        try:
            LOGGER.debug('%s: Started', self.task.name)
            self.task.execute(self.task)

        # BaseException too: SystemExit in a task must not leave it running.
        except BaseException as e:
            LOGGER.debug('%s: Failed. Exception: %s', self.task.name, str(e))
            self.task.signals.runner_failed.emit(self.task, e)

        else:
            LOGGER.debug('%s: Completed', self.task.name)
            self.task.signals.runner_completed.emit(self.task)
