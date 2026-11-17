from __future__ import annotations

import re
import copy
from typing import (Any, Set, Dict, List, Generic, TypeVar, Callable, Optional,
                    overload)

from PySide2.QtGui import QColor
from PySide2.QtCore import Qt

from .task import TaskUnit, TaskGroup, TaskExecutable
from ..utils import RandomColor
from ..exceptions import TaskGroupError
from ..typings import RGBA, TASK_COLOR
from .retry_policy import RetryPolicy, NoRetryPolicy, fixed_retry
from .task_actions import TaskAction, TaskActionVisibility
from .task_options import ProgressMode, ProgressBarOptions
from .task_callbacks import TaskCallbacks, CallbackConfig
from .task_predicate import TaskPredicate

TaskType = TypeVar('TaskType', TaskExecutable, TaskGroup)
Builder = TypeVar(
    'Builder',
    bound='_TaskBuilderBase[TaskBuilder | TaskGroupBuilder]'
)


class _TaskBuilderBase(Generic[Builder, TaskType]):
    """Base class for TaskBuilder and TaskGroupBuilder."""
    Actions = TaskActionVisibility
    DEFAULT_COLOR = QColor(230, 230, 230, 255)

    def __init__(self, name: str):
        self.name = name
        self.color = QColor(self.DEFAULT_COLOR)
        self.comment = ''

        self.parent: Optional[TaskUnit] = None

        self.predicate_condition: Optional[Callable[..., bool]] = None
        self.predicate_delay_ms = 2000
        self.predicate_max_attempts = 10

        self.retry_policy = NoRetryPolicy()

        self.data: Dict[str, Any] = {}

        self.on_start: Optional[CallbackConfig[TaskType]] = None
        self.on_finish: Optional[CallbackConfig[TaskType]] = None
        self.on_completed: Optional[CallbackConfig[TaskType]] = None
        self.on_failed: Optional[CallbackConfig[TaskType]] = None

        self._random_color = RandomColor()
        self._actions: List[TaskAction[TaskType]] = []

    def with_label(self: Builder, name: str) -> Builder:
        """Set the name of the task.

        >>> with_label('My Task')

        """
        self.name = name
        return self

    def with_comment(self: Builder, comment: str) -> Builder:
        """Add a comment to the task."""
        self.comment = comment
        return self

    def with_wait_for(self: Builder, parent: TaskUnit) -> Builder:
        """Wait for another task/group to finish before starting."""
        self.parent = parent
        return self

    def with_retry_policy(self: Builder, policy: RetryPolicy) -> Builder:
        """Sets the retry policy for the task builder.

        >>> from tqm import retry_policy
        >>> my_policy = retry_policy.ConditionalRetryPolicy(
        ...     5, retry_policy.LinearBackoff(5), lambda exception: isinstance(exception, IOError)
        ... )
        >>> with_retry_policy(my_policy)

        TODO: Add documentation about custom policy.
        """
        if not isinstance(policy, RetryPolicy):
            raise TypeError(f'Expected a RetryPolicy, got {policy!r}')
        self.retry_policy = policy
        return self

    def with_retry(
        self: Builder,
        max_attempts: int = 3,
        delay_seconds: int = 5,
    ) -> Builder:
        """Automatically retry the task if it fails on a fixed delay interval.

        For more advance retry features, use the `with_retry_policy`

        >>> with_retry(max_attempts=5)

        """
        self.retry_policy = fixed_retry(max_attempts, delay_seconds)
        return self

    def with_predicate(
        self: Builder,
        condition: Callable[..., bool],
        *,
        max_attempts: int = 2,
        delay_ms: int = 2000
    ) -> Builder:
        """Predicate to be executed before the task is started.

        >>> with_predicate(lambda: os.path.exists('file.txt'), max_attempts=2, delay_ms=2000)

        The condition takes no arguments. If it returns False, the task waits and the
        condition is checked again up to `max_attempts` times, every `delay_ms`
        milliseconds. If it raises, the task fails.

        """
        self.predicate_condition = condition
        self.predicate_delay_ms = delay_ms
        self.predicate_max_attempts = max_attempts
        return self

    def with_action(
        self: Builder,
        label: str,
        execute: Callable[[TaskType], Any],
        visibility: TaskActionVisibility = TaskActionVisibility.ON_COMPLETED
    ) -> Builder:
        """Add an action to the task.

        >>> with_action(
        ...    'Open File',
        ...    lambda task: QDesktopServices.openUrl(f'file://{task.data["file"]}'),
        ...    visibility=TaskActionVisibility.ON_COMPLETED
        ... )
        >>> with_action(
        ...    'Inspect Task',
        ...    lambda task: print(f'Running: {task.state.inspect()}'),
        ...    visibility=TaskActionVisibility.ALWAYS
        ... )

        An action is a context menu item that is displayed when the task is right-clicked.
        Can be called multiple times to add multiple actions.

        Tip: If you need to open a file, use `with_file_action` instead.

        """
        self._actions.append(TaskAction[TaskType](label, execute, visibility))
        return self

    def with_file_action(
        self: Builder,
        file: str,
        visibility: TaskActionVisibility = TaskActionVisibility.ON_COMPLETED
    ) -> Builder:
        """
        Adds a file menu action to the task, specifying a file to be used when the action is triggered.

        >>> with_file_action(__file__, visibility=TaskActionVisibility.ALWAYS)

        """
        self._actions.append(TaskAction[TaskType]('%file%', lambda _: file, visibility))
        return self

    def with_on_start(
        self: Builder,
        on_start: Callable[[TaskType], Any],
        cleanup: bool = True
    ) -> Builder:
        """Callback to be executed when the task begins its lifecycle.

        Args:
            on_start: Function to call when task starts. Receives the task as first argument.
            cleanup: If True (default), callback fires only once per task lifecycle.
                    If False, callback fires on each retry attempt.

        Examples:
            >>> with_on_start(lambda task: task.log('Task starting'))
            >>> with_on_start(lambda task: setup_resources(task), cleanup=False)  # Fire on each retry

        Note:
            The callback receives the task instance as its first argument.
        """
        self.on_start = CallbackConfig(on_start, cleanup)
        return self

    def with_on_failed(
        self: Builder,
        on_failed: Callable[[TaskType], Any],
        cleanup: bool = False
    ) -> Builder:
        """Callback to be executed when the task fails for good, after its retries.

        Args:
            on_failed: Function to call when task fails. Receives the task as first argument.
            cleanup: If True, callback fires only on the first final failure.
                    If False (default), it fires again after a manual retry fails.

        Examples:
            >>> with_on_failed(lambda task: task.log(f'Task failed: {task.exception}'))
            >>> with_on_failed(lambda task: send_alert(task), cleanup=True)  # Alert only once

        Note:
            The callback receives the task instance as its first argument.
            Use task.exception to access the failure reason.
        """
        self.on_failed = CallbackConfig(on_failed, cleanup)
        return self

    def with_on_finish(
        self: Builder,
        on_finish: Callable[[TaskType], Any],
        cleanup: bool = False
    ) -> Builder:
        """Callback to be executed when the task finishes for good, after its retries.

        Args:
            on_finish: Function to call when task finishes. Receives the task as first argument.
            cleanup: If True, callback fires only the first time the task finishes.
                    If False (default), it fires again after a manual retry finishes.

        Examples:
            >>> with_on_finish(lambda task: cleanup_temp_files(task))
            >>> with_on_finish(lambda task: log_final_state(task), cleanup=True)  # Log only once

        Note:
            The callback receives the task instance as its first argument.
            This fires regardless of success or failure.
        """
        self.on_finish = CallbackConfig(on_finish, cleanup)
        return self

    def with_on_completed(
        self: Builder,
        on_completed: Callable[[TaskType], Any],
        cleanup: bool = True
    ) -> Builder:
        """Callback to be executed when the task successfully completes.

        Args:
            on_completed: Function to call when task succeeds. Receives the task as first argument.
            cleanup: If True (default), callback fires only once when task succeeds.
                    If False, callback would fire on each successful retry (rarely useful).

        Examples:
            >>> with_on_completed(lambda task: task.log('Task completed successfully'))
            >>> with_on_completed(lambda task: save_results(task))

        Note:
            The callback receives the task instance as its first argument.
            This only fires on successful completion, not on failure.
        """
        self.on_completed = CallbackConfig(on_completed, cleanup)
        return self

    def with_data(self: Builder, **kwargs: Any) -> Builder:
        """Set additional data to the task.

        This can be used to store any additional data that is needed for the task.

        >>> with_data(key1='value1', key2='value2')

        NOTE: Make sure the data is JSON serializable as it will be stored as a string.

        """
        self.data.update(kwargs)
        return self

    @overload
    def with_color(self: Builder, color: RGBA) -> Builder:
        """Set the color of the task with an RGBA tuple.

        >>> with_color((255, 0, 0, 70))

        """

    @overload
    def with_color(self: Builder, color: Qt.GlobalColor) -> Builder:
        """Set the color of the task with a Qt.GlobalColor.

        >>> with_color(Qt.red)

        """

    @overload
    def with_color(self: Builder, color: str) -> Builder:
        """Set the color of the task with a string. It can be a color name or a hex value.

        >>> with_color('red')
        >>> with_color('#ff0000')

        """

    @overload
    def with_color(self: Builder) -> Builder:
        """Set the color of the task with a random color."""

    @overload
    def with_color(self: Builder, color: Optional[TASK_COLOR] = None) -> Builder: ...

    def with_color(self: Builder, color: Optional[TASK_COLOR] = None) -> Builder:
        """Set the color of the task.

        >>> with_color('red')
        >>> with_color('#ff0000')
        >>> with_color(Qt.red)
        >>> with_color('rgb(255, 0, 0)')
        >>> with_color((255, 0, 0, 70))
        >>> with_color() # Random color

        """
        if isinstance(color, QColor):
            self.color = color

        elif isinstance(color, (str, Qt.GlobalColor)):
            # Qt 5 does not parse 'rgb(...)' strings.
            rgb = re.fullmatch(r'\s*rgba?\(([\d\s,]+)\)\s*', color) if isinstance(color, str) else None
            user_color = QColor(*map(int, rgb.group(1).split(','))) if rgb else QColor(color)
            self.color = user_color if user_color.isValid() else self._random_color.generate()

        elif isinstance(color, tuple):
            self.color = QColor(*color)

        else:
            self.color = self._random_color.generate()

        return self


