from __future__ import annotations

import os
import sysconfig
from typing import Any, Dict, Optional
from platform import python_version

from PySide2 import __version__ as PySide2_version
from PySide2.QtGui import QDesktopServices
from PySide2.QtCore import QUrl, Slot
from PySide2.QtWidgets import (QLabel, QDialog, QWidget, QGridLayout,
                               QPushButton, QVBoxLayout, QPlainTextEdit)

from ..version import __version__


class HelpWidget(QDialog):
    def __init__(
        self,
        git_repo: str,
        config_path: str,
        about: Dict[str, Any],
        extra: Optional[Dict[str, Any]] = None,
        parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle('Help')

        self.git_repo = git_repo
        self.config_path = config_path

        about_info = QPlainTextEdit()
        about_info.setReadOnly(True)

        extra = extra or {}
        abouts = {**about, **extra}

        for name, value in abouts.items():
            about_info.appendPlainText(f'- {name.title()}: {value}')

        grid_layout = QGridLayout()
        grid_layout.addWidget(self._button_factory('Issues'), 0, 0, 1, 2)
        grid_layout.addWidget(self._button_factory('Readme'), 1, 0)
        grid_layout.addWidget(self._button_factory('Changelog'), 1, 1)
        grid_layout.addWidget(self._button_factory('Config'), 2, 0, 1, 2)

        layout = QVBoxLayout()
        layout.addWidget(QLabel('<h1>Help</h1>'))
        layout.addWidget(about_info)
        layout.addLayout(grid_layout)

        self.setLayout(layout)

    def _button_factory(self, text: str) -> QPushButton:
        button = QPushButton(text)
        button.clicked.connect(lambda: self._on_open_link(text))
        return button

    @Slot(str)
    def _on_open_link(self, link: str) -> None:
        links = {
            'issues': QUrl(f'{self.git_repo}/issues'),
            'changelog': QUrl(f'{self.git_repo}/blob/master/CHANGELOG.md'),
            'readme': QUrl(f'{self.git_repo}/blob/master/README.md'),
            'config': QUrl.fromLocalFile(self.config_path)
        }
        QDesktopServices.openUrl(links[link.lower()])


def about() -> Dict[str, str]:
    """Return a dictionary with information about the application."""
    return {
        'version': __version__,
        'python': python_version(),
        'pyside': PySide2_version,
        'machine': sysconfig.get_platform(),
    }


def show_help(**kwargs: Any) -> None:
    return HelpWidget(
        git_repo='https://github.com/sisoe24/_TODO_',
        config_path=os.environ['TQM_CONFIG_PATH'],
        about=about(),
        extra=kwargs
    ).show()
