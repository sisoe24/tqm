"""Hand-picked mutants for the gate in harness.py.

The list is biased toward risky logic, so the score is a regression measure, not a
general quality number. Each mutant replaces the first match of a source string, so line
shifts do not break it. Keep the order: results refer to mutants by position.
"""
from __future__ import annotations

from typing import NamedTuple

EXECUTOR = 'tqm/_core/task_executor.py'
RUNNER = 'tqm/_core/task_runner.py'
QUEUE = 'tqm/_core/queue.py'
STATE = 'tqm/_core/task_state.py'
RETRY = 'tqm/_core/task_retry.py'
POLICY = 'tqm/_core/retry_policy/retry_policy.py'
DELAY = 'tqm/_core/retry_policy/delay_strategy.py'
FACTORY = 'tqm/_core/retry_policy/factory_methods.py'
PREDICATE = 'tqm/_core/task_predicate.py'
CALLBACKS = 'tqm/_core/task_callbacks.py'
BUILDER = 'tqm/_core/task_builder.py'
SETTINGS = 'tqm/_core/settings.py'
CONTROLLER = 'tqm/_ui/ui_controller.py'
TASK_BASE = 'tqm/_core/task_base.py'
TASK = 'tqm/_core/task.py'


class Mutant(NamedTuple):
    file: str
    old: str
    new: str
    change: str
    # The reason it cannot change behaviour. Such mutants are not run or counted.
    equivalent: str = ''


