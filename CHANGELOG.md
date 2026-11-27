# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## v0.5.0 (2026-11-27)

### Added

- `TaskBuilder.with_event(event, cancellable=True)` marks a task whose callable stops when asked: it checks `task.cancel_requested`, uses `task.on_cancel`, or runs `tqm.utils.run_process`. It is set with the callable, like `show_progress`, because it is a promise about that callable. `TQManager.add_event` and `TaskGroup.add_event` take the same `cancellable` argument.

### Changed

- Stop is opt-in per task, off by default. A running thread cannot be killed, so a task without `cancellable=True` cannot be stopped in any state: Stop selected is not offered for it, and `cancel_tasks()` leaves it alone and logs a warning. A group has no flag: it can be stopped only if all its tasks are cancellable.
- The tasks that wait for a stopped task still end cancelled, cancellable or not, since they can never run. A running task that is not cancellable is never asked to stop.
- Stop selected shows when at least one selected task can be stopped, and stops only those.

## v0.4.0 (2026-11-23)

### Added

- Selecting tasks in the tree filters the log panel to their lines; groups include their children.
- A click on empty space in the tree clears the selection, so the log panel shows every task again.
- A "Last message" column shows the latest `task.log` line of each task.
- `callbacks.task_logged(task, text)` signal.
- A View toolbar button with Show Log and Show Debug Panel toggles. The log panel state is remembered; the debug panel starts closed.
- Stop a task: `TQManager.cancel_tasks(*tasks)`, or Stop selected in the right-click menu. A task that has not started ends cancelled at once. A running task cannot be killed: its callable checks `task.cancel_requested`, or registers a hook with `task.on_cancel(proc.terminate)`, and the task ends cancelled when the callable returns.
- A `cancelled` state. Its children and group members are cancelled too, it is not retried by its policy, and it can be retried or removed by hand.
- `callbacks.runner_cancelled(task)` signal.
- `tqm.utils.run_process(task, cmd, timeout=None, **popen_kwargs)` runs a command for a task. Its output goes to the task log. A stop or the timeout kills the whole process tree. A non-zero exit raises `subprocess.CalledProcessError` with the last output lines.
- `exceptions.TaskCancelled`, raised by `run_process` when the task is stopped.

### Changed

- Log panel lines are colored by task, not by thread, and no longer show the thread column.
- The log panel opens at 70/30 on first launch and remembers its size. `DEV_MODE` no longer affects it.
- Icons come from one set, Lucide (ISC license, in `resources/icons`). Unused icons are removed.

### Fixed

- The last column of the tree no longer stretches, so the tree scrolls to its end. A layout saved by an older version can still hold a squashed column: use Reset layout.

## v0.3.0

### Added

- `TQManager.log(text)` writes to that manager's log panel and file.

### Changed

- Python 3.9 or newer is required.
- `shutdown()` returns at once. Tasks not started are removed; running tasks finish without retries.
- `on_task_failed` callbacks get `(task, exception)` and fire once per final failure.
- Adding or starting tasks off the thread that created the manager raises `TaskError`.
- Re-adding a removed task raises `TaskError`.
- `conditional_retry`: `retry_if` gets the exception and returns True to retry.
- A `TaskGroupBuilder` with a retry policy raises at build. `with_retry_policy(None)` raises `TypeError`.
- Settings and log handlers are kept per manager. `TQM_CONFIG_PATH` and `TQM_SETTINGS_PATH` are no longer set. `TqmLogger.widget` is removed.
- Default sort is by name, ascending, in natural order.
- `pytest` is no longer a runtime dependency.

### Fixed

- Crashes on retry and on garbage collection in worker threads.
- Task groups starving the pool, and many state, remove, retry, shutdown, settings, log and UI bugs found in an audit.

## v0.2.0 (2025-05-26)

### Added

- Retry policy for failing tasks.
- Improved task callbacks with custom configuration.

### Changed

- Moved task callback execution on main thread rather than task runner thread.
- Replace tab layout with splitter. Logs tabs is now on the bottom side of the main widget.

## v0.1.0 (2025-05-20)

- Initial release
