from __future__ import annotations

import contextlib

import pytest
from pytestqt.qtbot import QtBot

from tqm import TQManager, TaskBuilder, TaskExecutor
from tqm.exceptions import TaskParentError

from ...utils import raise_error, run_events
from ...utils.harness import StepPool


def noop_task(name: str = '') -> TaskBuilder:
    return TaskBuilder(name).with_event(lambda t: None)


@pytest.mark.xfail(strict=True, raises=AssertionError, reason='V6')
def test_child_of_already_failed_parent_fails(executor: TaskExecutor, step_pool: StepPool):
    parent = TaskBuilder('P').with_event(raise_error).build()
    executor.add_task(parent)
    executor.start_workers()
    step_pool.drain()

    child = noop_task('C').with_wait_for(parent).build()
    executor.add_task(child)
    executor.start_workers()
    step_pool.drain()

    assert child.state.is_failed
    assert isinstance(child.exception, TaskParentError)


@pytest.mark.xfail(strict=True, raises=AssertionError, reason='V6')
def test_child_still_in_heap_when_parent_fails_fails(executor: TaskExecutor, step_pool: StepPool):
    executor.set_max_workers(2)
    parent = TaskBuilder('P').with_event(raise_error).build()
    others = [noop_task(f'L{i}').build() for i in range(2)]
    child = noop_task('C').with_wait_for(parent).build()
    for task in (parent, *others, child):
        executor.add_task(task)

    executor.start_workers()
    step_pool.drain()

    assert child.state.is_failed
    assert isinstance(child.exception, TaskParentError)


@pytest.mark.xfail(strict=True, raises=AssertionError, reason='V7')
def test_child_with_retry_policy_burns_no_retries(
    qtbot: QtBot,
    executor: TaskExecutor,
    step_pool: StepPool
):
    parent = TaskBuilder('P').with_event(raise_error).build()
    child = noop_task('C').with_wait_for(parent).with_retry(1, 0).build()
    grandchild = noop_task('G').with_wait_for(child).build()
    for task in (parent, child, grandchild):
        executor.add_task(task)

    executor.start_workers()
    step_pool.drain()
    qtbot.wait_until(lambda: child.state.is_failed or child.state.is_blocked)

    assert child.retry_policy.attempt == 0
    assert child.state.is_failed
    assert isinstance(child.exception, TaskParentError)
    assert grandchild.state.is_failed


@pytest.mark.xfail(strict=True, raises=AssertionError, reason='V8')
def test_child_in_predicate_retrying_fails_with_parent(
    qtbot: QtBot,
    executor: TaskExecutor,
    step_pool: StepPool
):
    ready = [False]
    parent = TaskBuilder('P').with_event(raise_error).build()
    child = (
        noop_task('C')
        .with_wait_for(parent)
        .with_predicate(lambda: ready[0], max_attempts=1000, delay_ms=1)
        .build()
    )
    executor.add_task(parent)
    executor.add_task(child)
    executor.start_workers()
    qtbot.wait_until(lambda: child.state.is_retrying)

    step_pool.drain()
    ready[0] = True
    qtbot.wait_until(lambda: child.state.is_failed or child.state.is_blocked)

    assert child.state.is_failed


@pytest.mark.xfail(strict=True, raises=AssertionError, reason='V13')
def test_raising_on_failed_still_fails_the_task(
    qtbot: QtBot,
    executor: TaskExecutor,
    step_pool: StepPool
):
    def bad_callback(task: object) -> None:
        raise ValueError('callback')

    parent = TaskBuilder('P').with_event(raise_error).with_on_failed(bad_callback).build()
    child = noop_task('C').with_wait_for(parent).build()
    executor.add_task(parent)
    executor.add_task(child)

    with qtbot.capture_exceptions():
        executor.start_workers()
        step_pool.drain()

    assert parent.state.is_failed
    assert child.state.is_failed


@pytest.mark.xfail(strict=True, raises=AssertionError, reason='V13')
def test_raising_on_completed_still_unblocks_children(
    qtbot: QtBot,
    executor: TaskExecutor,
    step_pool: StepPool
):
    def bad_callback(task: object) -> None:
        raise ValueError('callback')

    parent = noop_task('P').with_on_completed(bad_callback).build()
    child = noop_task('C').with_wait_for(parent).build()
    executor.add_task(parent)
    executor.add_task(child)

    with qtbot.capture_exceptions():
        executor.start_workers()
        step_pool.drain()

    assert child.state.is_completed


class Stop(BaseException):
    pass


@pytest.mark.xfail(strict=True, raises=AssertionError, reason='V13')
def test_base_exception_in_task_does_not_leave_it_running(qtbot: QtBot, app: TQManager):
    def stop(task: object) -> None:
        raise Stop

    task = TaskBuilder('T').with_event(stop).build()
    app.add_tasks(task)

    with qtbot.capture_exceptions():
        app.start_workers()
        qtbot.wait_until(lambda: task.state.is_running)
        run_events(qtbot, 200)

    assert task.state.is_failed


@pytest.mark.xfail(strict=True, raises=AssertionError, reason='V40')
def test_remove_task_is_atomic(executor: TaskExecutor, step_pool: StepPool):
    parent = TaskBuilder('P').with_event(raise_error).build()
    child = noop_task('C').with_wait_for(parent).build()
    executor.add_task(parent)
    executor.add_task(child)
    executor.start_workers()
    step_pool.drain()
    executor.retry_task(child)

    with contextlib.suppress(Exception):
        executor.remove_task(parent)

    assert parent.state.is_deleted == child.state.is_deleted
