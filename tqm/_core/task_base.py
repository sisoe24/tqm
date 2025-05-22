from __future__ import annotations

import uuid
from typing import (TYPE_CHECKING, Any, Set, Dict, Tuple, Generic, TypeVar,
                    Iterator, Optional, Generator)
from itertools import count
from dataclasses import field, dataclass

from PySide2.QtGui import QColor

from .logger import LOGGER, USER_LEVEL
from .task_state import TaskState
from .task_runner import BaseRunner
from .task_actions import TaskAction
from .task_options import ProgressBarOptions
from .._ui.task_item import TaskItem
from .task_callbacks import TaskCallbacks
from .task_predicate import TaskPredicate

if TYPE_CHECKING:
    from .task import TaskUnit

T = TypeVar('T')
W = TypeVar('W', bound=BaseRunner)

_INDEX_CACHE: Dict[str, Iterator[int]] = {}


def index_gen(suffix: str) -> int:
    if suffix not in _INDEX_CACHE:
        _INDEX_CACHE[suffix] = count(1)
    return next(_INDEX_CACHE[suffix])


@dataclass
class TaskBase(Generic[T, W]):
    """Base class for both Task and TaskGroup entities."""

    # attributes
    name: str = ''
    comment: str = ''
    retry_attempts: int = -1
    exception: Optional[Exception] = field(init=False, default=None)

    # user data container
    data: Dict[str, Any] = field(repr=False, default_factory=dict[str, Any])

    # states
    state: TaskState = field(init=False, default_factory=TaskState, repr=False)

    # events
    actions: Tuple[TaskAction[T], ...] = field(default_factory=tuple, repr=False)
    predicate: TaskPredicate = field(default_factory=TaskPredicate, repr=False)
    callbacks: TaskCallbacks[T] = field(default_factory=TaskCallbacks['T'], repr=False)

    runner: W = field(init=False)

    # UI
    color: QColor = QColor(220, 220, 220, 255)
    item: Optional[TaskItem] = field(init=False, repr=False, default=None)
    progress_bar: ProgressBarOptions = field(default_factory=ProgressBarOptions, repr=False)

    # relationships
    parent: Optional[TaskUnit] = None
    children: Set[TaskUnit] = field(init=False, default_factory=set['TqmTaskUnit'])

    # id
    id: uuid.UUID = field(init=False, default_factory=uuid.uuid4)
    index: int = field(init=False)

    def __post_init__(self, suffix: str = '') -> None:
        """Initialize the task state."""
        self.state.set_inactive()

        self.index = index_gen(suffix)

        if not self.name:
            self.name = f'{suffix}-{str(self.index).zfill(5)}'

        if self.parent:
            LOGGER.debug('Adding %s to parent %s', self.name, self.parent.name)
            self.parent.children.add(self)

        self._initial_attempts = self.retry_attempts

    def __eq__(self, value: object) -> bool:
        if not isinstance(value, TaskBase):
            raise NotImplementedError(f'Cannot compare a task object to {type(value)}')
        return self.id == value.id

    def __lt__(self, other: TaskBase[T, W]) -> bool:
        """Comparison method for the heap queue."""
        return self.index < other.index

    def __str__(self) -> str:
        return f'{self.name}.{self.state} <{self.id}>'

    def log(self, text: str) -> None:
        """Log a message with the task name as prefix."""
        LOGGER.log(USER_LEVEL, f'{self.name}: {text}')

    def get_children(self) -> Set[TaskUnit]:
        """Return all the children of the task recursively."""
        def recurse(task: TaskUnit) -> Generator[TaskUnit, Any, None]:
            for child in filter(lambda t: not t.state.is_inactive, task.children):
                yield child
                yield from recurse(child)
        return set(recurse(self))

    def can_retry(self) -> bool:
        """Check if the task can be retried."""
        return self.retry_attempts > 0

    def retry(self) -> None:
        if self.retry_attempts <= 0:
            raise ValueError('Not enough retry attempts')
        self.retry_attempts -= 1

    def delete(self, comment: str = '') -> None:
        """Mark the task as deleted and clean up resources."""
        self.predicate.delete()
        self.callbacks.delete()
        self.state.set_deleted(comment)

        if self.parent:
            self.parent.children.remove(self)
            self.parent = None

    def reset(self, comment: str = '', reset_attempts: bool = False) -> None:
        self.state.set_inactive(comment)

        if reset_attempts:
            self.retry_attempts = self._initial_attempts

        self.predicate.reset()
        self.exception = None

    def set_failed(self, exception: Optional[Exception] = None, comment: str = '') -> None:
        # XXX should we override previous exception with None?
        if exception is not None:
            self.exception = exception
        self.state.set_failed(comment)

    def inspect(self) -> Dict[str, Any]:
        return {
            'name': self.name,
            'id': str(self.id),
            'retry_attempts': self.retry_attempts,
            'parent': str(self.parent or ''),
            'children': [str(child) for child in self.children],
            'data': self.data,
            'comment': self.comment,
            'callbacks': self.callbacks.inspect(),
            'runner': str(self.runner),
            'state': self.state.inspect(),
            'actions': [action.inspect() for action in self.actions],
            'progress_bar_options': self.progress_bar.inspect(),
            'predicate': self.predicate.inspect(),
            'exception': str(self.exception or ''),
        }
