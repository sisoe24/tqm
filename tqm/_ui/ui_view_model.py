from __future__ import annotations

import os
import re
from typing import Any, Dict, List, Tuple, Union, Optional
from pathlib import Path
from functools import partial, lru_cache

import shiboken2
from PySide2.QtGui import (QIcon, QStandardItem, QContextMenuEvent,
                           QStandardItemModel)
from PySide2.QtCore import (Qt, Slot, Signal, QRegExp, QModelIndex,
                            QItemSelectionModel, QSortFilterProxyModel)
from PySide2.QtWidgets import (QMenu, QWidget, QSplitter, QTreeView,
                               QVBoxLayout)

from .toolbar import TasksViewToolbar
from ..widgets import Frame
from .task_item import TaskItem
from .._core.task import TaskUnit, TaskGroup, TaskExecutable
from ..exceptions import TaskGroupError
from .font_loader import get_monospace_font
from .context_menu import TaskFileMenu
from .debug_widget import DebugWidget
from .mixins.view_mixin import ViewStateMixing
from .._core.task_actions import TaskAction, TaskActionVisibility
from .._core.task_builder import TaskBuilder
from .._core.task_executor import TaskExecutor
from .progress_bar_delegate import ProgressBarDelegate
from .mixins.multi_select_mixin import MultiSelectMixin

_TaskActionsT = Union[
    Tuple[TaskAction[TaskExecutable], ...],
    Tuple[TaskAction[TaskGroup], ...]
]


@lru_cache(maxsize=None)
def _icon(path: str) -> QIcon:
    # Building a QIcon from a resource is slow; one per path keeps large adds fast.
    return QIcon(path)


class TreeModel(QStandardItemModel):

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

        self._headers = (
            'Task', 'Progress', 'Wait for', 'Comment',
            'Created', 'Started', 'Completed', 'Last message',
        )

        self.columns = {h: i for i, h in enumerate(self._headers)}

        self.setHorizontalHeaderLabels(self._headers)
        self.root_item = self.invisibleRootItem()

        self.itemChanged.connect(self._on_item_changed)

    @Slot(TaskItem)
    def _on_item_changed(self, item: TaskItem) -> None:
        if item.column() == self.columns['Comment']:
            task = self.itemFromIndex(item.index().siblingAtColumn(0)).data(Qt.UserRole)
            task.comment = item.text()

    def _create_task_row(self, item: TaskItem, task: TaskUnit) -> List[TaskItem]:
        return [
            item,
            TaskItem('', has_progress=True),
            TaskItem(task.parent.name if task.parent else ''),
            TaskItem(task.comment, is_editable=True),
            TaskItem(task.state.get_first().timestamp, alignment=Qt.AlignCenter),
            TaskItem('', alignment=Qt.AlignCenter),
            TaskItem('', alignment=Qt.AlignCenter),
            TaskItem(''),
        ]

    def _configure_group_item(self, task_group: TaskGroup) -> None:
        task_group.progress_bar.maximum = len(task_group.tasks)

        group_item = task_group.item
        if not group_item:
            raise TaskGroupError(
                f'Expected TaskGroup "{task_group.name}" to have an associated group item, but none was found.'
            )

        group_item.setIcon(_icon(':/icons/dark/circle-parent'))
        f = group_item.font()
        f.setBold(True)
        group_item.setFont(f)

        for task in task_group.tasks:
            # A task keeps its own color; one left at the default takes the group's.
            if task.color == TaskBuilder.DEFAULT_COLOR:
                task.color = task_group.color

            task.item = TaskItem(task.name, foreground=task.color)
            task.item.setIcon(_icon(':/icons/dark/circle-line'))
            task.item.setData(task, Qt.UserRole)

            group_item.appendRow(self._create_task_row(task.item, task))

    def add_task(self, task_unit: TaskUnit) -> TaskItem:

        task_unit.item = TaskItem(task_unit.name, foreground=task_unit.color)
        task_unit.item.setIcon(_icon(':/icons/dark/circle-filled'))
        task_unit.item.setData(task_unit, Qt.UserRole)

        if isinstance(task_unit, TaskGroup):
            self._configure_group_item(task_unit)

        self.root_item.appendRow(self._create_task_row(task_unit.item, task_unit))

        return task_unit.item

    def reset(self) -> None:
        self.clear()
        self.setHorizontalHeaderLabels(self._headers)
        self.root_item = self.invisibleRootItem()


