from __future__ import annotations

from typing import Callable
from threading import Event

from pytestqt.qtbot import QtBot

from tqm import TQManager, TaskBuilder

# Longer than the idle timeout the app fixture sets.
PAST_IDLE_TIMEOUT = 300


def test_no_idle_while_a_task_runs(qtbot: QtBot, app: TQManager, gate: Callable[[], Event]):
    release = gate()
    task = TaskBuilder().with_event(lambda t: release.wait()).build()
    app.add_tasks(task)
    app.start_workers()
    qtbot.wait_until(lambda: task.state.is_running)

    with qtbot.assert_not_emitted(app.callbacks.system_idle, wait=PAST_IDLE_TIMEOUT):
        pass

    release.set()
    qtbot.wait_until(lambda: task.state.is_completed)


def test_no_idle_while_a_predicate_polls(qtbot: QtBot, app: TQManager):
    ready = []
    task = TaskBuilder().with_predicate(lambda: bool(ready), max_attempts=1000, delay_ms=20).build()
    app.add_tasks(task)
    app.start_workers()
    qtbot.wait_until(lambda: task.state.is_retrying)

    with qtbot.assert_not_emitted(app.callbacks.system_idle, wait=PAST_IDLE_TIMEOUT):
        pass

    ready.append(True)
    qtbot.wait_until(lambda: task.state.is_completed)


def test_pending_idle_is_cancelled_when_work_resumes(
    qtbot: QtBot,
    app: TQManager,
    gate: Callable[[], Event]
):
    first = TaskBuilder().build()
    app.add_tasks(first)
    app.start_workers()
    qtbot.wait_until(lambda: first.state.is_completed)

    release = gate()
    second = TaskBuilder().with_event(lambda t: release.wait()).build()

    with qtbot.assert_not_emitted(app.callbacks.system_idle, wait=PAST_IDLE_TIMEOUT):
        app.add_tasks(second)
        app.start_workers()

    release.set()
    qtbot.wait_until(lambda: second.state.is_completed)
