from __future__ import annotations

import contextlib
from typing import Any, List, Callable
from threading import Event
from unittest import mock

import pytest
from pytestqt.qtbot import QtBot

from tqm import TQManager, TaskBuilder, TaskExecutor, TaskGroupBuilder

from ...utils import run_events
from ...utils.harness import StepPool


@pytest.mark.xfail(strict=True, raises=AssertionError, reason='V14')
def test_retry_of_a_running_task_does_not_run_it_twice(
    qtbot: QtBot,
    app: TQManager,
    gate: Callable[[], Event]
):
    release = gate()
    runs: List[int] = []

    def event(task: Any) -> None:
        runs.append(1)
        release.wait()

    task = TaskBuilder('T').with_event(event).build()
    app.add_tasks(task)
    app.start_workers()
    qtbot.wait_until(lambda: task.state.is_running)

    with contextlib.suppress(Exception):
        app.executor.retry_task(task)
    run_events(qtbot, 100)
    second_run = len(runs)
    release.set()
    qtbot.wait_until(lambda: task.state.is_completed)

    assert second_run == 1


@pytest.mark.xfail(strict=True, raises=AssertionError, reason='V14')
def test_retry_during_the_delay_adds_no_run(executor: TaskExecutor, step_pool: StepPool):
    runs: List[int] = []

    def event(task: Any) -> None:
        runs.append(1)
        raise RuntimeError('boom')

    task = TaskBuilder('T').with_event(event).with_retry(1, 5).build()
    executor.add_task(task)

    with mock.patch('tqm._core.task_retry.QTimer.singleShot') as single_shot:
        executor.start_workers()
        step_pool.drain()
        with contextlib.suppress(Exception):
            executor.retry_task(task)
        step_pool.drain()
        single_shot.call_args[0][1]()
        step_pool.drain()

    assert len(runs) == 2


@pytest.mark.xfail(strict=True, raises=AssertionError, reason='V14')
def test_retry_does_not_resurrect_a_deleted_task(executor: TaskExecutor, step_pool: StepPool):
    runs: List[int] = []
    task = TaskBuilder('T').with_event(lambda t: runs.append(1)).build()
    executor.add_task(task)
    executor.start_workers()
    step_pool.drain()
    executor.remove_task(task)

    with contextlib.suppress(Exception):
        executor.retry_task(task)
    step_pool.drain()

    assert len(runs) == 1
    assert task.state.is_deleted


@pytest.mark.xfail(strict=True, raises=AssertionError, reason='V24')
def test_retrying_a_group_retries_its_failed_members(qtbot: QtBot, app: TQManager):
    runs: List[int] = []

    def event(task: Any) -> None:
        runs.append(1)
        raise RuntimeError('boom')

    group = TaskGroupBuilder('G').with_tasks(TaskBuilder('T').with_event(event).build()).build()
    app.add_tasks(group)
    app.start_workers()
    qtbot.wait_until(lambda: group.state.is_failed)

    app.executor.retry_task(group)
    run_events(qtbot, 400)

    assert len(runs) == 2


@pytest.mark.xfail(strict=True, raises=AssertionError, reason='V52')
def test_manual_retry_after_exhaustion_gets_the_full_budget(
    qtbot: QtBot,
    executor: TaskExecutor,
    step_pool: StepPool
):
    runs: List[int] = []

    def event(task: Any) -> None:
        runs.append(1)
        raise RuntimeError('boom')

    def run_to_failure(task: Any) -> None:
        def finished() -> bool:
            step_pool.drain()
            return task.state.is_failed
        qtbot.wait_until(finished)

    task = TaskBuilder('T').with_event(event).with_retry(2, 0).build()
    executor.add_task(task)
    executor.start_workers()
    run_to_failure(task)
    assert len(runs) == 3

    executor.retry_task(task)
    run_to_failure(task)

    assert len(runs) == 6
