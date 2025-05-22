from __future__ import annotations

from typing import Union

from PySide2.QtGui import QBrush, QColor, QStandardItem, QLinearGradient
from PySide2.QtCore import Qt


class TaskItem(QStandardItem):
    def __init__(
        self,
        text: str,
        has_progress: bool = False,
        is_editable: bool = False,
        foreground: Union[QBrush, QColor, Qt.GlobalColor, QLinearGradient] = Qt.gray,
        alignment: Qt.AlignmentFlag = Qt.AlignLeft
    ):
        super().__init__(text)
        self.setTextAlignment(alignment)
        self.setEditable(is_editable)
        self.setForeground(foreground)

        if has_progress:
            # set initial progress to 0
            self.setData(0, Qt.DisplayRole)
