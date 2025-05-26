from __future__ import annotations

from typing import Callable, Optional

from PySide2.QtCore import QTimer, QObject

from .task import TaskUnit
from .logger import LOGGER
from .retry_policy.retry_policy import RetryStatus, RetryContext


class RetryHandler(QObject):
    """Handles retry logic for tasks."""

    def __init__(
        self,
        on_retry_task: Callable[[TaskUnit], None],
        parent: Optional[QObject] = None
    ) -> None:
        super().__init__(parent)
        self.on_retry_task = on_retry_task

    def handle_failure(self, task: TaskUnit, exception: Exception) -> bool:
        """
        Handle task failure. Returns True if retry will be attempted.
        """

        retry_policy = task.retry_policy

        context = RetryContext(task=task, exception=exception)
        retry_status = retry_policy.should_retry(context)

        if retry_status == RetryStatus.RETRY:

            delay = retry_policy.get_delay(context)
            QTimer.singleShot(delay * 1000, lambda: self.on_retry_task(task))

            retry_policy.attempt += 1
            task.state.set_retrying(
                f'Attempts left: {retry_policy.max_attempts - retry_policy.attempt}')
            LOGGER.debug(
                'Retry policy %s, attempt %s in %s seconds. Exception: %s',
                retry_policy, retry_policy.attempt, delay, exception
            )
            return True

        elif retry_status == RetryStatus.SUCCESS:
            LOGGER.debug('Task completed after %s attempts', retry_policy.attempt)
            return False

        LOGGER.debug('Task failed after %s attempts', retry_policy.attempt)
        return False
