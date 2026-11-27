from __future__ import annotations

from typing import Any, Set, Dict, Union, Callable, Optional
from dataclasses import field, dataclass

from ..utils import extract_fn_name
from ..exceptions import TaskGroupError
from .logger import LOGGER
from .task_base import TaskBase

TaskUnit = Union[TaskBase['TaskExecutable'], TaskBase['TaskGroup']]


@dataclass
class TaskExecutable(TaskBase['TaskExecutable']):
    execute: Callable[..., Any] = lambda task: None
    group: Optional[TaskGroup] = None
    # The callable checks `cancel_requested` or uses `on_cancel`, so Stop can end it.
    cancellable: bool = False

    def __post_init__(self) -> None:
        super().__post_init__(suffix='Task')
        LOGGER.debug('TaskExecutable created: %s', str(self))

    def __hash__(self) -> int:
        return hash(self.id)

    def delete(self, comment: str = '') -> None:
        if self.group:
            self.group.tasks.remove(self)
        return super().delete(comment)

    def emit_progress(self, value: float) -> None:
        self.signals.task_progress_updated.emit(self, value)

    def inspect(self) -> Dict[str, Any]:
        data = super().inspect()
        data['execute'] = extract_fn_name(self.execute)
        data['group'] = str(self.group) or ''
        return data


@dataclass
class TaskGroup(TaskBase['TaskGroup']):
    tasks: Set[TaskExecutable] = field(init=False, default_factory=set[TaskExecutable])

    def __post_init__(self) -> None:
        super().__post_init__(suffix='Group')
        LOGGER.debug('Task Group Created: %s', str(self))

    def __hash__(self) -> int:
        return hash(self.id)

    @property
    def cancellable(self) -> bool:
        """True if every member is cancellable. A group has no flag of its own."""
        return all(task.cancellable for task in self.tasks)

    def add_tasks(self, *tasks: TaskExecutable) -> None:
        # Members are registered when the group starts, so a later member would never run.
        if self.state.is_running:
            raise TaskGroupError(f'Cannot add tasks to running group {self.name}')

        for task in tasks:
            self.tasks.add(task)
            task.group = self

    def add_event(
        self,
        execute: Callable[[TaskExecutable], Any],
        *,
        show_progress: bool = False,
        label: str = '',
        comment: str = ''
    ) -> TaskExecutable:
        """Add a simple task to the queue.

        Args:
            execute (Callable[..., Any]): The event to be executed. The first argument is the task itself.
            show_progress (bool): If the task should show a progress.
            label (Optional[str], optional): The label of the task. If not provided,
                a default label will be generated.
            comment (str, optional): Comment of the task. Defaults to ''.

        ```
        add_event(
           execute=lambda task: print(task.name),
           show_progress=True,
           label='My task',
           comment='Comment of the task'
        )
        ```
        """
        # XXX: find a better way to avoid circular dependency
        from .task_builder import TaskBuilder
        task = (
            TaskBuilder(name=label)
            .with_event(execute, show_progress=show_progress)
            .with_comment(comment)
            .build()
        )
        self.add_tasks(task)
        return task

    def inspect(self) -> Dict[str, Any]:
        data = super().inspect()
        data['tasks'] = [str(task) for task in self.tasks]
        return data
