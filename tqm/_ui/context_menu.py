from __future__ import annotations

from PySide2.QtWidgets import QMenu, QAction, QWidget

from ..utils import open_file


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

