from __future__ import annotations

from typing import TYPE_CHECKING

from PySide2.QtCore import Qt, Slot
from PySide2.QtWidgets import QMenu, QAction, QWidget

from ..utils import open_file

if TYPE_CHECKING:
    from .ui_view_model import TaskTreeView


class TaskFileMenu(QMenu):
    def __init__(self, file_path: str, parent: QWidget) -> None:
        super().__init__(title='File', parent=parent)
        self._file_path = file_path

        self._open_action = QAction('Open', self)
        self._open_action.triggered.connect(
            lambda: open_file(self._file_path)
        )
        self.addAction(self._open_action)

        self._reveal_action = QAction('Reveal', self)
        self._reveal_action.triggered.connect(
            lambda: open_file(self._file_path, reveal=True)
        )
        self.addAction(self._reveal_action)


class TaskCheckerMenu(QMenu):
    def __init__(self, parent: TaskTreeView) -> None:
        super().__init__(title='Check/Uncheck', parent=parent)

        self._parent = parent
        self.tasks_model = parent.tasks_model

        check_all = QAction('Check All', self)
        check_all.triggered.connect(lambda: self._iter_all(Qt.Checked))

        uncheck_all = QAction('Uncheck All', self)
        uncheck_all.triggered.connect(lambda: self._iter_all(Qt.Unchecked))

        invert_all = QAction('Invert All', self)
        invert_all.triggered.connect(self._invert_all)

        check_selected = QAction('Check Selected', self)
        check_selected.triggered.connect(lambda: self._iter_selected(Qt.Checked))

        uncheck_selected = QAction('Uncheck Selected', self)
        uncheck_selected.triggered.connect(lambda: self._iter_selected(Qt.Unchecked))

        self.addAction(check_all)
        self.addAction(uncheck_all)
        self.addAction(invert_all)
        self.addSeparator()
        self.addAction(check_selected)
        self.addAction(uncheck_selected)

    @Slot(Qt.CheckState)
    def _iter_all(self, state: Qt.CheckState = Qt.Checked) -> None:
        for i in range(self.tasks_model.rowCount()):
            item = self.tasks_model.item(i, 0)
            item.setCheckState(state)

    @Slot()
    def _invert_all(self) -> None:
        for i in range(self.tasks_model.rowCount()):
            item = self.tasks_model.item(i, 0)
            item.setCheckState(
                Qt.Unchecked if item.checkState() == Qt.Checked else Qt.Checked
            )

    @Slot(Qt.CheckState)
    def _iter_selected(self, state: Qt.CheckState = Qt.Checked) -> None:
        for item in self._parent.get_selected_items():
            item.setCheckState(state)
