from __future__ import annotations

from enum import Enum, auto
from typing import Any, Dict, Generic, TypeVar, Callable
from dataclasses import dataclass

from ..utils import extract_fn_name

T = TypeVar('T')


class TaskActionVisibility(Enum):
    ON_COMPLETED = auto()
    ON_FAILED = auto()
    ALWAYS = auto()


@dataclass(frozen=True)
class TaskAction(Generic[T]):
    name: str
    action: Callable[[T], Any]
    visibility: TaskActionVisibility = TaskActionVisibility.ON_COMPLETED

    def inspect(self) -> Dict[str, str]:
        return {
            'name': self.name,
            'action': extract_fn_name(self.action),
            'visibility': self.visibility.name,
        }