class TaskBuilder(_TaskBuilderBase['TaskBuilder', TaskExecutable]):
    """
    A builder class for creating Task instances.

    >>> task = TaskBuilder('My Task').build()

    """

    def __init__(self, name: str = ''):
        super().__init__(name)

        self.event: Callable[[TaskExecutable], Any] = lambda task: None

        # Progress bar options
        self.minimum = 0
        self.maximum = 100
        self.show_progress: Optional[bool] = None

    def with_event(
        self,
        event: Callable[[TaskExecutable], Any],
        *,
        show_progress: bool = False
    ) -> TaskBuilder:
        """Set the event of the task.

        >>> with_event(lambda task: print(task.name))
        >>> with_event(show_progress_event, show_progress=True)

        NOTE:
            - The first argument is the task itself.
            - The event reports progress with `task.emit_progress(value)`

        """
        self.event = event
        self.show_progress = show_progress
        return self

    def with_min_max(self, minimum: int = 0, maximum: int = 100) -> TaskBuilder:
        """Minimum and maximum values for the progress bar."""
        self.minimum = minimum
        self.maximum = maximum
        return self

    def build(self) -> TaskExecutable:
        return TaskExecutable(
            name=self.name,
            execute=self.event,
            actions=tuple(self._actions),
            comment=self.comment,
            parent=self.parent,
            color=self.color,
            # Copies, so tasks built from one builder or policy do not share attempts or data.
            data=dict(self.data),
            retry_policy=copy.copy(self.retry_policy),
            progress_bar=ProgressBarOptions(
                minimum=self.minimum,
                maximum=self.maximum,
                mode=(
                    ProgressMode.DETERMINATE
                    if self.show_progress
                    else ProgressMode.INDETERMINATE
                )
            ),
            predicate=TaskPredicate(
                condition=self.predicate_condition,
                max_retries=self.predicate_max_attempts,
                retry_interval=self.predicate_delay_ms,
            ),
            callbacks=TaskCallbacks(
                on_start=self.on_start,
                on_finish=self.on_finish,
                on_failed=self.on_failed,
                on_completed=self.on_completed,
            ),
        )


