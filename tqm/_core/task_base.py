from __future__ import annotations

import uuid
import threading
from typing import (TYPE_CHECKING, Any, Set, Dict, List, Tuple, Generic, TypeVar,
                    Callable, Iterator, Optional)
from itertools import count
from dataclasses import field, dataclass

from PySide2.QtGui import QColor

from .logger import LOGGER, USER_LEVEL
from .task_state import TaskState
from .task_runner import RunnerSignals
from .retry_policy import RetryPolicy, NoRetryPolicy
from .task_actions import TaskAction
from .task_options import ProgressBarOptions
from .task_callbacks import TaskCallbacks
from .task_predicate import TaskPredicate

if TYPE_CHECKING:
    from .._ui.task_item import TaskItem
    from .task import TaskUnit

T = TypeVar('T')

_INDEX_CACHE: Dict[str, Iterator[int]] = {}


def index_gen(suffix: str) -> int:
    if suffix not in _INDEX_CACHE:
        _INDEX_CACHE[suffix] = count(1)
    return next(_INDEX_CACHE[suffix])


@dataclass
class TaskBase(Generic[T]):
    """Base class for both Task and TaskGroup entities."""

    # attributes
    name: str = ''
    comment: str = ''
    retry_policy: RetryPolicy = field(default_factory=NoRetryPolicy)
    exception: Optional[Exception] = field(init=False, default=None)

    # user data container
    data: Dict[str, Any] = field(repr=False, default_factory=dict[str, Any])

    # states
    state: TaskState = field(init=False, default_factory=TaskState, repr=False)

    # events
    actions: Tuple[TaskAction[T], ...] = field(default_factory=tuple, repr=False)
    predicate: TaskPredicate = field(default_factory=TaskPredicate, repr=False)
    callbacks: TaskCallbacks[T] = field(default_factory=TaskCallbacks['T'], repr=False)

    # The executor's signals, set when the task is added.
    signals: RunnerSignals = field(init=False, repr=False, compare=False)

    # UI
    color: QColor = QColor(220, 220, 220, 255)
    item: Optional[TaskItem] = field(init=False, repr=False, default=None)
    progress_bar: ProgressBarOptions = field(default_factory=ProgressBarOptions, repr=False)

    # relationships
    parent: Optional[TaskUnit] = None
    children: Set[TaskUnit] = field(init=False, default_factory=set['TaskUnit'])

    # id
    id: uuid.UUID = field(init=False, default_factory=uuid.uuid4)
    index: int = field(init=False)

    # cancel: set on the main thread, read by the running callable
    _cancel_requested: bool = field(init=False, default=False, repr=False, compare=False)
    _cancel_hooks: List[Callable[[], Any]] = field(init=False, default_factory=list, repr=False, compare=False)
    _cancel_lock: threading.Lock = field(init=False, default_factory=threading.Lock, repr=False, compare=False)

    def __post_init__(self, suffix: str = '') -> None:
        """Initialize the task state."""
        self.state.set_inactive()

        self.index = index_gen(suffix)

        if not self.name:
            self.name = f'{suffix}-{str(self.index).zfill(5)}'

        if self.parent:
            LOGGER.debug('Adding %s to parent %s', self.name, self.parent.name)
            self.parent.children.add(self)

    def __lt__(self, other: TaskBase[T]) -> bool:
        """Comparison method for the heap queue."""
        return self.index < other.index

    def __str__(self) -> str:
        return f'{self.name}.{self.state} <{self.id}>'

    def log(self, text: str) -> None:
        """Log a message with the task name as prefix."""
        # The tag lets each window show only the logs of its own tasks.
        tag = getattr(self, 'signals', None)
        extra = {'tqm_signals': tag, 'tqm_task': str(self.id)}
        LOGGER.log(USER_LEVEL, f'{self.name}: {text}', extra=extra)
        if tag:
            tag.task_logged.emit(self, text)

    @property
    def cancel_requested(self) -> bool:
        """True once the user asked to stop this task. A long callable checks it and returns."""
        return self._cancel_requested

    def on_cancel(self, hook: Callable[[], Any]) -> None:
        """Call `hook` when the task is cancelled, for work that blocks, like a subprocess.

        The hook runs on the thread that cancels the task. If the task is already
        cancelled, it runs now, on the caller's thread.

        ```
        proc = subprocess.Popen(cmd)
        task.on_cancel(proc.terminate)
        proc.wait()
        ```
        """
        with self._cancel_lock:
            if not self._cancel_requested:
                self._cancel_hooks.append(hook)
                return
        self._run_cancel_hook(hook)

    def _request_cancel(self) -> bool:
        """Set the flag and run the hooks once. False if the cancel was already requested."""
        with self._cancel_lock:
            if self._cancel_requested:
                return False
            self._cancel_requested = True
            hooks, self._cancel_hooks = self._cancel_hooks, []
        for hook in hooks:
            self._run_cancel_hook(hook)
        return True

    def _run_cancel_hook(self, hook: Callable[[], Any]) -> None:
        try:
            hook()
        except Exception as error:  # a broken hook must not stop the cancel
            LOGGER.error(f'{self.name} cancel hook failed: {error}', extra={'tqm_task': str(self.id)})

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
            self.retry_policy.reset()

        self.predicate.reset()
        self.exception = None

        with self._cancel_lock:
            self._cancel_requested = False
            self._cancel_hooks = []

    def set_failed(self, exception: Optional[Exception] = None, comment: str = '') -> None:
        self.exception = exception
        self.state.set_failed(comment)

    def inspect(self) -> Dict[str, Any]:
        return {
            'name': self.name,
            'id': str(self.id),
            'retry_policy': self.retry_policy.inspect(),
            'parent': str(self.parent or ''),
            'children': [str(child) for child in self.children],
            'data': self.data,
            'comment': self.comment,
            'callbacks': self.callbacks.inspect(),
            'state': self.state.inspect(),
            'actions': [action.inspect() for action in self.actions],
            'progress_bar_options': self.progress_bar.inspect(),
            'predicate': self.predicate.inspect(),
            'exception': str(self.exception or ''),
        }