MUTANTS = [
    Mutant(
        EXECUTOR,
        (
            'if self.retry_handler.handle_failure(task, exception):\n'
            '            return'
        ),
        'self.retry_handler.handle_failure(task, exception)',
        'failure: ignore retry decision, always finalize',
    ),
    Mutant(
        EXECUTOR,
        (
            'task.callbacks.execute_on_failed(task)\n'
            '        self._on_task_finished(task)'
        ),
        'self._on_task_finished(task)',
        'failure: drop on_failed callback',
    ),
    Mutant(
        EXECUTOR,
        (
            'task.callbacks.execute_on_failed(task)\n'
            '        self._on_task_finished(task)'
        ),
        'task.callbacks.execute_on_failed(task)',
        'failure: drop _on_task_finished call',
    ),
    Mutant(
        EXECUTOR,
        (
            'for child in filter(lambda t: t.state.is_blocked, task.children):\n'
            "            self._on_task_failed(child, TaskParentError(f'Parent {task.name} failed.'))"
        ),
        'pass',
        'failure: no cascade to blocked children',
    ),
    Mutant(
        EXECUTOR,
        (
            'if self.queue.is_task_deferred(task):\n'
            '            self.queue.remove_from_deferred(task)'
        ),
        'pass',
        'failure: leave failed task in deferred queue',
    ),
    Mutant(
        EXECUTOR,
        'task.set_failed(exception, str(exception))',
        'pass',
        'failure: never set failed state',
    ),
    Mutant(
        EXECUTOR,
        'task.set_failed(exception, str(exception))',
        'task.set_failed(None, str(exception))',
        'failure: drop task.exception',
    ),
    Mutant(
        EXECUTOR,
        'task.set_failed(exception, str(exception))',
        "task.set_failed(exception, '')",
        'failure: drop failed-state comment',
    ),
    Mutant(
        EXECUTOR,
        'task.state.set_completed()\n',
        'pass\n',
        'completion: never set completed',
    ),
    Mutant(
        EXECUTOR,
        (
            'task.callbacks.execute_on_completed(task)\n'
            '        self._on_task_finished(task)'
        ),
        'self._on_task_finished(task)',
        'completion: drop on_completed callback',
    ),
    Mutant(
        EXECUTOR,
        (
            'task.callbacks.execute_on_completed(task)\n'
            '        self._on_task_finished(task)'
        ),
        'task.callbacks.execute_on_completed(task)',
        'completion: drop _on_task_finished',
    ),
    Mutant(
        EXECUTOR,
        'self.callbacks.runner_completed.emit(task)',
        'pass',
        'completion: drop public runner_completed emit',
    ),
    Mutant(
        EXECUTOR,
        "child.state.set_waiting('Unblock from parent')",
        'pass',
        'unblock: child stays BLOCKED state',
    ),
    Mutant(
        EXECUTOR,
        'self.queue.promote_to_main(child)',
        'pass',
        'unblock: child never promoted',
    ),
    Mutant(
        EXECUTOR,
        (
            'if autostart:\n'
            '            self.start_workers()'
        ),
        'pass',
        'unblock: no start_workers after completion',
    ),
    Mutant(
        EXECUTOR,
        'def _on_task_completed(self, task: TaskUnit, *, autostart: bool = True)',
        'def _on_task_completed(self, task: TaskUnit, *, autostart: bool = False)',
        'autostart default flipped',
    ),
    Mutant(
        EXECUTOR,
        'task.callbacks.execute_on_start(task)',
        'pass',
        'start: drop on_start callback',
    ),
    Mutant(
        EXECUTOR,
        'self.callbacks.runner_started.emit(task)',
        'pass',
        'start: drop public runner_started emit',
    ),
    Mutant(
        EXECUTOR,
        'task.state.set_running()',
        'pass',
        'start: never set running',
    ),
    Mutant(
        EXECUTOR,
        'task.callbacks.execute_on_finish(task)',
        'pass',
        'finish: drop on_finish callback',
    ),
    Mutant(
        EXECUTOR,
        'self.callbacks.task_finished.emit(task)',
        'pass',
        'finish: drop public task_finished emit',
    ),
    Mutant(
        EXECUTOR,
        (
            '            if task not in self.registry:\n'
            '                self.add_task(task)'
        ),
        '            self.add_task(task)',
        'group add: no registry guard',
    ),
    Mutant(
        EXECUTOR,
        (
            '                self.add_task(task)\n'
            '\n'
            '        self.start_workers()'
        ),
        '                self.add_task(task)',
        'group add: no start_workers after adding group tasks',
    ),
    Mutant(
        EXECUTOR,
        (
            'if self._is_shutting_down:\n'
            "            LOGGER.warning('Task manager is shutting down. Cannot add new task')\n"
            '            return task'
        ),
        'pass',
        'add: accept tasks during shutdown',
    ),
    Mutant(
        EXECUTOR,
        (
            'if task in self.registry:\n'
            '            raise TaskAlreadyInQueue(f\'Task "{task}" already in queue\')'
        ),
        'pass',
        'add: no duplicate check',
    ),
    Mutant(
        EXECUTOR,
        'task.state.register_state_change_callback(self.status_tracker.update_status)',
        'pass',
        'add: never register status tracker',
    ),
    Mutant(
        EXECUTOR,
        'signals.runner_failed.connect(self._on_task_failed, Qt.QueuedConnection)',
        'signals.runner_failed.connect(self._on_task_failed, Qt.DirectConnection)',
        'wiring: failed slot runs direct (worker thread)',
    ),
    Mutant(
        EXECUTOR,
        'signals.runner_completed.connect(self._on_task_completed, Qt.QueuedConnection)',
        'signals.runner_completed.connect(self._on_task_completed, Qt.DirectConnection)',
        'wiring: completed slot runs direct (worker thread)',
    ),
    Mutant(
        EXECUTOR,
        (
            'if self._blocker.should_block(task):\n'
            "            LOGGER.info(f'{task.name} is on hold')\n"
            '            return'
        ),
        'pass',
        'start: ignore blocker (parent/predicate)',
    ),
    Mutant(
        EXECUTOR,
        'while self.queue.size() and self._threadpool.activeThreadCount() <= self.max_workers:',
        'while self.queue.size():',
        'start: no worker-cap check',
    ),
    Mutant(
        EXECUTOR,
        'while self.queue.size() and self._threadpool.activeThreadCount() <= self.max_workers:',
        'if self.queue.size() and self._threadpool.activeThreadCount() <= self.max_workers:',
        'start: start only one task per call',
    ),
    Mutant(
        EXECUTOR,
        (
            'self._threadpool.setMaxThreadCount(self.max_workers+1)\n'
            '\n'
            '    def _predicate'
        ),
        (
            'pass\n'
            '\n'
            '    def _predicate'
        ),
        'set_max_workers: threadpool not resized',
    ),
    Mutant(
        EXECUTOR,
        'self._max_workers = max(2, value)',
        'self._max_workers = value',
        'max_workers: no floor of 2',
    ),
    Mutant(
        EXECUTOR,
        (
            'self.queue.promote_to_main(task)\n'
            '        self.start_workers()'
        ),
        'self.queue.promote_to_main(task)',
        'predicate success: no start_workers',
    ),
    Mutant(
        EXECUTOR,
        (
            'if not task.state.is_removable:\n'
            '            raise TaskError(\n'
            "                f'Cannot remove task: {task.name}. '\n"
            '                f\'State "{task.state.current}" is not removable\'\n'
            '            )'
        ),
        'pass',
        'remove: running tasks removable',
    ),
    Mutant(
        EXECUTOR,
        (
            'if task not in self.registry:\n'
            '            return'
        ),
        'pass',
        'remove: no registry guard',
    ),
    Mutant(
        EXECUTOR,
        'self.registry.remove(task)',
        'pass',
        'remove: task leaks in registry',
    ),
    Mutant(
        EXECUTOR,
        (
            'with contextlib.suppress(TaskNotFoundError):\n'
            '            self.queue.remove_task(task)'
        ),
        'pass',
        'remove: task stays in queue',
    ),
    Mutant(
        EXECUTOR,
        (
            'for child in task.children.copy():\n'
            '            self.remove_task(child)'
        ),
        'pass',
        'remove: children not removed',
    ),
    Mutant(
        EXECUTOR,
        'self.callbacks.task_removed.emit(task)',
        'pass',
        'remove: no task_removed emit',
    ),
    Mutant(
        EXECUTOR,
        (
            'if task.state.is_inactive:\n'
            '            self._remove_and_cleanup_task(task)\n'
            '            return'
        ),
        'pass',
        'remove: no inactive fast path',
    ),
    Mutant(
        EXECUTOR,
        "task.reset('Reset & Retry')",
        'pass',
        'retry: no reset',
    ),
    Mutant(
        EXECUTOR,
        (
            'for child in task.children.copy():\n'
            '            if child.state.is_failed:\n'
            '                self.retry_task(child)'
        ),
        'pass',
        'retry: failed children not retried',
    ),
    Mutant(
        EXECUTOR,
        'self.retry_task(task.group)',
        'pass',
        'retry: failed group not retried',
    ),
    Mutant(
        EXECUTOR,
        (
            'self._initialize_task(task)\n'
            '        self._start_worker()'
        ),
        'self._initialize_task(task)',
        'retry: no worker kick',
    ),
    Mutant(
        EXECUTOR,
        (
            'if not self.status_tracker.running_tasks:\n'
            '            return'
        ),
        'pass',
        'shutdown: no idle early return',
    ),
    Mutant(
        EXECUTOR,
        (
            'while self.queue.size():\n'
            '            self.queue.dequeue()'
        ),
        'pass',
        'shutdown: queue not drained',
    ),
    Mutant(
        EXECUTOR,
        'self._is_shutting_down = True\n',
        'pass\n',
        'shutdown: flag never set',
    ),
    Mutant(
        EXECUTOR,
        (
            'self._shutdown_thread.run()\n'
            '        self._is_shutting_down = False'
        ),
        'self._shutdown_thread.run()',
        'shutdown: flag stuck True forever',
    ),
    Mutant(
        EXECUTOR,
        'self._shutdown_thread.run()\n',
        'pass\n',
        'shutdown: does not wait for workers',
    ),
    Mutant(
        EXECUTOR,
        'self._state_counts[old_state] -= 1',
        'pass',
        'status: never decrement',
    ),
    Mutant(
        EXECUTOR,
        "self._state_counts['waiting'] == 0 and\n",
        '',
        'idle: ignore waiting count',
        equivalent='waiting tasks are also counted by the queue checks',
    ),
    Mutant(
        EXECUTOR,
        "self._state_counts['running'] == 0 and\n",
        '',
        'idle: ignore running count',
    ),
    Mutant(
        EXECUTOR,
        (
            ' and\n'
            '            self._executor.queue.size_deferred() == 0'
        ),
        '',
        'idle: ignore deferred queue',
    ),
    Mutant(
        EXECUTOR,
        'self._executor.queue.size() == 0 and\n',
        '',
        'idle: ignore main queue',
        equivalent='queued tasks are also counted by the waiting check',
    ),
    Mutant(
        EXECUTOR,
        (
            'elif self._idle_timer and self._idle_timer.isActive():\n'
            '            self._idle_timer.stop()'
        ),
        'pass',
        'idle: pending idle not cancelled when work resumes',
    ),
    Mutant(
        EXECUTOR,
        'self._executor.callbacks.status_updated.emit(status)',
        'pass',
        'status: no status_updated emit',
    ),
    Mutant(
        EXECUTOR,
        "'Failed': self._state_counts['failed'],",
        "'Failed': self._state_counts['completed'],",
        'status: wrong Failed count',
    ),
    Mutant(
        EXECUTOR,
        'task.predicate.evaluate(partial(self._handle_predicate, task))',
        'pass',
        'blocker: predicate never polled',
    ),
    Mutant(
        EXECUTOR,
        (
            'if self._block_task_with_parent(task):\n'
            '            self._executor.queue.suspend(task)\n'
            '            return True'
        ),
        'pass',
        'blocker: parent ignored',
    ),
    Mutant(
        EXECUTOR,
        'if not task.parent.state.is_completed and not task.state.is_inactive:',
        'if not task.parent.state.is_completed:',
        'blocker: inactive check removed',
        equivalent='a blocked child is not inactive when the parent is unfinished',
    ),
    Mutant(
        EXECUTOR,
        'self.predicate_failed.emit(task, TaskPredicateError(task.name))',
        'pass',
        'predicate fail: no failure emitted',
    ),
    Mutant(
        EXECUTOR,
        "task.state.set_retrying(f'Attempts left: {task.predicate.retry_left}')",
        'pass',
        'predicate retry: no RETRYING state',
    ),
    Mutant(
        RUNNER,
        'if all(task.state.is_completed for task in self.group.tasks):',
        'if any(task.state.is_completed for task in self.group.tasks):',
        'group: complete if ANY task completed',
    ),
    Mutant(
        RUNNER,
        "self.signals.runner_failed.emit(self.group, TaskEventError('Some tasks failed'))",
        'pass',
        'group: failure not emitted',
    ),
    Mutant(
        RUNNER,
        'while not all(task.state.is_completed or task.state.is_failed for task in self.group.tasks):',
        'while not all(task.state.is_completed for task in self.group.tasks):',
        'group: waits forever on failed task',
    ),
    Mutant(
        RUNNER,
        'self.signals.runner_started.emit(self.group)',
        'pass',
        'group: no started emit',
    ),
    Mutant(
        RUNNER,
        'self.signals.runner_started.emit(self.task)',
        'pass',
        'task: no started emit',
    ),
    Mutant(
        RUNNER,
        'except Exception as e:',
        'except ValueError as e:',
        'task runner: only catches ValueError',
    ),
    Mutant(
        RUNNER,
        'self.signals.runner_failed.emit(self.task, e)',
        'pass',
        'task runner: failure swallowed',
    ),
    Mutant(
        RUNNER,
        'self.signals.runner_completed.emit(self.task)',
        'pass',
        'task runner: completion swallowed',
    ),
    Mutant(
        QUEUE,
        (
            'self.remove_from_deferred(task)\n'
            '        self.enqueue(task)'
        ),
        'self.enqueue(task)',
        'promote: stays in deferred',
    ),
    Mutant(
        QUEUE,
        'heapq.heapify(self.heap)',
        'pass',
        'remove_from_queue: heap invariant broken',
    ),
    Mutant(
        QUEUE,
        (
            'self.heap.clear()\n'
            '        self.deferred.clear()'
        ),
        'self.heap.clear()',
        'clear: deferred not cleared',
    ),
    Mutant(
        QUEUE,
        'self.deferred[task.id] = task',
        'pass',
        'suspend: no-op',
    ),
    Mutant(
        QUEUE,
        (
            'try:\n'
            '                self.remove_from_deferred(task)\n'
            '            except self.DeferredTaskNotFound as e:\n'
            '                raise self.TaskNotFound from e'
        ),
        'pass',
        'remove_task: deferred tasks not removed',
    ),
    Mutant(
        QUEUE,
        'return heapq.heappop(self.heap)',
        'return self.heap.pop()',
        'dequeue: not priority order',
    ),
    Mutant(
        TASK_BASE,
        'return self.index < other.index',
        'return self.index > other.index',
        'heap order reversed (LIFO)',
    ),
    Mutant(
        TASK_BASE,
        'self.retry_policy.reset()',
        'pass',
        'reset_attempts ignored',
    ),
    Mutant(
        TASK_BASE,
        'self.predicate.reset()',
        'pass',
        'reset: predicate retries not reset',
    ),
    Mutant(
        TASK_BASE,
        'self.exception = None\n',
        'pass\n',
        'reset: stale exception kept',
    ),
    Mutant(
        TASK_BASE,
        (
            'self.parent.children.remove(self)\n'
            '            self.parent = None'
        ),
        'pass',
        'delete: stays in parent children',
    ),
    Mutant(
        TASK_BASE,
        'self.callbacks.delete()',
        'pass',
        'delete: callbacks not released',
    ),
    Mutant(
        TASK,
        'self.group.tasks.remove(self)',
        'pass',
        'delete: stays in group.tasks',
    ),
    Mutant(
        TASK,
        (
            'super().reset(comment, reset_attempts)\n'
            '        self.runner = TaskRunner(self)'
        ),
        'super().reset(comment, reset_attempts)',
        'reset: reuses auto-deleted TaskRunner',
    ),
    Mutant(
        TASK,
        (
            'super().reset(comment, reset_attempts)\n'
            '        self.runner = GroupRunner(self)'
        ),
        'super().reset(comment, reset_attempts)',
        'reset: reuses auto-deleted GroupRunner',
    ),
    Mutant(
        STATE,
        'self.is_completed, self.is_failed\n',
        'self.is_failed\n',
        'is_removable: completed not removable',
    ),
    Mutant(
        STATE,
        'self.is_waiting, self.is_deleted, self.is_inactive,',
        'self.is_deleted, self.is_inactive,',
        'is_removable: waiting not removable',
    ),
    Mutant(
        STATE,
        'self.is_running, self.is_retrying, self.is_blocked,',
        'self.is_running,',
        'is_active: only running',
    ),
    Mutant(
        STATE,
        'self._on_state_changed(previous_state, state)',
        'self._on_state_changed(state, previous_state)',
        'callback args swapped',
    ),
    Mutant(
        STATE,
        'self.history = self.history + (history,)',
        'pass',
        'history not recorded',
    ),
    Mutant(
        STATE,
        'if seconds < 0.1:',
        'if seconds < 0.01:',
        'format_duration threshold',
    ),
    Mutant(
        STATE,
        'hours = int(seconds // 3600)',
        'hours = int(seconds // 360)',
        'format_duration hours wrong',
    ),
    Mutant(
        RETRY,
        'retry_policy.attempt += 1',
        'pass',
        'retry: attempt never increments (infinite)',
    ),
    Mutant(
        RETRY,
        'QTimer.singleShot(delay * 1000, lambda: self.on_retry_task(task))',
        'QTimer.singleShot(delay, lambda: self.on_retry_task(task))',
        'retry: delay in ms rather than s',
    ),
    Mutant(
        RETRY,
        'delay = retry_policy.get_delay(context)',
        'delay = 0',
        'retry: delay ignored',
    ),
    Mutant(
        RETRY,
        (
            'task.state.set_retrying(\n'
            "                f'Attempts left: {retry_policy.max_attempts - retry_policy.attempt}')"
        ),
        'pass',
        'retry: no RETRYING state',
    ),
    Mutant(
        RETRY,
        'if retry_status == RetryStatus.RETRY:',
        'if retry_status != RetryStatus.FAIL:',
        'retry: SUCCESS treated as retry',
    ),
    Mutant(
        POLICY,
        'if self.attempt < self.max_attempts:',
        'if self.attempt <= self.max_attempts:',
        'SimpleRetry off-by-one',
    ),
    Mutant(
        POLICY,
        'return RetryStatus.SUCCESS if self.condition() else RetryStatus.RETRY',
        'return RetryStatus.RETRY if self.condition() else RetryStatus.SUCCESS',
        'Conditional retry inverted',
    ),
    Mutant(
        POLICY,
        (
            'except Exception as e:\n'
            '            return RetryStatus.FAIL'
        ),
        (
            'except Exception as e:\n'
            '            return RetryStatus.RETRY'
        ),
        'Conditional: raising condition retries',
    ),
    Mutant(
        POLICY,
        (
            'if self._matches_exception_list(context.exception, self.never_retry_on):\n'
            '            return RetryStatus.FAIL'
        ),
        'pass',
        'ExceptionBased: never_retry_on ignored',
    ),
    Mutant(
        POLICY,
        (
            'if self._matches_exception_list(context.exception, self.retry_on):\n'
            '            return RetryStatus.RETRY\n'
            '\n'
            '        return RetryStatus.FAIL'
        ),
        'return RetryStatus.RETRY',
        'ExceptionBased: retry_on ignored',
    ),
    Mutant(
        POLICY,
        (
            'self.attempt = 0\n'
            '        return None'
        ),
        'return None',
        'RetryPolicy.reset no-op',
    ),
    Mutant(
        DELAY,
        (
            'return min(delay, self.max_delay)\n'
            '\n'
            '\n'
            'class Exp'
        ),
        (
            'return delay\n'
            '\n'
            '\n'
            'class Exp'
        ),
        'Linear: no cap',
    ),
    Mutant(
        DELAY,
        'delay = self.delay_seconds * (self.multiplier ** attempt)',
        'delay = self.delay_seconds * self.multiplier * attempt',
        'Exponential formula wrong',
    ),
    Mutant(
        DELAY,
        'delay = self.delay_seconds + (self.delay_seconds * attempt)',
        'delay = self.delay_seconds',
        'Linear formula constant',
    ),
    Mutant(
        FACTORY,
        'return SimpleRetryPolicy(attempts, LinearBackoff(delay_seconds))',
        'return SimpleRetryPolicy(attempts, FixedDelay(delay_seconds))',
        'linear_retry returns fixed',
    ),
    Mutant(
        FACTORY,
        'delay_strategy = ExponentialBackoff(base_delay, 2, max_delay)',
        'delay_strategy = ExponentialBackoff(base_delay, max_delay, 2)',
        'exponential_retry args swapped',
    ),
    Mutant(
        PREDICATE,
        'self.retry_left -= 1',
        'pass',
        'predicate: never decrements',
    ),
    Mutant(
        PREDICATE,
        (
            'self.stop_timer()\n'
            '                predicate_handler(PredicateEventType.FAIL)'
        ),
        'predicate_handler(PredicateEventType.FAIL)',
        'predicate: timer keeps firing after FAIL',
    ),
    Mutant(
        PREDICATE,
        (
            'self.delete()\n'
            '                predicate_handler(PredicateEventType.SUCCESS)'
        ),
        'predicate_handler(PredicateEventType.SUCCESS)',
        'predicate: timer keeps firing after SUCCESS',
    ),
    Mutant(
        PREDICATE,
        (
            'if self.retry_left <= 0:\n'
            '            predicate_handler(PredicateEventType.FAIL)\n'
            '            return'
        ),
        'pass',
        'predicate: no exhausted guard',
    ),
    Mutant(
        PREDICATE,
        (
            'self.retry_left = self.max_retries\n'
            '\n'
            '    def delete'
        ),
        (
            'pass\n'
            '\n'
            '    def delete'
        ),
        'predicate.reset no-op',
    ),
    Mutant(
        PREDICATE,
        'self.timer.setInterval(self.retry_interval)',
        'pass',
        'predicate: interval ignored',
    ),
    Mutant(
        CALLBACKS,
        'return config.cleanup',
        'return True',
        'cleanup=False ignored (fires once)',
    ),
    Mutant(
        CALLBACKS,
        'return config.cleanup',
        'return False',
        'cleanup=True ignored (fires each time)',
    ),
    Mutant(
        CALLBACKS,
        (
            'self.on_finish = None\n'
            '        self.on_failed = None'
        ),
        'self.on_failed = None',
        'delete: on_finish retained',
    ),
    Mutant(
        BUILDER,
        'self.predicate_delay_ms = delay_ms',
        'pass',
        'builder: predicate delay ignored',
    ),
    Mutant(
        BUILDER,
        'self.predicate_max_attempts = max_attempts',
        'pass',
        'builder: predicate attempts ignored',
    ),
    Mutant(
        BUILDER,
        'retry_policy=self.retry_policy,',
        '',
        'builder: retry policy dropped on build',
    ),
    Mutant(
        BUILDER,
        (
            'parent=self.parent,\n'
            '            color=self.color,\n'
            '            data=self.data,'
        ),
        (
            'parent=self.parent,\n'
            '            color=self.color,'
        ),
        'builder: data dropped',
    ),
    Mutant(
        BUILDER,
        (
            'actions=tuple(self._actions),\n'
            '            comment=self.comment,'
        ),
        'comment=self.comment,',
        'builder: task actions dropped',
    ),
    Mutant(
        BUILDER,
        'minimum=self.minimum,',
        '',
        'builder: progress min dropped',
    ),
    Mutant(
        BUILDER,
        'maximum=self.maximum,',
        '',
        'builder: progress max dropped',
    ),
    Mutant(
        BUILDER,
        'if self.show_progress\n',
        'if not self.show_progress\n',
        'builder: progress mode inverted',
    ),
    Mutant(
        BUILDER,
        (
            'on_start=self.on_start,\n'
            '                on_finish=self.on_finish,\n'
            '                on_completed=self.on_completed,\n'
            '                on_failed=self.on_failed\n'
        ),
        (
            'on_finish=self.on_finish,\n'
            '                on_completed=self.on_completed,\n'
            '                on_failed=self.on_failed\n'
        ),
        'group builder: on_start dropped',
    ),
    Mutant(
        BUILDER,
        (
            'on_finish=self.on_finish,\n'
            '                on_completed=self.on_completed,\n'
            '                on_failed=self.on_failed\n'
        ),
        (
            'on_finish=self.on_finish,\n'
            '                on_completed=self.on_completed,\n'
        ),
        'group builder: on_failed dropped',
    ),
    Mutant(
        BUILDER,
        'group.add_tasks(*self.tasks)',
        'pass',
        'group builder: tasks dropped',
    ),
    Mutant(
        BUILDER,
        'maximum=len(self.tasks),',
        '',
        'group builder: progress max wrong',
    ),
    Mutant(
        BUILDER,
        'self.parent = parent',
        'pass',
        'builder: with_wait_for ignored',
    ),
    Mutant(
        BUILDER,
        'self.color = QColor(*color)',
        'pass',
        'with_color tuple ignored',
    ),
    Mutant(
        BUILDER,
        'self.color = user_color if user_color.isValid() else self._random_color.generate()',
        'self.color = user_color',
        'with_color invalid string not replaced',
    ),
    Mutant(
        SETTINGS,
        (
            "if mode != 'w':\n"
            '        return'
        ),
        'return',
        'open_settings: write mode never persists',
    ),
    Mutant(
        SETTINGS,
        (
            "if mode != 'w':\n"
            '        return'
        ),
        'pass',
        'open_settings: read mode also persists',
    ),
    Mutant(
        SETTINGS,
        (
            'except Exception as e:\n'
            "        print('[tqm error]: Invalid settings file. Resetting settings.', e)\n"
            '        settings = Settings()'
        ),
        (
            'except ZeroDivisionError as e:\n'
            '        settings = Settings()'
        ),
        'open_settings: corrupt file crashes',
    ),
    Mutant(
        SETTINGS,
        (
            'settings = Settings()\n'
            "        with json_file_path.open('w') as f:\n"
            '            json.dump(asdict(settings), f, indent=4)'
        ),
        'settings = Settings()',
        'open_settings: default not written',
    ),
    Mutant(
        SETTINGS,
        (
            "env = os.getenv('TQM_QSS_PATH')\n"
            '    if env:\n'
            '        return Path(env)'
        ),
        'pass',
        'get_qss_path: env override ignored',
    ),
    Mutant(
        SETTINGS,
        (
            'if not user_qss.exists():\n'
            '        user_qss.write_text(base_qss.read_text())'
        ),
        'user_qss.write_text(base_qss.read_text())',
        'get_qss_path: user qss overwritten each start',
    ),
    Mutant(
        SETTINGS,
        "env = os.environ.get('XDG_CONFIG_HOME')",
        'env = None',
        'XDG_CONFIG_HOME ignored',
    ),
    Mutant(
        CONTROLLER,
        (
            'for task in self._controller.get_all_tasks():\n'
            '            if task.state.is_failed:\n'
            '                self._executor.retry_task(task)'
        ),
        (
            'for task in self._controller.get_all_tasks():\n'
            '            self._executor.retry_task(task)'
        ),
        'retry_all: retries non-failed tasks',
    ),
    Mutant(
        CONTROLLER,
        (
            'if task.state.is_completed:\n'
            '                self._executor.remove_task(task)'
        ),
        'self._executor.remove_task(task)',
        'clear_completed: removes everything',
    ),
    Mutant(
        CONTROLLER,
        (
            'if task.state.is_failed:\n'
            '                self._executor.remove_task(task)'
        ),
        'self._executor.remove_task(task)',
        'clear_failed: removes everything',
    ),
    Mutant(
        CONTROLLER,
        (
            'if task.state.is_waiting:\n'
            '                self._executor.remove_task(task)'
        ),
        'self._executor.remove_task(task)',
        'clear_waiting: removes everything',
    ),
    Mutant(
        CONTROLLER,
        'self.max_workers_updated.emit(value)',
        'pass',
        'ui max workers: no signal',
    ),
    Mutant(
        CONTROLLER,
        (
            "with open_settings('w') as s:\n"
            '            s.max_workers = value'
        ),
        'pass',
        'ui max workers: not persisted',
    ),
    Mutant(
        CONTROLLER,
        'value = max(2, value)\n',
        'pass\n',
        'ui max workers: floor removed',
    ),
    Mutant(
        CONTROLLER,
        'self._on_task_update_progress(task, task.progress_bar.maximum)',
        'pass',
        'completed: progress not set to max',
    ),
    Mutant(
        CONTROLLER,
        "self._update_item_data(task, 'Completed', task.state.get_last().timestamp)",
        'pass',
        'completed: no Completed timestamp',
    ),
    Mutant(
        CONTROLLER,
        "self._update_item_data(group, 'Progress', completed_tasks)",
        'pass',
        'group progress not updated',
    ),
    Mutant(
        CONTROLLER,
        "self._update_item_data(task, 'Started', task.state.get_last().timestamp)",
        'pass',
        'started: no Started timestamp',
    ),
    Mutant(
        CONTROLLER,
        (
            'task.runner.signals.task_progress_updated.connect(\n'
            '            partial(self._on_task_update_progress, task)\n'
            '        )'
        ),
        'pass',
        'task progress not wired',
    ),
    Mutant(
        CONTROLLER,
        (
            'if not group_parent.rowCount():\n'
            '                self._executor.remove_task(group_parent.data(Qt.UserRole))'
        ),
        'pass',
        'empty group not removed',
    ),
    Mutant(
        CONTROLLER,
        'group_parent.removeRow(remove_row)',
        'pass',
        'child row not removed',
    ),
    Mutant(
        CONTROLLER,
        'tasks.extend(item.tasks)',
        'pass',
        'get_all_tasks omits group tasks',
    ),
    Mutant(
        CONTROLLER,
        (
            'for task in self.get_selected_tasks():\n'
            '            self._executor.retry_task(task)'
        ),
        'pass',
        'retry selected no-op',
    ),
    Mutant(
        CONTROLLER,
        (
            'for task in self.get_selected_tasks():\n'
            '            self._executor.remove_task(task)'
        ),
        'pass',
        'remove selected no-op',
    ),
    Mutant(
        CONTROLLER,
        'view.toolbar.run_all_tasks.clicked.connect(executor.start_workers)',
        'pass',
        'run-all button unwired',
    ),
    Mutant(
        CONTROLLER,
        'executor.callbacks.task_removed.connect(self.remove_task)',
        'pass',
        'task_removed not wired to view',
    ),
    Mutant(
        CONTROLLER,
        'view.toolbar.retry_all_btn.clicked.connect(self.retry_all_failed)',
        'pass',
        'retry-all button unwired',
    ),
]
