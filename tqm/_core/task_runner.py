from __future__ import annotations

from typing import TYPE_CHECKING

from PySide2.QtCore import Slot, Signal, QObject, QRunnable

from .logger import LOGGER

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


class BaseRunner(QRunnable):

    def __init__(self) -> None:
        super().__init__()
        self.signals = RunnerSignals()
        # The task keeps one runner for its whole life. With auto delete, Qt frees it
        # after each run, and a retry can then reuse a freed address and crash.
        self.setAutoDelete(False)

    def __str__(self) -> str:
        return f'<{self.__class__.__name__} {hex(id(self))}>'


class GroupRunner(BaseRunner):
    """Holds a group's signals. Groups never run on the pool: the executor settles them."""

    def __init__(self, group: TaskGroup) -> None:
        super().__init__()
        self.group = group

    def run(self) -> None:
        raise RuntimeError('Groups do not run on the thread pool')


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
            self.task.execute(self.task)

        # BaseException too: SystemExit in a task must not leave it running.
        except BaseException as e:
            LOGGER.debug('%s: Failed. Exception: %s', self.task.name, str(e))
            self.signals.runner_failed.emit(self.task, e)

        else:
            LOGGER.debug('%s: Completed', self.task.name)
            self.signals.runner_completed.emit(self.task)
