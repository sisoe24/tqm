from __future__ import annotations

from typing import (Any, Set, Dict, List, Generic, TypeVar, Callable, Optional,
                    overload)

from PySide2.QtGui import QColor
from PySide2.QtCore import Qt

from .task import TaskGroup, TqmTaskUnit, TaskExecutable
from ..utils import RandomColor
from ..typings import RGBA, TASK_COLOR
from .task_actions import TaskAction, TaskActionVisibility
from .task_options import ProgressMode, ProgressBarOptions
from .task_callbacks import TaskCallbacks
from .task_predicate import TaskPredicate

TaskType = TypeVar('TaskType', TaskExecutable, TaskGroup)
Builder = TypeVar(
    'Builder',
    bound='_TaskBuilderBase[TaskBuilder | TaskGroupBuilder]'
)


class _TaskBuilderBase(Generic[Builder, TaskType]):
    """Base class for TaskBuilder and TaskGroupBuilder."""
    Actions = TaskActionVisibility

    def __init__(self, name: str):
        self.name = name
        self.color = QColor(230, 230, 230, 255)
        self.comment = ''

        self.parent: Optional[TqmTaskUnit] = None

        self.predicate: Optional[Callable[..., bool]] = None
        self.retry_interval_ms = 2000
        self.predicate_retries = 10

        self.max_retry_failed_attempts = 0

        self.data: Dict[str, Any] = {}

        self.on_start: Optional[Callable[[TaskType], Any]] = None
        self.on_finish: Optional[Callable[[TaskType], Any]] = None
        self.on_completed: Optional[Callable[[TaskType], Any]] = None
        self.on_failed: Optional[Callable[[TaskType], Any]] = None

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

    def with_wait_for(self: Builder, parent: TqmTaskUnit) -> Builder:
        """Wait for another task/group to finish before starting."""
        self.parent = parent
        return self

    def with_retry_failed(self: Builder, max_retries: int = 0) -> Builder:
        """Automatically retry the task if it fails.

        >>> with_retry_on_failed(max_retries=5)

        TODO: Add delay between retries

        """
        self.max_retry_failed_attempts = max_retries
        return self

    def with_predicate(
        self: Builder,
        predicate: Callable[..., bool],
        *,
        max_retries: int = 2,
        retry_interval_ms: int = 2000
    ) -> Builder:
        """Predicate to be executed before the task is started.

        >>> with_predicate(lambda _: os.path.exists('file.txt'), max_retries=2, retry_interval_ms=2000)

        If the predicate returns False, the task will not be executed. If
        `max_retries` is set, the task will be retried that many times every
        `retry_interval_ms` milliseconds.

        """
        self.predicate = predicate
        self.retry_interval_ms = retry_interval_ms
        self.predicate_retries = max_retries
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
        ...    lambda t: QDesktopServices.openUrl(f'file://{task.data["file"]}'),
        ...    visibility=TaskActionVisibility.ON_COMPLETED
        ... )
        >>> with_action(
        ...    'Inspect Task',
        ...    lambda task: print(f'Running: {task.state.inspect()}'),
        ...    visibility=TaskActionVisibility.ALWAYS
        ... )

        An action is a context menu item that is displayed when the task is right-clicked.
        Can be called multiple times to add multiple actions.

        Tip: If you need to open a file, use `with_file` instead.

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

    def with_on_start(self: Builder, on_start: Callable[[TaskType], Any], *args: Any, **kwargs: Any) -> Builder:
        """Callback to be executed before the task is started.

        >>> with_on_start(lambda task: print(task.name))

        NOTE: The first argument is the task itself.

        """
        self.on_start = on_start
        return self

    def with_on_failed(self: Builder, on_failed: Callable[[TaskType], Any]) -> Builder:
        """Callback to be executed if the task fails.

       >>> with_on_failed(lambda task: print(f'Error in {task.name}'))

        NOTE: The first argument is the task itself.

        """
        self.on_failed = on_failed
        return self

    def with_on_finish(self: Builder, on_finish: Callable[[TaskType], Any]) -> Builder:
        """Callback to be executed after the task is finished.

        >>> with_on_finish(lambda task: print(task.name))

        NOTE: The first argument is the task itself.

        """
        self.on_finish = on_finish
        return self

    def with_on_completed(self: Builder, on_completed: Callable[[TaskType], Any]) -> Builder:
        """Callback to be executed when the task is completed.

        >>> with_on_completed(lambda task: print(task.name))

        NOTE: The first argument is the task itself.

        """
        self.on_completed = on_completed
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
            user_color = QColor(color)
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
            - The progress is emitted by the `task.update_progress` signal

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
            data=self.data,
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
                condition=self.predicate,
                max_retries=self.predicate_retries,
                retry_interval=self.retry_interval_ms,
            ),
            retry_attempts=self.max_retry_failed_attempts,
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
        group = TaskGroup(
            name=self.name,
            parent=self.parent,
            comment=self.comment,
            color=self.color,
            actions=tuple(self._actions),
            progress_bar=ProgressBarOptions(
                maximum=len(self.tasks),
                mode=ProgressMode.DETERMINATE
            ),
            predicate=TaskPredicate(
                condition=self.predicate,
                max_retries=self.predicate_retries,
                retry_interval=self.retry_interval_ms,
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
