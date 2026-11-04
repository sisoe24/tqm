from __future__ import annotations

from typing import Any, List, Callable
from unittest import mock

import pytest
from pytestqt.qtbot import QtBot

from tqm import TQManager, TaskBuilder, TaskGroupBuilder

from ...utils import raise_error, run_events


@pytest.mark.xfail(strict=True, raises=AssertionError, reason='V45')
def test_no_idle_while_a_retry_is_pending(qtbot: QtBot, app: TQManager):
    idle: List[int] = []
    app.callbacks.on_system_idle(lambda: idle.append(1))
    task = TaskBuilder('T').with_event(raise_error).with_retry(1, 5).build()
    app.add_tasks(task)

    with mock.patch('tqm._core.task_retry.QTimer.singleShot'):
        app.start_workers()
        qtbot.wait_until(lambda: task.state.is_retrying)
        run_events(qtbot, 500)

    assert not idle


@pytest.mark.xfail(strict=True, raises=AssertionError, reason='V45')
def test_idle_fires_for_a_group_failed_by_its_predicate(qtbot: QtBot, app: TQManager):
    idle: List[int] = []
    app.callbacks.on_system_idle(lambda: idle.append(1))
    group = (
        TaskGroupBuilder('G')
        .with_tasks(TaskBuilder('T').with_event(lambda t: None).build())
        .with_predicate(lambda: False, max_attempts=1, delay_ms=1)
        .build()
    )
    app.add_tasks(group)

    app.start_workers()
    qtbot.wait_until(lambda: group.state.is_failed)
    run_events(qtbot, 500)

    assert idle


@pytest.mark.xfail(strict=True, raises=AssertionError, reason='V45')
def test_no_idle_while_a_group_runs_with_a_short_timeout(
    qtbot: QtBot,
    make_manager: Callable[[str], TQManager],
    monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv('TQM_IDLE_TIMEOUT', '0')
    manager = make_manager('a')
    seen: List[Any] = []
    groups = []

    def on_idle() -> None:
        seen.append(groups[-1].state.is_running)

    manager.callbacks.on_system_idle(on_idle)

    # One round can miss the window before the runner's next poll.
    for i in range(5):
        groups.append(TaskGroupBuilder(f'G{i}').with_tasks(TaskBuilder().with_event(lambda t: None).build()).build())
        manager.add_tasks(groups[-1])
        manager.start_workers()
        qtbot.wait_until(lambda: groups[-1].state.is_completed)
        run_events(qtbot, 20)

    assert not any(seen)
