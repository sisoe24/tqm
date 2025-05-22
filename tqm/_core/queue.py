from __future__ import annotations

import heapq
from uuid import UUID
from typing import Dict, List, Iterator

from tqm._core.task import TaskGroup, TaskExecutable
from tqm._core.task_base import TaskBase
from tqm._core.task_runner import TaskRunner, GroupRunner

from .task import TaskUnit


class DeferredTaskNotFound(Exception):
    pass


class TaskNotFoundError(Exception):
    pass


class TasksQueue:
    """Simple heap-based priority queue for tasks.

    The class also includes a deferred queue for tasks that are not ready to be
    executed. The deferred queue is a simple dictionary with the task id as the
    key and the task as the value.

    """

    DeferredTaskNotFound = DeferredTaskNotFound
    TaskNotFound = TaskNotFoundError

    def __init__(self) -> None:
        self.heap: List[TaskUnit] = []
        self.deferred: Dict[UUID, TaskUnit] = {}

    def is_empty(self) -> bool:
        """Return True if the queue is empty."""
        return not bool(self.heap)

    def peek(self) -> TaskUnit:
        """Return the task with the highest priority in the queue."""
        if not self.is_empty():
            return self.heap[0]
        raise IndexError('Queue is empty')

    def size(self) -> int:
        """Return the number of tasks in the main queue (heap)."""
        return len(self.heap)

    def size_deferred(self) -> int:
        return len(self.deferred)

    def enqueue(self, task: TaskUnit) -> None:
        """Push a task into the queue."""
        heapq.heappush(self.heap, task)

    def dequeue(self) -> TaskUnit:
        """Pop the task with the highest priority from the queue."""
        if not self.is_empty():
            return heapq.heappop(self.heap)
        raise IndexError('Queue is empty')

    def suspend(self, task: TaskUnit) -> None:
        """Defer a task to be executed later."""
        self.deferred[task.id] = task

    def is_task_deferred(self, task: TaskUnit) -> bool:
        """Check if task is in the deferred queue."""
        return task.id in self.deferred

    def remove_from_deferred(self, task: TaskUnit) -> TaskUnit:
        """Remove a task from the deferred queue.

        Raises:
            TasksQueueDeferredItemNotFound: If the task is not found in the deferred queue.
        """
        try:
            self.deferred.pop(task.id)
        except (ValueError, KeyError) as e:
            raise DeferredTaskNotFound(
                f'Item {task.name} not found in deferred queue'
            ) from e
        return task

    def main_to_deferred(self, task: TaskUnit) -> None:
        """Transfer a task from the main queue to the deferred queue."""
        self.remove_from_queue(task)
        self.suspend(task)

    def promote_to_main(self, task: TaskUnit) -> None:
        """Transfer a task from the deferred queue to the main queue."""
        self.remove_from_deferred(task)
        self.enqueue(task)

    def remove_from_queue(self, task: TaskUnit) -> TaskUnit:
        """Remove a task from the queue.

        Raises:
            TaskNotFoundError: If the task is not found in the queue.
        """
        try:
            self.heap.remove(task)
        except ValueError as e:
            raise TaskNotFoundError(f'Item {task.name} not found in queue') from e

        heapq.heapify(self.heap)
        return task

    def clear(self) -> None:
        """Clear the queue and deferred queue."""
        self.heap.clear()
        self.deferred.clear()

    def remove_task(self, task: TaskUnit) -> None:
        """Delete a task from the queue or deferred queue.

        Raises:
            TaskNotFoundError: If the task is not found in the queue or deferred queue.
        """
        try:
            self.remove_from_queue(task)
        except self.TaskNotFound:
            try:
                self.remove_from_deferred(task)
            except self.DeferredTaskNotFound as e:
                raise self.TaskNotFound from e

    def __iter__(self) -> Iterator[TaskBase[TaskExecutable, TaskRunner] | TaskBase[TaskGroup, GroupRunner]]:
        return iter([*self.heap, *self.deferred.values()])

    def __contains__(self, task: TaskUnit) -> bool:
        """
        Check if a given task is present in the queue.

        NOTE: debug only. not optimize for fast lookup

        Args:
            task (TqmTaskUnit): The task to check for presence in the queue.

        Returns:
            bool: True if the task is found in the deferred list or the heap,
                  otherwise False.
        """

        return (
            True if task.id in self.deferred
            else any(t == task for t in self.heap)
        )
