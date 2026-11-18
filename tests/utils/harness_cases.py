"""Cases for test_harness.py. Each one runs in its own pytest process, never in the suite."""
from __future__ import annotations

import time
from typing import Any

from tqm import TQManager, TaskBuilder, TaskGroupBuilder


def test_hang() -> None:
    time.sleep(120)


def test_fails_mid_group(app: TQManager, qtbot: Any, gate: Any) -> None:
    release = gate()
    task = TaskBuilder('blocked').with_event(lambda _: release.wait()).build()
    group = TaskGroupBuilder('group').with_tasks(task).build()
    app.add_tasks(group)
    app.start_workers()
    qtbot.wait_until(lambda: task.state.is_running)
    assert False, 'failure while the group is running'
