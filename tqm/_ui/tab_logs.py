from __future__ import annotations

import html
import heapq
import logging
import itertools
from typing import Set, Dict, Deque, Tuple, Iterable, Optional
from pathlib import Path
from collections import deque

from PySide2.QtCore import Qt, QDir, Slot, QPoint, QDateTime
from PySide2.QtWidgets import (QAction, QWidget, QFileDialog, QVBoxLayout,
                               QPlainTextEdit)

from ..utils import RandomColor
from .._core.task import TaskUnit, TaskGroup
from .font_loader import get_monospace_font
from .._core.logger import WidgetLogHandler
from .._core.settings import open_settings

LOG_COLORS = {
    'DEBUG':    '#00bcd4',  # Cyan
    'INFO':     '#e0e0e0',  # Light gray
    'WARNING':  '#ffb300',  # Amber
    'ERROR':    '#e53935',  # Red
    'CRITICAL': '#d500f9',  # Purple
    'USER':     '#81da27',  # Purple
}

# shortcut: buffers live until Clear, so memory grows with the number of tasks; drop a
# task's buffer on removal if long sessions with many tasks become a problem.
RECORDS_PER_TASK = 1000


class TasksLog(QWidget):
    def __init__(
        self,
        settings_path: Path,
        should_wrap: bool = False,
        debug: bool = False,
        parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)

        self._settings_path = settings_path

        self._logs = QPlainTextEdit()
        self._logs.setReadOnly(True)
        self._logs.setMaximumBlockCount(10000)
        self._logs.setObjectName('TqmTasksLogs')
        self._logs.setFont(get_monospace_font(14))
        self._logs.setContextMenuPolicy(Qt.CustomContextMenu)
        self._logs.customContextMenuRequested.connect(self._on_contextMenuEvent)

        self._set_line_wrapping(should_wrap)

        self.handler = WidgetLogHandler(self, debug)

        self._enable_debug = QAction('Enable Debug', self)
        self._enable_debug.setCheckable(True)
        self._enable_debug.setChecked(debug)
        self._enable_debug.toggled.connect(self._on_enable_debug)

        self._wrap_lines = QAction('Wrap Lines', self)
        self._wrap_lines.setCheckable(True)
        self._wrap_lines.setChecked(should_wrap)
        self._wrap_lines.toggled.connect(self._on_wrap_lines)

        self._clear_console = QAction('Clear', self)
        self._clear_console.triggered.connect(self.on_clear_logs)

        self._save_console = QAction('Save', self)
        self._save_console.triggered.connect(self.on_save_logs)

        layout = QVBoxLayout()
        layout.addWidget(self._logs)
        self.setLayout(layout)

        self._random_color = RandomColor(
            min_value=70,
            max_value=220,
            exclude_colors=list(LOG_COLORS.values())
        )
        self._task_colors: Dict[str, str] = {}

        # Task id ('' for lines without a task) to (sequence, html line), so a busy task
        # cannot push the lines of the others out.
        self._records: Dict[str, Deque[Tuple[int, str]]] = {}
        self._sequence = itertools.count()
        self._shown_tasks: Optional[Set[str]] = None  # None shows every line

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
        with open_settings(mode='w', json_file_path=self._settings_path) as s:
            s.wrap_lines = state

    @Slot(int)
    def _on_enable_debug(self, state: bool) -> None:
        self.handler.setLevel(logging.DEBUG if state else logging.INFO)
        with open_settings(mode='w', json_file_path=self._settings_path) as s:
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
        self._records.clear()
        self._logs.clear()

    def show_tasks(self, tasks: Iterable[TaskUnit]) -> None:
        """Show only the lines of `tasks` and their children, or every line if `tasks` is empty."""
        task_ids: Set[str] = set()
        for task in tasks:
            task_ids.add(str(task.id))
            if isinstance(task, TaskGroup):
                task_ids.update(str(child.id) for child in task.tasks)
        self._shown_tasks = task_ids or None

        buffers = [
            records for task_id, records in self._records.items()
            if self._shown_tasks is None or task_id in self._shown_tasks
        ]
        self._logs.setUpdatesEnabled(False)
        self._logs.clear()
        for _, line in heapq.merge(*buffers):
            self._logs.appendHtml(line)
        self._logs.setUpdatesEnabled(True)
        self._scroll_to_end()

    def _scroll_to_end(self) -> None:
        self._logs.verticalScrollBar().setValue(
            self._logs.verticalScrollBar().maximum()
        )

    def log(self, text: str, level_name: str = 'INFO', task_id: str = '') -> None:
        # TODO: Add a no color flag?

        # Escape first: the text is plain, but the view adds color with html.
        text = html.escape(text).replace(' ', '&nbsp;').replace('\n', '<br>')

        if task_id not in self._task_colors:
            self._task_colors[task_id] = self._random_color.generate().name()

        # use a different color for the log level
        log_level_color = LOG_COLORS[level_name] if level_name in LOG_COLORS else 'white'
        parts = text.split('|', 2)
        parts[1] = f'<font color="{log_level_color}">{parts[1]}</font>'
        text = '|'.join(parts)

        line = f'<font color="{self._task_colors[task_id]}">{text}</font>'
        records = self._records.setdefault(task_id, deque(maxlen=RECORDS_PER_TASK))
        records.append((next(self._sequence), line))

        if self._shown_tasks is None or task_id in self._shown_tasks:
            self._logs.appendHtml(line)
            self._scroll_to_end()
