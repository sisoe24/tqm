from __future__ import annotations

from typing import List

import pytest
from pytestqt.qtbot import QtBot

from tqm import TQManager, TaskBuilder
from tqm.exceptions import TqmError

from ...utils import run_events


@pytest.mark.xfail(strict=True, raises=AssertionError, reason='V48')
def test_readded_task_keeps_callbacks_and_predicate(qtbot: QtBot, app: TQManager):
    done: List[int] = []
    task = (
        TaskBuilder('T')
        .with_event(lambda t: None)
        .with_on_completed(lambda t: done.append(1))
        .with_predicate(lambda: True)
        .build()
    )
    app.add_tasks(task)
    app.remove_tasks(task)

    try:
        app.add_tasks(task)
    except TqmError:
        return

    app.start_workers()
    qtbot.wait_until(lambda: task.state.is_completed)
    run_events(qtbot, 20)

    assert done
    assert task.predicate.condition is not None
