from __future__ import annotations

import contextlib
from typing import Any, List

import pytest

from tqm import TaskBuilder, TaskExecutor
from tqm._core.task_state import TaskState

from ..utils import raise_error
from ..utils.harness import StepPool


@pytest.mark.xfail(strict=True, raises=AssertionError, reason='V5')
def test_queued_tasks_run_after_failures(executor: TaskExecutor, step_pool: StepPool):
    executor.set_max_workers(2)
    tasks = [TaskBuilder().with_event(raise_error).build() for _ in range(8)]
    for task in tasks:
        executor.add_task(task)

    executor.start_workers()
    step_pool.drain()

    assert all(task.state.is_failed for task in tasks)


@pytest.mark.xfail(strict=True, raises=AssertionError, reason='V17')
def test_manager_on_task_failed_fires(executor: TaskExecutor, step_pool: StepPool):
    failed: List[Any] = []
    executor.callbacks.on_task_failed(lambda *args: failed.append(args))
    task = TaskBuilder().with_event(raise_error).build()
    executor.add_task(task)

    executor.start_workers()
    step_pool.drain()

    assert failed


@pytest.mark.xfail(strict=True, raises=AssertionError, reason='V18')
def test_on_failed_sees_the_failure(executor: TaskExecutor, step_pool: StepPool):
    seen: List[Any] = []
    task = (
        TaskBuilder('Boom')
        .with_event(raise_error)
        .with_on_failed(lambda t: seen.append((t.state.is_failed, t.exception)))
        .build()
    )
    executor.add_task(task)

    executor.start_workers()
    step_pool.drain()

    assert seen[0][0]
    assert isinstance(seen[0][1], RuntimeError)


@pytest.mark.xfail(strict=True, raises=AssertionError, reason='V18')
def test_on_finish_sees_the_failure(executor: TaskExecutor, step_pool: StepPool):
    seen: List[bool] = []
    task = (
        TaskBuilder('Boom')
        .with_event(raise_error)
        .with_on_finish(lambda t: seen.append(t.state.is_failed))
        .build()
    )
    executor.add_task(task)

    executor.start_workers()
    step_pool.drain()

    assert seen == [True]


@pytest.mark.xfail(strict=True, raises=AssertionError, reason='V39')
def test_task_removed_after_dispatch_does_not_run(executor: TaskExecutor, step_pool: StepPool):
    ran: List[str] = []
    task = TaskBuilder('T').with_event(lambda t: ran.append(t.name)).build()
    executor.add_task(task)
    executor.start_workers()

    with contextlib.suppress(Exception):
        executor.remove_task(task)
    step_pool.drain()

    history = [entry.active_state for entry in task.state.history]
    assert not (ran and 'deleted' in history)


@pytest.mark.xfail(strict=True, raises=AssertionError, reason='V46')
def test_retry_starts_the_retried_task(executor: TaskExecutor, step_pool: StepPool):
    ran: List[str] = []
    earlier = TaskBuilder('Earlier').with_event(lambda t: ran.append(t.name)).build()
    failed = TaskBuilder('Failed').with_event(raise_error).build()
    executor.add_task(failed)
    executor.start_workers()
    step_pool.drain()

    executor.add_task(earlier)
    failed.execute = lambda t: ran.append(t.name)
    executor.retry_task(failed)
    step_pool.drain()

    assert ran == ['Failed']


@pytest.mark.xfail(strict=True, raises=AssertionError, reason='V51')
def test_deleted_state_cannot_go_back_to_running():
    state = TaskState()
    state.set_deleted()

    with contextlib.suppress(Exception):
        state.set_running()

    assert state.is_deleted


@pytest.mark.xfail(strict=True, raises=AssertionError, reason='V53')
def test_start_workers_stops_at_max_workers(executor: TaskExecutor, step_pool: StepPool):
    executor.set_max_workers(2)
    for task in [TaskBuilder().build() for _ in range(8)]:
        executor.add_task(task)

    executor.start_workers()
    started = step_pool.activeThreadCount()
    step_pool.drain()

    assert started == 2


@pytest.mark.xfail(strict=True, raises=AssertionError, reason='V53')
def test_constructor_enforces_minimum_workers(step_pool: StepPool):
    assert TaskExecutor(1, threadpool=step_pool).max_workers == 2


@pytest.mark.xfail(strict=True, raises=AssertionError, reason='V66')
def test_default_execute_succeeds(executor: TaskExecutor, step_pool: StepPool):
    from tqm import TaskExecutable
    task = TaskExecutable(name='Default')
    executor.add_task(task)

    executor.start_workers()
    step_pool.drain()

    assert task.state.is_completed


@pytest.mark.xfail(strict=True, raises=AssertionError, reason='V66')
def test_task_error_needs_no_message():
    from tqm.exceptions import TaskError
    try:
        TaskError()
    except TypeError as error:
        raise AssertionError('TaskError() needs a message') from error
