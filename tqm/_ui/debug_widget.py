from __future__ import annotations

from typing import Any, Dict, List, Optional

from PySide2.QtGui import QFont, QColor
from PySide2.QtCore import Qt
from PySide2.QtWidgets import (QLabel, QWidget, QSplitter, QTabWidget,
                               QHeaderView, QPushButton, QTreeWidget,
                               QVBoxLayout, QTableWidget, QTreeWidgetItem,
                               QTableWidgetItem)

from tqm._core.task_executor import TaskExecutor

from ..widgets import Frame
from .._core.task import TaskUnit, TaskGroup
from .font_loader import get_monospace_font
from .._core.task_state import TaskStates


class StateHistoryWidget(QTreeWidget):

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        self.setColumnCount(5)
        self.setHeaderLabels(['#', 'State', 'Comment', 'Duration', 'Time'])
        self.setAlternatingRowColors(True)
        self.setStyleSheet('background-color: #282828;')
        self.setFont(get_monospace_font())
        self.header().setObjectName('TqmHeaderView')

        self.bold_font = QFont()
        self.bold_font.setBold(True)

    def populate(self, history: List[Dict[str, str]]) -> None:
        """Populate with formatted state history data."""
        self.clear()

        for i, entry in enumerate(history, 1):
            item = QTreeWidgetItem(self)

            item.setText(0, str(i))

            state = entry['state']
            item.setText(1, state.upper())
            item.setFont(1, self.bold_font)

            item.setText(2, entry['comment'])
            item.setText(3, entry['duration'])
            item.setText(4, entry['timestamp'])

            bg_color = TaskStates.get_color(state)
            for col in range(5):
                item.setForeground(col, bg_color)

        for i in range(self.columnCount()):
            self.resizeColumnToContents(i)


class TaskPropertyTreeItem(QTreeWidgetItem):
    """Tree widget item for displaying task properties."""

    def __init__(self, parent: QTreeWidgetItem, key: str, value: Any, is_parent: bool = False):
        super().__init__(parent)
        self.key = key
        self.value = value
        self.is_parent_node = is_parent
        self.setText(0, key)

        if not is_parent:
            self.setText(1, str(value))

        # Set different styling for parent nodes
        if is_parent:
            self.setForeground(0, QColor(60, 120, 216))  # Blue color for parents
            font = self.font(0)
            font.setPixelSize(14)
            font.setBold(True)
            self.setFont(0, font)


class TasksList(QWidget):
    def __init__(self, executor: TaskExecutor, parent: Optional[QWidget] = None):
        super().__init__(parent)

        self._executor = executor

        self._tasks_table = QTableWidget()
        self._tasks_table.setFont(get_monospace_font())
        self._tasks_table.setColumnCount(5)
        self._tasks_table.setEditTriggers(QHeaderView.NoEditTriggers)
        self._tasks_table.setSelectionBehavior(QHeaderView.SelectRows)
        self._tasks_table.setAlternatingRowColors(True)
        self._tasks_table.setStyleSheet('background-color: #282828;')
        self._tasks_table.setSortingEnabled(True)
        self._tasks_table.setHorizontalHeaderLabels(
            ['Name', 'Type', 'State', 'In Queue', 'Parent']
        )

        self._tasks_table.horizontalHeader().setObjectName('TqmHeaderView')
        self._tasks_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        refresh_registry = QPushButton('Refresh')
        refresh_registry.clicked.connect(self._load_tasks)

        layout = QVBoxLayout()
        layout.addWidget(refresh_registry)
        layout.addWidget(self._tasks_table)
        self.setLayout(layout)

    def _load_tasks(self) -> None:
        tasks = self._executor.registry
        self._tasks_table.setRowCount(len(tasks))

        for row, task in enumerate(tasks):

            # name
            self._tasks_table.setItem(row, 0, QTableWidgetItem(task.name))

            # type
            obj_type = 'Group' if isinstance(task, TaskGroup) else 'Task'
            self._tasks_table.setItem(row, 1, QTableWidgetItem(obj_type))

            # state
            self._tasks_table.setItem(row, 2, QTableWidgetItem(task.state.current))

            # in queue
            in_queue = 'True' if task in self._executor.queue else 'False'
            self._tasks_table.setItem(row, 3, QTableWidgetItem(in_queue))

            # parent
            self._tasks_table.setItem(row, 4, QTableWidgetItem(str(task.parent)))


class DebugWidget(Frame):
    def __init__(self, executor: TaskExecutor, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setStyleSheet('font-size: 14px;')

        self._property_tree = QTreeWidget()
        self._property_tree.header().setObjectName('TqmHeaderView')
        self._property_tree.setFont(get_monospace_font())
        self._property_tree.setColumnCount(2)
        self._property_tree.setHeaderLabels(['Property', 'Value'])
        self._property_tree.setAlternatingRowColors(True)
        self._property_tree.setStyleSheet('background-color: #282828;')

        self._state_tree = StateHistoryWidget()

        tasks_registry = TasksList(executor)

        s = QSplitter(Qt.Vertical)
        s.addWidget(self._property_tree)
        s.addWidget(self._state_tree)

        tabs = QTabWidget()
        tabs.addTab(s, 'Task Properties')
        tabs.addTab(tasks_registry, 'Registry')

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel('<h3>Debug</h3>'))
        layout.addWidget(tabs)
        self.setLayout(layout)

    def _add_properties(self, parent: QTreeWidgetItem, data: Dict[str, Any]) -> None:
        """Recursively add dictionary data to tree."""

        for key, value in sorted(data.items()):
            if isinstance(value, dict):
                item = TaskPropertyTreeItem(parent, key, '', True)
                self._add_properties(item, value)

            elif isinstance(value, list) and value and isinstance(value[0], dict):
                item = TaskPropertyTreeItem(parent, key, f"({len(value)} items)", True)
                for i, sub_value in enumerate(value):
                    child = TaskPropertyTreeItem(item, f"[{i}]", '', True)
                    if isinstance(sub_value, dict):
                        self._add_properties(child, sub_value)
                    else:
                        TaskPropertyTreeItem(child, '', str(sub_value))

            elif isinstance(value, list):
                item = TaskPropertyTreeItem(parent, key, f"({len(value)} items)", True)
                for i, sub_value in enumerate(value):
                    TaskPropertyTreeItem(item, f"[{i}]", str(sub_value))

            else:
                TaskPropertyTreeItem(parent, key, value)

    def populate(self, task: TaskUnit) -> None:
        """Populate the dialog with task data."""
        self._property_tree.clear()

        task_data = task.inspect()

        # Populate the property tree
        self._add_properties(self._property_tree.invisibleRootItem(), task_data)

        # Populate state history with specialized widget
        if 'state' in task_data and 'history' in task_data['state']:
            self._state_tree.populate(task.state.inspect()['history'])

        # Expand property tree for better visibility
        self._property_tree.expandAll()

        # Resize property tree columns
        for i in range(self._property_tree.columnCount()):
            self._property_tree.resizeColumnToContents(i)
