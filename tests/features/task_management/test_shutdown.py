from __future__ import annotations

from typing import List, Callable
from threading import Event

from PySide2.QtCore import QTimer
from PySide2.QtWidgets import QMessageBox, QApplication
from pytestqt.qtbot import QtBot

from tqm import TQManager, TaskBuilder, TaskExecutable


def start_blocked_task(qtbot: QtBot, app: TQManager, release: Event) -> TaskExecutable:
    task = TaskBuilder().with_event(lambda t: release.wait()).build()
    app.add_tasks(task)
    app.start_workers()
    qtbot.wait_until(lambda: task.state.is_running)
    return task


def test_shutdown_returns_while_the_task_runs(
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

    # Fires only once an event loop runs, so a shutdown that waits would see the task finish.
    QTimer.singleShot(0, release.set)
    app.executor.shutdown()

    assert finished == []
    qtbot.wait_until(lambda: task.state.is_completed)
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
    running = start_blocked_task(qtbot, app, release)
    during = TaskBuilder().build()

    def add_then_release() -> None:
        app.executor.add_task(during)
        release.set()

    QTimer.singleShot(0, add_then_release)
    app.executor.shutdown()
    # Shutdown lasts until the running task finishes.
    qtbot.wait_until(lambda: running.state.is_completed)

    assert during.state.is_inactive

    after = TaskBuilder().build()
    app.executor.add_task(after)
    assert after.state.is_waiting


def ask_shutdown(app: TQManager) -> QMessageBox:
    """Call shutdown and return its dialog. Fails if shutdown waits for the answer."""
    nested: List[bool] = []

    def in_nested_loop() -> None:
        # Fires only if shutdown runs its own event loop. Answer so it can return.
        nested.append(True)
        modal = QApplication.activeModalWidget()
        if modal:
            modal.reject()

    QTimer.singleShot(0, in_nested_loop)
    app.shutdown()

    assert not nested, 'shutdown blocked on its question'
    dialog = app.findChild(QMessageBox)
    assert dialog is not None and dialog.isVisible()
    return dialog


def test_shutdown_question_does_not_block(qtbot: QtBot, app: TQManager):
    task = TaskBuilder().build()
    app.add_tasks(task)

    dialog = ask_shutdown(app)

    assert task.state.is_waiting
    dialog.button(QMessageBox.Yes).click()
    assert task.state.is_deleted


def test_shutdown_answered_no_keeps_the_tasks(qtbot: QtBot, app: TQManager):
    task = TaskBuilder().build()
    app.add_tasks(task)

    ask_shutdown(app).button(QMessageBox.No).click()

    assert task.state.is_waiting


def test_shutdown_when_idle_does_not_ask(qtbot: QtBot, app: TQManager):
    app.shutdown()

    assert app.findChild(QMessageBox) is None
