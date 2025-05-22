from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict
from functools import partial

from PySide2.QtCore import Qt, QPoint, QTimer, QByteArray
from PySide2.QtWidgets import QMenu, QAction

from ..._core.settings import open_settings

if TYPE_CHECKING:
    from ..._ui.ui_view_model import TaskTreeView


class ViewStateMixing:
    """
    Mixin for handling the persistent state of a view.

    This mixin offers functionality to save and restore the state of a view, including
    column widths and visibility. It also provides a context menu on the view's header
    to allow users to customize which columns are visible.

    Args:
        view (TaskTreeView): The view whose state will be managed.

    Note:
        This class contains extra complexity due to legacy support for both TaskTreeView
        and TaskDatabaseView. Consider refactoring if only one view type is needed in the future.
    """

    def __init__(
        self,
        view: TaskTreeView,
        *args: Any, **kwargs: Any
    ) -> None:
        super().__init__(*args, **kwargs)

        self.__view = view

        self.__header = self.__view.header()
        self.__parent = 'tasks'

        self.__initial_state = self.__header.saveState()
        self.__columns: Dict[str, int] = {}

        self.__timer = QTimer()
        self.__timer.setInterval(2000)
        self.__timer.timeout.connect(self._save_table_state)
        self.__timer.setSingleShot(True)

        self.__header.sectionMoved.connect(self._activate_timer)
        self.__header.sectionResized.connect(self._activate_timer)
        self.__header.setContextMenuPolicy(Qt.CustomContextMenu)
        self.__header.customContextMenuRequested.connect(self._on_header_menu)

        with open_settings(mode='w') as settings:
            if self.__parent not in settings.view:
                settings.view[self.__parent] = {
                    'state': '',
                    'columns': {}
                }

    def _activate_timer(self) -> None:
        if not self.__timer.isActive():
            self.__timer.start()

    def get_columns(self) -> Dict[str, int]:
        """
        Map the column names to their respective indices.

        Returns:
            dict[str, int]: A dictionary mapping column names to their indices.

        """
        if not self.__columns:
            self.__columns = self.__view.get_column_indexes()
        return self.__columns

    def load_table_state(self) -> None:
        """
        Loads the state of the table from the settings and applies it to the view.

        This method reads the table state from the settings, restores the header state,
        and hides or shows columns based on the saved state. If no table state is found
        in the settings, it uses the initial state.

        Returns:
            None

        """
        with open_settings() as s:
            settings = s

        current_state = settings.view[self.__parent]['state']

        state = QByteArray.fromBase64(settings.view[self.__parent]['state'].encode())

        if state.isEmpty():
            state = self.__initial_state

        self.__header.restoreState(state)

        for column, index in self.get_columns().items():
            self.__view.setColumnHidden(
                index, not settings.view[self.__parent]['columns'].get(column, True)
            )

        # when running first time, we want to set the size automatically
        if not current_state:
            for col in range(self.__view.tasks_model.columnCount()):
                self.__view.setColumnWidth(col, 250)

    def _save_table_state(self) -> None:
        """
        Save the state of the table to the settings.

        This method saves the current state of the table, including the column widths
        and visibility, to the settings.

        Returns:
            None

        """
        with open_settings(mode='w') as settings:
            settings.view[self.__parent]['state'] = (
                self.__header.saveState().toBase64().data().decode()
            )

    def _update_columns(self, column_name: str, state: bool) -> None:
        """
        Update the visibility of a column.

        This method updates the visibility of a column based on the provided state.

        Args:
            column_name (str): The name of the column to update.
            state (bool): The new visibility state of the column.

        Returns:
            None

        """
        with open_settings(mode='w') as settings:
            settings.view[self.__parent]['columns'][column_name] = state
            self.__view.setColumnHidden(self.get_columns()[column_name], not state)

    def _on_header_menu(self, pos: QPoint) -> None:
        """
        Show the context menu for customizing column visibility.

        This method shows a context menu with actions for hiding or showing columns
        based on the current visibility state.

        Args:
            pos (QPoint): The position of the context menu.

        Returns:
            None

        """
        menu = QMenu(self.__view)

        for col, i in self.get_columns().items():

            act = QAction(col, self.__view, checkable=True)
            act.setChecked(not self.__view.isColumnHidden(i))
            act.toggled.connect(partial(self._update_columns, col))
            menu.addAction(act)

        menu.exec_(self.__view.mapToGlobal(pos))

    def reset_table_state(self) -> None:
        """
        Reset the state of the table.

        This method resets the state of the table, including the column widths and visibility,
        to the initial state.

        """
        with open_settings(mode='w') as settings:
            settings.view.update({self.__parent: {'state': '', 'columns': {}}})
        self.load_table_state()
