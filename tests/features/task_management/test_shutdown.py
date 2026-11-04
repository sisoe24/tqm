from __future__ import annotations

from typing import List, Callable
from threading import Event

from PySide2.QtCore import QTimer
from pytestqt.qtbot import QtBot

from tqm import TQManager, TaskBuilder, TaskExecutable


def start_blocked_task(qtbot: QtBot, app: TQManager, release: Event) -> TaskExecutable:
    task = TaskBuilder().with_event(lambda t: release.wait()).build()
    app.add_tasks(task)
    app.start_workers()
    qtbot.wait_until(lambda: task.state.is_running)
    return task


def test_shutdown_waits_for_the_running_task(
    qtbot: QtBot,
    app: TQManager,
    gate: Callable[[], Event]
):
    release = gate()
    finished: List[str] = []

    def event(task: TaskExecutable) -> None:
        release.wait()
        finished.append(task.name)

    task = TaskBuilder('Slow').with_event(event).build()
    app.add_tasks(task)
    app.start_workers()
    qtbot.wait_until(lambda: task.state.is_running)

    # Fires inside the event loop that shutdown runs while it waits.
    QTimer.singleShot(0, release.set)
    app.executor.shutdown()

    assert finished == ['Slow']


def test_shutdown_drops_queued_tasks(qtbot: QtBot, app: TQManager, gate: Callable[[], Event]):
    release = gate()
    running = start_blocked_task(qtbot, app, release)

    ran: List[str] = []
    app.add_tasks(TaskBuilder('Queued').with_event(lambda t: ran.append(t.name)).build())

    QTimer.singleShot(0, release.set)
    app.executor.shutdown()
    qtbot.wait_until(lambda: running.state.is_completed)

    with qtbot.assert_not_emitted(app.callbacks.runner_started, wait=200):
        app.start_workers()

    assert ran == []


def test_add_task_is_rejected_only_during_shutdown(
    qtbot: QtBot,
    app: TQManager,
    gate: Callable[[], Event]
):
    release = gate()
    start_blocked_task(qtbot, app, release)
    during = TaskBuilder().build()

    def add_then_release() -> None:
        app.executor.add_task(during)
        release.set()

    QTimer.singleShot(0, add_then_release)
    app.executor.shutdown()

    assert during.state.is_inactive

    after = TaskBuilder().build()
    app.executor.add_task(after)
    assert after.state.is_waiting
