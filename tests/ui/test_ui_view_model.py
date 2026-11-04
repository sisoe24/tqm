

from __future__ import annotations

from PySide2.QtCore import Qt, QItemSelectionModel
from pytestqt.qtbot import QtBot

from tqm import TQManager, TaskBuilder
from tqm._core.task import TaskExecutable
from tqm._ui.ui_view_model import TaskTreeView


def select_task(view: TaskTreeView, row_index: int):
    """Helper method for testing that selects a specific row."""
    index = view.proxy_model.index(row_index, 0)
    view.selectionModel().select(index, QItemSelectionModel.Select | QItemSelectionModel.Rows)


def test_get_selected_items(qtbot: QtBot, app: TQManager):
    task1 = TaskBuilder('Task1') .build()
    task2 = TaskBuilder('Task2') .build()
    task3 = TaskBuilder('Task3') .build()
    app.add_tasks(task1, task2, task3)

    view = app.findChild(TaskTreeView)
    select_task(view, 0)
    select_task(view, 1)

    # the pair is asymmetric, so a selection read without proxy mapping picks other rows
    model = view.proxy_model
    first, second, unselected = (model.index(row, 0).data(Qt.UserRole) for row in range(3))

    # get selected tasks
    selected_tasks = view.get_selected_items()
    assert first.item in selected_tasks
    assert second.item in selected_tasks
    assert unselected.item not in selected_tasks

    assert isinstance(task1.item.data(Qt.UserRole), TaskExecutable)