class TaskFilterProxyModel(QSortFilterProxyModel):
    """Filter on the text columns and sort names in natural order.

    Qt's recursive filtering keeps the ancestors of a match; this class keeps its descendants.
    """

    def __init__(self, text_columns: Tuple[int, ...], parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._text_columns = text_columns
        self.setRecursiveFilteringEnabled(True)

    def set_search_text(self, text: str) -> None:
        regexp = QRegExp(text, Qt.CaseInsensitive)
        if not regexp.isValid():
            regexp = QRegExp(text, Qt.CaseInsensitive, QRegExp.FixedString)
        self.setFilterRegExp(regexp)

    def _row_matches(self, source_row: int, source_parent: QModelIndex) -> bool:
        model = self.sourceModel()
        regexp = self.filterRegExp()
        return any(
            regexp.indexIn(str(model.index(source_row, column, source_parent).data() or '')) != -1
            for column in self._text_columns
        )

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:
        if self._row_matches(source_row, source_parent):
            return True

        parent = source_parent
        while parent.isValid():
            if self._row_matches(parent.row(), parent.parent()):
                return True
            parent = parent.parent()
        return False

    def lessThan(self, left: QModelIndex, right: QModelIndex) -> bool:
        left_data, right_data = left.data(), right.data()
        if isinstance(left_data, str) and isinstance(right_data, str):
            return _natural_key(left_data) < _natural_key(right_data)
        return super().lessThan(left, right)


def _natural_key(text: str) -> List[Union[int, str]]:
    # re.split with a group alternates text and digits, so positions always compare like with like.
    return [int(part) if part.isdigit() else part.lower() for part in re.split(r'(\d+)', text)]


class TaskTreeView(MultiSelectMixin, ViewStateMixing, QTreeView):
    selected_task_retried = Signal(TaskExecutable)
    selected_task_removed = Signal()

    def __init__(self, settings_path: Path, parent: Optional[QWidget] = None) -> None:
        super().__init__(self, self, settings_path, parent)
        self.setObjectName('TqmTasksTreeView')

        self.tasks_model = TreeModel(self)

        columns = self.tasks_model.columns
        text_columns = (columns['Task'], columns['Wait for'], columns['Comment'])
        self.proxy_model = TaskFilterProxyModel(text_columns, self)
        self.proxy_model.setSortCaseSensitivity(Qt.CaseInsensitive)
        self.proxy_model.setFilterCaseSensitivity(Qt.CaseInsensitive)
        self.proxy_model.setSourceModel(self.tasks_model)
        self.setModel(self.proxy_model)
        # Expand rows as they appear, so adding or filtering keeps the groups the user collapsed.
        self.proxy_model.rowsInserted.connect(self._expand_inserted)

        self._progress_delegate = ProgressBarDelegate(self.tasks_model.columns['Progress'], self)
        self.setItemDelegate(self._progress_delegate)

        self.setAlternatingRowColors(True)
        self.setFont(get_monospace_font())

        self.setSelectionMode(QTreeView.SingleSelection)
        self.setSelectionBehavior(QTreeView.SelectRows)

        header = self.header()
        header.setObjectName('TqmHeaderView')
        header.setSortIndicatorShown(True)
        header.setStretchLastSection(True)
        header.setSectionsMovable(True)

        self.load_table_state()
        self.setSortingEnabled(True)

    @Slot(QModelIndex, int, int)
    def _expand_inserted(self, parent: QModelIndex, first: int, last: int) -> None:
        for row in range(first, last + 1):
            self.expand(self.proxy_model.index(row, 0, parent))

    def stop_animation(self) -> None:
        self._progress_delegate.cleanup()

    def get_column_indexes(self) -> Dict[str, int]:
        """Return a dictionary of column names and their corresponding indexes."""
        return self.tasks_model.columns

    def get_column_index(self, column_name: str) -> int:
        return self.tasks_model.columns[column_name]

    def get_selected_items(self) -> List[QStandardItem]:
        """Get a list of selected tasks QStandardItem in the tree view."""
        items: List[QStandardItem] = []
        for index in self.selectionModel().selectedRows():

            source_index = self.proxy_model.mapToSource(index)
            item = self.tasks_model.itemFromIndex(source_index)

            items.append(item)

        return items

    def contextMenuEvent(self, event: QContextMenuEvent) -> None:
        def add_actions(actions: _TaskActionsT, visibility: TaskActionVisibility) -> None:
            for action in filter(lambda a: a.visibility == visibility, actions):
                if action.name == '%file%':
                    # get the file assigned to the action return
                    user_file = action.action(task)
                    menu.addMenu(TaskFileMenu(user_file, menu))
                else:
                    menu.addAction(action.name).triggered.connect(partial(action.action, task))

        item = self.indexAt(event.pos()).siblingAtColumn(0)
        if not item.isValid() or not item.data(Qt.UserRole):
            return

        # Act on the clicked row: select it unless it is already part of the selection.
        if not self.selectionModel().isRowSelected(item.row(), item.parent()):
            self.selectionModel().select(item, QItemSelectionModel.ClearAndSelect | QItemSelectionModel.Rows)

        menu = QMenu(self)

        task: TaskUnit = item.data(Qt.UserRole)
        add_actions(task.actions, TaskActionVisibility.ALWAYS)

        if task.state.is_completed:
            add_actions(task.actions, TaskActionVisibility.ON_COMPLETED)

        elif task.state.is_failed:
            add_actions(task.actions, TaskActionVisibility.ON_FAILED)

            if isinstance(task, TaskExecutable) and not task.parent:
                retry = menu.addAction('Retry')
                retry.triggered.connect(lambda: self.selected_task_retried.emit(task))

        menu.addSeparator()

        if task.state.is_removable:
            menu.addAction('Remove selected').triggered.connect(self.selected_task_removed.emit)

        if any(not action.isSeparator() for action in menu.actions()):
            menu.exec_(event.globalPos())
        # Delete now, on the main thread: a parented menu would pile up on the view.
        shiboken2.delete(menu)


class TaskManagerView(QWidget):
    """
    A widget that displays tasks and provides various methods to interact with them.

    This widget consists of a tree view to display tasks, a search bar, buttons for
    actions, a log widget to display logs, and a status bar to show the current status.

    """

    def __init__(
        self,
        executor: TaskExecutor,
        settings_path: Path,
        parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)

        self.tree_view = TaskTreeView(settings_path)
        self.tree_view.clicked.connect(self._on_toggle_debug)

        self.toolbar = TasksViewToolbar()
        self.toolbar.search_bar.textChanged.connect(self.tree_view.proxy_model.set_search_text)
        self.toolbar.search_btn.toggled.connect(self._on_toggle_search)

        self._debug_widget = DebugWidget(executor)

        table_layout = QVBoxLayout()
        table_layout.addWidget(self.toolbar)
        table_layout.addWidget(self.tree_view)

        table_widget = Frame()
        table_widget.setLayout(table_layout)

        splitter = QSplitter()
        splitter.addWidget(table_widget)
        splitter.addWidget(self._debug_widget)
        if os.getenv('DEV_MODE') != '1':
            splitter.setSizes([100, 0])

        layout = QVBoxLayout()
        layout.addWidget(splitter)
        self.setLayout(layout)

    @Slot(bool)
    def _on_toggle_search(self, shown: bool) -> None:
        # Closing the bar clears the search, so no hidden filter stays on.
        if not shown:
            self.toolbar.search_bar.clear()

    @Slot(QModelIndex)
    def _on_toggle_debug(self, index: QModelIndex) -> None:
        self._debug_widget.populate(index.siblingAtColumn(0).data(Qt.UserRole))

    def update_status(self, status: Dict[str, Any]) -> None:
        stringified_status = ' | '.join(f'{k}: {v}' for k, v in status.items())
        self.toolbar.status_label.setText(stringified_status)
