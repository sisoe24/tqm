from __future__ import annotations

from typing import Any, Dict, Generic, TypeVar, Callable, Optional
from dataclasses import dataclass

from ..utils import extract_fn_name

T = TypeVar('T')


@dataclass
class CallbackConfig(Generic[T]):
    callback: Optional[Callable[[T], Any]] = None
    cleanup: bool = True

    def inspect(self) -> Dict[str, Any]:
        return {
            'name': extract_fn_name(self.callback),
            'cleanup': self.cleanup
        }


@dataclass
class TaskCallbacks(Generic[T]):
    on_start: Optional[CallbackConfig[T]] = None
    on_finish: Optional[CallbackConfig[T]] = None
    on_failed: Optional[CallbackConfig[T]] = None
    on_completed: Optional[CallbackConfig[T]] = None

    def delete(self) -> None:
        """Delete all callback configurations and release their references."""
        self.on_start = None
        self.on_finish = None
        self.on_failed = None
        self.on_completed = None

    def _execute_callback(self, config: Optional[CallbackConfig[T]], task: T) -> bool:
        """Execute a callback configuration.

        Returns:
            True if the callback should be cleaned up (set to None), False otherwise.
        """
        if not config or not config.callback:
            return False

        config.callback(task)
        return config.cleanup

    def execute_on_start(self, task: T) -> None:
        if self._execute_callback(self.on_start, task):
            self.on_start = None

    def execute_on_finish(self, task: T) -> None:
        if self._execute_callback(self.on_finish, task):
            self.on_finish = None

    def execute_on_failed(self, task: T) -> None:
        if self._execute_callback(self.on_failed, task):
            self.on_failed = None

    def execute_on_completed(self, task: T) -> None:
        if self._execute_callback(self.on_completed, task):
            self.on_completed = None

    def inspect(self) -> Dict[str, Any]:
        return {
            'on_start': self.on_start.inspect() if self.on_start else '',
            'on_finish': self.on_finish.inspect() if self.on_finish else '',
            'on_failed': self.on_failed.inspect() if self.on_failed else '',
            'on_completed': self.on_completed.inspect() if self.on_completed else ''
        }
