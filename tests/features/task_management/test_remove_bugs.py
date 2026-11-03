from __future__ import annotations

from typing import Any, List, Callable
from threading import Event
from unittest import mock

import pytest
from pytestqt.qtbot import QtBot

from tqm import TQManager, TaskBuilder, TaskExecutor, TaskGroupBuilder
from tqm.exceptions import TaskError
from tqm._ui.toolbar import ClearTasksMenu
from tqm._ui.ui_view_model import TaskTreeView

from ...utils import raise_error, must_not_raise
from ...utils.harness import StepPool


def noop_task(name: str = '') -> TaskBuilder:
    return TaskBuilder(name).with_event(lambda t: None)


def top_rows(app: TQManager) -> List[str]:
    model = app.findChild(TaskTreeView).model()
    return [model.index(i, 0).data() for i in range(model.rowCount())]


@pytest.mark.xfail(strict=True, raises=AssertionError, reason='V36')
def test_removing_the_last_waiting_member_of_a_running_group(
    qtbot: QtBot,
    app: TQManager,
    gate: Callable[[], Event]
):
    release = gate()
    app.set_max_workers(2)
    busy = [TaskBuilder(f'B{i}').with_event(lambda t: release.wait()).build() for i in range(2)]
    member = noop_task('M').build()
    group = TaskGroupBuilder('G').with_tasks(member).build()
    app.add_tasks(*busy, group)
    app.start_workers()
    qtbot.wait_until(lambda: group.state.is_running and member.state.is_waiting)

    with qtbot.capture_exceptions() as errors:
        app.remove_tasks(member)

    release.set()
    qtbot.wait_until(lambda: group.state.is_completed)
    assert not errors


@pytest.mark.xfail(strict=True, raises=AssertionError, reason='V41')
def test_blocked_task_is_removable(executor: TaskExecutor, step_pool: StepPool):
    parent = noop_task('P').build()
    child = noop_task('C').with_wait_for(parent).build()
    executor.add_task(parent)
    executor.add_task(child)
    executor.start_workers()

    with must_not_raise(TaskError):
        executor.remove_task(child)

    step_pool.drain()
    assert child.state.is_deleted


@pytest.mark.xfail(strict=True, raises=AssertionError, reason='V41')
def test_retrying_task_is_removable_and_its_timer_is_cancelled(
    executor: TaskExecutor,
    step_pool: StepPool
):
    runs: List[int] = []

    def event(task: Any) -> None:
        runs.append(1)
        raise RuntimeError('boom')

    task = TaskBuilder('T').with_event(event).with_retry(1, 5).build()
    executor.add_task(task)

    with mock.patch('tqm._core.task_retry.QTimer.singleShot') as single_shot:
        executor.start_workers()
        step_pool.drain()

        with must_not_raise(TaskError):
            executor.remove_task(task)

        single_shot.call_args[0][1]()
        step_pool.drain()

    assert task.state.is_deleted
    assert len(runs) == 1


@pytest.mark.xfail(strict=True, raises=AssertionError, reason='V42')
def test_clear_all_continues_past_a_running_task(
    qtbot: QtBot,
    app: TQManager,
    gate: Callable[[], Event]
):
    release = gate()
    running = TaskBuilder('Run').with_event(lambda t: release.wait()).build()
    app.add_tasks(running)
    app.start_workers()
    qtbot.wait_until(lambda: running.state.is_running)
    app.add_tasks(*[noop_task(f'T{i}').build() for i in range(3)])

    with qtbot.capture_exceptions():
        app.findChild(ClearTasksMenu).clear_all_tasks_btn.trigger()

    assert top_rows(app) == ['Run']


@pytest.mark.xfail(strict=True, raises=AssertionError, reason='V43')
def test_clearing_a_completed_group_raises_nothing(qtbot: QtBot, app: TQManager):
    group = TaskGroupBuilder('G').with_tasks(noop_task('A').build(), noop_task('B').build()).build()
    app.add_tasks(group)
    app.start_workers()
    qtbot.wait_until(lambda: group.state.is_completed)

    with qtbot.capture_exceptions() as errors:
        app.findChild(ClearTasksMenu).clear_completed_tasks_btn.trigger()

    assert not errors


@pytest.mark.xfail(strict=True, raises=AssertionError, reason='V43')
def test_clearing_a_failed_group_removes_its_completed_member(qtbot: QtBot, app: TQManager):
    completed = noop_task('Ok').build()
    failed = TaskBuilder('Bad').with_event(raise_error).build()
    group = TaskGroupBuilder('G').with_tasks(completed, failed).build()
    app.add_tasks(group)
    app.start_workers()
    qtbot.wait_until(lambda: group.state.is_failed)

    with qtbot.capture_exceptions():
        app.findChild(ClearTasksMenu).clear_failed_tasks_btn.trigger()

    assert completed not in app.executor.get_all_tasks()


@pytest.mark.xfail(strict=True, raises=AssertionError, reason='V44')
def test_removing_a_finished_group_removes_its_members(qtbot: QtBot, app: TQManager):
    member = noop_task('A').build()
    group = TaskGroupBuilder('G').with_tasks(member).build()
    app.add_tasks(group)
    app.start_workers()
    qtbot.wait_until(lambda: group.state.is_completed)

    app.remove_tasks(group)

    assert member not in app.executor.get_all_tasks()