class TaskGroupBuilder(_TaskBuilderBase['TaskGroupBuilder', TaskGroup]):
    """
    A builder class for creating TqmTaskGroup instances.

    >>> group = TaskGroupBuilder('My Group').build()

    """

    def __init__(self, name: str = ''):
        super().__init__(name)

        self.tasks: Set[TaskExecutable] = set()

    def with_tasks(self, *tasks: TaskExecutable) -> TaskGroupBuilder:
        for task in tasks:
            self.tasks.add(task)
        return self

    def build(self) -> TaskGroup:
        if not isinstance(self.retry_policy, NoRetryPolicy):
            raise TaskGroupError(f'Group {self.name} cannot retry: give its tasks a retry policy')

        group = TaskGroup(
            name=self.name,
            parent=self.parent,
            comment=self.comment,
            color=self.color,
            data=dict(self.data),
            actions=tuple(self._actions),
            progress_bar=ProgressBarOptions(
                maximum=len(self.tasks),
                mode=ProgressMode.DETERMINATE
            ),
            predicate=TaskPredicate(
                condition=self.predicate_condition,
                max_retries=self.predicate_max_attempts,
                retry_interval=self.predicate_delay_ms,
            ),
            callbacks=TaskCallbacks(
                on_start=self.on_start,
                on_finish=self.on_finish,
                on_completed=self.on_completed,
                on_failed=self.on_failed
            )
        )

        group.add_tasks(*self.tasks)
        return group
