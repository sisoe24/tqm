from __future__ import annotations

from typing import Any, List, Callable
from threading import Event

import pytest
from PySide2.QtCore import QTimer
from pytestqt.qtbot import QtBot

from tqm import TQManager, TaskBuilder, TaskExecutor
from tqm._ui.ui_view_model import TaskTreeView

from ...utils import run_events
from ...utils.harness import StepPool


@pytest.mark.xfail(strict=True, raises=AssertionError, reason='V30')
def test_no_retry_starts_during_or_after_shutdown(qtbot: QtBot, app: TQManager, gate: Callable[[], Event]):
    release = gate()
    runs: List[int] = []

    def event(task: Any) -> None:
        runs.append(1)
        release.wait()
        raise RuntimeError('boom')

    task = TaskBuilder('T').with_event(event).with_retry(2, 0).build()
    app.add_tasks(task)
    app.start_workers()
    qtbot.wait_until(lambda: task.state.is_running)

    QTimer.singleShot(0, release.set)
    app.executor.shutdown()
    run_events(qtbot, 200)

    assert len(runs) == 1


@pytest.mark.xfail(strict=True, raises=AssertionError, reason='V30')
def test_blocked_child_does_not_start_during_shutdown(qtbot: QtBot, app: TQManager, gate: Callable[[], Event]):
    release = gate()
    ran: List[int] = []
    parent = TaskBuilder('P').with_event(lambda t: release.wait()).build()
    child = TaskBuilder('C').with_event(lambda t: ran.append(1)).with_wait_for(parent).build()
    app.add_tasks(parent, child)
    app.start_workers()
    qtbot.wait_until(lambda: parent.state.is_running)

    QTimer.singleShot(0, release.set)
    app.executor.shutdown()
    run_events(qtbot, 200)

    assert not ran


@pytest.mark.xfail(strict=True, raises=AssertionError, reason='V31')
def test_drained_tasks_do_not_stay_waiting(qtbot: QtBot, app: TQManager, gate: Callable[[], Event]):
    release = gate()
    idle: List[int] = []
    app.callbacks.on_system_idle(lambda: idle.append(1))
    app.set_max_workers(2)
    tasks = [TaskBuilder(f'T{i}').with_event(lambda t: release.wait()).build() for i in range(6)]
    app.add_tasks(*tasks)
    app.start_workers()
    qtbot.wait_until(lambda: tasks[0].state.is_running)

    QTimer.singleShot(0, release.set)
    app.executor.shutdown()
    run_events(qtbot, 500)

    assert not any(task.state.is_waiting for task in tasks)
    assert idle


@pytest.mark.xfail(strict=True, raises=AssertionError, reason='V31')
def test_shutdown_with_nothing_running_drains_the_queue(executor: TaskExecutor, step_pool: StepPool):
    tasks = [TaskBuilder().build() for _ in range(2)]
    for task in tasks:
        executor.add_task(task)

    executor.shutdown()

    assert not any(task.state.is_waiting for task in tasks)


@pytest.mark.xfail(strict=True, raises=AssertionError, reason='V72')
def test_toolbar_retry_is_gated_during_shutdown(qtbot: QtBot, app: TQManager, gate: Callable[[], Event]):
    release = gate()
    runs: List[int] = []

    def fail(task: Any) -> None:
        runs.append(1)
        raise RuntimeError('boom')

    failed = TaskBuilder('F').with_event(fail).build()
    running = TaskBuilder('R').with_event(lambda t: release.wait()).build()
    app.add_tasks(failed, running)
    app.start_workers()
    qtbot.wait_until(lambda: failed.state.is_failed and running.state.is_running)

    QTimer.singleShot(0, app.operations.retry_all_failed)
    QTimer.singleShot(50, release.set)
    app.executor.shutdown()
    run_events(qtbot, 100)

    assert len(runs) == 1


@pytest.mark.xfail(strict=True, raises=AssertionError, reason='V72')
def test_add_tasks_is_gated_during_shutdown(qtbot: QtBot, app: TQManager, gate: Callable[[], Event]):
    release = gate()
    running = TaskBuilder('R').with_event(lambda t: release.wait()).build()
    late = TaskBuilder('Late').build()
    app.add_tasks(running)
    app.start_workers()
    qtbot.wait_until(lambda: running.state.is_running)

    QTimer.singleShot(0, lambda: app.add_tasks(late))
    QTimer.singleShot(50, release.set)
    app.executor.shutdown()

    model = app.findChild(TaskTreeView).model()
    assert [model.index(i, 0).data() for i in range(model.rowCount())] == ['R']
