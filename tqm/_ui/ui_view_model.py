from __future__ import annotations

import os
from typing import Any, Dict, List, Tuple, Union, Optional
from functools import partial

from PySide2.QtGui import (QIcon, QStandardItem, QContextMenuEvent,
                           QStandardItemModel)
from PySide2.QtCore import Qt, Slot, Signal, QModelIndex, QSortFilterProxyModel
from PySide2.QtWidgets import (QMenu, QAction, QWidget, QSplitter, QTreeView,
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
from .._core.task_executor import TaskExecutor
from .progress_bar_delegate import ProgressBarDelegate
from .mixins.multi_select_mixin import MultiSelectMixin

_TaskActionsT = Union[
    Tuple[TaskAction[TaskExecutable], ...],
    Tuple[TaskAction[TaskGroup], ...]
]


class TreeModel(QStandardItemModel):

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

        self._headers = (
            'Task', 'Progress', 'Wait for', 'Comment',
            'Created', 'Started', 'Completed',
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
        ]

    def _configure_group_item(self, task_group: TaskGroup) -> None:
        if not task_group.tasks:
            raise TaskGroupError(
                f'Cannot add TaskGroup "{task_group.name}" without any tasks'
            )

        task_group.progress_bar.maximum = len(task_group.tasks)

        group_item = task_group.item
        if not group_item:
            raise TaskGroupError(
                f'Expected TaskGroup "{task_group.name}" to have an associated group item, but none was found.'
            )

        group_item.setIcon(QIcon(':/icons/dark/circle-parent'))
        f = group_item.font()
        f.setBold(True)
        group_item.setFont(f)

        for task in task_group.tasks:
            task.color = task_group.color

            task.item = TaskItem(task.name, foreground=task.color)
            task.item.setIcon(QIcon(':/icons/dark/circle-line'))
            task.item.setData(task, Qt.UserRole)

            group_item.appendRow(self._create_task_row(task.item, task))

    def add_task(self, task_unit: TaskUnit) -> TaskItem:

        task_unit.item = TaskItem(task_unit.name, foreground=task_unit.color)
        task_unit.item.setIcon(QIcon(':/icons/dark/circle-filled'))
        task_unit.item.setData(task_unit, Qt.UserRole)

        if isinstance(task_unit, TaskGroup):
            self._configure_group_item(task_unit)

        self.root_item.appendRow(self._create_task_row(task_unit.item, task_unit))

        return task_unit.item

    def reset(self) -> None:
        self.clear()
        self.setHorizontalHeaderLabels(self._headers)
        self.root_item = self.invisibleRootItem()


class RecursiveFilterProxyModel(QSortFilterProxyModel):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:

        if super().filterAcceptsRow(source_row, source_parent):
            return True

        model = self.sourceModel()
        source_index = model.index(source_row, 0, source_parent)

        if source_index.isValid():
            rows = model.rowCount(source_index)
            for i in range(rows):
                if self.filterAcceptsRow(i, source_index):
                    return True
        return False


class TaskTreeView(MultiSelectMixin, ViewStateMixing, QTreeView):
    selected_task_retried = Signal(TaskExecutable)
    selected_task_removed = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(self, self, parent)
        self.setObjectName('TqmTasksTreeView')

        self.tasks_model = TreeModel()

        self.proxy_model = RecursiveFilterProxyModel()
        self.proxy_model.setFilterKeyColumn(-1)
        self.proxy_model.setSortCaseSensitivity(Qt.CaseInsensitive)
        self.proxy_model.setFilterCaseSensitivity(Qt.CaseInsensitive)
        self.proxy_model.setSourceModel(self.tasks_model)
        self.setModel(self.proxy_model)

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
                    menu.addMenu(TaskFileMenu(user_file, self))
                else:
                    act = QAction(action.name, self)
                    act.triggered.connect(partial(action.action, task))
                    menu.addAction(act)

        item = self.indexAt(event.pos()).siblingAtColumn(0)
        if not item.isValid() or not item.data(Qt.UserRole):
            return

        menu = QMenu(self)

        task: TaskUnit = item.data(Qt.UserRole)
        add_actions(task.actions, TaskActionVisibility.ALWAYS)

        if task.state.is_completed:
            add_actions(task.actions, TaskActionVisibility.ON_COMPLETED)

        elif task.state.is_failed:
            add_actions(task.actions, TaskActionVisibility.ON_FAILED)

            if isinstance(task, TaskExecutable) and not task.parent:
                retry_act = QAction('Retry', self)
                retry_act.triggered.connect(lambda: self.selected_task_retried.emit(task))
                menu.addAction(retry_act)

        menu.addSeparator()

        if task.state.is_removable:
            remove_task = QAction('Remove selected', self)
            remove_task.triggered.connect(self.selected_task_removed.emit)
            menu.addAction(remove_task)

        menu.exec_(event.globalPos())


class TaskManagerView(QWidget):
    """
    A widget that displays tasks and provides various methods to interact with them.

    This widget consists of a tree view to display tasks, a search bar, buttons for
    actions, a log widget to display logs, and a status bar to show the current status.

    """

    def __init__(self, executor: TaskExecutor, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

        self.tree_view = TaskTreeView()
        self.tree_view.clicked.connect(self._on_toggle_debug)

        self.toolbar = TasksViewToolbar()
        self.toolbar.search_bar.textChanged.connect(
            self.tree_view.proxy_model.setFilterRegExp
        )

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

    @Slot(QModelIndex)
    def _on_toggle_debug(self, index: QModelIndex) -> None:
        selected_item = self.tree_view.get_selected_items()
        task = selected_item[0].data(Qt.UserRole)
        self._debug_widget.populate(task)

    def toggle_expand(self, state: bool) -> None:
        self.tree_view.expandAll() if state else self.tree_view.collapseAll()

    def update_status(self, status: Dict[str, Any]) -> None:
        stringified_status = ' | '.join(f'{k}: {v}' for k, v in status.items())
        self.toolbar.status_label.setText(stringified_status)
