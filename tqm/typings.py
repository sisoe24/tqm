from __future__ import annotations

from typing import Tuple, Union

from PySide2.QtGui import QColor
from PySide2.QtCore import Qt

RGBA = Tuple[int, int, int, int]
TASK_COLOR = Union[str, Qt.GlobalColor, RGBA, QColor]
