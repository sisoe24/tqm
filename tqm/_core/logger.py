from __future__ import annotations

import os
import sys
import logging
from typing import TYPE_CHECKING, TextIO, Optional
from collections import Counter
from pathlib import Path
from logging.handlers import TimedRotatingFileHandler

from PySide2.QtCore import Qt, Signal, QObject

if TYPE_CHECKING:
    from .._ui.tab_logs import TasksLog

USER_LEVEL = 25
logging.addLevelName(USER_LEVEL, 'USER')

LOG_FILE_FORMAT = logging.Formatter(' | '.join([
    '%(asctime)s',
    '%(levelname)-8s',
    '%(threadName)-10s ID:%(thread)-15d',
    '%(message)s'
]), '%Y-%m-%d %H:%M:%S')

# No thread column: the panel colors lines by task, and the file log keeps the threads.
LOG_WIDGET_FORMAT = logging.Formatter(' | '.join([
    '%(asctime)s',
    '%(levelname)-8s',
    '%(message)s'
]), '%H:%M:%S')


class TqmLogger(logging.Logger):
    def __init__(self, name: str = 'tqm') -> None:
        super().__init__(name)
        self.setLevel(logging.DEBUG)


class HandlerSignal(QObject):
    log_message = Signal(str, str, str)


class WidgetLogHandler(logging.Handler):

    def __init__(self, widget: TasksLog, debug: bool = False) -> None:
        super().__init__()
        self.set_name('widget_handler')
        self.setLevel(logging.DEBUG if debug else logging.INFO)
        self.setFormatter(LOG_WIDGET_FORMAT)

        self._widget = widget
        # Parented, so the GC cannot free it on the worker thread that logs last.
        self._signal = HandlerSignal(widget)
        self._signal.log_message.connect(self._widget.log, Qt.QueuedConnection)

    def emit(self, record: logging.LogRecord) -> None:
        self._signal.log_message.emit(
            self.format(record),
            record.levelname.upper(),
            getattr(record, 'tqm_task', '')
        )


def log_file_handler(config_path: Path) -> TimedRotatingFileHandler:
    tqm_log_dir = config_path / 'logs'
    tqm_log_dir.mkdir(parents=True, exist_ok=True)

    handler = TimedRotatingFileHandler(
        filename=tqm_log_dir / 'tqm.log',
        when='midnight',
        backupCount=7
    )

    handler.setLevel(logging.DEBUG)
    handler.set_name('file_handler')
    handler.setFormatter(LOG_FILE_FORMAT)

    return handler


def add_file_handler(config_path: Path) -> logging.Handler:
    """Add the file handler for `config_path`. Managers with the same app name share it."""
    filename = os.path.abspath(config_path / 'logs' / 'tqm.log')
    handler = next(
        (h for h in LOGGER.handlers if getattr(h, 'baseFilename', None) == filename), None
    )
    if handler is None:
        handler = log_file_handler(config_path)
        LOGGER.addHandler(handler)
    _handler_users[handler] += 1
    return handler


def remove_handlers(*handlers: logging.Handler) -> None:
    """Remove and close the handlers that no manager uses any more."""
    for handler in handlers:
        _handler_users[handler] -= 1
        if _handler_users[handler] <= 0:
            del _handler_users[handler]
            LOGGER.removeHandler(handler)
            handler.close()


def _console_handler() -> logging.StreamHandler[TextIO]:
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.DEBUG)
    handler.set_name('console_handler')
    handler.setFormatter(LOG_FILE_FORMAT)
    return handler


def write_log(msg: str, *, stream: Optional[TextIO] = None) -> None:
    """Write a log level USER message to the logger.

    Args:
        msg (str): The message to log.
        stream (Optional[TextIO], optional): The stream to write to. Defaults to None.

    ```
    write_log('Hello, World!')
    write_log('Hello, World!', stream=sys.stdout)
    ```

    """
    if stream:
        try:
            stream.write(msg + '\n')
            stream.flush()
        except Exception as e:
            LOGGER.error('Invalid stream: %s', e)

    LOGGER.log(USER_LEVEL, msg)


LOGGER = TqmLogger()
_handler_users: Counter[logging.Handler] = Counter()
if os.getenv('TQM_DEBUG') == '1':
    LOGGER.addHandler(_console_handler())
