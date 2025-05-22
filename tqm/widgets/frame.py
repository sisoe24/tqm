from __future__ import annotations

from typing import Optional

from PySide2.QtWidgets import QFrame, QWidget


class Frame(QFrame):
    """Custom frame for styling purposes."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        self.setObjectName('TqmFrame')
        self.setFrameStyle(QFrame.StyledPanel)
