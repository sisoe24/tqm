from __future__ import annotations

from typing import Optional

from PySide2.QtGui import QIcon
from PySide2.QtCore import Qt, Slot, Signal
from PySide2.QtWidgets import (QMenu, QLabel, QAction, QWidget, QLineEdit,
                               QHBoxLayout, QToolButton)

from ..widgets import ToolButton, show_help


class ClearTasksMenu(ToolButton):

    completed_tasks_removed = Signal()
    failed_tasks_removed = Signal()
    waiting_tasks_removed = Signal()
    all_tasks_removed = Signal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        self.setIcon(QIcon(':/icons/dark/trash'))
        self.setToolTip('Clear tasks options')
        self.setPopupMode(QToolButton.InstantPopup)
        self.setToolButtonStyle(Qt.ToolButtonIconOnly)

        self.clear_completed_tasks_btn = QAction('Clear Completed Tasks', self)
        self.clear_completed_tasks_btn.triggered.connect(self.completed_tasks_removed.emit)

        self.clear_failed_tasks_btn = QAction('Clear Failed Tasks', self)
        self.clear_failed_tasks_btn.triggered.connect(self.failed_tasks_removed.emit)

        self.clear_waiting_tasks_btn = QAction('Clear Waiting Tasks', self)
        self.clear_waiting_tasks_btn.triggered.connect(self.waiting_tasks_removed.emit)

        self.clear_all_tasks_btn = QAction('Clear All Tasks', self)
        self.clear_all_tasks_btn.triggered.connect(self.all_tasks_removed.emit)

        menu = QMenu(self)
        menu.addAction(self.clear_completed_tasks_btn)
        menu.addAction(self.clear_failed_tasks_btn)
        menu.addAction(self.clear_waiting_tasks_btn)
        menu.addAction(self.clear_all_tasks_btn)
        self.setMenu(menu)


class TableOptions(ToolButton):

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        self.setIcon(QIcon(':/icons/dark/settings-gear'))
        self.setToolTip('Table state')
        self.setPopupMode(QToolButton.InstantPopup)

        self.reset_layout = QAction('Reset Layout', self)
        self.resize_columns = QAction('Resize Columns', self)
        self.expand_all = QAction('Expand All', self)
        self.set_max_workers = QAction('Set Max Workers', self)

        self.help = QAction('Help', self)
        self.help.triggered.connect(show_help)

        menu = QMenu(self)
        menu.addAction(self.set_max_workers)
        menu.addSeparator()
        menu.addAction(self.reset_layout)
        menu.addAction(self.resize_columns)
        menu.addAction(self.expand_all)
        menu.addSeparator()
        menu.addAction(self.help)
        self.setMenu(menu)


class TasksViewToolbar(QWidget):
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName('TqmTasksViewToolbar')

        self.clear_tasks = ClearTasksMenu()

        self.run_all_tasks = ToolButton()
        self.run_all_tasks.setIcon(QIcon(':/icons/dark/run-all'))
        self.run_all_tasks.setToolTip('Run all tasks')

        self.table_options = TableOptions()

        self.retry_all_btn = ToolButton()
        self.retry_all_btn.setIcon(QIcon(':/icons/dark/refresh'))
        self.retry_all_btn.setToolTip('Retry all failed tasks')

        self.search_btn = ToolButton()
        self.search_btn.setCheckable(True)
        self.search_btn.setIcon(QIcon(':/icons/dark/search'))
        self.search_btn.toggled.connect(self._on_toggle_search_bar)

        self.search_bar = QLineEdit()
        self.search_bar.setObjectName('TqmSearchBar')
        self.search_bar.setHidden(True)
        self.search_bar.setClearButtonEnabled(True)
        self.search_bar.setPlaceholderText('Search...')

        self.status_label = QLabel()
        self.status_label.setObjectName('TqmStatusLabel')

        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.run_all_tasks)
        layout.addWidget(self.retry_all_btn)
        layout.addWidget(self.clear_tasks)
        layout.addWidget(self.table_options)
        layout.addWidget(self.search_btn)
        layout.addWidget(self.search_bar)
        layout.addStretch()
        layout.addWidget(self.status_label)

        self.setLayout(layout)

    @Slot(bool)
    def _on_toggle_search_bar(self, state: bool) -> None:
        focus = Qt.OtherFocusReason if state else Qt.NoFocusReason
        self.search_bar.setFocus(focus)
        self.search_bar.setVisible(state)
