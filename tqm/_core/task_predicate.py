
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
    condition: Optional[Callable[[], bool]] = None
    max_retries: int = 2
    retry_interval: int = 1000

    # Created on first use, so it belongs to the main thread even when the task was built elsewhere.
    timer: Optional[QTimer] = field(init=False, default=None, repr=False)

    def __post_init__(self) -> None:
        self.retry_left = self.max_retries
        self.passed = False

    def reset(self) -> None:
        self.stop()
        self.retry_left = self.max_retries
        self.passed = False

    def delete(self) -> None:
        self.stop()
        self.condition = None

    def stop(self) -> None:
        if self.timer is not None:
            self.timer.stop()
            self.timer.deleteLater()
            self.timer = None

    def evaluate(self, predicate_handler: Callable[..., Any]) -> None:
        """Check the condition on a timer until it passes or the attempts run out.

        The handler gets a PredicateEventType, and for FAIL the exception the condition
        raised, if any. Call this on the main thread. See TaskExecutor._on_predicate_event.
        """
        condition = self.condition
        if condition is None or self.timer is not None:
            return

        if self.retry_left <= 0:
            predicate_handler(PredicateEventType.FAIL)
            return

        def _evaluate() -> None:
            self.retry_left -= 1
            predicate_handler(PredicateEventType.RETRY)
            try:
                passed = condition()
            except Exception as e:
                self.stop()
                predicate_handler(PredicateEventType.FAIL, e)
                return

            if passed:
                self.stop()
                self.passed = True
                predicate_handler(PredicateEventType.SUCCESS)
            elif self.retry_left <= 0:
                self.stop()
                predicate_handler(PredicateEventType.FAIL)

        self.timer = QTimer()
        self.timer.setInterval(self.retry_interval)
        self.timer.timeout.connect(_evaluate)
        self.timer.start()

    def inspect(self) -> Dict[str, Any]:
        return {
            'fn': extract_fn_name(self.condition),
            'retries': self.max_retries,
            'interval': self.retry_interval
        }
