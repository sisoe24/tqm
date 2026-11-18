from __future__ import annotations

import os
import threading
import contextlib
from typing import Any, Set, Dict, Callable, Optional
from functools import partial

from PySide2.QtCore import Qt, Slot, QTimer, Signal, QObject

from .task import TaskUnit, TaskGroup, TaskExecutable
from .queue import TasksQueue, TaskNotFoundError
from .logger import LOGGER
from .task_retry import RetryHandler
from ..exceptions import (TaskError, TaskEventError, TaskGroupError, TaskParentError,
                          TaskAlreadyInQueue, TaskPredicateError)
from .task_runner import TaskRunner, RunnerSignals
from .task_predicate import PredicateEventType
from .threadpool_interface import ThreadPoolWrapper, ThreadPoolInterface


def _depth(task: TaskUnit) -> int:
    depth = 0
    while task.parent:
        task, depth = task.parent, depth + 1
    return depth


class _ExecutorCallbacks(QObject):

    # ui
    task_added = Signal(object)
    task_removed = Signal(object)
    task_finished = Signal(object)
    task_progress_updated = Signal(object, float)

    runner_started = Signal(object)
    runner_completed = Signal(object)
    runner_failed = Signal(object, Exception)

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

    def on_task_failed(self, callback: Callable[[TaskUnit, Exception], Any]) -> None:
        """On task failed callback. It fires once, when the task fails for good.

        ```
        on_task_failed(lambda t, e: print(f'Task failed: {t.name}: {e}'))
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


class _ExecutorStateTracker(QObject):
    def __init__(self, executor: TaskExecutor, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._executor = executor
        self._state_counts = {
            'waiting': 0,
            'running': 0,
            'retrying': 0,
            'completed': 0,
            'failed': 0,
        }
        # Running or retrying groups. They are not in the task counts shown to the user.
        self._active_groups = 0

        self._idle_timer: Optional[QTimer] = None
        try:
            self._idle_timeout = int(os.getenv('TQM_IDLE_TIMEOUT', 1000))
        except ValueError:
            self._idle_timeout = 1000

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

    def update_group_status(self, old_state: str, new_state: str) -> None:
        active = ('running', 'retrying')
        self._active_groups += (new_state in active) - (old_state in active)
        self._handle_idle()

    def is_idle(self) -> bool:
        return (
            self._state_counts['running'] == 0 and
            self._state_counts['waiting'] == 0 and
            self._state_counts['retrying'] == 0 and
            self._active_groups == 0 and
            self._executor.queue.size() == 0 and
            self._executor.queue.size_deferred() == 0
        )

    @Slot(dict)
    def _emit_idle(self) -> None:
        self._executor.callbacks.system_idle.emit()

    def _handle_idle(self) -> None:
        if self.is_idle():

            if not self._idle_timer or not self._idle_timer.isActive():
                self._idle_timer = QTimer(self)
                self._idle_timer.setSingleShot(True)
                self._idle_timer.timeout.connect(self._emit_idle)
                self._idle_timer.start(self._idle_timeout)

        elif self._idle_timer and self._idle_timer.isActive():
            self._idle_timer.stop()


class TaskExecutor(QObject):
    """Queue and run tasks on a thread pool. Add and start tasks from the thread that created it.

    Used without a TQManager window, give it a Qt parent, or keep it alive and delete it on
    the main thread: left to Python's garbage collector it can be freed on a worker thread
    and crash.
    """

    def __init__(
        self,
        max_workers: int = 20,
        threadpool: Optional[ThreadPoolInterface] = None,
        parent: Optional[QObject] = None
    ):
        super().__init__(parent)
        LOGGER.info('Initializing TasksManager')

        self.queue = TasksQueue()
        self.callbacks = _ExecutorCallbacks(self)
        self.status_tracker = _ExecutorStateTracker(self, self)

        self.max_workers = max_workers

        self._threadpool = threadpool or ThreadPoolWrapper(self)
        self._threadpool.setMaxThreadCount(self.max_workers)

        self.retry_handler = RetryHandler(self._on_retry_due, self)

        # One for all tasks: a QObject owned by a task could be freed by a GC pass on a worker.
        self._runner_signals = RunnerSignals(self)
        self._runner_signals.runner_failed.connect(self._on_task_failed, Qt.QueuedConnection)
        self._runner_signals.runner_completed.connect(self._on_task_completed, Qt.QueuedConnection)
        self._runner_signals.task_progress_updated.connect(self.callbacks.task_progress_updated)

        self.registry: Set[TaskUnit] = set()
        # Tasks requeued by their retry policy: their next start is not a new run.
        self._policy_retries: Set[TaskUnit] = set()

        self._shutdown_requested = False
        self._thread_id = threading.get_ident()

    @property
    def max_workers(self) -> int:
        return self._max_workers

    @max_workers.setter
    def max_workers(self, value: int) -> None:
        self._max_workers = max(2, value)

    def set_max_workers(self, value: int) -> None:
        self.max_workers = value
        self._threadpool.setMaxThreadCount(self.max_workers)

    def _on_predicate_event(
        self,
        task: TaskUnit,
        event: PredicateEventType,
        error: Optional[Exception] = None
    ) -> None:
        # A predicate timer can outlive its task's wait, for example after a parent failed.
        if not (task.state.is_blocked or task.state.is_retrying):
            return

        if event == PredicateEventType.SUCCESS:
            LOGGER.info(f'{task.name} predicate passed')
            self.queue.promote_to_main(task)
            self.start_workers()

        elif event == PredicateEventType.FAIL:
            self._on_task_failed(task, TaskPredicateError(f'{task.name}: {error or "predicate failed"}'))

        elif event == PredicateEventType.RETRY:
            task.state.set_retrying(f'Attempts left: {task.predicate.retry_left}')
            LOGGER.info(
                f'{task.name} retrying in {task.predicate.retry_interval}ms. '
                f'Retries left: {task.predicate.retry_left}'
            )

    def _predicate_passes(self, task: TaskUnit) -> bool:
        """Check the predicate once. If it is false, block the task and keep checking on a timer."""
        predicate = task.predicate
        if predicate.condition is None or predicate.passed:
            return True

        try:
            passed = predicate.condition()
        except Exception as e:
            self._handle_failure(task, TaskPredicateError(f'{task.name}: {e}'))
            return False

        if passed:
            return True

        LOGGER.info(f'{task.name} predicate failed')
        task.state.set_blocked('Predicate failed')
        self.queue.suspend(task)
        predicate.evaluate(partial(self._on_predicate_event, task))
        return False

    def _remove_and_cleanup_task(self, task: TaskUnit) -> None:
        task.delete()
        # Rows go before their group row, or the group row deletes them first.
        for member in getattr(task, 'tasks', set()).copy():
            self.remove_task(member)
        self.callbacks.task_removed.emit(task)
        for child in task.children.copy():
            self.remove_task(child)

        group = getattr(task, 'group', None)
        if group is not None and not group.tasks and group.state.is_removable and not group.state.is_deleted:
            self.remove_task(group)

    def _check_removable(self, task: TaskUnit) -> None:
        if not task.state.is_removable:
            raise TaskError(
                f'Cannot remove task: {task.name}. '
                f'State "{task.state.current}" is not removable'
            )
        for other in (*task.children, *getattr(task, 'tasks', ())):
            self._check_removable(other)

    def remove_task(self, task: TaskUnit) -> None:
        """Remove a task, its group members and the tasks that wait for it.

        Running tasks are not removable. Nothing is removed if any of these tasks is running.

        Raises:
            TaskError: If the task or one of the tasks it takes along is running.

        """
        if not task.state.is_inactive and task not in self.registry:
            return

        self._check_removable(task)

        if task.state.is_inactive:
            self._remove_and_cleanup_task(task)
            return

        self._drop(task)

    def _drop(self, task: TaskUnit) -> None:
        with contextlib.suppress(TaskNotFoundError):
            self.queue.remove_task(task)

        self.registry.remove(task)
        self._policy_retries.discard(task)

        self._remove_and_cleanup_task(task)
        self._settle_group(getattr(task, 'group', None))

    def retry_task(self, task: TaskUnit) -> None:
        """Retry a failed or completed task by re-adding it to the queue.

        Raises:
            TaskError: If the task is not failed or completed.

        """
        if not task.state.is_retryable:
            raise TaskError(
                f'Cannot retry task: {task.name}. '
                f'State "{task.state.current}" is not retryable'
            )

        if self._shutting_down():
            LOGGER.warning('Task manager is shutting down. Cannot retry task')
            return

        # A manual retry gets the full retry budget again.
        task.reset('Reset & Retry', reset_attempts=True)

        # Reset members are queued when the group starts again.
        for member in getattr(task, 'tasks', ()):
            if member.state.is_failed:
                member.reset('Reset & Retry', reset_attempts=True)

        for child in task.children.copy():
            if child.state.is_failed:
                self.retry_task(child)

        if (
            isinstance(task, TaskExecutable)
            and (task.group and task.group.state.is_failed)
        ):
            self.retry_task(task.group)

        # Restarting the group may have queued this member already.
        if task.state.is_inactive:
            self._initialize_task(task)
            self._start_task(task)

    def _on_retry_due(self, task: TaskUnit) -> None:
        # The task may have been removed or retried by hand during the delay.
        if not task.state.is_retrying:
            return

        task.reset('Retry')
        self._policy_retries.add(task)
        self._initialize_task(task)
        self._start_task(task)

    @Slot(object)
    def _on_task_failed(self, task: TaskUnit, exception: Exception) -> None:
        """Handle a failed task. If its retry policy allows, it is retried later."""
        self._handle_failure(task, exception)
        self.start_workers()

    def _handle_failure(self, task: TaskUnit, exception: Exception) -> None:
        # A task blocked by its predicate waits in the deferred queue.
        with contextlib.suppress(TaskNotFoundError):
            self.queue.remove_task(task)

        if self._shutting_down() or not self.retry_handler.handle_failure(task, exception):
            self._fail_task(task, exception)

    def _fail_task(self, task: TaskUnit, exception: Exception) -> None:
        """Fail a task for good, and every child still waiting for it."""
        LOGGER.error(f'{task.name} failed: {exception}')

        with contextlib.suppress(TaskNotFoundError):
            self.queue.remove_task(task)

        task.predicate.stop()
        task.set_failed(exception, str(exception))

        task.callbacks.execute_on_failed(task)
        self._on_task_finished(task)
        self.callbacks.runner_failed.emit(task, exception)

        for child in task.children.copy():
            if child.state.is_waiting or child.state.is_blocked or child.state.is_retrying:
                self._fail_task(child, TaskParentError(f'Parent {task.name} failed.'))

        self._settle_group(getattr(task, 'group', None))

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

        self._settle_group(getattr(task, 'group', None))

        if autostart:
            self.start_workers()

    @Slot(object)
    def _on_task_finished(self, task: TaskUnit) -> None:
        task.callbacks.execute_on_finish(task)
        self.callbacks.task_finished.emit(task)

    def _initialize_task(self, task: TaskUnit) -> None:

        self.queue.enqueue(task)

        task.state.set_waiting()

    def _check_thread(self) -> None:
        if threading.get_ident() != self._thread_id:
            raise TaskError('Tasks can only be added or started from the main thread')

    def add_task(self, task: TaskUnit) -> TaskUnit:
        self._check_thread()

        if self._shutting_down():
            LOGGER.warning('Task manager is shutting down. Cannot add new task')
            return task

        if task in self.registry:
            raise TaskAlreadyInQueue(f'Task "{task}" already in queue')

        if task.state.is_deleted:
            raise TaskError(f'Task "{task}" was removed and cannot be added again')

        if isinstance(task, TaskGroup) and not task.tasks:
            raise TaskGroupError(f'Cannot add TaskGroup "{task.name}" without any tasks')

        if isinstance(task, TaskGroup) and (
            task.parent in task.tasks or any(member.parent is task for member in task.tasks)
        ):
            raise TaskError(f'Group {task.name} and one of its members wait for each other')

        self._register(task)
        self.callbacks.task_added.emit(task)
        return task

    def _register(self, task: TaskUnit) -> None:
        if isinstance(task, TaskExecutable):
            task.state.register_state_change_callback(self.status_tracker.update_status)
        else:
            task.state.register_state_change_callback(self.status_tracker.update_group_status)

        LOGGER.info('Adding task to queue: %s', task.name)

        self.registry.add(task)

        task.signals = self._runner_signals

        self._initialize_task(task)

    def _has_free_worker(self) -> bool:
        return self._threadpool.activeThreadCount() < self.max_workers

    def _start_group(self, group: TaskGroup) -> None:
        for member in list(group.tasks):
            if member not in self.registry:
                self._register(member)
            elif member.state.is_inactive:
                self._initialize_task(member)
        self._settle_group(group)
        self.start_workers()

    def _settle_group(self, group: Optional[TaskGroup]) -> None:
        """Complete or fail a running group once none of its members can still run."""
        if group is None or not group.state.is_running:
            return

        members = [t for t in group.tasks if not t.state.is_deleted]
        if not all(t.state.is_completed or t.state.is_failed for t in members):
            return

        if all(t.state.is_completed for t in members):
            self._on_task_completed(group, autostart=False)
        else:
            self._handle_failure(group, TaskEventError('Some tasks failed'))

    def _is_known(self, task: TaskUnit) -> bool:
        """True if the task was added, directly or through its group."""
        group = getattr(task, 'group', None)
        return task in self.registry or (group is not None and self._is_known(group))

    def _dispatch(self, task: TaskUnit) -> None:
        parent = task.parent
        if parent and parent.state.is_failed:
            self._fail_task(task, TaskParentError(f'Parent {parent.name} failed.'))
            return

        if parent and not self._is_known(parent):
            self._fail_task(task, TaskParentError(f'Parent {parent.name} was never added.'))
            return

        if parent and not parent.state.is_completed:
            LOGGER.info(f'{task.name} waiting for {parent.name}')
            task.state.set_blocked(f'Waiting for parent: {parent.name}')
            self.queue.suspend(task)
            return

        # After the parent check, so attempts are not used up while the parent runs.
        if not self._predicate_passes(task):
            return

        # Running from here on, so the task cannot be removed once it is in the pool.
        task.state.set_running()
        if task in self._policy_retries:
            self._policy_retries.discard(task)
        else:
            task.callbacks.execute_on_start(task)
        self.callbacks.runner_started.emit(task)

        if isinstance(task, TaskGroup):
            self._start_group(task)
        else:
            self._threadpool.start(TaskRunner(task))

    def _start_task(self, task: TaskUnit) -> None:
        """Start this task now if a worker is free; otherwise it waits in the queue."""
        if self._has_free_worker():
            self.queue.remove_from_queue(task)
            self._dispatch(task)

    def start_workers(self) -> None:
        """Start the workers."""
        self._check_thread()
        while self.queue.size() and self._has_free_worker():
            self._dispatch(self.queue.dequeue())

    def get_all_tasks(self) -> Set[TaskUnit]:
        return self.registry

    def _shutting_down(self) -> bool:
        """True from shutdown until the tasks that were running have finished."""
        if self._shutdown_requested and self.status_tracker.is_idle():
            self._shutdown_requested = False
        return self._shutdown_requested

    def shutdown(self) -> None:
        """Shutdown the task manager without waiting for running tasks.

        Tasks that have not started are removed and end deleted. Running tasks finish
        in the background, without retries. Until they do, add_task and retry_task
        are ignored.

        """
        LOGGER.info('Removing all tasks that have not started. Running tasks finish in the background.')
        self._shutdown_requested = True

        pending = [t for t in self.registry if t.state.is_waiting or t.state.is_blocked or t.state.is_retrying]
        # Children first, so removing a parent never meets a child that is still blocked.
        for task in sorted(pending, key=_depth, reverse=True):
            if task in self.registry:
                self._drop(task)
