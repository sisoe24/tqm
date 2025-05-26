from __future__ import annotations

import os
import contextlib
from typing import Any, Set, Dict, List, Callable, Optional
from functools import partial

from PySide2.QtCore import Qt, Slot, QTimer, Signal, QObject

from .task import TaskUnit, TaskExecutable
from .queue import TasksQueue, TaskNotFoundError
from .logger import LOGGER
from .shutdown import ShutdownThread
from .task_retry import RetryHandler
from ..exceptions import (TaskError, TaskParentError, TaskAlreadyInQueue,
                          TaskPredicateError)
from .task_runner import RunnerSignals
from .task_predicate import PredicateEventType
from .threadpool_interface import ThreadPoolWrapper, ThreadPoolInterface


class _ExecutorCallbacks(RunnerSignals):

    # ui
    task_added = Signal(object)
    task_removed = Signal(object)
    task_finished = Signal(object)

    status_updated = Signal(dict)
    system_idle = Signal()

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)

    def on_task_added(self, callback: Callable[[TaskUnit], Any]) -> None:
        """On task added callback.

        ```
        on_task_added(lambda t: print(f'Task added: {t.name}'))
        ```

        """
        self.task_added.connect(callback, Qt.QueuedConnection)

    def on_task_started(self, callback: Callable[[TaskUnit], Any]) -> None:
        """On task started callback.


        ```
        on_task_started(lambda t: print(f'Task started: {t.name}'))
        ```

        """
        self.runner_started.connect(callback, Qt.QueuedConnection)

    def on_task_completed(self, callback: Callable[[TaskUnit], Any]) -> None:
        """On task completed callback.

        ```
        on_task_completed(lambda t: print(f'Task completed: {t.name}'))
        ```

        """
        self.runner_completed.connect(callback, Qt.QueuedConnection)

    def on_task_finished(self, callback: Callable[[TaskUnit], Any]) -> None:
        """On task finished callback.

        ```
        on_task_finished(lambda t: print(f'Task finished: {t.name}'))
        ```

        """
        self.task_finished.connect(callback, Qt.QueuedConnection)

    def on_task_failed(self, callback: Callable[[TaskUnit], Any]) -> None:
        """On task failed callback.

        ```
        on_task_failed(lambda t: print(f'Task failed: {t.name}'))
        ```

        """
        self.runner_failed.connect(callback, Qt.QueuedConnection)

    def on_task_removed(self, callback: Callable[[TaskUnit], Any]) -> None:
        """On task removed callback.

        ```
        on_task_removed(lambda t: print(f'Task removed: {t.name}'))
        ```

        """
        self.task_removed.connect(callback, Qt.QueuedConnection)

    def on_system_idle(self, callback: Callable[..., Any]) -> None:
        """On workers idle callback.

        NOTE: This signal is primarily intended for testing and debugging.
        For production code, consider using task groups with completion signals.

        The signal is emitted when the system has been idle (no running, waiting,
        or queued tasks) for a short period (100ms by default).

        ```
        on_system_idle(lambda: print('System currently idle'))
        ```
        """
        self.system_idle.connect(callback, Qt.QueuedConnection)

    def on_status_updated(self, callback: Callable[[Dict[str, Any]], Any]) -> None:
        """On status updated callback.

        ```
        on_status_updated(lambda s: print(s))
        ```

        """
        self.status_updated.connect(callback, Qt.QueuedConnection)


