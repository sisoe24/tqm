# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

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
