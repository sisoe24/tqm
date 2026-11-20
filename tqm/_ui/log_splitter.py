from __future__ import annotations

from typing import List
from pathlib import Path

from PySide2.QtCore import Qt, Slot, Signal, QTimer
from PySide2.QtWidgets import QWidget, QSplitter

from .._core.settings import Settings, open_settings


def _valid_sizes(sizes: List[int]) -> bool:
    return len(sizes) == 2 and all(isinstance(s, int) and s >= 0 for s in sizes) and sum(sizes) > 0


class LogSplitter(QSplitter):
    """The tasks view above the log panel. It remembers the log panel size and can hide it."""

    log_shown = Signal(bool)

    def __init__(self, tasks: QWidget, logs: QWidget, settings_path: Path) -> None:
        super().__init__(Qt.Vertical)
        self.addWidget(tasks)
        self.addWidget(logs)
        self._settings_path = settings_path

        with open_settings(json_file_path=settings_path) as s:
            sizes = s.splitter_sizes
        default = Settings().splitter_sizes
        sizes = sizes if _valid_sizes(sizes) else default
        self.setSizes(sizes)

        # The sizes to restore when the log is shown again after being hidden.
        self._open_sizes = sizes if sizes[1] > 0 else default

        # Save once the drag stops, not on every move.
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(1000)
        self._save_timer.timeout.connect(self._save_sizes)

        self.splitterMoved.connect(self._on_moved)

    def is_log_shown(self) -> bool:
        return self.sizes()[1] > 0

    @Slot(bool)
    def show_log(self, show: bool) -> None:
        if show == self.is_log_shown():
            return
        if not show:
            self._open_sizes = self.sizes()
        self.setSizes(self._open_sizes if show else [sum(self.sizes()), 0])
        self._save_timer.start()
        self.log_shown.emit(show)

    @Slot()
    def _on_moved(self) -> None:
        if self.is_log_shown():
            self._open_sizes = self.sizes()
        self._save_timer.start()
        self.log_shown.emit(self.is_log_shown())

    @Slot()
    def _save_sizes(self) -> None:
        with open_settings(mode='w', json_file_path=self._settings_path) as s:
            s.splitter_sizes = self.sizes()
