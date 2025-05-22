from __future__ import annotations

import pytest

from tqm import TaskExecutable
from tqm._core import queue


def test_queue():
    q = queue.TasksQueue()
    assert q.is_empty()

    task = TaskExecutable(execute=lambda: None, name='abc')
    q.enqueue(task)

    assert not q.is_empty()
    assert q.peek() == task
    assert q.size() == 1

    t = q.dequeue()
    assert t == task
    assert q.is_empty()

    with pytest.raises(IndexError):
        q.dequeue()

    with pytest.raises(IndexError):
        q.peek()


def test_queue_multiple():
    q = queue.TasksQueue()
    assert q.is_empty()

    tasks = [
        TaskExecutable(execute=lambda: None, name='abc'),
        TaskExecutable(execute=lambda: None, name='def'),
        TaskExecutable(execute=lambda: None, name='ghi'),
    ]

    for t in tasks:
        q.enqueue(t)

    assert not q.is_empty()
    assert q.peek() == tasks[0]
    assert q.size() == 3

    t = q.dequeue()
    assert t == tasks[0]

    t = q.dequeue()
    assert t == tasks[1]

    t = q.dequeue()
    assert t == tasks[2]

    assert q.is_empty()


def test_defer_task():
    q = queue.TasksQueue()
    task = TaskExecutable(execute=lambda: None, name='abc')

    q.suspend(task)
    assert q.deferred[task.id] == task

    t = q.remove_from_deferred(task)
    assert t == task

    with pytest.raises(queue.DeferredTaskNotFound):
        q.remove_from_deferred(task)


def test_deferred_to_main():
    q = queue.TasksQueue()
    task = TaskExecutable(execute=lambda: None, name='abc')

    q.suspend(task)

    assert q.is_empty()
    assert q.size() == 0
    assert q.deferred[task.id] == task

    q.promote_to_main(task)

    assert not q.is_empty()
    assert q.peek() == task
    assert q.size() == 1

    t = q.dequeue()
    assert t == task
    assert q.is_empty()


def test_main_to_deferred():
    q = queue.TasksQueue()
    task = TaskExecutable(execute=lambda: None, name='abc')

    q.enqueue(task)

    assert not q.is_empty()
    assert q.size() == 1
    assert q.peek() == task

    assert task.id not in q.deferred

    q.main_to_deferred(task)

    assert q.is_empty()
    assert q.size() == 0
    assert task.id in q.deferred
    assert q.deferred[task.id] == task


def test_clear_queue():
    q = queue.TasksQueue()
    task = TaskExecutable(execute=lambda: None, name='abc')
    task1 = TaskExecutable(execute=lambda: None, name='def')

    q.enqueue(task1)
    q.suspend(task)
    q.clear()

    assert q.is_empty()
    assert q.heap == []
    assert q.deferred == {}


def test_remove_from_queue():
    q = queue.TasksQueue()
    task = TaskExecutable(execute=lambda: None, name='abc')

    q.enqueue(task)
    t = q.remove_from_queue(task)

    assert t == task
    assert q.is_empty()

    with pytest.raises(queue.TaskNotFoundError):
        q.remove_from_queue(task)


def test_remove_regular_task():
    q = queue.TasksQueue()
    task = TaskExecutable(execute=lambda: None, name='abc')

    q.enqueue(task)
    q.remove_task(task)

    assert q.is_empty()
    assert q.size() == 0


def test_remove_deferred_task():
    q = queue.TasksQueue()
    task = TaskExecutable(execute=lambda: None, name='abc')

    q.suspend(task)
    q.remove_task(task)

    assert q.deferred == {}
    assert q.size() == 0


def test_remove_task_not_in_queue():
    q = queue.TasksQueue()
    with pytest.raises(queue.TaskNotFoundError):
        q.remove_task(TaskExecutable(execute=lambda: None, name='def'))
