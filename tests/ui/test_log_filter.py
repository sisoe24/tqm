from __future__ import annotations

from pathlib import Path

import pytest
from PySide2.QtCore import QItemSelectionModel
from pytestqt.qtbot import QtBot
from PySide2.QtWidgets import QPlainTextEdit

from tqm import TQManager, TaskBuilder, TaskGroupBuilder
from tqm._ui.tab_logs import RECORDS_PER_TASK, TasksLog

from .test_ui_controller import find_row


def line(text: str) -> str:
    """Build a line in the panel format: time | level | message."""
    return f'00:00:00 | INFO | {text}'


@pytest.fixture
def logs(qtbot: QtBot, tmp_path: Path) -> TasksLog:
    widget = TasksLog(tmp_path / 'settings.json')
    qtbot.addWidget(widget)
    return widget


def shown(logs: TasksLog) -> str:
    return logs.findChild(QPlainTextEdit).toPlainText()


def test_selected_task_shows_only_its_lines(logs: TasksLog):
    a, b = TaskBuilder('A').build(), TaskBuilder('B').build()
    logs.log(line('from-a'), task_id=str(a.id))
    logs.log(line('from-b'), task_id=str(b.id))

    logs.show_tasks([a])

    assert 'from-a' in shown(logs)
    assert 'from-b' not in shown(logs)


def test_new_lines_of_hidden_tasks_stay_hidden(logs: TasksLog):
    a, b = TaskBuilder('A').build(), TaskBuilder('B').build()
    logs.show_tasks([a])

    logs.log(line('from-b'), task_id=str(b.id))

    assert 'from-b' not in shown(logs)


def test_empty_selection_shows_every_line_in_order(logs: TasksLog):
    a, b = TaskBuilder('A').build(), TaskBuilder('B').build()
    logs.log(line('first'), task_id=str(a.id))
    logs.log(line('second'), task_id=str(b.id))
    logs.log(line('system'))
    logs.show_tasks([a])

    logs.show_tasks([])

    text = shown(logs)
    assert text.index('first') < text.index('second') < text.index('system')


def test_selected_group_shows_its_children(logs: TasksLog):
    child = TaskBuilder('Child').build()
    group = TaskGroupBuilder('G').with_tasks(child).build()
    logs.log(line('from-child'), task_id=str(child.id))

    logs.show_tasks([group])

    assert 'from-child' in shown(logs)


def test_busy_task_keeps_the_lines_of_others(logs: TasksLog):
    quiet, busy = TaskBuilder('Quiet').build(), TaskBuilder('Busy').build()
    logs.log(line('quiet-start'), task_id=str(quiet.id))
    for i in range(RECORDS_PER_TASK + 10):
        logs.log(line(f'busy-{i}'), task_id=str(busy.id))

    logs.show_tasks([quiet])

    assert 'quiet-start' in shown(logs)


def test_clear_drops_the_stored_lines(logs: TasksLog):
    a = TaskBuilder('A').build()
    logs.log(line('from-a'), task_id=str(a.id))
    logs.on_clear_logs()

    logs.show_tasks([a])

    assert 'from-a' not in shown(logs)


def test_tree_selection_filters_the_log(qtbot: QtBot, app: TQManager):
    a = TaskBuilder('A').with_event(lambda t: None).build()
    b = TaskBuilder('B').with_event(lambda t: None).build()
    app.add_tasks(a, b)
    a.log('from-a')
    b.log('from-b')
    log = app.findChild(QPlainTextEdit, 'TqmTasksLogs')
    qtbot.wait_until(lambda: 'from-b' in log.toPlainText())

    view = app._view.tree_view
    view.selectionModel().select(
        find_row(view, 'A'), QItemSelectionModel.ClearAndSelect | QItemSelectionModel.Rows
    )

    assert 'from-a' in log.toPlainText()
    assert 'from-b' not in log.toPlainText()
