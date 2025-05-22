from __future__ import annotations

from typing import Any, Set, Dict, Union, Callable, Optional
from dataclasses import field, dataclass

from ..utils import extract_fn_name
from .logger import LOGGER
from .task_base import TaskBase
from .task_runner import TaskRunner, GroupRunner

TaskUnit = Union[
    TaskBase['TaskExecutable', TaskRunner],
    TaskBase['TaskGroup', GroupRunner]
]


@dataclass
class TaskExecutable(TaskBase['TaskExecutable', TaskRunner]):
    execute: Callable[..., Any] = lambda: None
    group: Optional[TaskGroup] = None
    runner: TaskRunner = field(init=False)

    def __post_init__(self) -> None:
        super().__post_init__(suffix='Task')
        LOGGER.debug('TaskExecutable created: %s', str(self))
        self.runner = TaskRunner(self)

    def __hash__(self) -> int:
        return hash(self.id)

    def reset(self, comment: str = '', reset_attempts: bool = False) -> None:
        super().reset(comment, reset_attempts)
        self.runner = TaskRunner(self)

    def delete(self, comment: str = '') -> None:
        if self.group:
            self.group.tasks.remove(self)
        return super().delete(comment)

    def emit_progress(self, value: float) -> None:
        self.runner.signals.task_progress_updated.emit(value)

    def inspect(self) -> Dict[str, Any]:
        data = super().inspect()
        data['execute'] = extract_fn_name(self.execute)
        data['group'] = str(self.group) or ''
        return data


@dataclass
class TaskGroup(TaskBase['TaskGroup', GroupRunner]):
    tasks: Set[TaskExecutable] = field(init=False, default_factory=set[TaskExecutable])
    runner: GroupRunner = field(init=False)

    def __post_init__(self) -> None:
        super().__post_init__(suffix='Group')
        LOGGER.debug('Task Group Created: %s', str(self))
        self.runner = GroupRunner(self)

    def __hash__(self) -> int:
        return hash(self.id)

    def reset(self, comment: str = '', reset_attempts: bool = False) -> None:
        super().reset(comment, reset_attempts)
        self.runner = GroupRunner(self)

    def add_tasks(self, *tasks: TaskExecutable) -> None:
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
            progress (bool): If the task should show a progress.
            label (Optional[str], optional): The label of the task. If not provided,
                a default label will be generated.
            details (Optional[str], optional): Comment of the task. Defaults to ''.

        ```
        add_event(
           execute=lambda task: print(task.name),
           progress=True,
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
