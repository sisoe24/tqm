from __future__ import annotations

import os
import logging
from typing import Dict, Optional

from PySide2.QtCore import Qt, QDir, Slot, QPoint, QDateTime
from PySide2.QtWidgets import (QAction, QWidget, QFileDialog, QVBoxLayout,
                               QPlainTextEdit)

from ..utils import RandomColor
from .font_loader import get_monospace_font
from .._core.logger import LOGGER
from .._core.settings import open_settings

LOG_COLORS = {
    'DEBUG': 'aqua',
    'INFO': 'white',
    'WARNING': 'orange',
    'ERROR': 'red',
    'CRITICAL': 'magenta',
}


class TasksLog(QWidget):
    def __init__(self, should_wrap: bool = False, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

        self._logs = QPlainTextEdit()
        self._logs.setReadOnly(True)
        self._logs.setObjectName('TqmTasksLogs')
        self._logs.setFont(get_monospace_font(14))
        self._logs.setContextMenuPolicy(Qt.CustomContextMenu)
        self._logs.customContextMenuRequested.connect(self._on_contextMenuEvent)

        self._set_line_wrapping(should_wrap)

        self._enable_debug = QAction('Enable Debug', self)
        self._enable_debug.setCheckable(True)
        self._enable_debug.toggled.connect(self._on_enable_debug)

        self._wrap_lines = QAction('Wrap Lines', self)
        self._wrap_lines.setCheckable(True)
        self._wrap_lines.toggled.connect(self._on_wrap_lines)

        self._clear_console = QAction('Clear', self)
        self._clear_console.triggered.connect(self.on_clear_logs)

        self._save_console = QAction('Save', self)
        self._save_console.triggered.connect(self.on_save_logs)

        layout = QVBoxLayout()
        layout.addWidget(self._logs)
        self.setLayout(layout)

        self._random_color = RandomColor()
        self._thread_colors: Dict[str, str] = {}

    def _on_contextMenuEvent(self, point: QPoint) -> None:

        menu = self._logs.createStandardContextMenu()
        menu.addSection('Console Options')
        menu.addAction(self._wrap_lines)
        menu.addAction(self._enable_debug)
        menu.addAction(self._clear_console)
        menu.addAction(self._save_console)
        menu.exec_(self._logs.mapToGlobal(point))

    def _set_line_wrapping(self, state: bool) -> None:
        self._logs.setLineWrapMode(
            QPlainTextEdit.WidgetWidth if state else QPlainTextEdit.NoWrap
        )

    @Slot()
    def _on_wrap_lines(self, state: bool) -> None:
        self._set_line_wrapping(state)
        with open_settings(mode='w') as s:
            s.wrap_lines = state

    @Slot(int)
    def _on_enable_debug(self, state: bool) -> None:
        LOGGER.widget.setLevel(logging.DEBUG if state else logging.INFO)
        with open_settings(mode='w') as s:
            s.enable_debug = state

    @Slot()
    def on_save_logs(self) -> None:
        now = QDateTime.currentDateTime().toString('yyyy-MM-dd_hh-mm-ss')
        report_file = f'{QDir.homePath()}/{now}_tqm_logs.csv'

        filename, _ = QFileDialog.getSaveFileName(
            self, 'Save log', report_file, 'Text files (*.txt);;All files (*)'
        )

        if not filename:
            return

        with open(filename, 'w') as f:
            f.write(self._logs.toPlainText())

    @Slot()
    def on_clear_logs(self) -> None:
        self._logs.clear()

    def log(self, text: str, level_name: str = 'INFO', thread: str = '') -> None:

        if level_name == 'USER':
            if thread in self._thread_colors:
                color = self._thread_colors[thread]
            else:
                color = self._random_color.generate().name()
                self._thread_colors[thread] = color

        else:
            color = LOG_COLORS.get(level_name, 'white')

        text = text.replace(' ', '&nbsp;')
        self._logs.appendHtml(f'<font color="{color}">{text}</font>')
        self._logs.verticalScrollBar().setValue(
            self._logs.verticalScrollBar().maximum()
        )
