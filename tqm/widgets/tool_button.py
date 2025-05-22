from __future__ import annotations

from typing import Optional

from PySide2.QtWidgets import QWidget, QToolButton


class ToolButton(QToolButton):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName('TqmToolButton')