class _ExecutorBlocker(QObject):
    predicate_successful = Signal(object)
    predicate_failed = Signal(object, Exception)

    def __init__(self, executor: TaskExecutor, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._executor = executor

    def _handle_predicate(
        self,
        task: TaskUnit,
        predicate_event: PredicateEventType
    ) -> None:

        if predicate_event == PredicateEventType.SUCCESS:
            LOGGER.info(f"{task.name} predicate passed")
            self.predicate_successful.emit(task)

        elif predicate_event == PredicateEventType.FAIL:
            self.predicate_failed.emit(task, TaskPredicateError(task.name))

        elif predicate_event == PredicateEventType.RETRY:
            task.state.set_retrying(f'Attempts left: {task.predicate.retry_left}')
            LOGGER.info(
                f'{task.name} retrying in {task.predicate.retry_interval}ms. '
                f'Retries left: {task.predicate.retry_left}'
            )
        else:
            raise TaskPredicateError('Unknown predicate event')

    def _block_task_with_predicate(self, task: TaskUnit) -> bool:
        """Blocks the given task if its predicate is not resolved."""
        if not task.predicate.condition or task.predicate.condition():
            return False

        LOGGER.info(f'{task.name} predicate failed')
        task.state.set_blocked('Predicate failed')
        return True

    def _block_task_with_parent(self, task: TaskUnit) -> bool:
        """Blocks the given task if its parent task is not completed."""
        if not task.parent:
            return False

        if not task.parent.state.is_completed and not task.state.is_inactive:
            LOGGER.info(f'{task.name} waiting for {task.parent.name}')
            task.state.set_blocked(f'Waiting for parent: {task.parent.name}')
            return True

        return False

    def should_block(self, task: TaskUnit) -> bool:
        if self._block_task_with_predicate(task):
            self._executor.queue.suspend(task)
            task.predicate.evaluate(partial(self._handle_predicate, task))
            return True

        if self._block_task_with_parent(task):
            self._executor.queue.suspend(task)
            return True

        return False


class _ExecutorStateTracker(QObject):
    def __init__(self, executor: TaskExecutor, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._executor = executor
        self._state_counts = {
            'waiting': 0,
            'running': 0,
            'completed': 0,
            'failed': 0,
        }

        self._idle_timer: Optional[QTimer] = None
        self._idle_timeout = int(os.getenv('TQM_IDLE_TIMEOUT', 1000))

    @property
    def running_tasks(self) -> int:
        return self._state_counts['running']

    def update_status(self, old_state: str, new_state: str) -> None:
        if old_state in self._state_counts:
            self._state_counts[old_state] -= 1

        if new_state in self._state_counts:
            self._state_counts[new_state] += 1

        status: Dict[str, int] = {
            'Running': self._state_counts['running'],
            'Completed': self._state_counts['completed'],
            'Failed': self._state_counts['failed'],
        }

        self._executor.callbacks.status_updated.emit(status)
        self._handle_idle()

    def is_idle(self) -> bool:
        return (
            self._state_counts['running'] == 0 and
            self._state_counts['waiting'] == 0 and
            self._executor.queue.size() == 0 and
            self._executor.queue.size_deferred() == 0
        )

    @Slot(dict)
    def _emit_idle(self) -> None:
        self._executor.callbacks.system_idle.emit()

    def _handle_idle(self) -> None:
        if self.is_idle():

            if not self._idle_timer or not self._idle_timer.isActive():
                self._idle_timer = QTimer()
                self._idle_timer.setSingleShot(True)
                self._idle_timer.timeout.connect(self._emit_idle)
                self._idle_timer.start(self._idle_timeout)

        elif self._idle_timer and self._idle_timer.isActive():
            self._idle_timer.stop()


class TaskExecutor(QObject):

    def __init__(
        self,
        max_workers: int = 20,
        threadpool: Optional[ThreadPoolInterface] = None,
        parent: Optional[QObject] = None
    ):
        super().__init__(parent)
        LOGGER.info('Initializing TasksManager')

        self.queue = TasksQueue()
        self.callbacks = _ExecutorCallbacks()
        self.status_tracker = _ExecutorStateTracker(self)

        self._max_workers = max_workers

        self._threadpool = threadpool or ThreadPoolWrapper(self)
        self._threadpool.setMaxThreadCount(self.max_workers+1)
        self._shutdown_thread = ShutdownThread(self._threadpool)

        self._blocker = _ExecutorBlocker(self)
        self._blocker.predicate_failed.connect(self._on_task_failed)
        self._blocker.predicate_successful.connect(self._predicate_success)

        self.retry_handler = RetryHandler(self.retry_task)

        self.registry: Set[TaskUnit] = set()

        self._is_shutting_down = False

    @property
    def max_workers(self) -> int:
        return self._max_workers

    @max_workers.setter
    def max_workers(self, value: int) -> None:
        self._max_workers = max(2, value)

    def set_max_workers(self, value: int) -> None:
        self.max_workers = value
        self._threadpool.setMaxThreadCount(self.max_workers+1)

    def _predicate_success(self, task: TaskUnit) -> None:
        self.queue.promote_to_main(task)
        self.start_workers()

    def _remove_and_cleanup_task(self, task: TaskUnit) -> None:
        task.delete()
        for child in task.children.copy():
            self.remove_task(child)
        self.callbacks.task_removed.emit(task)

    def remove_task(self, task: TaskUnit) -> None:
        """Attempt to remove a task from the queue.

        Tasks that depend on the removed task will be also removed since they will
        never be executed.

        Raises:
            TaskNotFound: If the task is not found in the queue.

        """
        if task.state.is_inactive:
            self._remove_and_cleanup_task(task)
            return

        if task not in self.registry:
            return

        if not task.state.is_removable:
            raise TaskError(
                f'Cannot remove task: {task.name}. '
                f'State "{task.state.current}" is not removable'
            )

        with contextlib.suppress(TaskNotFoundError):
            self.queue.remove_task(task)

        self.registry.remove(task)

        self._remove_and_cleanup_task(task)

    def retry_task(self, task: TaskUnit) -> None:
        """Retry a failed task.

        This method retries a failed task by re-adding it to the queue.
        The task must be in the deferred queue and have retries left.

        Raises:
            DeferredTaskNotFound: If the task is not found in the deferred queue.

        """

        task.reset('Reset & Retry')

        for child in task.children.copy():
            if child.state.is_failed:
                self.retry_task(child)

        if (
            isinstance(task, TaskExecutable)
            and (task.group and task.group.state.is_failed)
        ):
            self.retry_task(task.group)

        self._initialize_task(task)
        self._start_worker()

    @Slot(object)
    def _on_task_failed(self, task: TaskUnit, exception: Exception) -> None:
        """Handle a failed task.

        If the task can be retried, it will be re-added to the queue.

        Returns:
            str: The exception message if any

        """
        if self.retry_handler.handle_failure(task, exception):
            return

        LOGGER.error(f'{task.name} failed: {exception}')

        task.callbacks.execute_on_failed(task)
        self._on_task_finished(task)

        for child in filter(lambda t: t.state.is_blocked, task.children):
            self._on_task_failed(child, TaskParentError(f'Parent {task.name} failed.'))

        if self.queue.is_task_deferred(task):
            self.queue.remove_from_deferred(task)

        task.set_failed(exception, str(exception))

    @Slot(object)
    def _on_task_completed(self, task: TaskUnit, *, autostart: bool = True) -> None:
        task.state.set_completed()
        LOGGER.info(f'{task.name} completed')

        task.callbacks.execute_on_completed(task)
        self._on_task_finished(task)

        self.callbacks.runner_completed.emit(task)

        for child in filter(lambda t: t.state.is_blocked, task.children):
            child.state.set_waiting('Unblock from parent')
            self.queue.promote_to_main(child)

        if autostart:
            self.start_workers()

    @Slot(object)
    def _on_task_started(self, task: TaskUnit) -> None:
        task.callbacks.execute_on_start(task)
        self.callbacks.runner_started.emit(task)
        task.state.set_running()

    @Slot(object)
    def _on_task_finished(self, task: TaskUnit) -> None:
        task.callbacks.execute_on_finish(task)
        self.callbacks.task_finished.emit(task)

    @Slot(list)
    def _on_add_tasks(self, tasks: List[TaskUnit]) -> None:
        for task in tasks:
            if task not in self.registry:
                self.add_task(task)

        self.start_workers()

    def _initialize_task(self, task: TaskUnit) -> None:

        self.queue.enqueue(task)

        task.state.set_waiting()

        signals = task.runner.signals
        signals.runner_failed.connect(self._on_task_failed, Qt.QueuedConnection)
        signals.runner_completed.connect(self._on_task_completed, Qt.QueuedConnection)
        signals.runner_started.connect(self._on_task_started, Qt.QueuedConnection)
        signals.group_task_added.connect(self._on_add_tasks)

    def add_task(self, task: TaskUnit) -> TaskUnit:
        if self._is_shutting_down:
            LOGGER.warning('Task manager is shutting down. Cannot add new task')
            return task

        if task in self.registry:
            raise TaskAlreadyInQueue(f'Task "{task}" already in queue')

        if isinstance(task, TaskExecutable):
            task.state.register_state_change_callback(self.status_tracker.update_status)

        LOGGER.info('Adding task to queue: %s', task.name)

        self.registry.add(task)
        self._initialize_task(task)

        return task

    def _start_worker(self) -> None:
        task = self.queue.dequeue()

        if self._blocker.should_block(task):
            LOGGER.info(f'{task.name} is on hold')
            return

        self._threadpool.start(task.runner)

    def start_workers(self) -> None:
        """Start the workers."""
        while self.queue.size() and self._threadpool.activeThreadCount() <= self.max_workers:
            self._start_worker()

    def get_all_tasks(self) -> Set[TaskUnit]:
        return self.registry

    def shutdown(self) -> None:
        """Shutdown the task manager.

        This method clears the queue and waits for workers to finish their tasks.

        Note: Workers will complete their current tasks before shutting down.
        A new thread handles the shutdown.

        """
        if not self.status_tracker.running_tasks:
            return

        LOGGER.info('Removing all tasks from queue and waiting for workers to finish...')

        while self.queue.size():
            self.queue.dequeue()

        self._is_shutting_down = True
        self._shutdown_thread.run()
        self._is_shutting_down = False
