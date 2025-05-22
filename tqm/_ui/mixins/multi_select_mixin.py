
from __future__ import annotations

from typing import Any, cast

from PySide2.QtGui import QKeyEvent, QMouseEvent
from PySide2.QtCore import Qt
from PySide2.QtWidgets import QAbstractItemView


class MultiSelectMixin:
    """
    Mixin for multi-selecting items in a QAbstractItemView.

    This mixin provides methods for enabling multi-selection of items in a QAbstractItemView.
    It allows selecting multiple items by holding the Shift key and selecting all items by
    pressing the 'A' key.

    Args:
        view (QAbstractItemView): The view to enable multi-selection for.

    """

    def __init__(self, view: QAbstractItemView, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)

        self.view = view
        self.view.setSelectionMode(QAbstractItemView.SingleSelection)

    @property
    def parent(self) -> QAbstractItemView:
        return cast(QAbstractItemView, super())

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if (
            event.button() == Qt.RightButton
            and self.view.selectionMode() == QAbstractItemView.SingleSelection
        ):
            return
        return self.parent.mousePressEvent(event)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """
        Handle key press events.

        This method handles key press events and enables multi-selection mode when the Shift key
        is pressed. It also allows selecting all items when the 'A' key is pressed.

        Args:
            event (QKeyEvent): The key press event.

        Returns:
            None

        """
        if event.modifiers() == Qt.ShiftModifier:
            self.view.setSelectionMode(QAbstractItemView.MultiSelection)

        elif event.key() == Qt.Key_A:
            if self.view.selectionMode() == QAbstractItemView.SingleSelection:
                self.view.setSelectionMode(QAbstractItemView.MultiSelection)
                self.view.selectAll()
            else:
                self.view.clearSelection()
                self.view.setSelectionMode(QAbstractItemView.SingleSelection)

        self.parent.keyPressEvent(event)

    def keyReleaseEvent(self, event: QKeyEvent) -> None:
        """
        Handle key release events.

        This method handles key release events and restores the selection mode to single selection
        when the Shift key is released.

        Args:
            event (QKeyEvent): The key release event.

        Returns:
            None

        """
        if event.key() == Qt.Key_Shift:
            self.view.setSelectionMode(QAbstractItemView.SingleSelection)
        self.parent.keyReleaseEvent(event)
