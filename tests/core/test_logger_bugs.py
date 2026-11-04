from __future__ import annotations

import os
from typing import Callable
from pathlib import Path

import pytest
from pytestqt.qtbot import QtBot
from PySide2.QtWidgets import QPlainTextEdit

from tqm import TQManager, TaskBuilder
from tqm._core.logger import LOGGER

from ..utils import run_events


@pytest.mark.xfail(strict=True, raises=AssertionError, reason='V27')
def test_second_manager_does_not_duplicate_file_lines(make_manager: Callable[[str], TQManager]):
    _ = [make_manager('same') for _ in range(2)]

    LOGGER.info('MARKER')

    log = Path(os.environ['XDG_CONFIG_HOME']) / 'tqm' / 'same' / 'logs' / 'tqm.log'
    assert log.read_text().count('MARKER') == 1


@pytest.mark.xfail(strict=True, raises=AssertionError, reason='V27')
def test_task_log_stays_in_its_own_window(qtbot: QtBot, make_manager: Callable[[str], TQManager]):
    first, second = make_manager('a'), make_manager('b')
    task = TaskBuilder().with_event(lambda t: t.log('hello-from-a')).build()

    first.add_tasks(task)
    first.start_workers()
    qtbot.wait_until(lambda: task.state.is_completed)
    run_events(qtbot, 50)

    other_log = second.findChild(QPlainTextEdit, 'TqmTasksLogs')
    assert 'hello-from-a' not in other_log.toPlainText()
