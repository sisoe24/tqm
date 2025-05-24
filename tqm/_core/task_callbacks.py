from __future__ import annotations

from typing import Any, Dict, Generic, TypeVar, Callable, Optional
from dataclasses import dataclass

from tqm.utils import extract_fn_name

T = TypeVar('T')


@dataclass
class TaskCallbacks(Generic[T]):
    on_start: Optional[Callable[[T], Any]] = None
    on_finish: Optional[Callable[[T], Any]] = None
    on_failed: Optional[Callable[[T], Any]] = None
    on_completed: Optional[Callable[[T], Any]] = None

    def delete(self) -> None:
        self.on_start = None
        self.on_finish = None
        self.on_failed = None
        self.on_completed = None

    def inspect(self) -> Dict[str, str]:
        return {
            'on_start': extract_fn_name(self.on_start),
            'on_finish': extract_fn_name(self.on_finish),
            'on_failed': extract_fn_name(self.on_failed),
            'on_completed': extract_fn_name(self.on_completed),
        }
