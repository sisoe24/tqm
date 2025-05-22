
from __future__ import annotations

from enum import Enum, auto
from typing import Any, Dict, Callable, Optional
from dataclasses import field, dataclass

from PySide2.QtCore import QTimer

from ..utils import extract_fn_name


class PredicateEventType(Enum):
    START = auto()
    RETRY = auto()
    SUCCESS = auto()
    FAIL = auto()


@dataclass
class TaskPredicate:
    condition: Optional[Callable[..., bool]] = None
    max_retries: int = 2
    retry_interval: int = 1000

    timer: QTimer = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self.timer = QTimer()
        self.timer.setInterval(self.retry_interval)
        self.retry_left = self.max_retries

    def reset(self) -> None:
        self.retry_left = self.max_retries

    def delete(self) -> None:
        if self.timer.isActive():
            self.timer.stop()
            self.timer.deleteLater()
        self.condition = None

    def stop_timer(self) -> None:
        if self.timer.isActive():
            self.timer.stop()
            self.timer.timeout.disconnect()

    def evaluate(self, predicate_handler: Callable[[PredicateEventType], Any]) -> None:
        """Evaluate the predicate condition with retry logic.

        This method checks if the predicate condition is met. If not, it will retry
        according to the configured retry settings. The status_notifier callback
        is called with different PredicateEventType values to report the state.

        Args:
            status_notifier: Callback function that receives status updates

        NOTE: See TaskExecutor._handle_predicate for an example
        """
        condition = self.condition
        if condition is None:
            return

        if self.retry_left <= 0:
            predicate_handler(PredicateEventType.FAIL)
            return

        def _evaluate() -> None:
            self.retry_left -= 1
            predicate_handler(PredicateEventType.RETRY)

            if condition():
                self.delete()
                predicate_handler(PredicateEventType.SUCCESS)

            elif self.retry_left <= 0:
                self.stop_timer()
                predicate_handler(PredicateEventType.FAIL)

        if not self.timer.isActive():
            self.timer.timeout.connect(_evaluate)
            self.timer.start()

    def inspect(self) -> Dict[str, Any]:
        return {
            'fn': extract_fn_name(self.condition),
            'retries': self.max_retries,
            'interval': self.retry_interval
        }
