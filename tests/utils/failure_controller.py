
from __future__ import annotations

from typing import Type, TypeVar, Callable, Optional

from tqm._core.task import TaskUnit

E = TypeVar('E', bound=Exception)


def raise_error(task: TaskUnit, skip_error: bool = False):
    if skip_error:
        return
    raise RuntimeError(task.name)


def failure_controller(
    task: TaskUnit,
    *,
    fail_count: Optional[int] = None,
    fail_until: Optional[Callable[[], bool]] = None,
    fail_if: Optional[Callable[[], bool]] = None,
    exception_type: Type[E] = RuntimeError,
    exception_msg: Optional[str] = None
) -> int:
    """
    A utility function that fails in a controlled manner based on different conditions.

    Args:
        task: The current task being executed
        fail_count: Fail exactly this many times, then succeed (uses a counter in task.data)
        fail_until: Callable that returns True when task should stop failing
        fail_if: Callable that returns True when task should fail
        exception_type: Type of exception to raise when failing
        exception_msg: Message for the exception (defaults to task name)

    The function uses task.data to store state between retries.
    """
    # Initialize attempt counter if not present
    if 'attempt_count' not in task.data:
        task.data['attempt_count'] = 0

    # Increment attempt counter
    task.data['attempt_count'] += 1
    attempt = task.data['attempt_count']

    # Determine if we should fail based on the specified condition
    should_fail = False

    if fail_count is not None:
        should_fail = attempt <= fail_count
    elif fail_until is not None:
        should_fail = not fail_until()
    elif fail_if is not None:
        should_fail = fail_if()

    # Raise exception if we should fail
    if should_fail:
        msg = exception_msg or f"{task.name} failed on attempt {attempt}"
        raise exception_type(msg)

    # If we didn't fail, return the attempt count
    return attempt
