from __future__ import annotations

from pytestqt.qtbot import QtBot
from PySide2.QtWidgets import QWidget, QVBoxLayout, QPlainTextEdit

from tqm._core import logger


class Console(QWidget):
    def __init__(self):
        super().__init__()

        self.text = QPlainTextEdit()

        layout = QVBoxLayout()
        layout.addWidget(self.text)

        self.setLayout(layout)

    def log(self, text: str):
        self.text.appendPlainText(text)


def test_logger(qtbot: QtBot):
    log = logger.TqmLogger()

    console = Console()
    handler = logger.WidgetLogHandler(console)

    log.widget = handler
    assert log.widget == handler

    msg = 'This is a message'
    log.warning(msg)

    qtbot.wait_until(lambda: msg in console.text.toPlainText())
